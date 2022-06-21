import datetime
import time
from datetime import date
from decimal import Decimal

import pytest

from invoices.common import helpers
from invoices.invoice import model as invoice_model
from tests.fixtures import *

# XXX: Some parameters might seem like they are unused.
# However since they are pytest fixtures they are used to create a databaserecord
# that is needed for that specific test. Removing these paramters will fail the test
# as the record that is needed in the test database is no longer there.


def calc_due_date():
    return datetime.date.today() + invoice_model.PAYMENT_PERIOD


class TestSequenceNumber:
    @pytest.mark.parametrize(
        "current, prefix, expected",
        [
            ("PREFIX-2022-001", "PREFIX", "PREFIX-2022-002"),
            ("2022-001", "PREFIX", "PREFIX-2022-002"),
            ("PREFIX-2022-001", None, "2022-002"),
            ("2022-001", None, "2022-002"),
            ("2022-001", None, "2022-002"),
            ("TEST-2022-001", "SOMENAME", "SOMENAME-2022-002"),
            (None, None, "%s-001" % time.strftime("%Y")),
            (None, "PREFIX", "PREFIX-%s-001" % time.strftime("%Y")),
        ],
    )
    def test_prefix(self, current, prefix, expected):
        assert expected == invoice_model.determine_next_sequence_number(current, prefix)


class TestClass:
    def test_validate_payment_period(self):
        assert invoice_model.PAYMENT_PERIOD == datetime.timedelta(14)

    def test_pro_forma_prefix(self):
        assert "PF" == invoice_model.PRO_FORMA_PREFIX

    def test_round_price(self):
        assert str(helpers.round_price(12.255)) == "12.26"
        assert str(helpers.round_price(12.26)) == "12.26"
        assert str(helpers.round_price(12.22)) == "12.22"

    def test_determine_invoice_type(self, create_invoice_object):
        pro_forma = create_invoice_object(
            status=invoice_model.InvoiceStatus.RESERVATION.value
        )
        real_inv = create_invoice_object(status=invoice_model.InvoiceStatus.NEW.value)

        assert pro_forma._isProForma() is True
        assert real_inv._isProForma() is False

    def test_create_invoice(self, connection, client_object, companydetails_object):
        inv = invoice_model.Invoice.Create(
            connection,
            {
                "ID": 1,
                "title": "test invoice",
                "description": "test",
                "client": client_object["ID"],
                "status": invoice_model.InvoiceStatus.NEW.value,
            },
        )
        assert inv["ID"] == 1
        assert inv["title"] == "test invoice"
        assert inv["description"] == "test"
        assert inv["client"]["ID"] == client_object["ID"]
        assert inv["status"] == invoice_model.InvoiceStatus.NEW

    def test_invoice_sequence_number(self, connection, simple_invoice_dict):
        """Determine if the model creates the correct sequenceNumber."""
        inv = invoice_model.Invoice.Create(connection, simple_invoice_dict)
        # test is the companydetails prefix that we use during unittests
        assert inv["sequenceNumber"] == "%s-%s-001" % ("test", date.today().year)

    def test_invoice_sequence_numbers(self, connection, simple_invoice_dict):
        inv1, inv2, inv3 = (
            simple_invoice_dict.copy(),
            simple_invoice_dict.copy(),
            simple_invoice_dict.copy(),
        )
        inv1["ID"] = 1
        inv2["ID"] = 2
        inv3["ID"] = 3

        inv1 = invoice_model.Invoice.Create(connection, inv1)
        inv2 = invoice_model.Invoice.Create(connection, inv2)
        inv3 = invoice_model.Invoice.Create(connection, inv3)
        assert inv1["sequenceNumber"] == f"test-{date.today().year}-001"
        assert inv2["sequenceNumber"] == f"test-{date.today().year}-002"
        assert inv3["sequenceNumber"] == f"test-{date.today().year}-003"

    def test_pro_forma_invoice_sequence_number(
        self, connection, client_object, companydetails_object
    ):
        pro_forma = invoice_model.Invoice.Create(
            connection,
            {
                "ID": 1,
                "title": "test invoice",
                "description": "test",
                "client": client_object["ID"],
                "status": "reservation",
            },
        )
        assert (
            pro_forma["sequenceNumber"]
            == f"test-{invoice_model.PRO_FORMA_PREFIX}-{date.today().year}-001"
        )

    def test_invoice_and_pro_forma_mix_sequence_number(self, create_invoice_object):
        real_invoice = create_invoice_object(
            status=invoice_model.InvoiceStatus.NEW.value
        )
        pro_forma = create_invoice_object(
            status=invoice_model.InvoiceStatus.RESERVATION.value
        )
        second_real_invoice = create_invoice_object(
            status=invoice_model.InvoiceStatus.NEW.value
        )
        second_pro_forma = create_invoice_object(
            status=invoice_model.InvoiceStatus.RESERVATION.value
        )

        assert real_invoice["sequenceNumber"] == f"test-{date.today().year}-001"
        assert (
            pro_forma["sequenceNumber"]
            == f"test-{invoice_model.PRO_FORMA_PREFIX}-{date.today().year}-001"
        )
        assert second_real_invoice["sequenceNumber"] == f"test-{date.today().year}-002"
        assert (
            second_pro_forma["sequenceNumber"]
            == f"test-{invoice_model.PRO_FORMA_PREFIX}-{date.today().year}-002"
        )

    def test_dont_reuse_pro_forma_sequence_number(self, create_invoice_object):
        first_pro_forma = create_invoice_object(
            status=invoice_model.InvoiceStatus.RESERVATION.value
        )
        assert (
            first_pro_forma["sequenceNumber"]
            == f"test-{invoice_model.PRO_FORMA_PREFIX}-{date.today().year}-001"
        )
        first_pro_forma.Delete()
        second_pro_forma = create_invoice_object(
            status=invoice_model.InvoiceStatus.RESERVATION.value
        )
        assert (
            second_pro_forma["sequenceNumber"]
            == f"test-{invoice_model.PRO_FORMA_PREFIX}-{date.today().year}-002"
        )

    def test_datedue(self):
        assert calc_due_date() == invoice_model.Invoice.CalculateDateDue()

    def test_pro_forma_to_real_invoice(self, create_invoice_object):
        pro_forma = create_invoice_object(
            status=invoice_model.InvoiceStatus.RESERVATION.value
        )
        assert pro_forma["status"] == invoice_model.InvoiceStatus.RESERVATION

        pro_forma.ProFormaToRealInvoice()

        assert pro_forma["status"] == invoice_model.InvoiceStatus.NEW
        assert pro_forma["dateDue"] == calc_due_date()

    def test_invoice_to_paid(self, create_invoice_object):
        inv = create_invoice_object(status=invoice_model.InvoiceStatus.NEW.value)
        assert inv["status"] == invoice_model.InvoiceStatus.NEW

        inv.SetPayed()

        assert inv["status"] == invoice_model.InvoiceStatus.PAID
        assert inv["dateDue"] == calc_due_date()

    def test_pro_forma_to_paid(self, create_invoice_object):
        pro_forma = create_invoice_object(
            status=invoice_model.InvoiceStatus.RESERVATION.value
        )
        assert pro_forma["status"] == invoice_model.InvoiceStatus.RESERVATION

        pro_forma.SetPayed()

        assert pro_forma["sequenceNumber"] == f"test-{date.today().year}-001"
        assert pro_forma["status"] == invoice_model.InvoiceStatus.PAID
        assert pro_forma["dateDue"] == calc_due_date()

    def test_pro_forma_to_canceled(self, create_invoice_object):
        pro_forma = create_invoice_object(
            status=invoice_model.InvoiceStatus.RESERVATION.value
        )
        pro_forma.CancelProFormaInvoice()

        assert pro_forma["status"] == invoice_model.InvoiceStatus.CANCELED
        # Make sure the sequenceNumber is still a pro forma sequenceNumber
        assert (
            pro_forma["sequenceNumber"]
            == f"test-{invoice_model.PRO_FORMA_PREFIX}-{date.today().year}-001"
        )

    def test_real_invoice_to_canceled(self, create_invoice_object):
        inv = create_invoice_object(status=invoice_model.InvoiceStatus.NEW.value)
        with pytest.raises(ValueError) as excinfo:
            inv.CancelProFormaInvoice()
        assert "Only pro forma invoices can be canceled" in str(excinfo)

    def test_add_invoice_products(self, create_invoice_object):
        inv = create_invoice_object(status=invoice_model.InvoiceStatus.NEW.value)
        inv.AddProducts(
            [
                {
                    "name": "dakpan",
                    "price": 10,
                    "sku": 1,
                    "vat_percentage": 100,
                    "quantity": 2,
                },
                {
                    "name": "paneel",
                    "price": 5,
                    "sku": 2,
                    "vat_percentage": 25,
                    "quantity": 10,
                },
            ]
        )
        products = list(inv.products)
        assert len(products) == 2
        assert products[0]["name"] == "dakpan"
        assert products[0]["price"] == 10
        assert products[0]["vat_percentage"] == 100
        assert products[0]["quantity"] == 2

        assert products[1]["name"] == "paneel"
        assert products[1]["price"] == 5
        assert products[1]["vat_percentage"] == 25
        assert products[1]["quantity"] == 10

    def test_invoice_with_products(self, connection, simple_invoice_dict):
        inv = invoice_model.Invoice.Create(connection, simple_invoice_dict)
        products = [
            {
                "name": "dakpan",
                "price": 10,
                "sku": 1,
                "vat_percentage": 100,
                "quantity": 2,
            },
            {
                "name": "paneel",
                "price": 5,
                "sku": 2,
                "vat_percentage": 100,
                "quantity": 10,
            },
        ]
        inv.AddProducts(products)

        result = inv.Totals()
        assert result["total_price_without_vat"] == 70  # 2*10 + 5*10
        assert result["total_price"] == 140  # 2(2*10 + 5*10)
        assert result["total_vat"] == 70

    def test_invoice_with_products_decimal(self, connection, simple_invoice_dict):
        inv = invoice_model.Invoice.Create(connection, simple_invoice_dict)
        products = [
            {
                "name": "dakpan",
                "price": 100.34,
                "sku": 1,
                "vat_percentage": 20,
                "quantity": 10,  # 1204.08
            },
            {
                "name": "paneel",
                "price": 12.25,
                "sku": 2,
                "vat_percentage": 10,
                "quantity": 10,  # 134.75
            },
        ]
        inv.AddProducts(products)

        result = inv.Totals()
        assert result["total_price_without_vat"] == helpers.round_price(
            Decimal(1125.90)
        )
        assert result["total_price"] == helpers.round_price(1338.83)
        assert result["total_vat"] == helpers.round_price(212.93)

    def test_invoice_add_payment(self, connection, create_invoice_object):
        inv = create_invoice_object(status=invoice_model.InvoiceStatus.NEW.value)
        products = [
            {
                "name": "dakpan",
                "price": 25,
                "sku": 1,
                "vat_percentage": 10,
                "quantity": 10,
            },
        ]
        inv.AddProducts(products)
        platform = invoice_model.PaymentPlatform.FromName(connection, "contant")
        inv.AddPayment(platform["ID"], 10)
        platform = invoice_model.PaymentPlatform.FromName(connection, "ideal")
        inv.AddPayment(platform["ID"], 20)
        payments = inv.GetPayments()
        assert len(payments) == 2
        assert payments[0]["platform"]["name"] == "contant"
        assert payments[0]["invoice"]["ID"] == inv["ID"]
        assert payments[0]["amount"] == 10
        assert payments[1]["amount"] == 20
        assert payments[1]["platform"]["name"] == "ideal"

    def test_invoice_add_payment_roundup(self, default_invoice_and_products):
        inv = default_invoice_and_products(status=invoice_model.InvoiceStatus.NEW.value)

        values = [10.01, 20.05, 9.001, 100.006, 9000.005, 1.004]
        for amount in values:
            inv.AddPayment(1, amount)

        payments = inv.GetPayments()
        for i in range(len(values)):
            assert payments[i]["amount"] == helpers.round_price(values[i])

    def test_set_invoice_paid_when_invoice_price_paid(
        self, connection, default_invoice_and_products
    ):
        inv = default_invoice_and_products(status=invoice_model.InvoiceStatus.NEW.value)
        inv.AddPayment(1, 274.99)
        inv = invoice_model.Invoice.FromPrimary(connection, inv["ID"])

        # Status should not be changed as the total amount paid is not yet the amount required.
        assert inv["status"] == invoice_model.InvoiceStatus.NEW

        inv.AddPayment(1, 0.01)

        # Re-fetch from database to see if status has been changed propperly
        inv = invoice_model.Invoice.FromPrimary(connection, inv["ID"])
        assert inv["status"] == invoice_model.InvoiceStatus.PAID

    def test_do_not_uncancel_invoice_when_full_price_paid(
        self, connection, default_invoice_and_products
    ):
        """Ensure that a canceled invoice is not uncanceled if payments are added to it that fullfill the required price.
        This is important because when a invoice is canceled the parts required are refunded to warehouse, if for some reason
        the invoice gets uncanceled the parts can be refunded again leading to duplicate refunds.
        """
        inv = default_invoice_and_products(
            status=invoice_model.InvoiceStatus.RESERVATION.value
        )
        inv.CancelProFormaInvoice()
        inv.AddPayment(1, 1000)
        inv = invoice_model.Invoice.FromPrimary(connection, inv["ID"])
        assert inv["status"] == invoice_model.InvoiceStatus.CANCELED

        with pytest.raises(ValueError):
            inv.ProFormaToRealInvoice()

        with pytest.raises(ValueError):
            inv.SetPayed()

    def test_correct_companydetails_object_on_invoice(
        self, connection, create_invoice_object
    ):
        first_invoice = create_invoice_object(
            status=invoice_model.InvoiceStatus.NEW.value
        )
        # Test that this invoice uses the highest available companydetails, as of now this is ID 1
        assert first_invoice["companyDetails"] == 1

        # Create a new record for companydetails
        invoice_model.Companydetails.Create(
            connection,
            {
                "ID": 2,
                "name": "changed_name",
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
        second_invoice = create_invoice_object(
            status=invoice_model.InvoiceStatus.NEW.value
        )
        # Make sure that the companyDetails that the first invoice references has not changed
        assert first_invoice["companyDetails"] == 1
        assert second_invoice["companyDetails"] == 2
