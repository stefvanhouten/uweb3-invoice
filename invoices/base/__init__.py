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
          ('/', 'RequestIndex'),

          # # login / user management
          ('/login', 'HandleLogin', 'POST'),
          ('/login', 'RequestLogin'),
          ('/logout', 'RequestLogout'),
          ('/resetpassword', 'RequestResetPassword'),
          ('/resetpassword/([^/]*)/(.*)', 'RequestResetPassword'),
          ('/setup', 'RequestSetup'),

          # Settings
          ('/settings', 'RequestSettings', 'GET'),
          ('/settings', 'RequestSettingsSave', 'POST'),
          ('/warehousesettings', 'RequestWarehouseSettingsSave', 'POST'),
          ('/molliesettings', 'RequestMollieSettingsSave', 'POST'),

          # Clients
          ('/clients', 'RequestClientsPage', 'GET'),
          ('/clients', 'RequestNewClientPage', 'POST'),
          ('/clients/save', 'RequestSaveClientPage', 'POST'),
          (
              '/client/(.*)',
              'RequestClientPage',
          ),

          # Invoices
          ('/invoices', 'RequestInvoicesPage', 'GET'),
          ('/invoices/new', 'RequestNewInvoicePage', 'GET'),
          ('/invoices/new', 'RequestCreateNewInvoicePage', 'POST'),
          ('/invoices/settopayed', 'RequestInvoicePayed', 'POST'),
          ('/invoices/settonew', 'RequestInvoiceReservationToNew', 'POST'),
          ('/invoice/payments/(.*)', 'ManagePayments', 'GET'),
          ('/invoice/payments/(.*)', 'AddPayment', 'POST'),
          ('/invoice/(.*)', 'RequestInvoiceDetails', 'GET'),
          ('/invoices/cancel', 'RequestInvoiceCancel', 'POST'),
          ('/invoices/mt940', 'RequestMt940', 'GET'),
          ('/invoices/upload', 'RequestUploadMt940', 'POST'),
          ('/pdfinvoice/(.*)', 'RequestPDFInvoice'),

          # API routes
          (f'{basepages.API_VERSION}/client/([0-9]+)', 'RequestClient'),
          (f'{basepages.API_VERSION}/clients', 'RequestClients', 'GET'),
          (f'{basepages.API_VERSION}/clients', 'RequestNewClient', 'POST'),
          (f'{basepages.API_VERSION}/clients/save', 'RequestSaveClient'),

          ## Mollie routes
          (f'{basepages.API_VERSION}/mollie/redirect/(\d+)', 'Mollie_Redirect'),
          (f'{basepages.API_VERSION}/mollie/notification/([\w\-\.]+)',
           '_Mollie_HookPaymentReturn'),

          # Helper files
          ('(/styles/.*)', 'Static'),
          ('(/js/.*)', 'Static'),
          ('(/media/.*)', 'Static'),
          ('(/favicon.ico)', 'Static'),
          ('(/.*)', 'RequestInvalidcommand'),
      ],
      os.path.dirname(__file__))
