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
    assert inv['sequenceNumber'] == f'{date.today().year}-001'
