#!/usr/bin/python
"""Request handlers for the uWeb3 warehouse inventory software"""

# standard modules
import requests
from marshmallow.exceptions import ValidationError
from http import HTTPStatus
from invoices.base.pages.helpers.invoices import *
from invoices.base.pages.helpers.general import round_price, transaction
from invoices.base.pages.helpers.schemas import InvoiceSchema, PaymentSchema, ProductSchema, WarehouseStockChangeSchema, WarehouseStockRefundSchema

# uweb modules
import uweb3
from invoices.base.model import model
from uweb3.libs.mail import MailSender
from invoices.base.decorators import NotExistsErrorCatcher, RequestWrapper


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
      return self._handle_api_status_error(response)

    json_response = response.json()
    return {
        'clients': list(model.Client.List(self.connection)),
        'products': json_response['products'],
        'errors': errors,
        'api_url': self.warehouse_api_url,
        'apikey': self.warehouse_apikey,
        'scripts': ['/js/invoice.js']
    }

  def _handle_api_status_error(self, response):
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
    # Check if client exists
    model.Client.FromPrimary(self.connection, int(self.post.getfirst('client')))
    products = get_and_zip_products(self.post)

    try:
      sanitized_invoice = InvoiceSchema().load(self.post.__dict__)
      products = ProductSchema(many=True).load(products)
    except ValidationError as error:
      return self.RequestNewInvoicePage(errors=[error.messages])

    if not products:
      return self.RequestNewInvoicePage(
          errors=['cannot create invoice without products'])

    # Start a transaction that is rolled back when any unhandled exception occurs
    with transaction(self.connection, model.Invoice):
      invoice = model.Invoice.Create(self.connection, sanitized_invoice)
      invoice.AddProducts(products)
      warehouse_ready_products = WarehouseStockChangeSchema(
          many=True).load(products)

      reference = create_invoice_reference_msg(invoice['status'],
                                               invoice['sequenceNumber'])
      response = self._warehouse_bulk_stock_request(warehouse_ready_products,
                                                    reference)

      if response.status_code != 200:
        model.Client.rollback(self.connection)
        json_response = response.json()
        if 'errors' in json_response:
          return self.RequestNewInvoicePage(errors=json_response['errors'])
    self._handle_mail(invoice)
    return self.req.Redirect('/invoices', httpcode=303)

  def _warehouse_bulk_stock_request(self, products, reference):
    # Make sure that self.warehouse_apikey and self.warehouse_url are set.
    self._get_warehouse_api_data()
    return requests.post(f'{self.warehouse_api_url}/products/bulk_stock',
                         json={
                             "apikey": self.warehouse_apikey,
                             "products": products,
                             "reference": reference
                         })

  def _handle_mail(self, invoice):
    if not invoice:
      return

    should_mail = self.post.getfirst('shouldmail')
    mollie_amount = self.post.getfirst('mollie_payment_request')

    if should_mail:
      data = {}

      # Check if there is a payment request for mollie in the post data
      if mollie_amount:
        payment_req_url = self._create_mollie_request(invoice, mollie_amount)
        data['mollie'] = payment_req_url

      # Mail the invoice with PDF attached
      return self.mail_invoice(
          invoice, self.RequestInvoiceDetails(invoice['sequenceNumber']),
          **data)

    if mollie_amount:
      # Mollie payment request was added, but the invoice is not supposed to be mailed.. What to do here?
      raise NotImplementedError(
          "When a mollie payment is requested the invoice should also be mailed.."
      )

  def _create_mollie_request(self, invoice, amount):
    mollie_result = self.RequestMollie(invoice['ID'], round_price(amount),
                                       invoice['description'],
                                       invoice['sequenceNumber'])
    return mollie_result['url']['href']

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
    # TODO: When should we mail the invoice, and what should be in the mail?
    self.mail_invoice(invoice,
                      self.RequestInvoiceDetails(invoice['sequenceNumber']))
    return self.req.Redirect('/invoices', httpcode=303)

  @uweb3.decorators.loggedin
  @uweb3.decorators.checkxsrf
  @NotExistsErrorCatcher
  def RequestInvoiceCancel(self):
    """Sets the given invoice to paid."""
    self._get_warehouse_api_data()

    invoice = self.post.getfirst('invoice')
    invoice = model.Invoice.FromSequenceNumber(self.connection, invoice)
    products = invoice.Products()

    warehouse_ready_products = WarehouseStockRefundSchema(
        many=True).load(products)
    response = requests.post(
        f'{self.warehouse_api_url}/products/bulk_stock',
        json={
            "apikey":
                self.warehouse_apikey,
            "reference":
                f"Canceling pro forma invoice: {invoice['sequenceNumber']}",
            "products":
                warehouse_ready_products
        })
    if response.status_code != 200:
      return self._handle_api_status_error(response)

    invoice.CancelProFormaInvoice()
    return self.req.Redirect('/invoices', httpcode=303)

  def mail_invoice(self, invoice, details, **kwds):
    # Generate the PDF for newly created invoice
    pdf = ToPDF(details, filename='invoice.pdf')
    # Create a mollie payment request
    content = self.parser.Parse('email/invoice.txt', **kwds)

    with MailSender() as send_mail:
      send_mail.Attachments(recipients=invoice['client']['email'],
                            subject='Your invoice',
                            content=content,
                            attachments=(pdf,))

  @uweb3.decorators.loggedin
  @uweb3.decorators.checkxsrf
  @uweb3.decorators.TemplateParser('invoices/mt940.html')
  def RequestMt940(self, payments=[], failed_invoices=[]):
    return {
        'payments': payments,
        'failed_invoices': failed_invoices,
        'mt940_preview': True,
    }

  @uweb3.decorators.loggedin
  @uweb3.decorators.checkxsrf
  def RequestUploadMt940(self):
    # TODO: File validation.
    payments = []
    failed_payments = []
    found_invoice_references = MT940_processor(self.files.get(
        'fileupload', [])).process_files()

    for invoice_ref in found_invoice_references:
      try:
        invoice = model.Invoice.FromSequenceNumber(self.connection,
                                                   invoice_ref['invoice'])
      except (uweb3.model.NotExistError, Exception) as e:
        # Invoice could not be found. This could mean two things,
        # 1. The regex matched something that looks like an invoice sequence number, but its not part of our system.
        # 2. The transaction contains a pro-forma invoice, but this invoice was already set to paid and thus changed to a real invoice.
        # its also possible that there was a duplicate pro-forma invoice ID in the description, but since it was already processed no reference can be found to it anymore.
        failed_payments.append(invoice_ref)
        continue

      platform = model.PaymentPlatform.FromName(
          self.connection, 'ideal')  # XXX: What payment platform is this?
      invoice.AddPayment(platform['ID'], invoice_ref['amount'])
      payments.append(invoice_ref)

    return self.RequestMt940(payments=payments, failed_invoices=failed_payments)

  @uweb3.decorators.loggedin
  @uweb3.decorators.checkxsrf
  @NotExistsErrorCatcher
  @uweb3.decorators.TemplateParser('invoices/payments.html')
  def ManagePayments(self, sequenceNumber):
    invoice = model.Invoice.FromSequenceNumber(self.connection, sequenceNumber)
    return {
        'invoice': invoice,
        'payments': invoice.GetPayments(),
        'totals': invoice.Totals(),
        'platforms': model.PaymentPlatform.List(self.connection)
    }

  @uweb3.decorators.loggedin
  @uweb3.decorators.checkxsrf
  @NotExistsErrorCatcher
  def AddPayment(self, sequenceNumber):
    payment = PaymentSchema().load(self.post.__dict__)
    invoice = model.Invoice.FromSequenceNumber(self.connection, sequenceNumber)
    invoice.AddPayment(payment['platform'], payment['amount'])
    return uweb3.Redirect(f'/invoice/payments/{invoice["sequenceNumber"]}',
                          httpcode=303)
