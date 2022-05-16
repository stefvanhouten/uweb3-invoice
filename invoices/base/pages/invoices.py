#!/usr/bin/python
"""Request handlers for the uWeb3 warehouse inventory software"""

# standard modules
from http.client import FORBIDDEN
import re
import mt940
import decimal
import requests
import marshmallow
from http import HTTPStatus
from itertools import zip_longest
from marshmallow import Schema, fields, EXCLUDE, post_load, validate
from invoices.base.model.invoice import InvoiceProduct

from weasyprint import HTML
from io import BytesIO, StringIO

# uweb modules
import uweb3
from invoices.base.model import model
from uweb3.libs.mail import MailSender
from invoices.base.decorators import NotExistsErrorCatcher, RequestWrapper

INVOICE_REGEX_PATTERN = r"([0-9]{4}-[0-9]{3})|(PF-[0-9]{4}-[0-9]{3})"


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


def get_and_zip_products(products, product_prices, product_vat,
                         product_quantity):
  """Transform invoice products post data to a list of dictionaries.
  This function uses zip_longest, so any missing data will be filled with None.

  Arguments:
    @ products: list
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
  for product, price, vat, quantity in zip_longest(products, product_prices,
                                                   product_vat,
                                                   product_quantity):
    products.append({
        'name': product,
        'price': price,
        'vat_percentage': vat,
        'quantity': quantity
    })
  return products


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

    if response.status_code != 200:
      return self._hadle_api_status_error(response)

    json_response = response.json()
    return {
        'clients': list(model.Client.List(self.connection)),
        'products': json_response['products'],
        'errors': errors,
        'api_url': api_url,
        'apikey': apikey,
        'scripts': ['/js/invoice.js']
    }

  def _hadle_api_status_error(self, response):
    json_response = response.json()
    if response.status_code == HTTPStatus.NOT_FOUND:
      return self.Error(f"Warehouse API at url '{api_url}' could not be found.")
    elif response.status_code == HTTPStatus.FORBIDDEN:
      error = json_response.get(
          'error',
          'Not allowed to access this page. Are you using a valid apikey?')
      return self.Error(error)
    return self.Error("Something went wrong!")

  @uweb3.decorators.loggedin
  @uweb3.decorators.checkxsrf
  def RequestCreateNewInvoicePage(self):
    # TODO: Handle validation errors
    products = get_and_zip_products(self.post.getlist('products'),
                                    self.post.getlist('invoice_prices'),
                                    self.post.getlist('invoice_vat'),
                                    self.post.getlist('quantity'))
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
      return self.RequestNewInvoicePage(errors='Something went wrong')

    if invoice:
      self.mail_invoice(invoice,
                        self.RequestInvoiceDetails(invoice['sequenceNumber']))
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
    self.mail_invoice(invoice,
                      self.RequestInvoiceDetails(invoice['sequenceNumber']))
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

  def mail_invoice(self, invoice, details):
    # Generate the PDF for newly created invoice
    pdf = ToPDF(details, filename='invoice.pdf')
    # Create a mollie payment request
    content = self.parser.Parse(
        'email/invoice.txt',
        **{'mollie': self.RequestMollie(invoice)['url']['href']})

    with MailSender() as send_mail:
      send_mail.Attachments(recipients=invoice['client']['email'],
                            subject='Your invoice',
                            content=content,
                            attachments=(pdf,))

  @uweb3.decorators.loggedin
  @uweb3.decorators.checkxsrf
  @uweb3.decorators.TemplateParser('invoices/mt940.html')
  def RequestMt940(self, changed_invoices=[], failed_invoices=[]):
    return {
        'invoices': changed_invoices,
        'failed_invoices': failed_invoices,
        'mt940_preview': True,
    }

  @uweb3.decorators.loggedin
  @uweb3.decorators.checkxsrf
  def RequestUploadMt940(self):
    # TODO: File validation.
    changed_invoices = []
    failed_invoices = []
    for posted_file in self.files.get('fileupload', []):
      io_file = StringIO(posted_file['content'])
      results = regex_search(io_file, INVOICE_REGEX_PATTERN)
      for res in results:
        try:
          invoice = model.Invoice.FromSequenceNumber(self.connection,
                                                     res['invoice'])
          price = invoice.Totals()['total_price']
          res['amount'] = decimal.Decimal(res['amount'])
          if res['amount'] == price:
            previous_status = invoice['status']
            invoice.SetPayed()
            invoice['previous_status'] = previous_status
            changed_invoices.append(invoice)
          else:
            # XXX: These fields do not exist on a real invoice object. This is purely for the failed invoices table.
            invoice['actual_amount'] = price
            invoice['expected_amount'] = res['amount']
            invoice['diff'] = res['amount'] - price
            failed_invoices.append(invoice)
        except (uweb3.model.NotExistError, Exception) as e:
          # Invoice could not be found. This could mean two things,
          # 1. The regex matched something that looks like an invoice sequence number, but its not part of our system.
          # 2. The transaction contains a pro-forma invoice, but this invoice was already set to paid and thus changed to a real invoice.
          # its also possible that there was a duplicate pro-forma invoice ID in the description, but since it was already processed no reference can be found to it anymore.
          continue
    return self.RequestMt940(changed_invoices=changed_invoices,
                             failed_invoices=failed_invoices)
