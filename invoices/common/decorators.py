import os
from http import HTTPStatus

import uweb3
from marshmallow import ValidationError

from invoices import basepages
from invoices.common import helpers


def NotExistsErrorCatcher(f):
    """Decorator to return a 404 if a NotExistError exception was returned."""

    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except uweb3.model.NotExistError as error:
            return args[0].RequestInvalidcommand(error=error)

    return wrapper


def json_error_wrapper(func):
    def wrapper_schema_validation(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except uweb3.model.NotExistError as msg:
            return uweb3.Response(
                {
                    "error": True,
                    "errors": msg.args,
                    "http_status": HTTPStatus.NOT_FOUND,
                },
                httpcode=HTTPStatus.NOT_FOUND,
            )
        except ValueError as e:
            return uweb3.Response(
                {
                    "error": True,
                    "errors": e.args,
                    "http_status": HTTPStatus.NOT_FOUND,
                },
                httpcode=HTTPStatus.NOT_FOUND,
            )
        except ValidationError as error:
            return uweb3.Response(
                {
                    "error": True,
                    "errors": error.messages,
                    "http_status": HTTPStatus.BAD_REQUEST,
                },
                httpcode=HTTPStatus.BAD_REQUEST,
            )
        except Exception as err:
            print(err)
            return uweb3.Response(
                {
                    "error": True,
                    "errors": ["Something went wrong!"],
                    "http_status": HTTPStatus.INTERNAL_SERVER_ERROR,
                },
                httpcode=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    return wrapper_schema_validation


def loggedin(f):
    """Decorator that checks if the user requesting the page is logged in based on set cookie."""

    def wrapper(pagemaker, *args, **kwargs):
        if not pagemaker.user:
            return uweb3.Redirect("/login", httpcode=303)
        return f(pagemaker, *args, **kwargs)

    return wrapper


def ParseView(f):
    def Wrapper(pagemaker: basepages.PageMaker, *args, **kwargs):
        view = f(pagemaker, *args, **kwargs) or {}
        if isinstance(view, helpers.BaseView):
            return pagemaker.parser.Parse(
                os.path.join(pagemaker.TEMPLATE_DIR, view.template), **view.asdict()
            )
        return view

    return Wrapper
