#!/usr/bin/python
"""Request handlers for the uWeb3 warehouse inventory software"""

# standard modules
import decimal
import re
import mt940
from itertools import zip_longest

from weasyprint import HTML
from io import BytesIO

from invoices.base.model.invoice import InvoiceStatus
from invoices.base.pages.helpers.general import round_price

__all__ = [
    'ToPDF', 'CreateCleanProductList', 'MT940_processor',
    'get_and_zip_products', 'decide_reference_message'
]


def ToPDF(html, filename=None):
  """Returns a PDF based on the given HTML."""
  result = BytesIO()
  HTML(string=html).write_pdf(result)
  if filename:
    result.filename = filename
    return result
  return result.getvalue()


def CreateCleanProductList(products, negative_abs=False):
  """Create a simple list containing {name: value, quantity: x} pairs.

  Arguments:
    % negative_abs: Change the quantity to an absolute value or leave as is.
                    This is used when adding stock or decrementing stock.
  """
  items = []
  for product in products:
    # Check if a product was entered multiple times, if so update quantity of said product.
    target = list(filter(lambda item: item['name'] == product['name'], items))
    if len(target) > 0:
      target[0]['quantity'] += -abs(
          product['quantity']) if negative_abs else product['quantity']
      continue
    # If product not yet in items, add it.
    items.append({
        'name':
            product['name'],
        'quantity':
            -abs(product['quantity']) if negative_abs else product['quantity']
    })
  return items


def get_and_zip_products(product_names, product_prices, product_vat,
                         product_quantity):
  """Transform invoice products post data to a list of dictionaries.
  This function uses zip_longest, so any missing data will be filled with None.

  Arguments:
    @ product_names: list
    @ product_prices: list
    @ product_vat: list
    @ product_quantity: list

  Returns: [
      { name: The name of the product,
        price: The price of the product,
        vat_percentage: specified vat percentage of a given product,
        quantity: The amount of products that were specified
      }]
  """
  products = []
  for product, price, vat, quantity in zip_longest(product_names,
                                                   product_prices, product_vat,
                                                   product_quantity):
    products.append({
        'name': product,
        'price': price,
        'vat_percentage': vat,
        'quantity': quantity
    })
  return products


def decide_reference_message(status, sequenceNumber):
  """Determines the reference message that is send to the warehouse API.

  Arguments:
    @ status: str
      The status of the invoice
    @ sequenceNumber:
      The sequenceNumber of the invoice
  """
  if status == InvoiceStatus.RESERVATION:
    reference = f"Reservation for invoice: {sequenceNumber}"
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
      results.extend(self._regex_search(f['content']))
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
    transactions = mt940.models.Transactions(processors=dict(pre_statement=[
        mt940.processors.add_currency_pre_processor('EUR'),
    ],))
    transactions.parse(data)

    for transaction in transactions:
      matches = re.finditer(self.INVOICE_REGEX_PATTERN,
                            transaction.data['transaction_details'],
                            re.MULTILINE)
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
        transaction.data['amount'].amount)  # Get the value of the transaction
    return [{
        "invoice": x.group(),
        "amount": amount,
        "customer_reference": transaction.data.get('customer_reference'),
        "entry_date": transaction.data.get('entry_date'),
        "transaction_id": transaction.data.get('id')
    } for x in matches]
