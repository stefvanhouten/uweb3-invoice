import os

# Third-party modules
import uweb3

from invoices.clients import clients
from invoices.invoice import invoices
from invoices.login import login
from invoices.settings import settings

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
            ("/", (login.PageMaker, "RequestIndex")),
            # # login / user management
            ("/login", (login.PageMaker, "HandleLogin"), "POST"),
            ("/login", (login.PageMaker, "RequestLogin")),
            ("/logout", (login.PageMaker, "RequestLogout")),
            ("/setup", (login.PageMaker, "RequestSetup")),
            # # Settings
            ("/settings", (settings.PageMaker, "RequestSettings"), "GET"),
            ("/settings", (settings.PageMaker, "RequestSettingsSave"), "POST"),
            (
                "/warehousesettings",
                (settings.PageMaker, "RequestWarehouseSettingsSave"),
                "POST",
            ),
            (
                "/molliesettings",
                (settings.PageMaker, "RequestMollieSettingsSave"),
                "POST",
            ),
            # Clients
            ("/clients", (clients.PageMaker, "RequestClientsPage"), "GET"),
            ("/clients", (clients.PageMaker, "RequestNewClientPage"), "POST"),
            (
                "/clients/save",
                (clients.PageMaker, "RequestRequestSaveClientPage"),
                "POST",
            ),
            ("/client/(.*)", (clients.PageMaker, "RequestClientPage")),
            # # Invoices
            ("/invoices", (invoices.PageMaker, "RequestInvoicesPage"), "GET"),
            ("/invoices/new", (invoices.PageMaker, "RequestNewInvoicePage"), "GET"),
            (
                "/invoices/new",
                (invoices.PageMaker, "RequestCreateNewInvoicePage"),
                "POST",
            ),
            (
                "/invoices/settopayed",
                (invoices.PageMaker, "RequestInvoicePayed"),
                "POST",
            ),
            (
                "/invoices/settonew",
                (invoices.PageMaker, "RequestInvoiceReservationToNew"),
                "POST",
            ),
            ("/invoice/payments/(.*)", (invoices.PageMaker, "ManagePayments"), "GET"),
            ("/invoice/payments/(.*)", (invoices.PageMaker, "AddPayment"), "POST"),
            ("/invoice/(.*)", (invoices.PageMaker, "RequestInvoiceDetails"), "GET"),
            ("/invoices/cancel", (invoices.PageMaker, "RequestInvoiceCancel"), "POST"),
            ("/invoices/mt940", (invoices.PageMaker, "RequestMt940"), "GET"),
            ("/invoices/upload", (invoices.PageMaker, "RequestUploadMt940"), "POST"),
            ("/pdfinvoice/(.*)", (invoices.PageMaker, "RequestPDFInvoice")),
            # # API routes
            # (f"{basepages.API_VERSION}/client/([0-9]+)", "RequestClient"),
            # (f"{basepages.API_VERSION}/clients", "RequestClients", "GET"),
            # (f"{basepages.API_VERSION}/clients", "RequestNewClient", "POST"),
            # (f"{basepages.API_VERSION}/clients/save", "RequestSaveClient"),
            # ## Mollie routes
            # (f"{basepages.API_VERSION}/mollie/redirect/(\d+)", "Mollie_Redirect"),
            # (
            #     f"{basepages.API_VERSION}/mollie/notification/([\w\-\.]+)",
            #     "_Mollie_HookPaymentReturn",
            # ),
            # Helper files
            ("(/styles/.*)", "Static"),
            ("(/js/.*)", "Static"),
            ("(/media/.*)", "Static"),
            ("(/favicon.ico)", "Static"),
            ("(/.*)", "RequestInvalidcommand"),
        ],
        os.path.dirname(__file__),
    )
