import time
from http import HTTPStatus

import uweb3

import invoices.login.model as login_model
from invoices.invoice.model import PRO_FORMA_PREFIX


class PageMaker(
    uweb3.DebuggingPageMaker,
    uweb3.LoginMixin,
):
    """Holds all the request handlers for the application"""

    def _PostInit(self):
        """Sets up all the default vars"""
        self.validatexsrf()
        self.parser.RegisterFunction("CentRound", lambda x: "%.2f" % x if x else None)
        self.parser.RegisterFunction("items", lambda x: x.items())
        self.parser.RegisterFunction("DateOnly", lambda x: str(x)[0:10])
        self.parser.RegisterFunction("TimeOnly", lambda x: str(x)[0:5])
        self.parser.RegisterFunction("NullString", lambda x: "" if x is None else x)
        self.parser.RegisterTag("year", time.strftime("%Y"))
        self.parser.RegisterTag(
            "header", self.parser.JITTag(lambda: self.parser.Parse("parts/header.html"))
        )
        self.parser.RegisterTag(
            "footer",
            self.parser.JITTag(
                lambda *args, **kwargs: self.parser.Parse(
                    "parts/footer.html", *args, **kwargs
                )
            ),
        )
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
            raise ValueError("Session cookie invalid")
        try:
            user = login_model.User.FromPrimary(self.connection, int(str(user)))
        except uweb3.model.NotExistError:
            return None
        if user["active"] != "true":
            raise ValueError("User not active, session invalid")
        return user

    @uweb3.decorators.TemplateParser("login.html")
    def RequestLogin(self, url=None):
        """Please login"""
        if self.user:
            return uweb3.Redirect("/invoices")
        if not url and "url" in self.get:
            url = self.get.getfirst("url")
        return {"url": url}

    def RequestInvalidcommand(self, command=None, error=None, httpcode=404):
        """Returns an error message"""
        uweb3.logging.warning(
            "Bad page %r requested with method %s", command, self.req.method
        )
        if command is None and error is None:
            command = "%s for method %s" % (self.req.path, self.req.method)
        page_data = self.parser.Parse("parts/404.html", command=command, error=error)
        return uweb3.Response(content=page_data, httpcode=httpcode)

    @uweb3.decorators.ContentType("application/json")
    def FourOhFour(self, path):
        """The request could not be fulfilled, this returns a 404."""
        return uweb3.Response(
            {
                "error": True,
                "errors": ["Requested page not found"],
                "http_status": HTTPStatus.NOT_FOUND,
            },
            httpcode=HTTPStatus.NOT_FOUND,
        )

    def Error(self, error="", httpcode=500, link=None):
        """Returns a generic error page based on the given parameters."""
        uweb3.logging.error("Error page triggered: %r", error)
        page_data = self.parser.Parse("parts/error.html", error=error, link=link)
        return uweb3.Response(content=page_data, httpcode=httpcode)

    def WarehouseError(self, error="", httpcode=500, api_status_code=None):
        uweb3.logging.error(
            f"Error page triggered: {error} with API status code {api_status_code}"
        )
        page_data = self.parser.Parse(
            "parts/warehouse_error.html", error=error, api_status_code=api_status_code
        )
        return uweb3.Response(content=page_data, httpcode=httpcode)
