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
    'get_and_zip_products', 'decide_reference_message', 'MT940_invoice_handler'
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
    return [{"invoice": x.group(), "amount": amount} for x in matches]


class MT940_invoice_handler:

  def __init__(self, invoice_pairs):
    """Processes a list of InvoicePairs and updates the database for found results.

    Arguments:
      @ invoice_pairs: list(InvoicePair)
        A list containing the actual invoice and the found reference from the MT940 file.
    """
    self.processed_invoices = [
    ]  # The invoices that have been processed successfully
    self.failed_invoices = []  # The invoices that have failed
    self.invoice_pairs = invoice_pairs

  def process(self):
    """Process all InvoicePairs and keep track of which invoice was processed successfully and which was not.
    If an invoice is processed the status in the database will be updated accordingly.
    """
    for pair in self.invoice_pairs:
      self.current_pair = pair
      if self.current_pair.costs_match():
        self.handleSuccess()
      else:
        self.handleFailed()

  def handleSuccess(self):
    self.current_pair.ok()
    self.processed_invoices.append(self.current_pair.invoice)

  def handleFailed(self):
    self.current_pair.failed()
    self.failed_invoices.append(self.current_pair.invoice)


class InvoicePair:

  def __init__(self, invoice, reference):
    """"""
    self.invoice = invoice
    self.reference = reference
    self.target_price = self.invoice.Totals()['total_price']
    self.reference['amount'] = round_price(
        decimal.Decimal(self.reference['amount']))

  def costs_match(self):
    """Compare the price that was mentioned in the mt940 file with the price that we have stored in the database."""
    return self.reference['amount'] == self.target_price

  def ok(self):
    """Sets the current invoice to paid and adds previous_state to the object so that it can be displayed on the page."""
    previous_status = self.invoice['status']
    self.invoice.SetPayed()
    self.invoice['previous_status'] = previous_status

  def failed(self):
    """Add a few values to the invoice object for extra information as of why the invoice was not processed propperly."""
    self.invoice['actual_amount'] = self.target_price
    self.invoice['expected_amount'] = self.reference['amount']
    self.invoice['diff'] = self.reference['amount'] - self.target_price
