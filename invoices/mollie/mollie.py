#!/usr/bin/python
"""Html/JSON generators for api.coolmoo.se"""

__author__ = "Jan Klopper <janklopper@underdark.nl>"
__version__ = "0.1"

import json

import requests
import uweb3
from uweb3 import model

from invoices import basepages
from invoices.common import decorators
from invoices.invoice import model as invoice_model
from invoices.mollie import model as mollie_model


class MolliePaymentGateway:
    def __init__(self, uweb, apikey=None, redirect_url=None, webhook_url=None):
        """Init the mollie object and set its values

        Arguments:
          % apikey: str
            The apikey used to query mollie
          % redirect_url: str
            The URL your customer will be redirected to after the payment process.
          % webhook_url: str
            Set the webhook URL, where we will send payment status updates to.
        """
        self.api_url = "https://api.mollie.nl/v2"
        self.uweb = uweb
        self.apikey = apikey
        self.redirect_url = redirect_url
        self.webhook_url = webhook_url

        # try to fill missing values from the uweb config
        try:
            if not apikey:
                self.apikey = self.uweb.options["mollie"]["apikey"]

            if not redirect_url:
                self.redirect_url = self.uweb.options["mollie"]["redirect_url"]

            if not webhook_url:
                self.webhook_url = self.uweb.options["mollie"]["webhook_url"]
        except KeyError as e:
            raise mollie_model.MollieConfigError(
                f"""Mollie config error: You need to supply a
          value for: {e.args[0]} in your µweb config under the header mollie"""
            )

    def CreateTransaction(self, invoiceID, total, description, referenceID):
        """Store the transaction into the database and fetch the unique transaction
        id

        Arguments:
          @ invoiceID: int
            The primary key by which an invoice is identified.
          @ total: Decimal|str
            Value representing the currency amount that has to be paid.
          @ description: str
            The description from the invoice, this will be placed in mollie details.
          @ referenceID: char(11)
            The sequenceNumber used to identify an invoice with
        """
        transaction = {
            "amount": str(total),
            "status": mollie_model.MollieStatus.OPEN.value,
            "invoice": invoiceID,
        }
        transaction = mollie_model.MollieTransaction.Create(
            self.uweb.connection, transaction
        )
        mollietransaction = {
            "amount": {
                "currency": "EUR",
                "value": str(total),
            },
            "description": description,
            "metadata": {"order": referenceID},
            "redirectUrl": f'{self.redirect_url}/{transaction["ID"]}',
            "webhookUrl": f'{self.webhook_url}/{transaction["ID"]}',  # TODO: Add secret key
            "method": "ideal",
        }
        paymentdata = requests.post(
            f"{self.api_url}/paymentpayments",
            headers={"Authorization": "Bearer " + self.apikey},
            data=json.dumps(mollietransaction),
        )
        response = json.loads(paymentdata.text)

        if paymentdata.status_code >= 300:
            raise Exception(response["detail"])  # TODO:Better API exceptions

        transaction["description"] = response["id"]
        transaction.Save()
        return response["_links"]["checkout"]

    def _UpdateTransaction(self, transaction, payment):
        """Update the transaction in the database and trigger a succesfull payment
        if the payment has progressed into an authorized state

        returns True if the notification should trigger a payment
        returns False if the notification did not change a transaction into an
          authorized state
        """
        transaction = mollie_model.MollieTransaction.FromDescription(
            self.uweb.connection, transaction
        )
        changed = transaction.SetState(payment["status"])
        if changed:
            if payment["status"] == mollie_model.MollieStatus.PAID and (
                payment["amount"]["value"]
            ) == str(transaction["amount"]):
                return True
            if payment["status"] == mollie_model.MollieStatus.FAILED:
                raise mollie_model.MollieTransactionFailed(
                    "Mollie payment failed"
                )  # XXX: Should we throw errors here?
            if payment["status"] == mollie_model.MollieStatus.CANCELED:
                raise mollie_model.MollieTransactionCanceled(
                    "Mollie payment was canceled"
                )
        return False

    def GetForm(self, invoiceID, total, description, referenceID):
        """Stores the current transaction and uses the unique id to return the html
        form containing the redirect and information for mollie

        Arguments:
          @ invoiceID: int
            The primary key by which an invoice is identified.
          @ total: Decimal|str
            Value representing the currency amount that has to be paid.
          @ description: str
            The description from the invoice, this will be placed in mollie details.
          @ referenceID: char(11)
            The sequenceNumber used to identify an invoice with
        """
        url = self.CreateTransaction(invoiceID, total, description, referenceID)
        return {
            "url": url,
            "html": '<a href="%s">Klik hier om door te gaan.</a>' % (url),
        }

    def GetPayment(self, transaction):
        data = requests.request(
            "GET",
            f"{self.api_url}/payments/%s" % transaction,
            headers={"Authorization": "Bearer " + self.apikey},
        )
        payment = json.loads(data.text)
        return payment

    def Notification(self, transaction):
        """Handles a notification from Mollie, either by a server to server call or
        a client returning to our notification url"""
        payment = self.GetPayment(transaction)
        return self._UpdateTransaction(transaction, payment)


class MollieMixin:
    """Provides the Mollie Framework for uWeb."""

    def _Mollie_HookPaymentReturn(self, transaction):
        """Handles a notification from Mollie, either by a server to server call or
        a client returning to our notification url"""
        if not transaction:
            return self._MollieHandleUnsuccessfulNotification(
                transaction, "invalid transaction ID"
            )
        Mollie = self.NewMolliePaymentGateway()
        try:
            if Mollie.Notification(transaction):
                # Only when the notification changes the status to paid Mollie.Notification() returns True.
                # In every other scenario it will either return False or raise an exception.
                return self._MollieHandleSuccessfulpayment(transaction)
            return self._MollieHandleSuccessfulNotification(transaction)
        except mollie_model.MollieTransaction.NotExistError:
            return self._MollieHandleUnsuccessfulNotification(
                transaction, "invalid transaction ID"
            )
        except (
            mollie_model.MollieTransactionFailed,
            mollie_model.MollieTransactionCanceled,
        ) as e:
            return self._MollieHandleUnsuccessfulNotification(transaction, str(e))
        except (mollie_model.MollieError, model.PermissionError, Exception) as e:
            return self._MollieHandleUnsuccessfulNotification(transaction, str(e))

    def NewMolliePaymentGateway(self):
        """Overwrite this to implement an MolliePaymentGateway instance with non
        config (eg, argument) options, by default this returns an instance that uses
        all config flags"""
        return MolliePaymentGateway(self)

    def _MollieHandleSuccessfulpayment(self, transaction):
        """This method gets called when the transaction has been updated
        succesfully to an authorized state, this happens only once for every
        succesfull transaction"""
        raise NotImplementedError

    def _MollieHandleSuccessfulNotification(self, transaction):
        """This method gets called when the transaction has been updated
        succesfully to any state which does not trigger an _HandleSuccessfullpayment
        call instead"""
        raise NotImplementedError

    def _MollieHandleUnsuccessfulNotification(self, transaction, error):
        """This method gets called when the transaction could not be updated
        because the signature was wrong or some other error occured"""
        raise NotImplementedError


class PageMaker(basepages.PageMaker, MollieMixin):
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

    @decorators.NotExistsErrorCatcher
    @uweb3.decorators.TemplateParser("mollie/payment_ok.html")
    def Mollie_Redirect(self, transactionID):
        return
