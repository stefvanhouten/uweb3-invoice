from datetime import date

import pytest
from uweb3.libs.sqltalk import mysql

from invoices.base.invoice import model as invoice_model

current_year = date.today().year


@pytest.fixture(scope="module")
def connection():
    connection = mysql.Connect(
        host="localhost",
        user="test_invoices",
        passwd="test_invoices",
        db="test_invoices",
        charset="utf8",
    )

    with connection as cursor:
        cursor.Execute("TRUNCATE TABLE test_invoices.paymentPlatform;")
        cursor.Execute(
            "INSERT INTO test_invoices.paymentPlatform (name) VALUES ('ideal'),('marktplaats'),('mollie'),('contant')"
        )
    yield connection


@pytest.fixture
def client_object(connection) -> invoice_model.Client:
    client = invoice_model.Client.Create(
        connection,
        {
            "ID": 1,
            "clientNumber": 1,
            "name": "client_name",
            "city": "city",
            "postalCode": "1234AB",
            "email": "test@gmail.com",
            "telephone": "12345678",
            "address": "address",
        },
    )
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
        cursor.Execute("TRUNCATE TABLE test_invoices.proFormaSequenceTable;")
        cursor.Execute("SET FOREIGN_KEY_CHECKS=0;")


@pytest.fixture
def companydetails_object(connection) -> invoice_model.Companydetails:
    companydetails = invoice_model.Companydetails.Create(
        connection,
        {
            "ID": 1,
            "name": "companyname",
            "telephone": "12345678",
            "address": "address",
            "postalCode": "postalCode",
            "city": "city",
            "country": "country",
            "vat": "vat",
            "kvk": "kvk",
            "bank": "bank",
            "bankAccount": "bankAccount",
            "bankCity": "bankCity",
            "invoiceprefix": "test",
        },
    )
    return companydetails


@pytest.fixture
def simple_invoice_dict(client_object, companydetails_object) -> dict:
    return {
        "ID": 1,
        "title": "test invoice",
        "description": "test",
        "client": client_object["ID"],
        "status": "new",
    }


@pytest.fixture
def create_invoice_object(connection, client_object, companydetails_object):
    def create(status=invoice_model.InvoiceStatus.NEW.value) -> invoice_model.Invoice:
        return invoice_model.Invoice.Create(
            connection,
            {
                "title": "test invoice",
                "description": "test",
                "client": client_object["ID"],
                "status": status,
            },
        )

    return create


@pytest.fixture
def default_invoice_and_products(create_invoice_object):
    def create_default_invoice(
        status=invoice_model.InvoiceStatus.NEW.value,
    ) -> invoice_model.Invoice:
        invoice = create_invoice_object(status=status)
        products = [
            {"name": "dakpan", "price": 25, "vat_percentage": 10, "quantity": 10},
        ]
        invoice.AddProducts(products)
        return invoice

    return create_default_invoice
