import decimal

from wtforms import (
    BooleanField,
    DecimalField,
    FieldList,
    Form,
    FormField,
    IntegerField,
    SelectField,
    StringField,
    TextAreaField,
    validators,
)

from invoices.invoice.model import InvoiceStatus


class ProductForm(Form):
    name = StringField("name", validators=[validators.InputRequired()])
    product_sku = StringField("sku", validators=[validators.InputRequired()])
    price = DecimalField(
        "Price",
        [validators.NumberRange(min=0)],
    )
    vat_percentage = DecimalField(
        "VAT",
        [validators.NumberRange(min=0)],
    )
    quantity = IntegerField("Quantity", [validators.NumberRange(min=1)])


class InvoiceForm(Form):
    client = SelectField(
        "Client",
        description="The name of the client",
        validators=[validators.InputRequired()],
    )
    status = SelectField(
        "Status",
        choices=[
            (InvoiceStatus.NEW.value, "New invoice"),
            (InvoiceStatus.RESERVATION.value, "Pro forma"),
        ],
        validators=[validators.InputRequired()],
    )
    title = StringField(
        "Title",
        description="The title of the invoice",
        validators=[validators.InputRequired(), validators.Length(min=5, max=80)],
        render_kw={"placeholder": "Invoice title"},
    )
    send_mail = BooleanField(
        "Send mail",
        description="Send an email to the client?",
        validators=[validators.Optional()],
    )
    mollie_payment_request = DecimalField(
        "Mollie payment request",
        places=2,
        rounding=decimal.ROUND_UP,
        description=(
            "The amount for the payment request. "
            "Setting this value will also send an email to the client containing the mollie payment url."
        ),
        validators=[validators.Optional(), validators.NumberRange(min=0)],
        render_kw={"placeholder": "0.00"},
    )
    description = TextAreaField(
        "Description",
        description="A general description for on the invoice",
        validators=[validators.InputRequired()],
        render_kw={"placeholder": "Details about the invoice."},
    )
    products = FieldList(FormField(ProductForm), min_entries=1)
