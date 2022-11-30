from wtforms import StringField, validators

from invoices.common.base_forms import BaseForm, Legend


class MollieSettingsForm(BaseForm):
    legend_urls = Legend("Urls")
    webhook_url = StringField(
        "Webhook URL (notification)", [validators.InputRequired(), validators.URL()]
    )
    redirect_url = StringField(
        "Redirect URL (client)", [validators.InputRequired(), validators.URL()]
    )
    apikey = StringField("Apikey", [validators.InputRequired()])


class WarehouseSettingsForm(BaseForm):
    legend_api_access = Legend("API access")
    warehouse_api = StringField(
        "Warehouse API", [validators.InputRequired(), validators.URL()]
    )
    apikey = StringField("Apikey", [validators.InputRequired()])
