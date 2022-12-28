from wtforms import StringField, validators

from invoices.common.base_forms import BaseForm, Legend


class SettingsForm(BaseForm):
    legend_urls = Legend("Urls")
    webhook_url = StringField(
        "Webhook URL (notification)", [validators.InputRequired(), validators.URL()]
    )
    redirect_url = StringField(
        "Redirect URL (client)", [validators.InputRequired(), validators.URL()]
    )
    mollie_apikey = StringField("Apikey", [validators.InputRequired()])

    legend_api_access = Legend("API access")
    warehouse_api = StringField(
        "Warehouse API", [validators.InputRequired(), validators.URL()]
    )
    warehouse_apikey = StringField("Apikey", [validators.InputRequired()])

    legend_timestamping_service = Legend("Timestamping service")
    timestamp_api = StringField(
        "Timestamping API", [validators.InputRequired(), validators.URL()]
    )
    timestamp_apikey = StringField("Apikey", [validators.InputRequired()])
