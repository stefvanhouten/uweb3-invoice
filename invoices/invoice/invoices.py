#!/usr/bin/python
"""Request handlers for the uWeb3 warehouse inventory software"""

import os

# standard modules
import requests

# uweb modules
import uweb3

from invoices import basepages
from invoices.common.decorators import NotExistsErrorCatcher, loggedin
from invoices.common.helpers import transaction
from invoices.common.schemas import PaymentSchema, WarehouseStockRefundSchema
from invoices.invoice import forms, helpers, model
from invoices.invoice.decorators import WarehouseRequestWrapper
from invoices.mollie import model as mollie_model


class WarehouseAPIException(Exception):
    """Error that was raised during an API call to warehouse."""


class PageMaker(basepages.PageMaker):
    TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.warehouse_api_url = self.config.options["general"]["warehouse_api"]
        self.warehouse_apikey = self.config.options["general"]["apikey"]
        self.warehouse = helpers.WarehouseApi(
            self.warehouse_api_url, self.warehouse_apikey
        )

    @loggedin
    @uweb3.decorators.checkxsrf
    @uweb3.decorators.TemplateParser("invoices.html")
    def RequestInvoicesPage(self):
        return {
            "invoices": list(
                model.Invoice.List(self.connection, order=["sequenceNumber"])
            ),
        }

    @loggedin
    @uweb3.decorators.checkxsrf
    @WarehouseRequestWrapper
    @uweb3.decorators.TemplateParser("create.html")
    def RequestNewInvoicePage(self, errors=[], invoice_form=None):
        products = self.warehouse.get_products()

        if not invoice_form:
            invoice_form = forms.get_invoice_form(
                model.Client.List(self.connection), products
            )

        return {
            "products": products,
            "errors": errors,
            "api_url": self.warehouse_api_url,
            "apikey": self.warehouse_apikey,
            "invoice_form": invoice_form,
            "scripts": ["/js/invoice.js"],
        }

    @loggedin
    @uweb3.decorators.checkxsrf
    @WarehouseRequestWrapper
    def RequestCreateNewInvoicePage(self):
        # Check if client exists
        model.Client.FromPrimary(self.connection, int(self.post.getfirst("client")))
        warehouse_products = self.warehouse.get_products()

        invoice_form = forms.get_invoice_form(
            model.Client.List(self.connection), warehouse_products, postdata=self.post
        )

        if not invoice_form.validate():
            return self.RequestNewInvoicePage(invoice_form=invoice_form)

        # Start a transaction that is rolled back when any unhandled exception occurs
        with transaction(self.connection, model.Invoice):
            invoice = helpers.create_invoice(
                invoice_form, warehouse_products, self.connection
            )
            self.warehouse.add_order(invoice, invoice_form.product.data)

        should_mail = invoice_form.send_mail.data
        payment_request = invoice_form.mollie_payment_request.data

        if invoice and (should_mail or payment_request):
            mail_data = {}
            if payment_request:
                url = helpers.create_mollie_request(
                    invoice, payment_request, self.connection, self.options["mollie"]
                )
                mail_data["mollie"] = url

            content = self.parser.Parse("email/invoice.txt", **mail_data)
            pdf = helpers.to_pdf(
                self.RequestInvoiceDetails(invoice["sequenceNumber"]),
                filename="invoice.pdf",
            )
            helpers.mail_invoice(
                recipients=invoice["client"]["email"],
                subject="Your invoice",
                body=content,
                attachments=(pdf,),
            )

        return self.req.Redirect("/invoices", httpcode=303)

    @uweb3.decorators.TemplateParser("invoice.html")
    @NotExistsErrorCatcher
    def RequestInvoiceDetails(self, sequence_number):
        invoice = model.Invoice.FromSequenceNumber(self.connection, sequence_number)
        return {
            "invoice": invoice,
            "products": invoice.Products(),
            "totals": invoice.Totals(),
        }

    @loggedin
    def RequestPDFInvoice(self, invoice):
        """Returns the invoice as a pdf file.

        Takes:
            invoice: int or str
        """
        requestedinvoice = self.RequestInvoiceDetails(invoice)
        if type(requestedinvoice) != uweb3.response.Redirect:
            return uweb3.Response(
                helpers.to_pdf(requestedinvoice), content_type="application/pdf"
            )
        return requestedinvoice

    @loggedin
    @uweb3.decorators.checkxsrf
    @NotExistsErrorCatcher
    def RequestInvoicePayed(self):
        """Sets the given invoice to paid."""
        invoice = self.post.getfirst("invoice")
        invoice = model.Invoice.FromSequenceNumber(self.connection, invoice)
        invoice["status"] = "paid"
        invoice.Save()
        return self.req.Redirect("/invoices", httpcode=303)

    @loggedin
    @uweb3.decorators.checkxsrf
    @NotExistsErrorCatcher
    def RequestInvoiceReservationToNew(self):
        """Sets the given invoice to paid."""
        sequence_number = self.post.getfirst("invoice")
        invoice = model.Invoice.FromSequenceNumber(self.connection, sequence_number)
        invoice.ProFormaToRealInvoice()

        updated_invoice = model.Invoice.FromPrimary(self.connection, invoice["ID"])

        mail_data = {}
        content = self.parser.Parse("email/invoice.txt", **mail_data)
        pdf = helpers.to_pdf(
            self.RequestInvoiceDetails(updated_invoice["sequenceNumber"]),
            filename="invoice.pdf",
        )
        helpers.mail_invoice(
            updated_invoice["client"]["email"],
            subject="Your invoice",
            body=content,
            attachments=(pdf,),
        )
        return self.req.Redirect("/invoices", httpcode=303)

    @loggedin
    @uweb3.decorators.checkxsrf
    @NotExistsErrorCatcher
    @WarehouseRequestWrapper
    def RequestInvoiceCancel(self):
        """Sets the given invoice to paid."""
        invoice = self.post.getfirst("invoice")
        invoice = model.Invoice.FromSequenceNumber(self.connection, invoice)
        self.warehouse.cancel_order(
            invoice.Products(),
            f"Canceling pro forma invoice: {invoice['sequenceNumber']}",
        )
        invoice.CancelProFormaInvoice()
        return self.req.Redirect("/invoices", httpcode=303)

    @loggedin
    @uweb3.decorators.checkxsrf
    @uweb3.decorators.TemplateParser("mt940.html")
    def RequestMt940(self, payments=[], failed_invoices=[]):
        return {
            "payments": payments,
            "failed_invoices": failed_invoices,
            "mt940_preview": True,
        }

    @loggedin
    @uweb3.decorators.checkxsrf
    def RequestUploadMt940(self):
        # TODO: File validation.
        payments = []
        failed_payments = []
        found_invoice_references = helpers.MT940_processor(
            self.files.get("fileupload", [])
        ).process_files()

        for invoice_ref in found_invoice_references:
            try:
                invoice = model.Invoice.FromSequenceNumber(
                    self.connection, invoice_ref["invoice"]
                )
            except (uweb3.model.NotExistError, Exception):
                # Invoice could not be found. This could mean two things,
                # 1. The regex matched something that looks like an invoice sequence number, but its not part of our system.
                # 2. The transaction contains a pro-forma invoice, but this invoice was already set to paid and thus changed to a real invoice.
                # its also possible that there was a duplicate pro-forma invoice ID in the description, but since it was already processed no reference can be found to it anymore.
                failed_payments.append(invoice_ref)
                continue

            platform = model.PaymentPlatform.FromName(
                self.connection, "ideal"
            )  # XXX: What payment platform is this?
            invoice.AddPayment(platform["ID"], invoice_ref["amount"])
            payments.append(invoice_ref)

        return self.RequestMt940(payments=payments, failed_invoices=failed_payments)

    @loggedin
    @uweb3.decorators.checkxsrf
    @NotExistsErrorCatcher
    @uweb3.decorators.TemplateParser("payments.html")
    def ManagePayments(self, sequenceNumber):
        invoice = model.Invoice.FromSequenceNumber(self.connection, sequenceNumber)
        return {
            "invoice": invoice,
            "payments": invoice.GetPayments(),
            "totals": invoice.Totals(),
            "mollie_payments": list(
                mollie_model.MollieTransaction.List(
                    self.connection, conditions=[f'invoice = {invoice["ID"]}']
                )
            ),
            "platforms": model.PaymentPlatform.List(self.connection),
        }

    @loggedin
    @uweb3.decorators.checkxsrf
    @NotExistsErrorCatcher
    def AddPayment(self, sequenceNumber):
        payment = PaymentSchema().load(self.post.__dict__)
        invoice = model.Invoice.FromSequenceNumber(self.connection, sequenceNumber)
        invoice.AddPayment(payment["platform"], payment["amount"])
        return uweb3.Redirect(
            f'/invoice/payments/{invoice["sequenceNumber"]}', httpcode=303
        )

    @loggedin
    @uweb3.decorators.checkxsrf
    @NotExistsErrorCatcher
    def AddMolliePaymentRequest(self, sequenceNumber):
        invoice = model.Invoice.FromSequenceNumber(self.connection, sequenceNumber)
        payment = PaymentSchema().load(self.post.__dict__, partial=("platform",))

        url = helpers.create_mollie_request(
            invoice, payment["amount"], self.connection, self.options["mollie"]
        )
        content = self.parser.Parse("email/invoice.txt", **{"mollie": url})
        helpers.mail_invoice(
            recipients=invoice["client"]["email"],
            subject="Mollie payment request",
            body=content,
        )
        return uweb3.Redirect(
            f'/invoice/payments/{invoice["sequenceNumber"]}', httpcode=303
        )
