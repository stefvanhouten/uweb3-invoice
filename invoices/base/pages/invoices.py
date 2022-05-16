#!/usr/bin/python
"""Request handlers for the uWeb3 warehouse inventory software"""

# standard modules
import decimal
import requests
from marshmallow.exceptions import ValidationError
from http import HTTPStatus
from invoices.base.pages.helpers.general import transaction
from invoices.base.pages.helpers.invoices import *

from io import StringIO
from invoices.base.pages.helpers.invoices import decide_reference_message
from invoices.base.pages.helpers.schemas import InvoiceSchema, ProductsCollectionSchema

# uweb modules
import uweb3
from invoices.base.model import model
from uweb3.libs.mail import MailSender
from invoices.base.decorators import NotExistsErrorCatcher, RequestWrapper

INVOICE_REGEX_PATTERN = r"([0-9]{4}-[0-9]{3})|(PF-[0-9]{4}-[0-9]{3})"


class WarehouseAPIException(Exception):
  """Error that was raised during an API call to warehouse."""


class PageMaker:

  def _get_warehouse_api_data(
      self
  ):  # XXX: This is used because the __init__ and _PostInit methods are not called because this PageMakers super class is object.
    """Reads the config for warehouse API data and sets:
    - self.warehouse_api_url: The warehouse url to access the API
    - self.warehouse_apikey: The apikey that is needed to access the warehouse API
    """
    self.warehouse_api_url = self.config.options['general']['warehouse_api']
    self.warehouse_apikey = self.config.options['general']['apikey']

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
    self._get_warehouse_api_data()
    response = requests.get(
        f'{self.warehouse_api_url}/products?apikey={self.warehouse_apikey}')

    if response.status_code != 200:
      return self._hadle_api_status_error(response)

    json_response = response.json()
    return {
        'clients': list(model.Client.List(self.connection)),
        'products': json_response['products'],
        'errors': errors,
        'api_url': self.warehouse_api_url,
        'apikey': self.warehouse_apikey,
        'scripts': ['/js/invoice.js']
    }

  def _hadle_api_status_error(self, response):
    json_response = response.json()

    if response.status_code == HTTPStatus.NOT_FOUND:
      return self.Error(
          f"Warehouse API at url '{self.warehouse_api_url}' could not be found."
      )
    elif response.status_code == HTTPStatus.FORBIDDEN:
      error = json_response.get(
          'error',
          'Not allowed to access this page. Are you using a valid apikey?')
      return self.Error(error)
    return self.Error("Something went wrong!")

  @uweb3.decorators.loggedin
  @uweb3.decorators.checkxsrf
  @RequestWrapper
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
    except ValidationError as error:
      return self.RequestNewInvoicePage(errors=[error.messages])

    try:
      invoice = self._create_invoice_and_products(sanitized_invoice,
                                                  products['products'])
    except WarehouseAPIException as error:
      if 'errors' in error.args[0]:
        return self.RequestNewInvoicePage(errors=error.args[0]['errors'])
      return self.RequestNewInvoicePage(errors='Something went wrong')

    if invoice and self.post.getfirst('shouldmail'):
      self.mail_invoice(invoice,
                        self.RequestInvoiceDetails(invoice['sequenceNumber']))
    return self.req.Redirect('/invoices', httpcode=303)

  def _create_invoice_and_products(self, sanitized_invoice, invoice_products):
    self._get_warehouse_api_data()
    clean_products = CreateCleanProductList(invoice_products, negative_abs=True)

    with transaction(self.connection, model.Invoice):
      invoice = model.Invoice.Create(self.connection, sanitized_invoice)
      invoice.AddProducts(invoice_products)
      reference_message = decide_reference_message(invoice['status'],
                                                   invoice['sequenceNumber'])

      response = requests.post(f'{self.warehouse_api_url}/products/bulk_stock',
                               json={
                                   "apikey": self.warehouse_apikey,
                                   "products": clean_products,
                                   "reference": reference_message,
                               })
      if response.status_code == 200:
        model.Client.commit(self.connection)
      else:
        model.Client.rollback(self.connection)
        raise WarehouseAPIException(response.json())

    return invoice

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
    api_url, apikey = self._get_warehouse_api_data()

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
