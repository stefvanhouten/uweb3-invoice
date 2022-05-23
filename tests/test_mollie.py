from invoices.common import helpers as common_helpers
from invoices.invoice import model as invoice_model
from invoices.mollie import helpers
from invoices.mollie import model as mollie_model
from tests.fixtures import *  # noqa: F401; pylint: disable=unused-variable


class TestClass:
    def test_mollie_factory(self, connection, mollie_config):
        mollie_obj = helpers.mollie_factory(connection, mollie_config)
        assert mollie_obj.apikey == mollie_config["apikey"]
        assert mollie_obj.redirect_url == mollie_config["redirect_url"]
        assert mollie_obj.webhook_url == mollie_config["webhook_url"]

    def test_add_invoice_payment(self, connection, default_invoice_and_products):
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
