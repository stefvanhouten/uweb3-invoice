from datetime import datetime
from enum import Enum

from pymysql import IntegrityError
from uweb3 import model

KEY_UNIQUE_ERROR = 1062


class AppointmentStatus(str, Enum):
    COMPLETE = "complete"


class PickupError(Exception):
    pass


class PickupAppointmentSlotUnavailable(PickupError):
    pass


class PickupDateNotAvailable(PickupError):
    pass


class PickupTimeError(PickupError):
    pass


class PickupSlotModifyError(PickupError):
    pass


class Pickupslot(model.Record):
    """Abstraction class for the pickupslot table."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._appointments = None

    def _PostSelect(self):
        self["start_time"] = datetime.time(datetime.min + self["start_time"])
        self["end_time"] = datetime.time(datetime.min + self["end_time"])

    @classmethod
    def FromPrimary(cls, connection, pkey_value):
        record = super().FromPrimary(connection, pkey_value)
        record._PostSelect()
        return record

    @classmethod
    def FromDate(cls, connection, date):
        safe_date = connection.EscapeValues(date.strftime("%Y-%m-%d"))
        with connection as cursor:
            record = cursor.Select(
                table=cls.TableName(),
                conditions=f"date = {safe_date}",
            )
        if not record:
            return None
        return cls(connection, record[0])

    @classmethod
    def Create(self, connection, record):
        try:
            return super().Create(connection, record)
        except IntegrityError as exc:
            if exc.args[0] == KEY_UNIQUE_ERROR:
                raise PickupDateNotAvailable(
                    "Pickup date is not available because it is already taken"
                ) from exc

    def Save(self, save_foreign=False):
        diff = self._Changes()
        if "slots" in diff and len(self.appointments) > diff["slots"]:
            self.update(self._record)
            raise PickupSlotModifyError(
                "Cannot change the number of slots to less than the current amount of appointments"
            )
        super().Save(save_foreign=save_foreign)

    @property
    def appointments(self):
        if not self._appointments:
            self._appointments = list(self._Children(PickupSlotAppointment))
        return self._appointments


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
    def Create(cls, connection, record):
        pickupslot = Pickupslot.FromPrimary(connection, record["pickupslot"])
        total_appointments = len(
            list(cls.List(connection, conditions=f"pickupslot={pickupslot['ID']}"))
        )

        if total_appointments >= pickupslot["slots"]:
            raise PickupAppointmentSlotUnavailable("Max appointment capacity reached.")

        if not appointment_within_slot_time(pickupslot, record):
            raise PickupTimeError(
                f"Appointment must be between {pickupslot['start_time']} and {pickupslot['end_time']}."
            )
        return super().Create(connection, record)

    def set_status(self, status: AppointmentStatus):
        self["status"] = status.value
        self.Save()


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
