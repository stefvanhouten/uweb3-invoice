"""A uWeb3 warehousing inventory software."""
import os
# Third-party modules
import uweb3

# Application
from . import basepages


def main():
  """Creates a uWeb3 application.

  The application is created from the following components:

  - The presenter class (PageMaker) which implements the request handlers.
  - The routes iterable, where each 2-tuple defines a url-pattern and the
    name of a presenter method which should handle it.
  - The execution path, internally used to find templates etc.
  """
  return uweb3.uWeb(
      basepages.PageMaker,
      [
          ('/invoice/(.*)', 'RequestInvoiceDetails', 'GET'),
          # API routes
          ('/api/v1/invoices', 'RequestInvoices', 'GET'),
          ('/api/v1/invoices', 'RequestNewInvoice', 'POST'),
          ('/invoice/(.*)', 'RequestInvoiceDetails', 'GET'),
          ('/api/v1/invoice/(.*)', 'RequestInvoiceDetailsJSON', 'GET'),
          ('/api/v1/client/([0-9]+)', 'RequestClient'),
          ('/api/v1/clients', 'RequestClients', 'GET'),
          ('/api/v1/clients', 'RequestNewClient', 'POST'),
          ('/api/v1/clients/save', 'RequestSaveClient', 'POST'),
          ('(/.*)', 'FourOhFour')
      ],
      os.path.dirname(__file__))
