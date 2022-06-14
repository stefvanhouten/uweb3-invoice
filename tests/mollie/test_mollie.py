import decimal
import json
from dataclasses import asdict
from decimal import Decimal

import pytest

from invoices.invoice import model as invoice_model
from invoices.mollie import helpers
from invoices.mollie import model as mollie_model
from tests import utils
from tests.fixtures import *  # noqa: F401; pylint: disable=unused-variable


@pytest.fixture(scope="function")
def gateway(mollie_config) -> helpers.MolliePaymentGateway:
    yield helpers.MolliePaymentGateway(
        connection=None,
        apikey=mollie_config["apikey"],
        redirect_url=mollie_config["redirect_url"],
        webhook_url=mollie_config["webhook_url"],
        request_lib=utils.MockRequestMollieApi(),
        transaction_model=utils.MockMollieTransactionModel,
        debug=True,
    )


@pytest.fixture(scope="module")
def mollie_transaction_object() -> helpers.MollieTransactionObject:
    yield helpers.MollieTransactionObject(
        id=1,
        price=Decimal(10.25),
        description="description for mollie req",
        reference="reference",
    )


class TestMollie:
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
            == f'{mollie_gateway.redirect_url}/{record["ID"]}/{record["secret"]}'
        )
        assert (
            mollie_transaction_obj["webhookUrl"]
            == f'{mollie_gateway.webhook_url}/{record["ID"]}/{record["secret"]}'
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
                    "secret": "testsecret",
                },
            )


class TestMolliePaymentGateway:
    def test_create_database_record(
        self,
        gateway: helpers.MolliePaymentGateway,
        mollie_transaction_object: helpers.MollieTransactionObject,
    ):
        db_record = gateway._CreateDatabaseRecord(mollie_transaction_object)
        assert db_record == {
            "ID": 1,
            "status": helpers.MollieStatus.OPEN.value,
            "invoice": 1,
            "amount": mollie_transaction_object.price,
            "secret": db_record["secret"],
        }

    def test_create_transaction_method(
        self,
        gateway: helpers.MolliePaymentGateway,
        mollie_transaction_object: helpers.MollieTransactionObject,
    ):
        db_record = gateway._CreateDatabaseRecord(mollie_transaction_object)
        transaction = gateway._CreateMollieTransaction(
            mollie_transaction_object, db_record
        )
        assert transaction == {
            "amount": {
                "currency": "EUR",
                "value": "10.25",
            },
            "description": "description for mollie req",
            "metadata": {"order": "reference"},
            "redirectUrl": f'{gateway.redirect_url}/{db_record["ID"]}/{db_record["secret"]}',
            "webhookUrl": f'{gateway.webhook_url}/{db_record["ID"]}/{db_record["secret"]}',
            "method": "ideal",
        }

    def test_post_payment_request(self, gateway: helpers.MolliePaymentGateway):
        transaction = {
            "amount": {
                "currency": "EUR",
                "value": "10.25",
            },
            "description": "description for mollie req",
            "metadata": {"order": "reference"},
            "redirectUrl": f"{gateway.redirect_url}/1",
            "webhookUrl": f"{gateway.webhook_url}/1",
            "method": "ideal",
        }
        response = gateway._PostPaymentRequest(transaction)

        assert response.post_data == json.dumps(transaction)
        assert response.post_headers == {"Authorization": "Bearer " + gateway.apikey}

    def test_process_response(self, gateway: helpers.MolliePaymentGateway):
        mock_data = json.dumps({"_links": {"checkout": "checkout_gateway_url"}})
        response = utils.MockResponse(data=mock_data, status_code=200)
        result = gateway._ProcessResponse(response)
        assert result == {"_links": {"checkout": "checkout_gateway_url"}}

    def test_create_transaction(
        self,
        gateway: helpers.MolliePaymentGateway,
        mollie_transaction_object: helpers.MollieTransactionObject,
    ):
        result = gateway.CreateTransaction(mollie_transaction_object)
        assert result == "checkout_gateway_url"

    def test_update_transaction_status(
        self,
        gateway: helpers.MolliePaymentGateway,
    ):
        payment = {
            "status": helpers.MollieStatus.OPEN.value,
            "amount": {"value": decimal.Decimal(10.25)},
        }
        assert False is gateway._UpdateTransaction("description", payment)

    def test_update_transaction_status_paid(
        self,
        gateway: helpers.MolliePaymentGateway,
    ):
        payment = {
            "status": helpers.MollieStatus.PAID.value,
            "amount": {"value": decimal.Decimal(10.25)},
        }

        assert True is gateway._UpdateTransaction("description", payment)

    def test_update_transaction_status_failed(
        self, gateway: helpers.MolliePaymentGateway
    ):
        payment = {
            "status": helpers.MollieStatus.FAILED.value,
            "amount": {"value": decimal.Decimal(10.25)},
        }
        with pytest.raises(mollie_model.MollieTransactionFailed):
            gateway._UpdateTransaction("description", payment)

    def test_update_transaction_status_canceled(
        self, gateway: helpers.MolliePaymentGateway
    ):
        payment = {
            "status": helpers.MollieStatus.CANCELED.value,
            "amount": {"value": decimal.Decimal(10.25)},
        }
        with pytest.raises(mollie_model.MollieTransactionCanceled):
            gateway._UpdateTransaction("description", payment)

    def test_payment_success_price_mismatch(
        self, gateway: helpers.MolliePaymentGateway
    ):
        payment = {
            "status": helpers.MollieStatus.PAID.value,
            "amount": {"value": decimal.Decimal(30)},
        }

        assert True is gateway._UpdateTransaction("description", payment)
