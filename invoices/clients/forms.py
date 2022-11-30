import re

from wtforms import Form, IntegerField, RadioField, StringField, validators

VAT_NUMBER_REGEX = re.compile(
    (
        "(?:(AT)\s*(U\d{8}))|"
        "(?:(BE)\s*(0?\d{*}))|(?:(CZ)\s*(\d{8,10}))|"
        "(?:(DE)\s*(\d{9}))|"
        "(?:(CY)\s*(\d{8}[A-Z]))|"
        "(?:(DK)\s*(\d{8}))|"
        "(?:(EE)\s*(\d{9}))|"
        "(?:(GR)\s*(\d{9}))|"
        "(?:(ES|NIF:?)\s*([0-9A-Z]\d{7}[0-9A-Z]))|"
        "(?:(FI)\s*(\d{8}))|"
        "(?:(FR)\s*([0-9A-Z]{2}\d{9}))|"
        "(?:(GB)\s*((\d{9}|\d{12})~(GD|HA)\d{3}))|"
        "(?:(HU)\s*(\d{8}))|"
        "(?:(IE)\s*(\d[A-Z0-9\\+\\*]\d{5}[A-Z]))|"
        "(?:(IT)\s*(\d{11}))|"
        "(?:(LT)\s*((\d{9}|\d{12})))|"
        "(?:(LU)\s*(\d{8}))|"
        "(?:(LV)\s*(\d{11}))|"
        "(?:(MT)\s*(\d{8}))|"
        "(?:(NL)\s*(\d{9}B\d{2}))|"
        "(?:(PL)\s*(\d{10}))|"
        "(?:(PT)\s*(\d{9}))|"
        "(?:(SE)\s*(\d{12}))|"
        "(?:(SI)\s*(\d{8}))|"
        "(?:(SK)\s*(\d{10}))|"
        "(?:\D|^)(\d{11})(?:\D|$)|"
        "(?:(CHE)(-|\s*)(\d{3}\.\d{3}\.\d{3}))|"
        "(?:(SM)\s*(\d{5}))"
    )
)


class ClientTypeAndVatNumberValidation(validators.Optional):
    """This validator makes sure that the VAT number is validated
    only if the client type is set to "Company"."""

    def __init__(
        self, other_field_name, other_field_value, message=None, *args, **kwargs
    ):
        self.other_field_name = other_field_name
        self.other_field_value = other_field_value
        self.message = message
        super().__init__(*args, **kwargs)

    def __call__(self, form, field):
        other_field = form._fields.get(self.other_field_name)

        if other_field is None:
            raise Exception(f'no field named "{self.other_field_name}" in form')

        if not bool(other_field.data) or not other_field.data == self.other_field_value:
            field.errors[:] = []
            raise validators.StopValidation()

        if not bool(field.data):
            if not self.message:
                message = f"This field is required if {self.other_field_name} is set to {self.other_field_value}"
            else:
                message = self.message

            raise validators.ValidationError(message)


class ClientForm(Form):
    client_type = RadioField(
        "Client type",
        choices=["Individual", "Company"],
        validators=[validators.InputRequired()],
        render_kw={"id": "client_type_radio"},
    )
    vat_number = StringField(
        "VAT number",
        validators=[
            ClientTypeAndVatNumberValidation(
                "client_type",
                "Company",
                message="This field is required when client type is set to Company",
            ),
            validators.Regexp(
                VAT_NUMBER_REGEX,
                message="Invalid VAT number format.",
            ),
        ],
        render_kw={"placeholder": "NL123456789B01"},
    )
    name = StringField(
        "Name",
        validators=[
            validators.InputRequired(),
            validators.Length(max=255),
        ],
        render_kw={"placeholder": "Client name"},
    )
    telephone = StringField(
        "Telephone",
        validators=[
            validators.Optional(),
            validators.Length(max=30),
        ],
        render_kw={"placeholder": "0612345678"},
    )
    email = StringField(
        "Email",
        validators=[
            validators.Optional(),
            validators.Regexp("^\S+@\S+$", message="Must be a valid email address"),
            validators.Length(max=100),
        ],
        render_kw={"placeholder": "name@email.com"},
    )
    address = StringField(
        "Street name",
        validators=[
            validators.InputRequired(),
            validators.Length(max=45),
        ],
        render_kw={"placeholder": "Clients street, without house number."},
    )
    house_number = IntegerField(
        "House number",
        validators=[
            validators.InputRequired(),
            validators.NumberRange(min=1, max=99999),
        ],
        render_kw={"placeholder": "123"},
    )
    house_number_addition = StringField(
        "House number addition",
        validators=[validators.Optional()],
        render_kw={"placeholder": "B"},
    )
    postalCode = StringField(
        "Postal code",
        validators=[
            validators.Regexp(
                r"^[1-9][0-9]{3} ?(?!sa|sd|ss|SA|SD|SS)[A-Za-z]{2}$",
                message="Zipcodes must be in the form 1234 AB.",
            ),
            validators.InputRequired(),
            validators.Length(max=10),
        ],
        render_kw={"placeholder": "1234 AB"},
    )
    city = StringField(
        "City",
        validators=[
            validators.InputRequired(),
            validators.Length(max=45),
        ],
        render_kw={"placeholder": "Clients city"},
    )

    def validate(self, extra_validators=None):
        isvalid: bool = super().validate(extra_validators)

        # Make sure to strip the vat_number if the client_type is set to Individual
        # this prevents silent updates when form data was set, but type was switched.
        if self.client_type.data == "Individual":
            self.vat_number.data = None
        return isvalid
