#!/usr/bin/python
"""Html/JSON generators for api.coolmoo.se"""

__author__ = "Jan Klopper <janklopper@underdark.nl>"
__version__ = "0.1"

import json
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

import requests
from uweb3 import model

from invoices.mollie import model as mollie_model


class MollieStatus(str, Enum):
    PAID = "paid"  # https://docs.mollie.com/overview/webhooks#payments-api
    EXPIRED = "expired"  # These are the states the payments API can send us.
    FAILED = "failed"
    CANCELED = "canceled"
    OPEN = "open"
    PENDING = "pending"
    REFUNDED = "refunded"

    CHARGEBACK = "chargeback"  # These are states that we currently do not use.
    SETTLED = "settled"
    PARTIALLY_REFUNDED = "partially_refunded"
    AUTHORIZED = "authorized"


@dataclass
class MollieTransactionObject:
    id: str
    price: Decimal
    description: str
    reference: str


class MolliePaymentGateway:
    def __init__(self, connection, apikey, redirect_url, webhook_url):
        """Init the mollie object and set its values

        Arguments:
            % apikey: str
                The apikey used to query mollie
            % redirect_url: str
                The URL your customer will be redirected to after the payment process.
            % webhook_url: str
                Set the webhook URL, where we will send payment status updates to.
        """
        if not apikey or not redirect_url or not webhook_url:
            raise mollie_model.MollieConfigError(
                "Missing required mollie API setup field."
            )

        self.api_url = "https://api.mollie.nl/v2"
        self.connection = connection
        self.apikey = apikey
        self.redirect_url = redirect_url
        self.webhook_url = webhook_url

    def CreateTransaction(self, obj: MollieTransactionObject):
        """Store the transaction into the database and fetch the unique transaction id"""
        transaction = self._CreateDatabaseRecord(obj)
        mollie_transaction = self._CreateMollieTransaction(obj, transaction)
        payment_data = self._PostPaymentRequest(mollie_transaction)
        response = self._ProcessResponse(payment_data)

        transaction["description"] = response["id"]
        transaction.Save()
        return response["_links"]["checkout"]

    def _ProcessResponse(self, paymentdata):
        response = json.loads(paymentdata.text)
        if paymentdata.status_code >= 300:
            raise Exception(response["detail"])  # TODO:Better API exceptions
        return response

    def _PostPaymentRequest(self, mollietransaction):
        return requests.post(
            f"{self.api_url}/payments",
            headers={"Authorization": "Bearer " + self.apikey},
            data=json.dumps(mollietransaction),
        )

    def _CreateDatabaseRecord(self, obj):
        return mollie_model.MollieTransaction.Create(
            self.connection,
            {
                "amount": obj.price,
                "status": mollie_model.MollieStatus.OPEN.value,
                "invoice": obj.id,
            },
        )

    def _CreateMollieTransaction(self, obj, transaction):
        return {
            "amount": {
                "currency": "EUR",
                "value": str(obj.price),
            },
            "description": obj.description,
            "metadata": {"order": obj.reference},
            "redirectUrl": f'{self.redirect_url}/{transaction["ID"]}',
            "webhookUrl": f'{self.webhook_url}/{transaction["ID"]}',
            "method": "ideal",
        }

    def _UpdateTransaction(self, transaction, payment):
        """Update the transaction in the database and trigger a succesfull payment
        if the payment has progressed into an authorized state

        returns True if the notification should trigger a payment
        returns False if the notification did not change a transaction into an
        authorized state
        """
        transaction = mollie_model.MollieTransaction.FromDescription(
            self.connection, transaction
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

    def GetForm(self, obj: MollieTransactionObject):
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
        url = self.CreateTransaction(obj)
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
        ) as error:
            return self._MollieHandleUnsuccessfulNotification(transaction, str(error))
        except (mollie_model.MollieError, model.PermissionError, Exception) as error:
            return self._MollieHandleUnsuccessfulNotification(transaction, str(error))

    def NewMolliePaymentGateway(self):
        """Overwrite this to implement an MolliePaymentGateway instance with non
        config (eg, argument) options"""
        raise NotImplementedError

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
