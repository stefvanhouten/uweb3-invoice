from decimal import Decimal

import pytest
import uweb3

from invoices.common import helpers as common_helpers
from invoices.invoice import model as invoice_model
from invoices.mollie import helpers
from invoices.mollie import model as mollie_model
from tests.fixtures import *  # noqa: F401; pylint: disable=unused-variable


class TestClass:
    def test_mollie_factory(self, connection, mollie_config):
        """Make sure all attributes are set correctly."""
        mollie_gateway = helpers.mollie_factory(connection, mollie_config)
        assert mollie_gateway.apikey == mollie_config["apikey"]
        assert mollie_gateway.redirect_url == mollie_config["redirect_url"]
        assert mollie_gateway.webhook_url == mollie_config["webhook_url"]

    def test_create_db_record(
        self, connection, mollie_config, default_invoice_and_products
    ):
        default_invoice_and_products(status=invoice_model.InvoiceStatus.NEW.value)
        mollie_gateway = helpers.mollie_factory(connection, mollie_config)
        obj = helpers.MollieTransactionObject(
            id=1,
            price=Decimal(10),
            description="description for mollie req",
            reference="reference",
        )
        mollie_gateway._CreateDatabaseRecord(obj)
        record = mollie_model.MollieTransaction.FromPrimary(connection, 1)
        assert obj.id == record["ID"]
        assert obj.price == record["amount"]
        assert obj.id == record["invoice"]["ID"]

    def test_create_mollie_transaction_dict(self, connection, mollie_config):
        mollie_gateway = helpers.mollie_factory(connection, mollie_config)
        obj = helpers.MollieTransactionObject(
            id=1,
            price=Decimal(10),
            description="description for mollie req",
            reference="reference",
        )
        record = mollie_gateway._CreateDatabaseRecord(obj)
        mollie_transaction_obj = mollie_gateway._CreateMollieTransaction(obj, record)

        assert mollie_transaction_obj["amount"] == {
            "currency": "EUR",
            "value": str(obj.price),
        }
        assert mollie_transaction_obj["description"] == obj.description
        assert mollie_transaction_obj["metadata"] == {
            "order": obj.reference
        }  # This will show the invoice that is referenced on mollie page.
        assert (
            mollie_transaction_obj["redirectUrl"]
            == f'{mollie_gateway.redirect_url}/{record["ID"]}'
        )
        assert (
            mollie_transaction_obj["webhookUrl"]
            == f'{mollie_gateway.webhook_url}/{record["ID"]}'
        )

    def test_add_invoice_payment(self, connection, default_invoice_and_products):
        """Check if a mollie request which status was changed to paid also adds a invoice payment."""
        invoice = default_invoice_and_products(
            status=invoice_model.InvoiceStatus.NEW.value
        )
        mollie_model.MollieTransaction.Create(
            connection,
            {
                "ID": 1,
                "invoice": invoice["ID"],
                "amount": 50,
                "status": helpers.MollieStatus.OPEN.value,
                "description": "payment_test",
            },
        )
        original_record = mollie_model.MollieTransaction.FromPrimary(connection, 1)

        record = mollie_model.MollieTransaction.FromPrimary(connection, 1)
        record["status"] = helpers.MollieStatus.PAID.value
        record.Save()

        assert helpers.CheckAndAddPayment(connection, original_record) is True

        payment = invoice_model.InvoicePayment.FromPrimary(connection, 1)
        assert payment["invoice"]["ID"] == invoice["ID"]
        assert payment["amount"] == common_helpers.round_price(50)

    def test_dont_add_payments_state_same(
        self, connection, default_invoice_and_products
    ):
        """Make sure that no invoice payment is added when the mollie status was not changed."""
        invoice = default_invoice_and_products(
            status=invoice_model.InvoiceStatus.NEW.value
        )
        mollie_model.MollieTransaction.Create(
            connection,
            {
                "ID": 1,
                "invoice": invoice["ID"],
                "amount": 50,
                "status": helpers.MollieStatus.OPEN.value,
                "description": "payment_test",
            },
        )

        original_record = mollie_model.MollieTransaction.FromPrimary(connection, 1)
        helpers.CheckAndAddPayment(connection, original_record)
        # Re-fetch record to make sure nothing changed
        refetched_record = mollie_model.MollieTransaction.FromPrimary(connection, 1)

        assert refetched_record["status"] == helpers.MollieStatus.OPEN
        with pytest.raises(uweb3.model.NotExistError):
            invoice_model.InvoicePayment.FromPrimary(connection, 1)
