import json
import os
import time
from http import HTTPStatus

import uweb3
from loguru import logger
from uweb3plugins.core.pagemakers import restricted

import invoices.login.model as login_model


def centround(x):
    try:
        return "%.2f" % x
    except Exception:
        return None


class PageMaker(
    restricted.RestrictedDebuggingMixin,
    uweb3.LoginMixin,
):
    """Holds all the request handlers for the application"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.page_size = 10

    def _PostInit(self):
        """Sets up all the default vars"""
        self.validatexsrf()
        self.parser.RegisterFunction("json", lambda x: json.dumps(x, default=str))
        self.parser.RegisterFunction("CentRound", centround)
        self.parser.RegisterFunction("items", lambda x: x.items())
        self.parser.RegisterFunction("DateOnly", lambda x: str(x)[0:10])
        self.parser.RegisterFunction("TimeOnly", lambda x: str(x)[0:5])
        self.parser.RegisterFunction("NullString", lambda x: "" if x is None else x)
        self.parser.RegisterTag("is_development", self.is_development)
        self.parser.RegisterTag("year", time.strftime("%Y"))
        self.parser.RegisterTag("xsrf", self._Get_XSRF())
        self.parser.RegisterTag("user", self.user)

    def _PostRequest(self, response):
        response.headers.update(
            {
                "Access-Control-Allow-Origin": "*",
            }
        )
        return response

    def _ReadSession(self):
        """Attempts to read the session for this user from his session cookie"""
        try:
            user = login_model.Session(self.connection)
        except Exception:
            logger.debug("Session cookie for user is invalid.")
            raise ValueError("Session cookie invalid")
        try:
            user = login_model.User.FromPrimary(self.connection, int(str(user)))
        except uweb3.model.NotExistError:
            return None
        if user["active"] != "true":
            logger.debug("User is not active, session invalid.")
            raise ValueError("User not active, session invalid")
        return user

    @uweb3.decorators.TemplateParser("login.html")
    def RequestLogin(self, url=None):
        """Please login"""
        if self.user:
            return uweb3.Redirect("/invoices")
        if not url and "url" in self.get:
            url = self.get.getfirst("url")
        return {"url": url, "title": "Login"}

    def RequestInvalidcommand(self, command=None, error=None, httpcode=404):
        """Returns an error message"""
        self.TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
        self.logger.warning(
            "Bad page %r requested with method %s", command, self.req.method
        )

        if command is None and error is None:
            command = "%s for method %s" % (self.req.path, self.req.method)
        page_data = self.parser.Parse(
            "parts/404.html", command=command, error=error, title="404"
        )
        return uweb3.Response(content=page_data, httpcode=httpcode)

    @uweb3.decorators.ContentType("application/json")
    def FourOhFour(self, path):
        """The request could not be fulfilled, this returns a 404."""
        logger.debug("Request page not found at path %s" % path)
        return uweb3.Response(
            {
                "error": True,
                "errors": ["Requested page not found"],
                "http_status": HTTPStatus.NOT_FOUND,
            },
            httpcode=HTTPStatus.NOT_FOUND,
        )

    def Error(self, error="", httpcode=500, link=None, log_error=True):
        """Returns a generic error page based on the given parameters."""
        self.TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
        logger.debug("Error page triggered: %s" % error)

        if log_error:
            self.logger.error("Error page triggered: %r", error)

        page_data = self.parser.Parse(
            "parts/error.html", error=error, link=link, title="Error"
        )
        return uweb3.Response(content=page_data, httpcode=httpcode)

    def WarehouseError(self, error="", httpcode=500, api_status_code=None):
        self.logger.error(
            f"Error page triggered: {error} with API status code '{api_status_code}'"
        )
        self.TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

        page_data = self.parser.Parse(
            "parts/warehouse_error.html",
            title="Warehouse Error",
            error=error,
            api_status_code=api_status_code,
        )
        return uweb3.Response(content=page_data, httpcode=httpcode)
