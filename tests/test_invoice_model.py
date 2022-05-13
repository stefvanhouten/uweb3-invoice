import datetime
from datetime import date
from decimal import Decimal
import pytest

from invoices.base.model import invoice, model
from uweb3.libs.sqltalk import mysql

current_year = date.today().year


@pytest.fixture()
def connection():
  connection = mysql.Connect(host='localhost',
                             user='test_invoices',
                             passwd='test_invoices',
                             db='test_invoices',
                             charset='utf8')
  connection.modelcache = model.modelcache.ClearCache()
  yield connection


@pytest.fixture(scope='function')
def client_object(request, connection):
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


@pytest.fixture(scope='function')
def companydetails_object(request, connection):
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
def simple_invoice_dict(client_object, companydetails_object):
  # Even though companydetails_object is not used the fixture is called and creates a record that we need.
  return {
      'ID': 1,
      'title': 'test invoice',
      'description': 'test',
      'client': client_object['ID'],
      'status': 'new'
  }


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

  def test_correct_invoice_sequence_number(self, connection,
                                           simple_invoice_dict):
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
