from invoices.clients import clients

urls = [
    (
        "/clients",
        (
            clients.PageMaker,
            "RequestClientsPage",
        ),
        "GET",
    ),
    (
        "/clients",
        (
            clients.PageMaker,
            "RequestNewClientPage",
        ),
        "POST",
    ),
    (
        "/clients/save",
        (
            clients.PageMaker,
            "RequestSaveClientPage",
        ),
        "POST",
    ),
    (
        "/client/(.*)",
        (
            clients.PageMaker,
            "RequestClientPage",
        ),
    ),
]
