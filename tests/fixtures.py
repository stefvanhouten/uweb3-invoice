from datetime import date
import pytest

from invoices.base.model import invoice
from uweb3.libs.sqltalk import mysql

current_year = date.today().year


@pytest.fixture(scope="module")
def connection():
  connection = mysql.Connect(host='localhost',
                             user='test_invoices',
                             passwd='test_invoices',
                             db='test_invoices',
                             charset='utf8')

  with connection as cursor:
    cursor.Execute("TRUNCATE TABLE test_invoices.paymentPlatform;")
    cursor.Execute(
        "INSERT INTO test_invoices.paymentPlatform (name) VALUES ('ideal'),('marktplaats'),('mollie'),('contant')"
    )
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
    cursor.Execute("TRUNCATE TABLE test_invoices.invoicePayment;")
    cursor.Execute("TRUNCATE TABLE test_invoices.invoiceProduct;")
    cursor.Execute("TRUNCATE TABLE test_invoices.mollieTransaction;")
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

  def create(status=invoice.InvoiceStatus.NEW.value) -> invoice.Invoice:
    return invoice.Invoice.Create(
        connection, {
            'title': 'test invoice',
            'description': 'test',
            'client': client_object['ID'],
            'status': status
        })

  return create


@pytest.fixture
def default_invoice_and_products(create_invoice_object):

  def create_default_invoice(
      status=invoice.InvoiceStatus.NEW.value) -> invoice.Invoice:
    invoice = create_invoice_object(status=status)
    products = [
        {
            'name': 'dakpan',
            'price': 25,
            'vat_percentage': 10,
            'quantity': 10
        },
    ]
    invoice.AddProducts(products)
    return invoice

  return create_default_invoice
