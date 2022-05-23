import time
from http import HTTPStatus

import uweb3

import invoices.base.login.model as login_model
from invoices.base.invoice.model import PRO_FORMA_PREFIX

API_VERSION = "/api/v1"


class PageMaker(
    uweb3.DebuggingPageMaker,
    uweb3.LoginMixin,
):
    """Holds all the request handlers for the application"""

    def __init__(self, *args, **kwds):
        super(PageMaker, self).__init__(*args, **kwds)

    def _PostInit(self):
        """Sets up all the default vars"""
        self.validatexsrf()
        self.parser.RegisterFunction("CentRound", lambda x: "%.2f" % x if x else None)
        self.parser.RegisterFunction("items", lambda x: x.items())
        self.parser.RegisterFunction("DateOnly", lambda x: str(x)[0:10])
        self.parser.RegisterFunction(
            "isProForma", lambda x: bool(str(x).startswith(PRO_FORMA_PREFIX))
        )
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

    def RequestInvalidcommand(self, command=None, error=None, httpcode=404):
        """Returns an error message"""
        uweb3.logging.warning(
            "Bad page %r requested with method %s", command, self.req.method
        )
        if command is None and error is None:
            command = "%s for method %s" % (self.req.path, self.req.method)
        page_data = self.parser.Parse("404.html", command=command, error=error)
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
        page_data = self.parser.Parse("error.html", error=error, link=link)
        return uweb3.Response(content=page_data, httpcode=httpcode)
