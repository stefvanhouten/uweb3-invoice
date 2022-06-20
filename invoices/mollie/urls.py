from invoices.mollie import mollie

API_VERSION = "/api/v1"

urls = [
    ## Mollie routes
    (
        f"{API_VERSION}/mollie/redirect/(\d+)/([\w\-\.]+)",
        (mollie.PageMaker, "Mollie_Redirect"),
    ),
    (
        f"{API_VERSION}/mollie/notification/([\w\-\.]+)/([\w\-\.]+)",
        (mollie.PageMaker, "_Mollie_HookPaymentReturn"),
    ),
]
