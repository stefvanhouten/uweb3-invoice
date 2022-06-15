#!/usr/bin/python
"""Html/JSON generators for api.coolmoo.se"""

__author__ = "Jan Klopper <janklopper@underdark.nl>"
__version__ = "0.1"

import os

import uweb3

from invoices import basepages
from invoices.common.decorators import NotExistsErrorCatcher
from invoices.mollie import helpers
from invoices.mollie import model as mollie_model


class PageMaker(basepages.PageMaker, helpers.MollieMixin):
    TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

    def NewMolliePaymentGateway(self):
        return helpers.mollie_factory(self.connection, self.options["mollie"])

    @NotExistsErrorCatcher
    def Mollie_Redirect(self, transactionID, secret):
        # TODO: Add logic to check if payment was actually done successfully
        transaction = mollie_model.MollieTransaction.FromPrimary(
            self.connection, transactionID
        )
        title = "Bestelling niet gevonden"
        message = "Uw bestelling kon niet gevonden worden."

        if transaction["secret"] != secret:
            return self.parser.Parse(
                "payment_status.html", title=title, message=message
            )

        mollie_gateway = self.NewMolliePaymentGateway()
        status = mollie_gateway.get_payment(transaction["description"])["status"]

        match status:
            case helpers.MollieStatus.OPEN:
                title = "Deze bestelling is nog niet betaald."
                message = "Als u zojuist betaald heeft dan verzoeken wij u contact op te nemen met ons."
            case helpers.MollieStatus.PAID:
                title = "Betaling gelukt!"
                message = "Bedankt voor uw bestelling."
            case helpers.MollieStatus.CANCELED:
                title = "Uw betaling is geannuleerd."
                message = ""
            case helpers.MollieStatus.FAILED:
                title = "Betaling mislukt"
                message = "Er is iets mis gegaan tijdens het verwerken van uw betaling."
            case helpers.MollieStatus.EXPIRED:
                title = "Betaling verlopen"
                message = "Het betalingsverzoek is verlopen, als u alsnog wilt betalen dan moet u een nieuw betalingsverzoek aanvragen."
            case _:
                title = "Helaas is er iets mis gegaan."
                message = f"De status van uw betaling is: {status}"

        return self.parser.Parse("payment_status.html", title=title, message=message)

    def _Mollie_HookPaymentReturn(self, transaction, secret):
        """This is the webhook that mollie calls when that transaction is updated."""
        # This route is used to receive updates from mollie about the transaction status.
        try:
            transaction = mollie_model.MollieTransaction.FromPrimary(
                self.connection, transaction
            )

            if transaction["secret"] != secret:
                return "ok"

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
