#!/usr/bin/python
# coding=utf8
"""Underdark uWeb PageMaker Mixins for mollie.com payment/callback purposes."""
from __future__ import with_statement

import simplejson

__author__ = 'Arjen Pander <arjen@underdark.nl>'
__version__ = '0.1'

# Standard modules
from hashlib import sha1
import time
import json
import requests

# Package modules
from uweb3 import model


# ##############################################################################
# Record classes for Mollie integration
#
# Model classes have many methods, this is acceptable
# pylint: disable=R0904
class MollieError(Exception):
  """Raises a mollie specific error"""


class MollieTransactionFailed(MollieError):
  """Raised when a transaction status gets set to failed"""


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
    if self['status'] not in ('open'):
      if self['status'] == 'paid' and status == 'paid':
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

  def __init__(self, uweb, test=None, apikey=None, shopid=None, methods=None):
    """Init the mollie object and set its values"""
    self.apikey = apikey
    self.test = test
    self.orderdata = {}
    self.user = None
    self.uweb = uweb
    self.shopid = shopid

    # try to fill missing values from the uweb config
    try:
      if not test:
        self.test = self.uweb.options['mollie']['test'] in ('True', 'true', 1)

      if not apikey:
        self.apikey = self.uweb.options['mollie']['apikey']

      if not shopid:
        self.shopid = self.uweb.options['mollie']['shop_id']

      try:
        self.allowedMethods = ','.join(methods)
      except TypeError:
        if methods:
          self.allowedMethods = methods
        else:
          self.allowedMethods = self.uweb.options['mollie']['methods']
    except (KeyError, key):
      raise MollieConfigError(u'''Mollie config error: You need to supply a
          value for: %s in your µweb config under the header mollie''' % key)

  def GetIdealBanks(self):
    directorydata = requests.request(
        'GET',
        'https://api.mollie.nl/v1/issuers',
        headers={'Authorization': 'Bearer ' + self.apikey})
    banks = json.loads(directorydata.text)
    issuerlist = []
    for issuer in banks['data']:
      issuername = issuer['name']
      issuerid = issuer['id']
      issuerlist.append({'id': issuerid, 'name': issuername})
    return issuerlist

  def CreateTransaction(self, order, user, total, description):
    """Store the transaction into the database and fetch the unique transaction
    id"""
    self.orderdata['description'] = description
    self.user = user
    self.order = order
    transaction = {
        'amount': str(total),
        'status': 'open',
        'description': description,
        'invoice': self.order.get('ID')
    }
    transaction = MollieTransaction.Create(self.uweb.connection, transaction)
    mollietransaction = {
        'amount': {
            'currency': 'EUR',
            'value': str(total),  # TODO: set value
        },
        'description':
            description,
        'metadata': {
            'order': self.order.get('sequenceNumber')
        },
        'redirectUrl':
            f'http://127.0.0.1:8001/api/v1/mollie/redirect/{transaction["ID"]}',
        'method':
            'ideal'
    }
    paymentdata = requests.request(
        'POST',
        'https://api.mollie.nl/v2/payments',
        headers={'Authorization': 'Bearer ' + self.apikey},
        data=json.dumps(mollietransaction))
    response = json.loads(paymentdata.text)
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
    change = transaction.SetState(payment['status'])
    if (change and payment['status'] == 'paid' and
        (payment['amount']['value']) == transaction['amount']):
      return True
    if change and payment['status'] == 'failed':
      raise MollieTransactionFailed("Mollie payment failed")
    return False

  def GetForm(self, order, user, total, description):
    """Stores the current transaction and uses the unique id to return the html
    form containing the redirect and information for mollie
    """
    url = self.CreateTransaction(order, user, total, description)
    return {
        'url': url,
        'html': '<a href="%s">Klik hier om door te gaan.</a>' % (url)
    }

  def GetPayment(self, transaction):
    data = requests.request('GET',
                            'https://api.mollie.nl/v2/payments/%s' %
                            transaction,
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
        return self._MollieHandleSuccessfulpayment(transaction)
      else:
        return self._MollieHandleSuccessfulNotification(transaction)
    except MollieTransaction.NotExistError:
      return self._MollieHandleUnsuccessfulNotification(
          transaction, 'invalid transaction ID')
    except MollieTransactionFailed as e:
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
