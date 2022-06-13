from invoices.invoice import helpers


def WarehouseRequestWrapper(f):
    def wrapper(pagemaker, *args, **kwargs):
        try:
            return f(pagemaker, *args, **kwargs)
        except helpers.WarehouseException as exc:
            return pagemaker.WarehouseError(
                error=exc.args[0], api_status_code=exc.status_code
            )

    return wrapper
