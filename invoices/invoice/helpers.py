#!/usr/bin/python
"""Request handlers for the uWeb3 warehouse inventory software"""

import re

# standard modules
from io import BytesIO
from typing import Callable

import mt940
from uweb3.libs.mail import MailSender
from weasyprint import HTML

from invoices.common import helpers as common_helpers
from invoices.invoice import model
from invoices.mollie.mollie import helpers as mollie_module


def mail_invoice(recipients, subject, body, attachments=None):
    """Used for sending a mail with attachments or as plain text.

    Args:
        recipients (list[str]): The recipients to send it to
        subject (str): The mail subject
        body (str): The mail body
        attachments: The attachments that should be send with this mail
        mailconfig (dict): Config with host/port for the mailserver.
            example: { 'host': 'localhost', 'port': 25 }
    """
    if attachments:
        with MailSender() as send_mail:
            send_mail.Attachments(
                recipients=recipients,
                subject=subject,
                content=body,
                attachments=attachments,
            )
    else:
        with MailSender() as send_mail:
            send_mail.Text(recipients=recipients, subject=subject, content=body)


def create_mollie_request(invoice, amount, connection, mollie_config):
    """Generate a new mollie payment request and return its url

    Args:
        invoice (InvoiceSchema): The invoice
        amount (str/Decimal): The amount for the mollie payment request
        connection (self.connection): Db connection
        mollie_config (self.options['mollie']): The mollie config

    Returns:
        _type_: _description_
    """
    mollie_request_object = mollie_module.MollieTransactionObject(
        invoice["ID"],
        common_helpers.round_price(amount),
        invoice["description"],
        invoice["sequenceNumber"],
    )
    mollie_gateway = mollie_module.mollie_factory(connection, mollie_config)
    return mollie_gateway.create_transaction(mollie_request_object)["href"]


def to_pdf(html, filename=None):
    """Returns a PDF based on the given HTML."""
    result = BytesIO()
    HTML(string=html).write_pdf(result)
    if filename:
        result.filename = filename
        return result
    return result.getvalue()


class MT940_processor:
    INVOICE_REGEX_PATTERN = r"((.*)-[0-9]{4}-[0-9]{3})|((.*)-PF-[0-9]{4}-[0-9]{3})"

    def __init__(self, files, prefix="invoice"):
        self.files = files

    def process_files(self):
        """Processes the contents of all MT-940 files."""
        results = []
        for f in self.files:
            # XXX: The content of an MT-940 file should be str. uweb3 handles this, but should we also check this?
            results.extend(self._regex_search(f.value.decode("utf-8")))
        return results

    def _regex_search(self, data):
        """Parse data and match patterns that could indicate a invoice or a pro forma invoice

        Arguments:
          @ data: str
            Data read from .STA file.

        Returns:
          List of dictionaries that matched the invoice pattern.
          [
            {
              invoice: sequenceNumber,
              amount: value
            }
          ]
        """
        results = []
        transactions = mt940.models.Transactions(
            processors=dict(
                pre_statement=[
                    mt940.processors.add_currency_pre_processor("EUR"),
                ],
            )
        )
        transactions.parse(data)

        for transaction in transactions:
            matches = re.finditer(
                self.INVOICE_REGEX_PATTERN,
                transaction.data["transaction_details"],
                re.MULTILINE,
            )
            potential_invoice_references = self._clean_results(matches, transaction)
            results.extend(potential_invoice_references)
        return results

    def _clean_results(self, matches, transaction):
        """Iterates over all found matches and returns the matches in a dict.

        Arguments:
          @ matches:
            The found regex matches
          @ transaction:
            The current transaction that is being parsed.

        Returns:
          List of dictionaries that matched the invoice pattern
            [
              {
                invoice: sequenceNumber,
                amount: value
              }
            ]
        """
        amount = str(
            transaction.data["amount"].amount
        )  # Get the value of the transaction
        return [
            {
                "invoice": x.group(),
                "amount": amount,
                "customer_reference": transaction.data.get("customer_reference"),
                "entry_date": transaction.data.get("entry_date"),
                "transaction_id": transaction.data.get("id"),
            }
            for x in matches
        ]


class InvoiceServiceBuilder(common_helpers.BaseFormServiceBuilder):
    def __init__(self, form, client_method: Callable):
        self._instance = None
        self.form = form
        self.client_method = client_method

    def _populate_select(self, client_number):
        self._instance.client.choices = [
            (c["ID"], c["name"]) for c in self.client_method(client_number)
        ]

    def __call__(self, *args, client_number, **kwargs):
        if not self._instance:
            self._instance = self.form(*args, **kwargs)
            self._populate_select(client_number)
        return self._instance


def map_products_to_warehouse_products(connection, invoice_form):
    record = dict(invoice_form.data)
    record["products"] = []

    # Find the product name by the chosen product SKU
    for product in invoice_form.products.data:
        if product["product_sku"] == "":
            continue

        wh_product = model.WarehouseProduct.FromSku(connection, product["product_sku"])
        record["products"].append(
            dict(
                name=wh_product["name"],
                product_sku=product["product_sku"],
                price=product["price"],
                vat_percentage=product["vat_percentage"],
                quantity=product["quantity"],
            )
        )
    return record
