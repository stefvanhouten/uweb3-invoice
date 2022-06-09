from invoices.mollie import mollie

API_VERSION = "/api/v1"

urls = [
    (f"{API_VERSION}/client/([0-9]+)", (mollie.PageMaker, "RequestClient")),
    (f"{API_VERSION}/clients", (mollie.PageMaker, "RequestClients"), "GET"),
    (f"{API_VERSION}/clients", (mollie.PageMaker, "RequestNewClient"), "POST"),
    (f"{API_VERSION}/clients/save", (mollie.PageMaker, "RequestSaveClient")),
    ## Mollie routes
    (f"{API_VERSION}/mollie/redirect/(\d+)", (mollie.PageMaker, "Mollie_Redirect")),
    (
        f"{API_VERSION}/mollie/notification/([\w\-\.]+)",
        (mollie.PageMaker, "_Mollie_HookPaymentReturn"),
    ),
]
