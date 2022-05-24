from invoices.login import login

urls = [
    ("/", (login.PageMaker, "RequestIndex")),
    ("/login", (login.PageMaker, "HandleLogin"), "POST"),
    ("/login", (login.PageMaker, "RequestLogin")),
    ("/logout", (login.PageMaker, "RequestLogout")),
    ("/setup", (login.PageMaker, "RequestSetup")),
]
