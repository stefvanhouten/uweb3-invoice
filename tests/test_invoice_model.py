import datetime
from datetime import date
from decimal import Decimal
import pytest

from invoices.base.model import invoice, model
from uweb3.libs.sqltalk import mysql

current_year = date.today().year

# XXX: Some parameters might seem like they are unused.
# However since they are pytest fixtures they are used to create a databaserecord
# that is needed for that specific test. Removing these paramters will fail the test
# as the record that is needed in the test database is no longer there.


@pytest.fixture
def connection():
  connection = mysql.Connect(host='localhost',
                             user='test_invoices',
                             passwd='test_invoices',
                             db='test_invoices',
                             charset='utf8')
  connection.modelcache = model.modelcache.ClearCache()
  yield connection


@pytest.fixture
def client_object(connection) -> invoice.Client:
  client = invoice.Client.Create(
      connection, {
          'ID': 1,
          'clientNumber': 1,
          'name': 'client_name',
          'city': 'city',
          'postalCode': '1234AB',
          'email': 'test@gmail.com',
          'telephone': '12345678',
          'address': 'address'
      })
  return client


@pytest.fixture(autouse=True)
def run_before_and_after_tests(connection):
  with connection as cursor:
    cursor.Execute("SET FOREIGN_KEY_CHECKS=0;")
    cursor.Execute("TRUNCATE TABLE test_invoices.client;")
    cursor.Execute("TRUNCATE TABLE test_invoices.companydetails;")
    cursor.Execute("TRUNCATE TABLE test_invoices.invoice;")
    cursor.Execute("TRUNCATE TABLE test_invoices.invoiceProduct;")
    cursor.Execute("SET FOREIGN_KEY_CHECKS=0;")


@pytest.fixture
def companydetails_object(connection) -> invoice.Companydetails:
  companydetails = invoice.Companydetails.Create(
      connection, {
          'ID': 1,
          'name': 'companyname',
          'telephone': '12345678',
          'address': 'address',
          'postalCode': 'postalCode',
          'city': 'city',
          'country': 'country',
          'vat': 'vat',
          'kvk': 'kvk',
          'bank': 'bank',
          'bankAccount': 'bankAccount',
          'bankCity': 'bankCity',
          'invoiceprefix': 'test'
      })
  return companydetails


@pytest.fixture
def simple_invoice_dict(client_object, companydetails_object) -> dict:
  return {
      'ID': 1,
      'title': 'test invoice',
      'description': 'test',
      'client': client_object['ID'],
      'status': 'new'
  }


@pytest.fixture
def create_invoice_object(connection, client_object, companydetails_object):

  def create(status='new') -> invoice.Invoice:
    return invoice.Invoice.Create(
        connection, {
            'title': 'test invoice',
            'description': 'test',
            'client': client_object['ID'],
            'status': status
        })

  return create


def calc_due_date():
  return datetime.date.today() + invoice.PAYMENT_PERIOD


class TestClass:

  def test_validate_payment_period(self):
    assert invoice.PAYMENT_PERIOD == datetime.timedelta(14)

  def test_pro_forma_prefix(self):
    assert "PF" == invoice.PRO_FORMA_PREFIX

  def test_round_price(self):
    assert str(invoice.round_price(Decimal(12.255))) == '12.26'
    assert str(invoice.round_price(Decimal(12.26))) == '12.26'
    assert str(invoice.round_price(Decimal(12.22))) == '12.22'

  def test_create_invoice(self, connection, client_object,
                          companydetails_object):
    inv = invoice.Invoice.Create(
        connection, {
            'ID': 1,
            'title': 'test invoice',
            'description': 'test',
            'client': client_object['ID'],
            'status': 'new'
        })
    assert inv['ID'] == 1

  def test_invoice_sequence_number(self, connection, simple_invoice_dict):
    inv = invoice.Invoice.Create(connection, simple_invoice_dict)
    assert inv['sequenceNumber'] == f'{date.today().year}-001'

  def test_invoice_sequence_numbers(self, connection, simple_invoice_dict):
    inv1, inv2, inv3 = simple_invoice_dict.copy(), simple_invoice_dict.copy(
    ), simple_invoice_dict.copy()
    inv1['ID'] = 1
    inv2['ID'] = 2
    inv3['ID'] = 3

    inv1 = invoice.Invoice.Create(connection, inv1)
    inv2 = invoice.Invoice.Create(connection, inv2)
    inv3 = invoice.Invoice.Create(connection, inv3)
    assert inv1['sequenceNumber'] == f'{date.today().year}-001'
    assert inv2['sequenceNumber'] == f'{date.today().year}-002'
    assert inv3['sequenceNumber'] == f'{date.today().year}-003'

  def test_pro_forma_invoice_sequence_number(self, connection, client_object,
                                             companydetails_object):
    pro_forma = invoice.Invoice.Create(
        connection, {
            'ID': 1,
            'title': 'test invoice',
            'description': 'test',
            'client': client_object['ID'],
            'status': 'reservation'
        })
    assert pro_forma[
        'sequenceNumber'] == f'{invoice.PRO_FORMA_PREFIX}-{date.today().year}-001'

  def test_invoice_and_pro_forma_mix_sequence_number(self, connection,
                                                     client_object,
                                                     create_invoice_object):
    real_invoice = create_invoice_object(status='new')
    pro_forma = create_invoice_object(status='reservation')
    second_real_invoice = create_invoice_object(status='new')
    second_pro_forma = create_invoice_object(status='reservation')

    assert real_invoice['sequenceNumber'] == f'{date.today().year}-001'
    assert pro_forma[
        'sequenceNumber'] == f'{invoice.PRO_FORMA_PREFIX}-{date.today().year}-001'
    assert second_real_invoice['sequenceNumber'] == f'{date.today().year}-002'
    assert second_pro_forma[
        'sequenceNumber'] == f'{invoice.PRO_FORMA_PREFIX}-{date.today().year}-002'

  def test_datedue(self):
    assert calc_due_date() == invoice.Invoice.CalculateDateDue()

  def test_pro_forma_to_real_invoice(self, create_invoice_object):
    pro_forma = create_invoice_object(status='reservation')
    assert pro_forma['status'] == 'reservation'

    pro_forma.ProFormaToRealInvoice()

    assert pro_forma['status'] == 'new'
    assert pro_forma['dateDue'] == calc_due_date()

  def test_invoice_to_paid(self, create_invoice_object):
    inv = create_invoice_object(status='new')
    assert inv['status'] == 'new'

    inv.SetPayed()

    assert inv['status'] == 'paid'
    assert inv['dateDue'] == calc_due_date()

  def test_pro_forma_to_paid(self, create_invoice_object):
    pro_forma = create_invoice_object(status='reservation')
    assert pro_forma['status'] == 'reservation'

    pro_forma.SetPayed()

    assert pro_forma['sequenceNumber'] == f'{date.today().year}-001'
    assert pro_forma['status'] == 'paid'
    assert pro_forma['dateDue'] == calc_due_date()

  def test(self):
    """Empty test to ensure that all data is truncated from the database."""
    pass
