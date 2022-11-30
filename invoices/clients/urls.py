from invoices.clients.pagemakers import clients

urls = [
    ("/clients", (clients.PageMaker, "RequestClientsPage"), "GET"),
    ("/clients", (clients.PageMaker, "RequestNewClientPage"), "POST"),
    ("/client/(\d+)", (clients.PageMaker, "RequestClientPage"), "GET"),
    ("/client/(\d+)", (clients.PageMaker, "RequestSaveClientPage"), "POST"),
]
