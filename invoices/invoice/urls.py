from invoices.invoice.pagemakers import invoices, payments

urls = [
    ("/invoices", (invoices.PageMaker, "RequestInvoicesPage"), "GET"),
    ("/invoices/create/(.*)", (invoices.PageMaker, "RequestNewInvoicePage"), "GET"),
    (
        "/invoices/create/(.*)",
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
    ("/invoice/payments/mollie/(.*)", (payments.PageMaker, "AddMolliePaymentRequest")),
    ("/invoice/payments/(.*)", (payments.PageMaker, "ManagePayments"), "GET"),
    ("/invoice/payments/(.*)", (payments.PageMaker, "AddPayment"), "POST"),
    ("/invoice/(.*)", (invoices.PageMaker, "RequestInvoiceDetails"), "GET"),
    ("/invoices/cancel", (invoices.PageMaker, "RequestInvoiceCancel"), "POST"),
    ("/invoices/mt940", (invoices.PageMaker, "RequestMt940"), "GET"),
    ("/invoices/upload", (invoices.PageMaker, "RequestUploadMt940"), "POST"),
    ("/pdfinvoice/(.*)", (invoices.PageMaker, "RequestPDFInvoice")),
]
