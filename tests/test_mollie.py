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

    def test_mollie_update_transaction_paid(self, mollie_gateway):
        payment = {
            "status": helpers.MollieStatus.PAID.value,
            "amount": {
                "value": "50.00",  # Mollie sends a string value back
            },
        }
        assert True is mollie_gateway._UpdateTransaction("payment_test", payment)

    def test_mollie_update_transaction_failed(self, mollie_gateway):
        payment = {
            "status": helpers.MollieStatus.FAILED.value,
            "amount": {
                "value": "50.00",  # Mollie sends a string value back
            },
        }
        with pytest.raises(mollie_model.MollieTransactionFailed):
            mollie_gateway._UpdateTransaction("payment_test", payment)

    def test_mollie_update_transaction_canceled(self, mollie_gateway):
        payment = {
            "status": helpers.MollieStatus.CANCELED.value,
            "amount": {
                "value": "50.00",  # Mollie sends a string value back
            },
        }
        with pytest.raises(mollie_model.MollieTransactionCanceled):
            mollie_gateway._UpdateTransaction("payment_test", payment)

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

    def test_create_all_mollie_statuses(self, connection):
        """Test if all MollieStatus enum values are allowed in database"""
        for status in helpers.MollieStatus:
            mollie_model.MollieTransaction.Create(
                connection,
                {
                    "invoice": 1,
                    "amount": 50,
                    "status": status.value,
                    "description": "payment_test",
                },
            )
