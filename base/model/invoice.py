# Standard modules
# Standard modules

import datetime
import time

# Custom modules
from base.model.model import RichModel
from base.libs import modelcache

class Companydetails(modelcache.Record):
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

  def Totals(self, state='new', client=None):
    """Returns the financial total with and without vat.

    Specifying a client will limit the totals to that client.
    """
    conditions = [
        "invoice.client=client.ID", "product.invoice = invoice.ID",
        "invoice.status='%s'" % state
    ]
    if client:
      conditions.append('client.clientNumber = %d' % (client['clientNumber']))

    with self.connection as cursor:
      total = cursor.Select(
          table=('invoice', 'client', 'product'),
          fields=('SUM((price / 100) * vat_percentage) + SUM(price) AS total',
                  'SUM(price) as totalex'),
          conditions=conditions,
          escape=False)
    return total

  @classmethod
  def Pricing(cls, connection):
    """Return the current global system prices as a Dict."""
    with connection as cursor:
      prices = cursor.Select(table=cls.TableName(),
                             order=[('ID', True)],
                             limit=1)
    if prices:
      returnvalues = {}
      for key in list(prices[0].keys()):
        if key.startswith('price'):
          returnvalues[key[5:]] = float(prices[0][key])
      return returnvalues


class Invoice(RichModel):
  """Abstraction class for Invoices stored in the database."""

  _FOREIGN_RELATIONS = {
      'contract': None,
      'client': {
          'class': 'Client',
          'loader': 'FromPrimary',
          'LookupKey': 'ID'
      }
  }
  SEARCHABLE_COLUMNS = [
      'sequenceNumber', 'client.name', 'title', 'dateCreated', 'status'
  ]

  def _PreCreate(self, cursor):
    super(Invoice, self)._PreCreate(cursor)
    self['title'] = self['title'].strip(' ')[:80]

  def _PreSave(self, cursor):
    super(Invoice, self)._PreSave(cursor)
    self['title'] = self['title'].strip(' ')[:80]

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
    record.setdefault('sequenceNumber', cls.NextNumber(connection))
    record.setdefault('companyDetails',
                      Companydetails.HighestNumber(connection))
    record.setdefault('dateDue', datetime.date.today() + PAYMENT_PERIOD)
    return super(Invoice, cls).Create(connection, record)

  @classmethod
  def NextNumber(cls, connection):
    """Returns the sequenceNumber for the next invoice to create."""
    with connection as cursor:
      current_max = cursor.Select(table=cls.TableName(),
                                  fields='sequenceNumber',
                                  conditions='YEAR(dateCreated) = YEAR(NOW())',
                                  limit=1,
                                  order=[('sequenceNumber', True)],
                                  escape=False)
    if current_max:
      year, sequence = current_max[0][0].split('-')
      return '%s-%03d' % (year, int(sequence) + 1)
    return '%s-%03d' % (time.strftime('%Y'), 1)

  def Totals(self):
    """Read the price from the database and create the vat amount."""
    with self.connection as cursor:
      totals = cursor.Select(
          table='product',
          fields=('SUM((price / 100) * vat_percentage) + SUM(price) AS total',
                  'SUM(price) as totalex'),
          conditions='invoice=%d' % self,
          escape=False)

    vatresults = []
    with self.connection as cursor:
      vatgroup = cursor.Select(
          table='product',
          fields=('vat_percentage',
                  'sum((price / 100) * vat_percentage) as total',
                  'sum(price) as taxable'),
          group='vat_percentage',
          conditions='invoice=%d' % self,
          escape=False)
    total_vat = 0
    for vat in vatgroup:
      total_vat = total_vat + vat['total']
      vatresults.append({
          'amount': vat['total'],
          'taxable': vat['taxable'],
          'type': vat['vat_percentage']
      })
    return {
        'total_price_without_vat': totals[0]['totalex'],
        'total_price': totals[0]['total'],
        'total_vat': total_vat,
        'vat': vatresults
    }

  def Products(self):
    """Returns all products that are part of this invoice."""
    products = Product.List(self.connection, conditions='invoice=%d' % self)
    index = 1
    for product in products:
      product['invoice'] = self
      product = Product(self.connection, product)
      product.Totals()
      product['index'] = index
      index = index + 1  # TODO implement loop indices in the template parser
      yield product

  def AddProduct(self, name, price, vat_percent):
    """Adds a product to the current invoice."""
    return Product.Create(
        self.connection, {
            'invoice': self.key,
            'name': name,
            'price': price,
            'vat_percentage': vat_percent
        })