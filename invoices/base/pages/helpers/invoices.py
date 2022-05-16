#!/usr/bin/python
"""Request handlers for the uWeb3 warehouse inventory software"""

# standard modules
import re
import mt940
from itertools import zip_longest

from weasyprint import HTML
from io import BytesIO

from invoices.base.model.invoice import InvoiceStatus

__all__ = [
    'ToPDF', 'CreateCleanProductList', 'regex_search', 'get_and_zip_products',
    'decide_reference_message'
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


def regex_search(file, regex):
  """Parse a StringIO object"""
  transactions = mt940.models.Transactions(processors=dict(pre_statement=[
      mt940.processors.add_currency_pre_processor('EUR'),
  ],))
  data = file.read()
  transactions.parse(data)
  results = []
  for transaction in transactions:
    matches = re.finditer(regex, transaction.data['transaction_details'],
                          re.MULTILINE)
    amount = str(transaction.data['amount'].amount)
    results.extend([{"invoice": x.group(), "amount": amount} for x in matches])
  return results


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
  if status == InvoiceStatus.RESERVATION:
    reference = f"Reservation for invoice: {sequenceNumber}"
  else:
    reference = f"Buy order for invoice: {sequenceNumber}"
  return reference
