#!/usr/bin/python
"""Request handlers for the uWeb3 warehouse inventory software"""

# standard modules
from itertools import zip_longest
from multiprocessing.sharedctypes import Value
import requests
from marshmallow import Schema, fields, EXCLUDE
from base.model.invoice import InvoiceProduct

# uweb modules
import uweb3
from base.decorators import NotExistsErrorCatcher, json_error_wrapper
from base.model import model
from base.pages.clients import RequestClientSchema


class InvoiceSchema(Schema):

  class Meta:
    unknown = EXCLUDE

  client = fields.Int(required=True, allow_none=False)
  title = fields.Str(required=True, allow_none=False)
  description = fields.Str(required=True, allow_none=False)


class ProductSchema(Schema):
  name = fields.Str(required=True, allow_none=False)
  price = fields.Decimal(required=True, allow_nan=False)
  vat_percentage = fields.Int(required=True, allow_none=False)
  quantity = fields.Int(required=True, allow_none=False)


class ProductsCollectionSchema(Schema):

  class Meta:
    unknown = EXCLUDE

  products = fields.Nested(ProductSchema, many=True, required=True)


class PageMaker:

  @uweb3.decorators.loggedin
  @uweb3.decorators.checkxsrf
  @uweb3.decorators.TemplateParser('invoices/invoices.html')
  def RequestInvoicesPage(self):
    return {
        'invoices': list(model.Invoice.List(self.connection)),
    }

  @uweb3.decorators.loggedin
  @uweb3.decorators.checkxsrf
  @uweb3.decorators.TemplateParser('invoices/create.html')
  def RequestNewInvoicePage(self):
    # TODO: Setup for API route nad key.
    # Catch connectionerror
    response = requests.get(
        'http://127.0.0.1:8002/api/v1/products?apikey=6435e79d8b1f6d9ef1cf35fd458bcd5e'
    )
    if response.status_code != 200:
      return self.Error("Something went wrong!")

    return {
        'clients': list(model.Client.List(self.connection)),
        'products': response.json()['products'],
        'scripts': ['/js/invoice.js']
    }

  @uweb3.decorators.loggedin
  @uweb3.decorators.checkxsrf
  def RequestCreateNewInvoicePage(self):
    # TODO: Handle validation errors
    products = []
    for product, price, vat, quantity in zip_longest(
        self.post.getlist('products'), self.post.getlist('invoice_prices'),
        self.post.getlist('invoice_vat'), self.post.getlist('quantity')):
      products.append({
          'name': product,
          'price': price,
          'vat_percentage': vat,
          'quantity': quantity
      })

    client = model.Client.FromClientNumber(self.connection,
                                           int(self.post.getfirst('client')))

    sanitized_invoice = InvoiceSchema().load({
        'client': client['ID'],
        'title': self.post.getfirst('title'),
        'description': self.post.getfirst('description')
    })
    products = ProductsCollectionSchema().load({'products': products})
    self._handle_create(sanitized_invoice, products)
    return self.req.Redirect('/invoices', httpcode=303)

  @uweb3.decorators.ContentType('application/json')
  @json_error_wrapper
  def RequestInvoices(self):
    return {
        ' invoices': list(model.Invoice.List(self.connection)),
    }

  @uweb3.decorators.ContentType('application/json')
  @json_error_wrapper
  def RequestInvoiceDetails(self, sequence_number):
    invoice = model.Invoice.FromSequenceNumber(self.connection, sequence_number)
    return {
        'invoice': invoice,
        'products': invoice.Products(),
        'totals': invoice.Totals()
    }

  @uweb3.decorators.ContentType('application/json')
  @json_error_wrapper
  def RequestNewInvoice(self):
    client_number = RequestClientSchema().load(dict(self.post))
    sanitized_invoice = InvoiceSchema().load(dict(self.post))
    products = ProductsCollectionSchema().load(dict(self.post))

    client = model.Client.FromPrimary(self.connection, client_number['client'])
    sanitized_invoice['client'] = client['ID']

    invoice = self._handle_create(sanitized_invoice, products)
    return self.RequestInvoiceDetailsJSON(invoice['sequenceNumber'])

  @uweb3.decorators.TemplateParser('invoice.html')
  @NotExistsErrorCatcher
  def RequestInvoiceDetails(self, sequence_number):
    invoice = model.Invoice.FromSequenceNumber(self.connection, sequence_number)
    companydetails = {'companydetails': self.options.get('companydetails')}
    invoice.update(companydetails)
    return {
        'invoice': invoice,
        'products': invoice.Products(),
        'totals': invoice.Totals()
    }

  @uweb3.decorators.ContentType('application/json')
  @json_error_wrapper
  def RequestInvoiceDetailsJSON(self, sequence_number):
    invoice = model.Invoice.FromSequenceNumber(self.connection, sequence_number)
    companydetails = {'companydetails': self.options.get('companydetails')}
    invoice.update(companydetails)
    return {
        'invoice': invoice,
        'products': list(invoice.Products()),
        'totals': invoice.Totals()
    }

  def _handle_create(self, sanitized_invoice, products):
    try:
      model.Client.autocommit(self.connection, False)
      invoice = model.Invoice.Create(self.connection, sanitized_invoice)
      for product in products['products']:
        product['invoice'] = invoice['ID']
        # TODO: Add API call to reduce stock
        InvoiceProduct.Create(self.connection, product)
        response = requests.post(
            f'http://127.0.0.1:8002/api/v1/product/{product["name"]}/stock',
            json={
                "amount": -abs(product['quantity']),
                "apikey": "6435e79d8b1f6d9ef1cf35fd458bcd5e"
            })
        if response.status_code == 200:
          model.Client.commit(self.connection)
        else:
          model.Client.rollback(self.connection)
          raise ValueError(response.json())
    except ValueError:
      raise
    except Exception:
      model.Client.rollback(self.connection)
      raise
    finally:
      model.Client.autocommit(self.connection, True)
    return invoice
