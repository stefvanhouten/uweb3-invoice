#!/usr/bin/python
"""Request handlers for the uWeb3 warehouse inventory software"""

import os

import uweb3

from invoices import basepages
from invoices.common.decorators import NotExistsErrorCatcher, ParseView, loggedin
from invoices.common.schemas import PaymentSchema
from invoices.invoice import helpers, model, views
from invoices.mollie import model as mollie_model


class PageMaker(basepages.PageMaker):
    TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")

    @loggedin
    @uweb3.decorators.checkxsrf
    @NotExistsErrorCatcher
    @ParseView
    def ManagePayments(self, sequenceNumber):
        invoice = model.Invoice.FromSequenceNumber(self.connection, sequenceNumber)
        return views.InvoicePayments(
            title=f"Payments: {invoice['sequenceNumber']}",
            invoice=invoice,
            payments=invoice.GetPayments(),
            totals=invoice.Totals(),
            mollie_payments=list(
                mollie_model.MollieTransaction.List(
                    self.connection, conditions=[f'invoice = {invoice["ID"]}']
                )
            ),
            platforms=list(model.PaymentPlatform.List(self.connection)),
        )

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

        if invoice["client"]["email"]:
            helpers.mail_invoice(
                recipients=invoice["client"]["email"],
                subject="Mollie payment request",
                body=content,
            )
        return uweb3.Redirect(
            f'/invoice/payments/{invoice["sequenceNumber"]}', httpcode=303
        )
