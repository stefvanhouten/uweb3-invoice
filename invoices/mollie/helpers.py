#!/usr/bin/python
"""Html/JSON generators for api.coolmoo.se"""

__author__ = "Jan Klopper <janklopper@underdark.nl>"
__version__ = "0.1"

import json
import logging
import os
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

import requests
import uweb3
from uweb3 import model

from invoices.invoice import model as invoice_model
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
    AUTHORIZED = "authorized"


@dataclass
class MollieTransactionObject:
    id: int
    price: Decimal
    description: str
    reference: str


def mollie_factory(connection, config):
    apikey = config["apikey"]
    redirect_url = config["redirect_url"]
    webhook_url = config["webhook_url"]
    return MolliePaymentGateway(
        connection, apikey=apikey, redirect_url=redirect_url, webhook_url=webhook_url
    )


def new_mollie_request(connection, config, obj: MollieTransactionObject):
    mollie = mollie_factory(connection, config)
    return mollie.GetForm(obj)


def get_request_url(mollie_request):
    return mollie_request["url"]["href"]


def CheckAndAddPayment(connection, transaction):
    updated_transaction = mollie_model.MollieTransaction.FromPrimary(
        connection, transaction
    )
    if (
        updated_transaction["status"] == MollieStatus.PAID
        and transaction["status"] != updated_transaction["status"]
    ):
        invoice = invoice_model.Invoice.FromPrimary(connection, transaction["invoice"])
        platformID = invoice_model.PaymentPlatform.FromName(connection, "mollie")["ID"]
        invoice.AddPayment(platformID, transaction["amount"])
        return True
    return False


def _setup_loggers():
    logger = logging.getLogger("payment_logs")
    logger.setLevel(logging.DEBUG)

    error_log_path = os.path.join(os.path.dirname(__file__), "payment_errors.log")
    requests_log_path = os.path.join(os.path.dirname(__file__), "payment_requests.log")

    error_log = logging.FileHandler(error_log_path, encoding="utf-8", delay=False)
    error_log.setLevel(logging.ERROR)

    requests_log = logging.FileHandler(requests_log_path, encoding="utf-8", delay=False)
    requests_log.setLevel(logging.INFO)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    error_log.setFormatter(formatter)
    requests_log.setFormatter(formatter)

    logger.addHandler(error_log)
    logger.addHandler(requests_log)
    return logger


class MolliePaymentGateway:
    def __init__(
        self,
        connection,
        apikey: str,
        redirect_url: str,
        webhook_url: str,
        request_lib=requests,
        transaction_model=mollie_model.MollieTransaction,
        debug=False,
    ):
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

        self.request_lib = request_lib
        self.transaction_model = transaction_model
        self._logger = None
        self.debug = debug

    @property
    def logger(self):
        if not self._logger:
            self._logger = _setup_loggers()

        self._logger.disabled = self.debug
        return self._logger

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
        return self.request_lib.post(
            f"{self.api_url}/payments",
            headers={"Authorization": "Bearer " + self.apikey},
            data=json.dumps(mollietransaction),
        )

    def _CreateDatabaseRecord(self, obj):
        return self.transaction_model.Create(
            self.connection,
            {
                "amount": obj.price,
                "status": MollieStatus.OPEN.value,
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

    def _UpdateTransaction(self, transaction_description, payment):
        """Update the transaction in the database and trigger a succesfull payment
        if the payment has progressed into an authorized state

        returns True if the notification should trigger a payment
        returns False if the notification did not change a transaction into an
        authorized state
        """
        self.logger.info(
            """Updating
                transaction: %s
                with payment: %s
            """,
            transaction_description,
            payment,
        )
        transaction = self.transaction_model.FromDescription(
            self.connection, transaction_description
        )
        state_changed = transaction.SetState(payment["status"])

        if not state_changed:
            return False

        return self._status_change_success(payment, transaction)

    def _status_change_success(self, mollie_payment, record):
        match mollie_payment["status"]:
            case MollieStatus.PAID if (
                str(mollie_payment["amount"]["value"]) != str(record["amount"])
            ):
                self.logger.critical(
                    """Mollie payment was received successfully but there was a mismatch in the values:
                    Mollie payment: %s
                    Stored payment: %s
                    """,
                    mollie_payment,
                    record,
                )
                return True
            case MollieStatus.PAID:
                return True
            case MollieStatus.FAILED:
                raise mollie_model.MollieTransactionFailed("Mollie payment failed")
            case MollieStatus.CANCELED:
                raise mollie_model.MollieTransactionCanceled(
                    "Mollie payment was canceled"
                )
            case _:
                self.logger.critical(
                    "MolliePaymentGateway received an unhandled status %s",
                    mollie_payment,
                )
                raise mollie_model.MollieError("Unhandled status was passed")

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
        data = self.request_lib.request(
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
