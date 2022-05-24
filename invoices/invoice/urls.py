from invoices.invoice import invoices

urls = [
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
    ("/invoice/payments/mollie/(.*)", (invoices.PageMaker, "AddMolliePaymentRequest")),
    ("/invoice/payments/(.*)", (invoices.PageMaker, "ManagePayments"), "GET"),
    ("/invoice/payments/(.*)", (invoices.PageMaker, "AddPayment"), "POST"),
    ("/invoice/(.*)", (invoices.PageMaker, "RequestInvoiceDetails"), "GET"),
    ("/invoices/cancel", (invoices.PageMaker, "RequestInvoiceCancel"), "POST"),
    ("/invoices/mt940", (invoices.PageMaker, "RequestMt940"), "GET"),
    ("/invoices/upload", (invoices.PageMaker, "RequestUploadMt940"), "POST"),
    ("/pdfinvoice/(.*)", (invoices.PageMaker, "RequestPDFInvoice")),
]
