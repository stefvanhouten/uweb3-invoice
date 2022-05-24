from invoices.settings import settings

urls = [
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
]
