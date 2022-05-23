from invoices.invoice.model import InvoiceStatus
from invoices.mollie import helpers
from invoices.mollie import model as mollie_model
from tests.fixtures import (  # noqa: F401; pylint: disable=unused-variable
    config,
    connection,
    default_invoice_and_products,
)


class TestClass:
    def test_mollie_factory(self, connection, mollie_config):
        mollie_obj = helpers.mollie_factory(connection, mollie_config)
        assert mollie_obj.apikey == mollie_config["apikey"]
        assert mollie_obj.redirect_url == mollie_config["redirect_url"]
        assert mollie_obj.webhook_url == mollie_config["webhook_url"]

    def test_add_invoice_payment(self, connection, default_invoice_and_products):
        invoice = default_invoice_and_products(status=InvoiceStatus.NEW.value)
        mollie_model.MollieTransaction.Create(
            connection,
            {
                "invoice": invoice["ID"],
                "amount": 50,
                "status": helpers.MollieStatus.OPEN.value,
                "description": "payment_test",
            },
        )
