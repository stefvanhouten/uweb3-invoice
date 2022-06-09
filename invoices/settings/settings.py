import marshmallow.exceptions
import uweb3

import invoices.invoice.model as invoice_model
from invoices import basepages
from invoices.common.decorators import loggedin
from invoices.common.schemas import CompanyDetailsSchema


class PageMaker(basepages.PageMaker):
    @loggedin
    @uweb3.decorators.TemplateParser("settings.html")
    def RequestSettings(self, errors=None):
        """Returns the settings page."""
        if not errors:
            errors = {}
        settings = None
        highestcompanyid = invoice_model.Companydetails.HighestNumber(self.connection)
        if highestcompanyid:
            settings = invoice_model.Companydetails.FromPrimary(
                self.connection, highestcompanyid
            )
        return {
            "title": "Settings",
            "page_id": "settings",
            "warehouse": self.options.get("general", {}),
            "mollie": self.options.get("mollie", {}),
            "settings": settings,
            "errors": errors,
        }

    @loggedin
    @uweb3.decorators.checkxsrf
    def RequestSettingsSave(self):
        """Saves the changes and returns the settings page."""
        try:
            newsettings = CompanyDetailsSchema().load(self.post.__dict__)
        except marshmallow.exceptions.ValidationError as error:
            return self.RequestSettings(errors=error.messages)

        settings = None
        increment = invoice_model.Companydetails.HighestNumber(self.connection)

        try:
            settings = invoice_model.Companydetails.FromPrimary(
                self.connection, increment
            )
        except uweb3.model.NotExistError:
            pass

        if settings:
            settings.Create(self.connection, newsettings)
        else:
            invoice_model.Companydetails.Create(self.connection, newsettings)

        return self.RequestSettings()

    @loggedin
    @uweb3.decorators.checkxsrf
    def RequestWarehouseSettingsSave(self):
        self.config.Update(
            "general", "warehouse_api", self.post.getfirst("warehouse_api")
        )
        self.config.Update("general", "apikey", self.post.getfirst("apikey"))
        return self.req.Redirect("/settings", httpcode=303)

    @loggedin
    @uweb3.decorators.checkxsrf
    def RequestMollieSettingsSave(self):
        self.config.Update("mollie", "apikey", self.post.getfirst("apikey"))
        self.config.Update("mollie", "webhook_url", self.post.getfirst("webhook_url"))
        self.config.Update("mollie", "redirect_url", self.post.getfirst("redirect_url"))
        return self.req.Redirect("/settings", httpcode=303)
