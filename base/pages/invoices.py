#!/usr/bin/python
"""Request handlers for the uWeb3 warehouse inventory software"""

# standard modules
from email.policy import default
from http import HTTPStatus
from itertools import zip_longest
from multiprocessing.sharedctypes import Value
import marshmallow
import requests
from marshmallow import Schema, fields, EXCLUDE, missing, post_load, validate
from base.model.invoice import InvoiceProduct

from weasyprint import HTML
from io import BytesIO

# uweb modules
import uweb3
from base.decorators import NotExistsErrorCatcher, RequestWrapper, json_error_wrapper
from base.model import model
from base.pages.clients import RequestClientSchema
from uweb3.libs.mail import MailSender


def ToPDF(html):
  """Returns a PDF based on the given HTML."""
  result = BytesIO()
  HTML(string=html).write_pdf(result)
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


class WarehouseAPIException(Exception):
  """Error that was raised during an API call to warehouse."""


class InvoiceSchema(Schema):

  class Meta:
    unknown = EXCLUDE

  client = fields.Int(required=True, allow_none=False)
  title = fields.Str(required=True, allow_none=False)
  description = fields.Str(required=True, allow_none=False)
  status = fields.Str(
      missing='new')  # Default status to new when field is missing.

  @post_load
  def no_status(self, item, *args, **kwargs):
    """When an empty string is provided set status to new."""
    if not item['status'] or item['status'] == '':
      item['status'] = 'new'
    if item['status'] == 'on':  # This is for when the checkbox value is passed.
      item['status'] = 'reservation'
    return item


class ProductSchema(Schema):
  name = fields.Str(required=True, allow_none=False)
  price = fields.Decimal(required=True, allow_nan=False)
  vat_percentage = fields.Int(required=True, allow_none=False)
  quantity = fields.Int(required=True, allow_none=False)


class ProductsCollectionSchema(Schema):

  class Meta:
    unknown = EXCLUDE

  products = fields.Nested(ProductSchema, many=True, required=True)


class CompanyDetailsSchema(Schema):

  class Meta:
    unknown = EXCLUDE

  name = fields.Str(required=True, allow_none=False)
  telephone = fields.Str(required=True, allow_none=False)
  address = fields.Str(required=True, allow_none=False)
  postalCode = fields.Str(
      required=True,
      allow_none=False,
      validate=validate.Regexp(
          r"^[1-9][0-9]{3} ?(?!sa|sd|ss|SA|SD|SS)[A-Za-z]{2}$",
          error="Should be 4 numbers and 2 letters"))
  city = fields.Str(required=True, allow_none=False)
  country = fields.Str(required=True, allow_none=False)
  vat = fields.Str(required=True, allow_none=False)
  kvk = fields.Str(required=True, allow_none=False)
  bankAccount = fields.Str(required=True, allow_none=False)
  bank = fields.Str(required=True, allow_none=False)
  bankCity = fields.Str(required=True, allow_none=False)
  invoiceprefix = fields.Str(required=True, allow_none=False)


class APIPages:

  # @uweb3.decorators.ContentType('application/json')
  # @json_error_wrapper
  # def RequestInvoices(self):
  #   return {
  #       ' invoices': list(model.Invoice.List(self.connection)),
  #   }

  # @uweb3.decorators.ContentType('application/json')
  # @json_error_wrapper
  # def RequestNewInvoice(self):
  #   client_number = RequestClientSchema().load(dict(self.post))
  #   sanitized_invoice = InvoiceSchema().load(dict(self.post))
  #   products = ProductsCollectionSchema().load(dict(self.post))

  #   client = model.Client.FromPrimary(self.connection, client_number['client'])
  #   sanitized_invoice['client'] = client['ID']

  #   invoice = self._handle_create(sanitized_invoice, products['products'])
  #   return self.RequestInvoiceDetailsJSON(invoice['sequenceNumber'])

  # @uweb3.decorators.ContentType('application/json')
  # @json_error_wrapper
  # def RequestInvoiceDetailsJSON(self, sequence_number):
  #   invoice = model.Invoice.FromSequenceNumber(self.connection, sequence_number)
  #   companydetails = {'companydetails': self.options.get('companydetails')}
  #   invoice.update(companydetails)
  #   return {
  #       'invoice': invoice,
  #       'products': list(invoice.Products()),
  #       'totals': invoice.Totals()
  #   }

  def _handle_create(self, sanitized_invoice, products):
    api_url = self.config.options['general']['warehouse_api']
    api_key = self.config.options['general']['apikey']

    items = CreateCleanProductList(products, negative_abs=True)

    try:
      model.Client.autocommit(self.connection, False)
      invoice = model.Invoice.Create(self.connection, sanitized_invoice)
      for product in products:
        product['invoice'] = invoice['ID']
        InvoiceProduct.Create(self.connection, product)

      reference = f"Buy order for invoice: {invoice['sequenceNumber']}"
      if invoice['status'] == 'reservation':
        reference = f"Reservation for invoice: {invoice['sequenceNumber']}"
      response = requests.post(f'{api_url}/products/bulk_stock',
                               json={
                                   "apikey": api_key,
                                   "products": items,
                                   "reference": reference,
                               })
      if response.status_code == 200:
        model.Client.commit(self.connection)
      else:
        model.Client.rollback(self.connection)
        raise WarehouseAPIException(response.json())
    except Exception:
      model.Client.rollback(self.connection)
      raise
    finally:
      model.Client.autocommit(self.connection, True)
    return invoice


class PageMaker(APIPages):

  @uweb3.decorators.loggedin
  @uweb3.decorators.checkxsrf
  @uweb3.decorators.TemplateParser('invoices/invoices.html')
  def RequestInvoicesPage(self):
    return {
        'invoices':
            list(model.Invoice.List(self.connection, order=['sequenceNumber'])),
    }

  @uweb3.decorators.loggedin
  @uweb3.decorators.checkxsrf
  @RequestWrapper
  @uweb3.decorators.TemplateParser('invoices/create.html')
  def RequestNewInvoicePage(self, errors=[]):
    api_url = self.config.options['general']['warehouse_api']
    apikey = self.config.options['general']['apikey']
    response = requests.get(f'{api_url}/products?apikey={apikey}')
    json_response = response.json()
    if response.status_code != 200:
      if response.status_code == HTTPStatus.NOT_FOUND:
        return self.Error(
            f"Warehouse API at url '{api_url}' could not be found.")
      if response.status_code == HTTPStatus.FORBIDDEN:
        error = json_response.get(
            'error',
            'Not allowed to access this page. Are you using a valid apikey?')
        return self.Error(error)
      return self.Error("Something went wrong!")

    return {
        'clients': list(model.Client.List(self.connection)),
        'products': json_response['products'],
        'errors': errors,
        'api_url': api_url,
        'apikey': apikey,
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
    invoice = None
    client = model.Client.FromClientNumber(self.connection,
                                           int(self.post.getfirst('client')))
    try:
      sanitized_invoice = InvoiceSchema().load({
          'client': client['ID'],
          'title': self.post.getfirst('title'),
          'description': self.post.getfirst('description'),
          'status': self.post.getfirst('reservation', '')
      })
      products = ProductsCollectionSchema().load({'products': products})
      invoice = self._handle_create(sanitized_invoice, products['products'])
    except marshmallow.exceptions.ValidationError as error:
      return self.RequestNewInvoicePage(errors=[error.messages])
    except WarehouseAPIException as error:
      if 'errors' in error.args[0]:
        return self.RequestNewInvoicePage(errors=error.args[0]['errors'])

    if invoice and invoice['status'] == 'new':
      pdf = ToPDF(self.RequestInvoiceDetails(invoice['sequenceNumber']))
      data = self.RequestMollie(invoice)
      # content = self.parser.Parse('email/test.txt')
      recipients = invoice['client']['email']
      subject = 'Your invoice'
      with MailSender() as send_mail:
        send_mail.Attachments(recipients,
                              subject,
                              data['url']['href'],
                              attachments=(pdf,))
    return self.req.Redirect('/invoices', httpcode=303)

  @uweb3.decorators.TemplateParser('invoices/invoice.html')
  @NotExistsErrorCatcher
  def RequestInvoiceDetails(self, sequence_number):
    invoice = model.Invoice.FromSequenceNumber(self.connection, sequence_number)
    return {
        'invoice': invoice,
        'products': invoice.Products(),
        'totals': invoice.Totals()
    }

  @uweb3.decorators.loggedin
  def RequestPDFInvoice(self, invoice):
    """Returns the invoice as a pdf file.

    Takes:
      invoice: int or str
    """
    requestedinvoice = self.RequestInvoiceDetails(invoice)
    if type(requestedinvoice) != uweb3.response.Redirect:
      return uweb3.Response(ToPDF(requestedinvoice),
                            content_type='application/pdf')
    return requestedinvoice

  @uweb3.decorators.loggedin
  @uweb3.decorators.checkxsrf
  @NotExistsErrorCatcher
  def RequestInvoicePayed(self):
    """Sets the given invoice to paid."""
    invoice = self.post.getfirst('invoice')
    invoice = model.Invoice.FromSequenceNumber(self.connection, invoice)
    invoice['status'] = 'paid'
    invoice.Save()
    return self.req.Redirect('/invoices', httpcode=303)

  @uweb3.decorators.loggedin
  @uweb3.decorators.checkxsrf
  @NotExistsErrorCatcher
  def RequestInvoiceReservationToNew(self):
    """Sets the given invoice to paid."""
    invoice = self.post.getfirst('invoice')
    invoice = model.Invoice.FromSequenceNumber(self.connection, invoice)
    invoice.ProFormaToRealInvoice()
    return self.req.Redirect('/invoices', httpcode=303)

  @uweb3.decorators.loggedin
  @uweb3.decorators.checkxsrf
  @NotExistsErrorCatcher
  def RequestInvoiceCancel(self):
    """Sets the given invoice to paid."""
    api_url = self.config.options['general']['warehouse_api']
    apikey = self.config.options['general']['apikey']

    invoice = self.post.getfirst('invoice')
    invoice = model.Invoice.FromSequenceNumber(self.connection, invoice)
    products = invoice.Products()

    items = CreateCleanProductList(products)
    response = requests.post(
        f'{api_url}/products/bulk_stock',
        json={
            "apikey": apikey,
            "reference": f"Canceling reservation: {invoice['sequenceNumber']}",
            "products": items
        })
    if response.status_code == 200:
      invoice['status'] = 'canceled'
      invoice.Save()
    return self.req.Redirect('/invoices', httpcode=303)
