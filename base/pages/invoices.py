#!/usr/bin/python
"""Request handlers for the uWeb3 warehouse inventory software"""

# standard modules
from itertools import zip_longest
from marshmallow import Schema, fields, EXCLUDE
from base.model.invoice import InvoiceProduct

# uweb modules
import uweb3
from base.decorators import NotExistsErrorCatcher, json_error_wrapper
from base.model import model
from base.pages.clients import RequestClientSchema
from base import basepages


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

    try:
      model.Client.autocommit(self.connection, False)
      invoice = model.Invoice.Create(self.connection, sanitized_invoice)
      for product in products['products']:
        product['invoice'] = invoice['ID']
        InvoiceProduct.Create(self.connection, product)
        model.Client.commit(self.connection)
    except Exception as e:
      model.Client.rollback(self.connection)
      raise e
    finally:
      model.Client.autocommit(self.connection, True)
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
