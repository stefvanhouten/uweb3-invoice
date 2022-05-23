#!/usr/bin/python
"""Html/JSON generators for api.coolmoo.se"""

__author__ = "Jan Klopper <janklopper@underdark.nl>"
__version__ = "0.1"

import uweb3

from invoices import basepages
from invoices.invoice import model as invoice_model
from invoices.mollie import helpers
from invoices.mollie import model as mollie_model


def mollie_factory(connection, config):
    apikey = config["apikey"]
    redirect_url = config["redirect_url"]
    webhook_url = config["webhook_url"]
    return helpers.MolliePaymentGateway(
        connection, apikey=apikey, redirect_url=redirect_url, webhook_url=webhook_url
    )


def new_mollie_request(connection, config, obj: helpers.MollieTransactionObject):
    mollie = mollie_factory(connection, config)
    return mollie.GetForm(obj)


def get_request_url(mollie_request):
    return mollie_request["url"]["href"]


class PageMaker(basepages.PageMaker, helpers.MollieMixin):
    def NewMolliePaymentGateway(self):
        return mollie_factory(self.connection, self.options["mollie"])

    def _Mollie_HookPaymentReturn(self, transaction):
        """This is the webhook that mollie calls when that transaction is updated."""
        # This route is used to receive updates from mollie about the transaction status.
        try:
            transaction = mollie_model.MollieTransaction.FromPrimary(
                self.connection, transaction
            )
            super()._Mollie_HookPaymentReturn(transaction["description"])

            updated_transaction = mollie_model.MollieTransaction.FromPrimary(
                self.connection, transaction
            )

            #  If the updated transactions status is paid and the status of the transaction was changed since the beginning of this route
            if (
                updated_transaction["status"] == mollie_model.MollieStatus.PAID
                and transaction["status"] != updated_transaction["status"]
            ):
                invoice = invoice_model.Invoice.FromPrimary(
                    self.connection, transaction["invoice"]
                )
                platformID = invoice_model.PaymentPlatform.FromName(
                    self.connection, "mollie"
                )["ID"]
                invoice.AddPayment(platformID, transaction["amount"])
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

    @uweb3.decorators.TemplateParser("mollie/payment_ok.html")
    def Mollie_Redirect(self, transactionID):
        # TODO: Add logic to check if payment was actually done successfully
        return
