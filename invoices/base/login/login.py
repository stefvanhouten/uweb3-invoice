import marshmallow.exceptions
import uweb3

from invoices.base import basepages
from invoices.base.common.schemas import CompanyDetailsSchema
from invoices.base.invoice import model as invoice_model
from invoices.base.login import model


class PageMaker(basepages.PageMaker):
    def __init__(self, *args, **kwargs):
        super(PageMaker, self).__init__(*args, **kwargs)

    @uweb3.decorators.loggedin
    def RequestIndex(self):
        """Returns the homepage"""
        return self.req.Redirect("/invoices", httpcode=303)

    @uweb3.decorators.TemplateParser("login.html")
    def RequestLogin(self, url=None):
        """Please login"""
        if self.user:
            return self.RequestIndex()
        if not url and "url" in self.get:
            url = self.get.getfirst("url")
        return {"url": url}

    @uweb3.decorators.checkxsrf
    @uweb3.decorators.TemplateParser("logout.html")
    def RequestLogout(self):
        """Handles logouts"""
        message = "You were already logged out."
        if self.user:
            message = ""
            if "action" in self.post:
                session = model.Session(self.connection)
                session.Delete()
                return self.req.Redirect("/login")
        return {"message": message}

    @uweb3.decorators.checkxsrf
    def HandleLogin(self):
        """Handles a username/password combo post."""
        if self.user or "email" not in self.post or "password" not in self.post:
            return self.RequestIndex()
        url = (
            self.post.getfirst("url", None)
            if self.post.getfirst("url", "").startswith("/")
            else "/"
        )
        try:
            self._user = model.User.FromLogin(
                self.connection,
                self.post.getfirst("email"),
                self.post.getfirst("password"),
            )
            model.Session.Create(self.connection, int(self.user), path="/")
            print("login successful.", self.post.getfirst("email"))
            # redirect 303 to make sure we GET the next page, not post again to avoid leaking login details.
            return self.req.Redirect(url, httpcode=303)
        except model.User.NotExistError as error:
            self.parser.RegisterTag("loginerror", "%s" % error)
            print("login failed.", self.post.getfirst("email"))
        return self.RequestLogin(url)

    @uweb3.decorators.checkxsrf
    @uweb3.decorators.TemplateParser("setup.html")
    def RequestSetup(self):
        """Allows the user to setup various fields, and create an admin user.

        If these fields are already filled out, this page will not function any
        longer.
        """
        if not model.User.IsFirstUser(self.connection):
            return self.req.Redirect("/login")

        if (
            "email" in self.post
            and "password" in self.post
            and "password_confirm" in self.post
            and self.post.getfirst("password") == self.post.getfirst("password_confirm")
        ):

            # We do this because marshmallow only validates dicts. Calling dict(self.post) does not work propperly because the values of the dict will be indexfield.
            fieldstorage_to_dict = {
                key: self.post.getfirst(key, "") for key in list(self.post.keys())
            }
            try:
                settings = CompanyDetailsSchema().load(fieldstorage_to_dict)
                invoice_model.Companydetails.Create(self.connection, settings)
                user = model.User.Create(
                    self.connection,
                    {
                        "ID": 1,
                        "email": self.post.getfirst("email"),
                        "active": "true",
                        "password": self.post.getfirst("password"),
                    },
                    generate_password_hash=True,
                )
            except ValueError:
                return {
                    "errors": {
                        "password": ["Password too short, 8 characters minimal."]
                    },
                    "postdata": fieldstorage_to_dict,
                }
            except marshmallow.exceptions.ValidationError as error:
                return {"errors": error.messages, "postdata": fieldstorage_to_dict}

            self.config.Update("general", "host", self.post.getfirst("hostname"))
            self.config.Update(
                "general", "locale", self.post.getfirst("locale", "en_GB")
            )
            self.config.Update(
                "general", "warehouse_api", self.post.getfirst("warehouse_api")
            )
            self.config.Update("general", "apikey", self.post.getfirst("apikey"))
            model.Session.Create(self.connection, int(user), path="/")
            return self.req.Redirect("/", httpcode=301)
