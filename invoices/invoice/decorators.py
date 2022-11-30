from http import HTTPStatus

import requests


def WarehouseRequestWrapper(f):
    def wrapper(pagemaker, *args, **kwargs):
        try:
            return f(pagemaker, *args, **kwargs)
        except requests.exceptions.Timeout as exc:
            pagemaker.logger.exception(exc)
            return pagemaker.WarehouseError(
                error="Connection to the warehouse API timed out.",
                api_status_code=HTTPStatus.REQUEST_TIMEOUT,
            )
        except requests.exceptions.ConnectionError as exc:
            pagemaker.logger.exception(exc)
            return pagemaker.WarehouseError(
                error="An error occured while trying to connect to the warehouse API.",
                api_status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            )
        except requests.exceptions.HTTPError as exc:
            pagemaker.logger.debug(exc.response.json())
            return pagemaker.WarehouseError(
                error=exc.response.json(), api_status_code=HTTPStatus.CONFLICT
            )
        except requests.exceptions.RequestException as exc:
            pagemaker.logger.exception(exc)
            return pagemaker.WarehouseError(
                error="An error occured while communicating with the warehouse API.",
                api_status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            )

    return wrapper
