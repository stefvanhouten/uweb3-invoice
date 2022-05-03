#!/usr/bin/python
"""Request handlers for the uWeb3 warehouse inventory software"""

# standard modules
from itertools import zip_longest
from marshmallow import Schema, fields, EXCLUDE

# uweb modules
import uweb3
from base import decorators
from base.model import model


class InvoiceSchema(Schema):

  class Meta:
    unknown = EXCLUDE

  title = fields.Str(required=True, allow_none=False)
  description = fields.Str(required=True, allow_none=False)
  client = fields.Str(required=True, allow_none=False)
  status = fields.Str(required=True, allow_none=False)
  reservation = fields.Str()


class PageMaker:

  @uweb3.decorators.ContentType('application/json')
  @decorators.json_error_wrapper
  def RequestInvoices(self):
    return {
        ' invoices': list(model.Invoice.List(self.connection)),
    }

  def RequestInvoiceDetails(self, sequence_number):
    invoice = model.Invoice.FromSequenceNumber(self.connection, sequence_number)
    return {
        'invoice': invoice,
        'products': invoice.Products(),
        'totals': invoice.Totals()
    }

  def RequestNewInvoice(self):
    client = model.Client.FromClientNumber(self.connection,
                                           int(self.post.getfirst('client')))

    products = self.post.getlist('products')
    prices = self.post.getlist('invoice_prices')
    vat = self.post.getlist('invoice_vat')
    quantity = self.post.getlist('quantity')

    model.Client.autocommit(self.connection, False)
    try:
      invoice = model.Invoice.Create(
          self.connection, {
              'client': client['ID'],
              'title': self.post.getfirst('title'),
              'description': self.post.getfirst('description')
          })
      for product, price, vat, quantity in zip_longest(products, prices, vat,
                                                       quantity):
        invoice.AddProduct(product, price, vat, int(quantity))
      model.Client.commit(self.connection)
    except model.AssemblyError as error:
      model.Client.rollback(self.connection)
      return self.Error(error)
    except Exception as e:
      model.Client.rollback(self.connection)
      raise e
    finally:
      model.Client.autocommit(self.connection, True)
    return self.req.Redirect('/invoices', httpcode=303)
