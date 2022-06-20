import pytest
import uweb3

from invoices.common import helpers as common_helpers
from invoices.invoice import model as invoice_model
from invoices.mollie import helpers
from invoices.mollie import model as mollie_model
from tests.fixtures import *  # noqa: F401; pylint: disable=unused-variable


class TestClass:
    def test_SetState_paid_transaction(self, connection):
        transaction = mollie_model.MollieTransaction.Create(
            connection,
            {
                "ID": 1,
                "invoice": 1,
                "amount": 50,
                "status": helpers.MollieStatus.PAID.value,
                "description": "payment_test",
                "secret": "testsecret",
            },
        )
        # Prevent changing record state that is already set to paid
        with pytest.raises(uweb3.model.PermissionError):
            transaction.SetState(helpers.MollieStatus.OPEN.value)
            transaction.SetState(helpers.MollieStatus.CANCELED.value)

    def test_setState(self, connection):
        transaction = mollie_model.MollieTransaction.Create(
            connection,
            {
                "ID": 1,
                "invoice": 1,
                "amount": 50,
                "status": helpers.MollieStatus.CANCELED.value,
                "description": "payment_test",
                "secret": "testsecret",
            },
        )

        # Do not allow making changes to status when oldstatus and new status are the same
        # This prevents the record updatetime from being updated for no valid reason
        with pytest.raises(uweb3.model.PermissionError) as excinfo:
            transaction.SetState(helpers.MollieStatus.CANCELED.value)
        assert True is str(excinfo.value).startswith(
            "Cannot update transaction, current state is"
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
                "secret": "testsecret",
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
                "secret": "testsecret",
            },
        )

        original_record = mollie_model.MollieTransaction.FromPrimary(connection, 1)
        helpers.CheckAndAddPayment(connection, original_record)
        # Re-fetch record to make sure nothing changed
        refetched_record = mollie_model.MollieTransaction.FromPrimary(connection, 1)

        assert refetched_record["status"] == helpers.MollieStatus.OPEN
        with pytest.raises(uweb3.model.NotExistError):
            invoice_model.InvoicePayment.FromPrimary(connection, 1)
