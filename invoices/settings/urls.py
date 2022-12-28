from invoices.settings import settings

urls = [
    ("/settings", (settings.PageMaker, "RequestSettings"), "GET"),
    ("/settings", (settings.PageMaker, "RequestSettingsSave"), "POST"),
    (
        "/molliesettings",
        (settings.PageMaker, "RequestMollieSettingsSave"),
        "POST",
    ),
]
