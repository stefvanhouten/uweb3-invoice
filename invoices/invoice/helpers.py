#!/usr/bin/python
"""Request handlers for the uWeb3 warehouse inventory software"""

import decimal
import re

# standard modules
from http import HTTPStatus
from http.client import INTERNAL_SERVER_ERROR
from io import BytesIO
from itertools import zip_longest
from typing import NamedTuple

import mt940
import requests
from uweb3.libs.mail import MailSender
from weasyprint import HTML

from invoices.common import helpers as common_helpers
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


class WarehouseException(Exception):
    status_code: int

    def __init__(self, message, status_code):
        super().__init__(message)
        self.status_code = status_code


class WarehouseApi:
    def __init__(self, url, apikey):
        self.url = url
        self.apikey = apikey
        self.requested_url = None
        self.endpoints = {
            "products": "/products",
            "bulk_stock": "/products/bulk_stock",
        }

    def get_products(self):
        response = self._request(self.endpoints["products"])
        json_response = response.json()

        if response.status_code != 200:
            return self.handle_api_errors(response)

        return json_response["products"]

    def add_order(self, invoice, products):
        reference = create_invoice_reference_msg(
            invoice["status"], invoice["sequenceNumber"]
        )
        prods = [
            {
                "sku": product["sku"],
                "quantity": -abs(product["quantity"]),
                "reference": reference,
            }
            for product in products
        ]
        response = self._post(
            self.endpoints["bulk_stock"],
            {
                "products": prods,
                "reference": reference,
            },
        )

        if response.status_code != 200:
            return self.handle_api_errors(response)
        return response

    def cancel_order(self, products, reference):
        prods = [
            {
                "sku": product["sku"],
                "quantity": product["quantity"],
                "reference": reference,
            }
            for product in products
        ]
        response = self._post(
            self.endpoints["bulk_stock"],
            json={"products": prods, "reference": reference},
        )

        if response.status_code != 200:
            return self.handle_api_errors(response)
        return response

    def _request(self, endpoint):
        self.requested_url = f"{self.url}{endpoint}"
        return self._execute(requests.get, f"{self.requested_url}?apikey={self.apikey}")

    def _post(self, endpoint, json):
        self.requested_url = f"{self.url}{endpoint}"
        return self._execute(
            requests.post, f"{self.requested_url}?apikey={self.apikey}", json=json
        )

    def _execute(self, method, *args, **kwargs):
        try:
            return method(*args, **kwargs)
        except requests.exceptions.ConnectionError as exc:
            raise WarehouseException(
                "Could not connect to warehouse API, is the warehouse service running?",
                HTTPStatus.SERVICE_UNAVAILABLE,
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise WarehouseException("Unhandled warehouse API exception", 0) from exc

    def handle_api_errors(self, response):
        match response.status_code:
            case HTTPStatus.NOT_FOUND:
                raise WarehouseException(
                    f"Warehouse API at url '{self.requested_url}' could not be found.",
                    HTTPStatus.NOT_FOUND,
                )
            case HTTPStatus.FORBIDDEN:
                raise WarehouseException(
                    f"Access denied to page '{self.requested_url}'. Are you using a valid apikey?",
                    HTTPStatus.FORBIDDEN,
                )
            case HTTPStatus.INTERNAL_SERVER_ERROR:
                raise WarehouseException(
                    "Something went wrong on the warehouse server.",
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
            case _:
                raise WarehouseException(
                    "Unhandled warehouse API exception", response.status_code
                )


def create_invoice(invoice_form, warehouse_products, connection):
    invoice = model.Invoice.Create(
        connection,
        {
            "client": invoice_form.client.data,
            "status": model.InvoiceStatus.RESERVATION.value
            if invoice_form.reservation.data
            else model.InvoiceStatus.NEW.value,
            "title": invoice_form.title.data,
            "description": invoice_form.description.data,
        },
    )
    prods = _create_product_list(invoice_form, warehouse_products, invoice["ID"])
    invoice.AddProducts(prods)
    return invoice


def _create_product_list(invoice_form, warehouse_products, invoiceID):
    products = []

    for product in invoice_form.product.data:
        name = _product_name_from_sku(warehouse_products, product)
        products.append(
            dict(
                name=name,
                sku=product["sku"],
                invoice=invoiceID,
                price=product["price"],
                vat_percentage=product["vat_percentage"],
                quantity=product["quantity"],
            )
        )

    return products


def _product_name_from_sku(warehouse_products, product):
    for warehouse_product in warehouse_products:
        if product["sku"] == warehouse_product["sku"]:
            return warehouse_product["name"]
