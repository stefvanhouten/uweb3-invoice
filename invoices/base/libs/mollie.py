#!/usr/bin/python
# coding=utf8
"""Underdark uWeb PageMaker Mixins for mollie.com payment/callback purposes."""
from __future__ import with_statement

__author__ = 'Arjen Pander <arjen@underdark.nl>'
__version__ = '0.1'

# Standard modules
from hashlib import sha1
import time
import json
import requests
from enum import Enum
# Package modules
from uweb3 import model

MOLLIE_API = 'https://api.mollie.nl/v2'


class MollieStatus(str, Enum):
  PAID = 'paid'  # https://docs.mollie.com/overview/webhooks#payments-api
  EXPIRED = 'expired'  # These are the states the payments API can send us.
  FAILED = 'failed'
  CANCELED = 'canceled'
  OPEN = 'open'
  PENDING = 'pending'
  REFUNDED = 'refunded'

  CHARGEBACK = 'chargeback'  # These are states that we currently do not use.
  SETTLED = 'settled'
  PARTIALLY_REFUNDED = 'partially_refunded'
  AUTHORIZED = 'authorized'


# ##############################################################################
# Record classes for Mollie integration
#
# Model classes have many methods, this is acceptable
# pylint: disable=R0904
class MollieError(Exception):
  """Raises a mollie specific error"""


class MollieTransactionFailed(MollieError):
  """Raised when a transaction status gets set to failed"""


class MollieTransactionCanceled(MollieError):
  """Raised when a transaction status gets set to canceled"""


class MollieConfigError(MollieError):
  """Raises a config error"""


class MollieTransaction(model.Record):
  """Abstraction for the `MollieTransaction` table."""

  def _PreCreate(self, cursor):
    super(MollieTransaction, self)._PreCreate(cursor)
    self['creationTime'] = time.gmtime()

  def _PreSave(self, cursor):
    super(MollieTransaction, self)._PreSave(cursor)
    self['updateTime'] = time.gmtime()

  def SetState(self, status):
    if self['status'] not in (MollieStatus.OPEN,):
      if self['status'] == MollieStatus.PAID and status == MollieStatus.PAID:
        raise model.PermissionError("Mollie transaction is already paid for.")
      raise model.PermissionError(
          'Cannot update transaction, current state is %r new state %r' %
          (self['status'], status))
    change = (self['status'] != status
             )  # we return true if a change has happened
    self['status'] = status
    self.Save()
    return change

  @classmethod
  def FromDescription(cls, connection, remoteID):
    """Fetches an order object by remoteID"""
    with connection as cursor:
      order = cursor.Execute("""
          SELECT *
          FROM mollieTransaction
          WHERE `description` = "%s"
      """ % remoteID)
    if not order:
      raise model.NotExistError('No order for id %s' % remoteID)
    return cls(connection, order[0])


class MolliePaymentGateway(object):

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
    self.uweb = uweb
    self.apikey = apikey
    self.redirect_url = redirect_url
    self.webhook_url = webhook_url

    # try to fill missing values from the uweb config
    try:
      if not apikey:
        self.apikey = self.uweb.options['mollie']['apikey']

      if not redirect_url:
        self.redirect_url = self.uweb.options['mollie']['redirect_url']

      if not webhook_url:
        self.webhook_url = self.uweb.options['mollie']['webhook_url']
    except KeyError as e:
      raise MollieConfigError(f'''Mollie config error: You need to supply a
          value for: {e.args[0]} in your µweb config under the header mollie''')

  def GetIdealBanks(self):
    directorydata = requests.request(
        'GET',
        f'{MOLLIE_API}/issuers',
        headers={'Authorization': 'Bearer ' + self.apikey})
    banks = json.loads(directorydata.text)
    issuerlist = []
    for issuer in banks['data']:
      issuername = issuer['name']
      issuerid = issuer['id']
      issuerlist.append({'id': issuerid, 'name': issuername})
    return issuerlist

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
        'amount': str(total),
        'status': MollieStatus.OPEN.value,
        'invoice': invoiceID
    }
    transaction = MollieTransaction.Create(self.uweb.connection, transaction)
    mollietransaction = {
        'amount': {
            'currency': 'EUR',
            'value': str(total),
        },
        'description': description,
        'metadata': {
            'order': referenceID
        },
        'redirectUrl': f'{self.redirect_url}/{transaction["ID"]}',
        'webhookUrl':
            f'{self.webhook_url}/{transaction["ID"]}',  # TODO: Add secret key
        'method': 'ideal'
    }
    paymentdata = requests.post(
        f'{MOLLIE_API}/payments',
        headers={'Authorization': 'Bearer ' + self.apikey},
        data=json.dumps(mollietransaction))
    response = json.loads(paymentdata.text)

    if paymentdata.status_code >= 300:
      raise Exception(response['detail'])  # TODO:Better API exceptions

    transaction['description'] = response['id']
    transaction.Save()
    return response['_links']['checkout']

  def _UpdateTransaction(self, transaction, payment):
    """Update the transaction in the database and trigger a succesfull payment
    if the payment has progressed into an authorized state

    returns True if the notification should trigger a payment
    returns False if the notification did not change a transaction into an
      authorized state
    """
    transaction = MollieTransaction.FromDescription(self.uweb.connection,
                                                    transaction)
    changed = transaction.SetState(payment['status'])
    if changed:
      if payment['status'] == MollieStatus.PAID and (
          payment['amount']['value']) == transaction['amount']:
        return True
      if payment['status'] == MollieStatus.FAILED:
        raise MollieTransactionFailed(
            "Mollie payment failed")  # XXX: Should we throw errors here?
      if payment['status'] == MollieStatus.CANCELED:
        raise MollieTransactionCanceled("Mollie payment was canceled")
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
        'url': url,
        'html': '<a href="%s">Klik hier om door te gaan.</a>' % (url)
    }

  def GetPayment(self, transaction):
    data = requests.request('GET',
                            f'{MOLLIE_API}/payments/%s' % transaction,
                            headers={'Authorization': 'Bearer ' + self.apikey})
    payment = json.loads(data.text)
    return payment

  def Notification(self, transaction):
    """Handles a notification from Mollie, either by a server to server call or
    a client returning to our notification url"""
    payment = self.GetPayment(transaction)
    return self._UpdateTransaction(transaction, payment)


# ##############################################################################
# Actual Pagemaker mixin class
#
class MollieMixin(object):
  """Provides the Mollie Framework for uWeb."""

  def _Mollie_HookPaymentReturn(self, transaction):
    """Handles a notification from Mollie, either by a server to server call or
    a client returning to our notification url"""
    if not transaction:
      return self._MollieHandleUnsuccessfulNotification(
          transaction, 'invalid transaction ID')
    Mollie = self.NewMolliePaymentGateway()
    try:
      if Mollie.Notification(transaction):
        # Only when the notification changes the status to paid Mollie.Notification() returns True.
        # In every other scenario it will either return False or raise an exception.
        return self._MollieHandleSuccessfulpayment(transaction)
      return self._MollieHandleSuccessfulNotification(transaction)
    except MollieTransaction.NotExistError:
      return self._MollieHandleUnsuccessfulNotification(
          transaction, 'invalid transaction ID')
    except (MollieTransactionFailed, MollieTransactionCanceled) as e:
      return self._MollieHandleUnsuccessfulNotification(transaction, str(e))
    except (MollieError, model.PermissionError, Exception) as e:
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
