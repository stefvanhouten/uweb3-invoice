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
            "mollie_settings",
            BaseFormServiceBuilder(form=forms.MollieSettingsForm),
        )
        self.forms.register_form(
            "warehouse_settings",
            BaseFormServiceBuilder(form=forms.WarehouseSettingsForm),
        )

    @loggedin
    @uweb3.decorators.TemplateParser("settings.html")
    def RequestSettings(self, errors=None):
        """Returns the settings page."""
        if not errors:
            errors = {}

        mollie_form = self.forms.get_form(
            "mollie_settings",
            data=dict(
                webhook_url=self.options["mollie"]["webhook_url"],
                redirect_url=self.options["mollie"]["redirect_url"],
                apikey=self.options["mollie"]["apikey"],
            ),
        )
        warehouse_form = self.forms.get_form(
            "warehouse_settings",
            data=dict(
                warehouse_api=self.options["general"]["warehouse_api"],
                apikey=self.options["general"]["apikey"],
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
            "warehouse_form": warehouse_form,
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
    def RequestWarehouseSettingsSave(self):
        warehouse_form: forms.WarehouseSettingsForm = self.forms.get_form(
            "warehouse_settings", self.post
        )  # type: ignore

        if not warehouse_form.validate():
            return self.RequestSettings()

        self.config.Update(
            "general", "warehouse_api", str(warehouse_form.warehouse_api.data)
        )

        self.config.Update("general", "apikey", str(warehouse_form.apikey.data))
        return self.req.Redirect("/settings", httpcode=303)

    @loggedin
    @uweb3.decorators.checkxsrf
    def RequestMollieSettingsSave(self):
        mollie_form: forms.MollieSettingsForm = self.forms.get_form(
            "mollie_settings", self.post
        )  # type: ignore

        if not mollie_form.validate():
            return self.RequestSettings()

        self.config.Update("mollie", "apikey", str(mollie_form.apikey.data))
        self.config.Update("mollie", "webhook_url", str(mollie_form.webhook_url.data))
        self.config.Update("mollie", "redirect_url", str(mollie_form.redirect_url.data))
        return self.req.Redirect("/settings", httpcode=303)
