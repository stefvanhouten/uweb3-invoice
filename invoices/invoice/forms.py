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


class ProductForm(Form):
    sku = SelectField("Name")
    price = DecimalField("Price", [validators.NumberRange(min=0)])
    vat_percentage = DecimalField("VAT", [validators.NumberRange(min=0)])
    quantity = IntegerField("Quantity", [validators.NumberRange(min=1)])


class InvoiceForm(Form):
    client = SelectField(
        "Client",
        description="The name of the client",
        validators=[validators.InputRequired()],
    )
    reservation = BooleanField(
        "Reservation",
        description="Is this a pro-forma invoice?",
        validators=[validators.optional()],
    )
    send_mail = BooleanField(
        "Send mail",
        description="Send an email to the client?",
        validators=[validators.Optional()],
    )
    title = StringField(
        "Title",
        description="The title of the invoice",
        validators=[validators.DataRequired(), validators.Length(min=5, max=80)],
    )
    mollie_payment_request = DecimalField(
        "Mollie payment request",
        places=2,
        rounding=decimal.ROUND_UP,
        description="The amount of the payment request",
        validators=[validators.optional(), validators.NumberRange(min=0)],
    )
    description = TextAreaField(
        "Description",
        description="A general description for on the invoice",
        validators=[validators.InputRequired()],
    )
    product = FieldList(FormField(ProductForm), min_entries=1)


def get_invoice_form(clients, products, postdata=None):
    form = InvoiceForm(postdata)
    form.client.choices = [(c["ID"], c["name"]) for c in clients]
    for entry in form.product.entries:
        entry.sku.choices = [(p["sku"], p["name"]) for p in products]
        entry.sku.choices.insert(0, ("", "Select product"))
    return form
