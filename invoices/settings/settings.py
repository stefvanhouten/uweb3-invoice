import os

import marshmallow.exceptions
import uweb3

import invoices.invoice.model as invoice_model
from invoices import basepages
from invoices.common.decorators import loggedin
from invoices.common.helpers import BaseFormServiceBuilder, FormFactory
from invoices.common.schemas import CompanyDetailsSchema
from invoices.settings import forms


class PageMaker(basepages.PageMaker):
    TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.forms = FormFactory()
        self.forms.register_form(
            "settings",
            BaseFormServiceBuilder(form=forms.SettingsForm),
        )

    @loggedin
    @uweb3.decorators.TemplateParser("settings.html")
    def RequestSettings(self, errors=None):
        """Returns the settings page."""
        if not errors:
            errors = {}

        mollie_form = self.forms.get_form(
            "settings",
            data=dict(
                webhook_url=self.options["mollie"]["webhook_url"],
                redirect_url=self.options["mollie"]["redirect_url"],
                mollie_apikey=self.options["mollie"]["apikey"],
                warehouse_api=self.options["general"]["warehouse_api"],
                warehouse_apikey=self.options["general"]["warehouse_apikey"],
                timestamp_api=self.options["general"]["timestamping_api"],
                timestamp_apikey=self.options["general"]["timestamping_apikey"],
            ),
        )

        settings = None
        highestcompanyid = invoice_model.Companydetails.HighestNumber(self.connection)
        if highestcompanyid:
            settings = invoice_model.Companydetails.FromPrimary(
                self.connection, highestcompanyid
            )
        return {
            "title": "Settings",
            "page_id": "settings",
            "mollie_form": mollie_form,
            "settings": settings,
            "errors": errors,
            "redirect_errors": self.get.getlist("error"),
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
    def RequestMollieSettingsSave(self):
        form: forms.SettingsForm = self.forms.get_form(
            "settings", self.post
        )  # type: ignore

        if not form.validate():
            return self.RequestSettings()

        self.config.Update("mollie", "apikey", str(form.mollie_apikey.data))
        self.config.Update("mollie", "webhook_url", str(form.webhook_url.data))
        self.config.Update("mollie", "redirect_url", str(form.redirect_url.data))
        self.config.Update("general", "warehouse_api", str(form.warehouse_api.data))
        self.config.Update(
            "general", "warehouse_apikey", str(form.warehouse_apikey.data)
        )
        self.config.Update("general", "timestamping_api", str(form.timestamp_api.data))
        self.config.Update(
            "general", "timestamping_apikey", str(form.timestamp_apikey.data)
        )
        return self.req.Redirect("/settings", httpcode=303)
