#!/usr/bin/python
"""Request handlers for the uWeb3 warehouse inventory software"""

# standard modules
import re
from io import BytesIO
from itertools import zip_longest

import mt940
import requests
from weasyprint import HTML

from invoices.common.schemas import (
    InvoiceSchema,
    ProductSchema,
    WarehouseStockChangeSchema,
)
from invoices.invoice import model
from invoices.invoice.model import InvoiceStatus


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


def sanitize_new_invoice_post_data(postdata):
    """Sanitize post data for invoice creation.

    Args:
        postdata (IndexedFieldStorage): uweb3 self.post data.

    Raises:
        marshmallow.exceptions.ValidationError: Marshmallow validation failed
        ValueError: No products were supplied by the post request

    Returns:
        sanitized_invoice (dict): Invoice with sanitized data
        products list(ProductSchema): List of products from the invoice.
    """
    unclean_products = get_and_zip_products(postdata)

    sanitized_invoice = InvoiceSchema().load(postdata.__dict__)
    products = ProductSchema(many=True).load(unclean_products)

    if not products:
        raise ValueError("cannot create invoice without products")

    return sanitized_invoice, products


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
