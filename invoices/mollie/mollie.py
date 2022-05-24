#!/usr/bin/python
"""Html/JSON generators for api.coolmoo.se"""

__author__ = "Jan Klopper <janklopper@underdark.nl>"
__version__ = "0.1"

import uweb3

from invoices import basepages
from invoices.common import decorators
from invoices.mollie import helpers
from invoices.mollie import model as mollie_model


class PageMaker(basepages.PageMaker, helpers.MollieMixin):
    def NewMolliePaymentGateway(self):
        return helpers.mollie_factory(self.connection, self.options["mollie"])

    def _Mollie_HookPaymentReturn(self, transaction):
        """This is the webhook that mollie calls when that transaction is updated."""
        # This route is used to receive updates from mollie about the transaction status.
        try:
            transaction = mollie_model.MollieTransaction.FromPrimary(
                self.connection, transaction
            )
            super()._Mollie_HookPaymentReturn(transaction["description"])
            helpers.CheckAndAddPayment(self.connection, transaction)
        except (uweb3.model.NotExistError, Exception) as error:
            # Prevent leaking data about transactions.
            uweb3.logging.error(
                f"Error triggered while processing mollie notification for transaction: {transaction} {error}"
            )
        finally:
            return "ok"

    def _MollieHandleSuccessfulpayment(self, transaction):
        return "ok"

    def _MollieHandleSuccessfulNotification(self, transaction):
        return "ok"

    def _MollieHandleUnsuccessfulNotification(self, transaction, error):
        return "ok"

    @decorators.NotExistsErrorCatcher
    def Mollie_Redirect(self, transactionID):
        # TODO: Add logic to check if payment was actually done successfully
        transaction = mollie_model.MollieTransaction.FromPrimary(
            self.connection, transactionID
        )
        mollie_gateway = self.NewMolliePaymentGateway()
        status = mollie_gateway.GetPayment(transaction["description"])["status"]
        if status == helpers.MollieStatus.PAID:
            return self._PaymentOk()
        else:
            return self._PaymentFailed()

    @uweb3.decorators.TemplateParser("mollie/payment_success.html")
    def _PaymentOk(self):
        return

    @uweb3.decorators.TemplateParser("mollie/payment_failed.html")
    def _PaymentFailed(self):
        return
