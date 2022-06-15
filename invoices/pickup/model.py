from datetime import datetime

from pymysql import IntegrityError
from uweb3 import model

KEY_UNIQUE_ERROR = 1062


class PickupDateNotAvailable(Exception):
    pass


class PickupTimeError(Exception):
    pass


class Pickupslot(model.Record):
    """Abstraction class for the pickupslot table."""

    def _PostSelect(self):
        self["start_time"] = datetime.time(datetime.min + self["start_time"])
        self["end_time"] = datetime.time(datetime.min + self["end_time"])

    @classmethod
    def FromPrimary(cls, connection, pkey_value):
        record = super().FromPrimary(connection, pkey_value)
        record._PostSelect()
        return record

    @classmethod
    def Create(self, connection, record):
        try:
            return super().Create(connection, record)
        except IntegrityError as exc:
            if exc.args[0] == KEY_UNIQUE_ERROR:
                raise PickupDateNotAvailable(
                    "Pickup date is not available because it is already taken"
                ) from exc


class PickupSlotAppointment(model.Record):
    """Abstraction class for the pickupslot appointment table."""

    _PRIMARY_KEY = (
        "ID",
        "pickupslot",
    )

    def _PostSelect(self):
        self["time"] = datetime.time(datetime.min + self["time"])

    @classmethod
    def FromPrimary(cls, connection, pkey_value):
        record = super().FromPrimary(connection, pkey_value)
        record._PostSelect()
        return record

    @classmethod
    def Create(self, connection, record):
        pickupslot = Pickupslot.FromPrimary(connection, record["pickupslot"])
        if not appointment_within_slot_time(pickupslot, record):
            raise PickupTimeError(
                f"Appointment must be between {pickupslot['start_time']} and {pickupslot['end_time']}."
            )
        return super().Create(connection, record)


def appointment_within_slot_time(
    record: Pickupslot, appointment: PickupSlotAppointment
):
    """Determines whether the appointment is within the slot time.

    Args:
        record (Pickupslot): The Pickupslot record
        appointment (PickupSlotAppointment): The PickupSlotAppointment record to be.

    Returns:
        boolean: True when the appointment is within the slot time. False otherwise.
    """
    if (
        record["start_time"] > appointment["time"]
        or record["end_time"] < appointment["time"]
    ):
        return False
    return True
