from datetime import datetime
from typing import TypeVar

from wtforms import (
    DateField,
    Form,
    HiddenField,
    IntegerField,
    SelectField,
    TextAreaField,
    TimeField,
    validators,
)

from invoices.clients import model as client_model
from invoices.pickup import model


class PickupSlotForm(Form):
    date = DateField(
        "Date", validators=[validators.InputRequired()], default=datetime.now()
    )
    start_time = TimeField(
        "Start Time",
        validators=[validators.InputRequired()],
        default=datetime.now().time(),
    )
    end_time = TimeField(
        "End Time",
        validators=[validators.InputRequired()],
        default=datetime.now().time(),
    )
    slots = IntegerField(
        "Slots", validators=[validators.InputRequired(), validators.NumberRange(min=1)]
    )

    def validate(self, extra_validators=None):
        result = super().validate(extra_validators=extra_validators)

        if self.date.data < datetime.date(datetime.now()):  # type: ignore
            self.date.errors.append("Date must be in the future")  # type: ignore
            result = False

        if self.end_time.data <= self.start_time.data:  # type: ignore
            self.end_time.errors.append("End time must be after start time")  # type: ignore
            result = False

        return result


class PickupSlotAppointmentForm(Form):
    pickupslot = HiddenField("Pickup Slot")
    time = TimeField(
        "Time",
        validators=[validators.InputRequired()],
        default=datetime.now().time(),
    )
    client = SelectField("Client", validators=[validators.InputRequired()])
    description = TextAreaField("Description", validators=[validators.Optional()])


def setup_pickup_slot_appointment_form(
    context: client_model.Client,
    connection,
    postdata,
    slotID: int,
    data: model.PickupSlotAppointment | None = None,
) -> PickupSlotAppointmentForm:
    clients = context.List(connection)
    form = PickupSlotAppointmentForm(postdata, data=data)
    form.pickupslot.data = slotID
    form.client.choices = [(c["clientNumber"], c["name"]) for c in clients]
    return form
