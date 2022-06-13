#!/usr/bin/python
"""Request handlers for the uWeb3 warehouse inventory software"""

# standard modules
import re
from io import BytesIO
from itertools import zip_longest

import mt940
import requests
from uweb3.libs.mail import MailSender
from weasyprint import HTML

from invoices.common import helpers as common_helpers
from invoices.common.schemas import (
    InvoiceSchema,
    ProductSchema,
    WarehouseStockChangeSchema,
)
from invoices.invoice import model
from invoices.invoice.model import InvoiceStatus
from invoices.mollie.mollie import helpers as mollie_module


def mail_invoice(recipients, subject, body, attachments=None):
    """Used for sending a mail with attachments or as plain text.

    Args:
        recipients (list[str]): The recipients to send it to
        subject (str): The mail subject
        body (str): The mail body
        attachments: The attachments that should be send with this mail
    """
    if attachments:
        _mail_attachment(recipients, subject, body, attachments)
    else:
        _mail_text(recipients, subject, body)


def _mail_attachment(recipients, subject, body, attachments):
    with MailSender() as send_mail:
        send_mail.Attachments(
            recipients=recipients,
            subject=subject,
            content=body,
            attachments=attachments,
        )


def _mail_text(recipients, subject, body):
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
    return mollie_gateway.CreateTransaction(mollie_request_object)["href"]


def warehouse_stock_update_request(warehouse_url, warehouse_apikey, invoice, products):
    """Send a stock update request to the warehouse.

    Args:
        warehouse_url (str): The API url of the warehouse
        warehouse_apikey (str): The API key of the warehouse
        invoice (InvoiceSchema): The invoice data
        products (ProductSchema): List of products

    Returns:
        response: Request response
    """
    reference = create_invoice_reference_msg(
        invoice["status"], invoice["sequenceNumber"]
    )
    warehouse_products = WarehouseStockChangeSchema(many=True).load(products)
    return requests.post(
        f"{warehouse_url}/products/bulk_stock",
        json={
            "apikey": warehouse_apikey,
            "products": warehouse_products,
            "reference": reference,
        },
    )


def create_invoice_add_products(connection, data, products):
    """Create a new invoice and add products to that invoice

    Args:
        connection (self.connection): Uweb connection object
        data (InvoiceSchema): The cleaned data for the new invoice
        products (ProductSchema(many=True)): A list of products that should be added to the invoice

    Returns:
        model.Invoice: The newly created invoice object
    """
    invoice = model.Invoice.Create(connection, data)
    invoice.AddProducts(products)
    return invoice


def correct_products_name_key(products):
    prods = list(products)
    for product in prods:
        product["name"] = product.pop("name_field")
    return prods


def to_pdf(html, filename=None):
    """Returns a PDF based on the given HTML."""
    result = BytesIO()
    HTML(string=html).write_pdf(result)
    if filename:
        result.filename = filename
        return result
    return result.getvalue()


def get_and_zip_products(postdata):
    """Transform invoice products post data to a list of dictionaries.
    This function uses zip_longest, so any missing data will be filled with None.
    Returns: [
        { name: The name of the product,
          price: The price of the product,
          vat_percentage: specified vat percentage of a given product,
          quantity: The amount of products that were specified
        }]
    """

    products = []
    for product, price, vat, quantity in zip_longest(
        postdata.getlist("products"),
        postdata.getlist("invoice_prices"),
        postdata.getlist("invoice_vat"),
        postdata.getlist("quantity"),
    ):
        products.append(
            {
                "name": product,
                "price": price,
                "vat_percentage": vat,
                "quantity": quantity,
            }
        )
    return products


def create_invoice_reference_msg(status, sequenceNumber):
    """Determines the reference message that is send to the warehouse API.

    Arguments:
      @ status: str
        The status of the invoice
      @ sequenceNumber:
        The sequenceNumber of the invoice
    """
    if status == InvoiceStatus.RESERVATION:
        reference = f"Reservation for pro forma invoice: {sequenceNumber}"
    else:
        reference = f"Buy order for invoice: {sequenceNumber}"
    return reference


class MT940_processor:
    INVOICE_REGEX_PATTERN = r"([0-9]{4}-[0-9]{3})|(PF-[0-9]{4}-[0-9]{3})"

    def __init__(self, files):
        self.files = files

    def process_files(self):
        """Processes the contents of all MT-940 files."""
        results = []
        for f in self.files:
            # XXX: The content of an MT-940 file should be str. uweb3 handles this, but should we also check this?
            results.extend(self._regex_search(f["content"]))
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
