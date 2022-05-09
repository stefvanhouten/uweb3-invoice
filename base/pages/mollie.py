#!/usr/bin/python
"""Html/JSON generators for api.coolmoo.se"""

__author__ = 'Jan Klopper <janklopper@underdark.nl>'
__version__ = '0.1'

import decimal
import uweb3
from base.libs import mollie
from base.model import model
from base.decorators import json_error_wrapper


class PageMaker(mollie.MollieMixin):
  """Holds all the html generators for the webapp

  Each page as a separate method.
  """
  # PUBLIC_DIR = 'static'
  # TEMPLATE_DIR = 'templates/api'
  # TEMPLATE_DIR_MAIL = 'templates/mails'

  @uweb3.decorators.ContentType("application/json")
  def RequestPaymentInfoMollieIdeal(self):
    mollie = self.NewMolliePaymentGateway()
    return {'issuers': mollie.GetIdealBanks()}

  @uweb3.decorators.ContentType("application/json")
  @json_error_wrapper
  def RequestPaymentFormMollie(self):
    sequence_number = self.post.get('invoice')
    invoice = model.Invoice.FromSequenceNumber(self.connection, sequence_number)
    molliedata = self.RequestMollie(invoice)
    return molliedata

  def RequestMollie(self, invoice):
    totals = invoice.Totals()['total_price']
    cents = decimal.Decimal('0.01')

    client_email = invoice['client'].get('email')
    price = totals.quantize(cents, decimal.ROUND_HALF_UP)
    description = invoice.get('description')
    # TODO: Secret

    mollie = self.NewMolliePaymentGateway()
    return mollie.GetForm(
        invoice,
        client_email,
        price,  # Mollie expects amounts in euros  # TODO: (Jan) How should the currency be handled? Currently using a Decimal which is then converted to a string for mollie
        description,
    )

  def RequestLabel(self, order, secret):
    return uweb3.Response('pass', content_type='application/pdf')

  def _MollieHandleSuccessfulpayment(self, transaction):
    return 'ok'

  def _MollieHandleSuccessfulNotification(self, transaction):
    return 'ok'

  def _MollieHandleUnsuccessfulNotification(self, transaction, error):
    return 'ok'

  def Mollie_Redirect(self, transactionID, secret):
    transaction = mollie.MollieTransaction.FromPrimary(self.connection,
                                                       int(transactionID))
    redirecturl = '%s?change=%s&transaction=%d' % (
        transaction['order']['shop']['updateurl'], transaction['status'],
        transaction['ID'])
    return uweb3.Redirect(redirecturl, httpcode=301)

  def JsonCorsResponse(self, json):
    return uweb3.Response(json,
                          content_type='application/json',
                          headers={
                              'Access-Control-Allow-Origin': '*',
                              'Cache-Control': 'no-cache, must-revalidate'
                          })
