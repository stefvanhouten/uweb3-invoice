#!/usr/bin/python
"""Html/JSON generators for api.coolmoo.se"""

__author__ = "Jan Klopper <janklopper@underdark.nl>"
__version__ = "0.1"

import uweb3

from invoices.base import decorators, model
from invoices.base.libs import mollie


class PageMaker(mollie.MollieMixin):
    """Holds all the html generators for the webapp

    Each page as a separate method.
    """

    def RequestMollie(self, invoiceID, price, description, reference):
        """
        Arguments:
          invoiceID: int
            The ID of the invoice
          price: Decimal
            The amount that we want to be on the mollie request
          description:
            The description
          reference: str
            The invoice sequenceNumber. We use this for processing #TODO: fix description
        """

        mollie = self.NewMolliePaymentGateway()
        return mollie.GetForm(invoiceID, price, description, reference)

    def _Mollie_HookPaymentReturn(self, transaction):
        """This is the webhook that mollie calls when that transaction is updated."""
        # This route is used to receive updates from mollie about the transaction status.
        try:
            transaction = mollie.MollieTransaction.FromPrimary(
                self.connection, transaction
            )
            super()._Mollie_HookPaymentReturn(transaction["description"])

            updated_transaction = mollie.MollieTransaction.FromPrimary(
                self.connection, transaction
            )

            #  If the updated transactions status is paid and the status of the transaction was changed since the beginning of this route
            if (
                updated_transaction["status"] == mollie.MollieStatus.PAID
                and transaction["status"] != updated_transaction["status"]
            ):
                invoice = model.Invoice.FromPrimary(
                    self.connection, transaction["invoice"]
                )
                platformID = model.PaymentPlatform.FromName(self.connection, "mollie")[
                    "ID"
                ]
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

    @decorators.NotExistsErrorCatcher
    @uweb3.decorators.TemplateParser("mollie/payment_ok.html")
    def Mollie_Redirect(self, transactionID):
        return
