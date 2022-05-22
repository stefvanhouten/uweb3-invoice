# Standard modules
# Standard modules

import datetime
import decimal
import time
from enum import Enum

import pytz
# Custom modules
from uweb3.model import Record

from invoices.base.model.model import Client, RichModel
from invoices.base.pages.helpers.general import round_price

__all__ = [
    'PRO_FORMA_PREFIX', 'PAYMENT_PERIOD', 'InvoiceStatus', 'Companydetails',
    'InvoiceProduct', 'Invoice', 'PaymentPlatform', 'InvoicePayment'
]

PRO_FORMA_PREFIX = 'PF'
PAYMENT_PERIOD = datetime.timedelta(14)


class InvoiceStatus(str, Enum):
  NEW = 'new'
  SENT = 'sent'
  PAID = 'paid'
  RESERVATION = 'reservation'
  CANCELED = 'canceled'


class Companydetails(Record):
  """Abstraction class for companyDetails stored in the database."""

  @classmethod
  def HighestNumber(cls, connection):
    """Returns the ID for the newest companydetails."""
    with connection as cursor:
      number = cursor.Select(fields='max(ID) AS maxid',
                             table=cls.TableName(),
                             escape=False)
    if number:
      return number[0]['maxid']
    return 0


class InvoiceProduct(RichModel):
  """Abstraction class for Products that are linked to an invoice"""

  def Totals(self):
    """Read the price from the database and create the vat amount."""
    self['vat_amount'] = (self['price'] * self['quantity'] /
                          100) * self['vat_percentage']


class Invoice(RichModel):
  """Abstraction class for Invoices stored in the database."""

  _FOREIGN_RELATIONS = {
      'contract': None,
      'client': {
          'class': Client,
          'loader': 'FromPrimary',
          'LookupKey': 'ID'
      }
  }

  def _PreCreate(self, cursor):
    super(Invoice, self)._PreCreate(cursor)
    self['title'] = self['title'].strip(' ')[:80]

  def _PreSave(self, cursor):
    super(Invoice, self)._PreSave(cursor)
    self['title'] = self['title'].strip(' ')[:80]

  @classmethod
  def CalculateDateDue(self):
    return datetime.date.today() + PAYMENT_PERIOD

  @classmethod
  def FromSequenceNumber(cls, connection, seq_num):
    """Returns the invoice belonging to the given `sequence_number`."""
    safe_num = connection.EscapeValues(seq_num)
    with connection as cursor:
      invoice = cursor.Select(table=cls.TableName(),
                              conditions='sequenceNumber = %s' % safe_num)
    if not invoice:
      raise cls.NotExistError('There is no invoice with number %r.' % seq_num)
    return cls(connection, invoice[0])

  @classmethod
  def Create(cls, connection, record):
    """Creates a new invoice in the database and then returns it.

    Arguments:
      @ connection
        Database connection to use.
      @ record: mapping
        The Invoice record to create.

    Returns:
      Invoice: the newly created invoice.
    """
    status = record.get('status', InvoiceStatus.NEW.value)
    if status and status == InvoiceStatus.RESERVATION:
      record.setdefault('sequenceNumber',
                        ProFormaSequenceTable.NextProFormaNumber(connection))
    else:
      record.setdefault('sequenceNumber', cls.NextNumber(connection))
    record.setdefault('companyDetails',
                      Companydetails.HighestNumber(connection))
    record.setdefault('dateDue', cls.CalculateDateDue())
    return super(Invoice, cls).Create(connection, record)

  def ProFormaToRealInvoice(self):
    """Changes a pro forma invoice to an actual invoice.
    This changes the status to new, calculates a new date for when the invoice is due and generates a new sequencenumber.
    """
    if self['status'] == InvoiceStatus.CANCELED:
      raise ValueError(
          "Can not change the status of a canceled invoice to paid.")

    self['sequenceNumber'] = self.NextNumber(self.connection)
    # Pro forma invoices can be paid for already, only set status to new when the invoice is not paid for yet.
    if self['status'] != InvoiceStatus.PAID:
      self['status'] = InvoiceStatus.NEW.value
    self['dateDue'] = self.CalculateDateDue()
    self.Save()

  def SetPayed(self):
    """Sets the current invoice status to paid. """
    if self['status'] == InvoiceStatus.CANCELED:
      raise ValueError(
          "Can not change the status of a canceled invoice to paid.")
    if self._isProForma():
      self.ProFormaToRealInvoice()
    self['status'] = InvoiceStatus.PAID.value
    self.Save()

  def CancelProFormaInvoice(self):
    """Cancels a pro forma invoice"""
    if not self._isProForma():
      raise ValueError("Only pro forma invoices can be canceled.")
    self['status'] = InvoiceStatus.CANCELED.value
    self.Save()

  def _isProForma(self):
    return self['sequenceNumber'][:2] == PRO_FORMA_PREFIX

  @classmethod
  def NextNumber(cls, connection):
    """Returns the sequenceNumber for the next invoice to create."""
    with connection as cursor:
      current_max = cursor.Select(
          table=cls.TableName(),
          fields='sequenceNumber',
          conditions=[
              'YEAR(dateCreated) = YEAR(NOW())',
              f'sequenceNumber NOT LIKE "{PRO_FORMA_PREFIX}-%"',
          ],
          limit=1,
          order=[('sequenceNumber', True)],
          escape=False)
    if current_max:
      year, sequence = current_max[0][0].split('-')
      return '%s-%03d' % (year, int(sequence) + 1)
    return '%s-%03d' % (time.strftime('%Y'), 1)

  @classmethod
  def List(cls, connection, *args, **kwds):
    test = ProFormaSequenceTable.NextProFormaNumber(connection)
    invoices = list(super().List(connection, *args, **kwds))
    today = pytz.utc.localize(datetime.datetime.utcnow())
    for invoice in invoices:
      invoice['totals'] = invoice.Totals()
      invoice['dateDue'] = invoice['dateDue'].replace(
          tzinfo=datetime.timezone.utc)

      if today > invoice['dateDue'] and invoice[
          'status'] != InvoiceStatus.PAID.value:
        invoice['overdue'] = 'overdue'
      else:
        invoice['overdue'] = ''
    return invoices

  def Totals(self):
    """Read the price from the database and create the vat amount."""
    with self.connection as cursor:
      totals = cursor.Select(
          table='invoiceProduct',
          fields=
          ('SUM(((price * quantity) / 100) * vat_percentage) + SUM(price * quantity) AS total',
           'SUM(price * quantity) as totalex'),
          conditions='invoice=%d' % self,
          escape=False)

    vatresults = []
    with self.connection as cursor:
      vatgroup = cursor.Select(
          table='invoiceProduct',
          fields=('vat_percentage',
                  'sum(((price * quantity) / 100) * vat_percentage) as total',
                  'sum(price * quantity) as taxable'),
          group='vat_percentage',
          conditions='invoice=%d' % self,
          escape=False)

    total_vat = decimal.Decimal(0)
    for vat in vatgroup:
      total_vat = total_vat + vat['total']
      vatresults.append({
          'amount': round_price(vat['total']),
          'taxable': round_price(vat['taxable']),
          'type': vat['vat_percentage']
      })
    total_paid = decimal.Decimal(0)
    for payment in self.GetPayments():
      total_paid += payment['amount']

    # TODO: Clean up the round_price stuff
    return {
        'total_price_without_vat': round_price(totals[0]['totalex']),
        'total_price': round_price(totals[0]['total']),
        'total_vat': round_price(total_vat),
        'total_paid': round_price(total_paid),
        'remaining': round_price(totals[0]['total']) - round_price(total_paid),
        'vat': vatresults
    }

  def Products(self):
    """Returns all products that are part of this invoice."""
    products = InvoiceProduct.List(self.connection,
                                   conditions=['invoice=%d' % self])
    index = 1
    for product in products:
      product['invoice'] = self
      product = InvoiceProduct(self.connection, product)
      product.Totals()
      product['index'] = index
      index = index + 1  # TODO implement loop indices in the template parser
      yield product

  def AddProducts(self, products):
    """Add multiple InvoiceProducts to an invoice.

    Arguments:
      @ products: [
                    { price: The price of the product,
                      vat_percentage: The amount of VAT that has to be paid over said product,
                      name: The name of the product
                      quantity: The amount of products
                    }
                  ]
    """
    for product in products:
      product['invoice'] = self[
          'ID']  # Set the product to the current invoice ID.
      InvoiceProduct.Create(self.connection, product)

  def GetPayments(self):
    return list(
        InvoicePayment.List(self.connection,
                            conditions=[f'invoice = {self["ID"]}']))

  def AddPayment(self, platformID, amount):
    """Add a payment to the current invoice."""
    platform = PaymentPlatform.FromPrimary(self.connection, platformID)
    return InvoicePayment.Create(
        self.connection, {
            'invoice': self['ID'],
            'platform': platform['ID'],
            'amount': round_price(amount)
        })


class PaymentPlatform(Record):

  @classmethod
  def FromName(cls, connection, name):
    name = connection.EscapeValues(name)
    with connection as cursor:
      platform = cursor.Execute("""
        SELECT *
        FROM paymentPlatform
        WHERE name = %s
      """ % (name))
    if not name:
      raise cls.NotExistError("Invalid name")
    return cls(connection, platform[0])


class InvoicePayment(RichModel):
  _FOREIGN_RELATIONS = {
      'invoice': {
          'class': Invoice,
          'loader': 'FromPrimary',
          'LookupKey': 'ID'
      },
      'platform': {
          'class': PaymentPlatform,
          'loader': 'FromPrimary',
          'LookupKey': 'ID'
      }
  }


class ProFormaSequenceTable(Record):
  """This table is used to keep track of the current pro forma sequencenumber.
  This is needed to prevent MT-940 payments from former pro forma invoices
  being added to new pro forma invoices.
  """

  @classmethod
  def NextProFormaNumber(cls, connection):
    """Generate a new sequence number for a pro forma invoice and return its value.

    Returns:
        str: The next sequenceNumber for a pro forma invoice.
    """
    with connection as cursor:
      record = cursor.Select(table=cls.TableName(), limit=1)

    if record:
      current_max = cls(connection, record[0])
      current_max.SetToNextNum()
      return current_max['sequenceNumber']
    return cls.Create(connection)['sequenceNumber']

  @classmethod
  def Create(cls, connection):
    """Create a record to keep track of the current pro forma invoice sequence number"""
    if list(cls.List(connection)):
      raise ValueError(
          "Only one record is needed to keep track of the pro forma sequence number."
      )
    return super().Create(connection, {
        'sequenceNumber':
            '%s-%s-%03d' % (PRO_FORMA_PREFIX, time.strftime('%Y'), 1)
    })

  def SetToNextNum(self):
    prefix, year, sequence = self['sequenceNumber'].split('-')
    self['sequenceNumber'] = '%s-%s-%03d' % (prefix, year, int(sequence) + 1)
    self.Save()
