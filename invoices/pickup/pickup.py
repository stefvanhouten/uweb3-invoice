import os
from datetime import datetime

import uweb3

from invoices import basepages
from invoices.clients import model as client_model
from invoices.common.decorators import NotExistsErrorCatcher, loggedin
from invoices.pickup import forms, helpers, model


class PageMaker(basepages.PageMaker):
    TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

    @loggedin
    @uweb3.decorators.checkxsrf
    @uweb3.decorators.TemplateParser("slots.html")
    def RequestPickupSlots(self):
        pickup_slot_form = forms.PickupSlotForm(self.post)

        if self.post and pickup_slot_form.validate():
            try:
                model.Pickupslot.Create(self.connection, pickup_slot_form.data)
                return uweb3.Redirect("/pickupslots", httpcode=303)
            except model.PickupDateNotAvailable as exc:
                pickup_slot_form.date.errors.append(exc)

        result = model.Pickupslot.FromDate(self.connection, datetime.now())
        return dict(
            pickup_slot_form=pickup_slot_form,
            slots=model.Pickupslot.List(self.connection),
            appointments=result.appointments if result else [],
            slot=result,
        )

    @loggedin
    @uweb3.decorators.checkxsrf
    @NotExistsErrorCatcher
    @uweb3.decorators.TemplateParser("manage_appointments.html")
    def RequestManagePickupSlot(
        self, slotID, appointment_form=None, pickup_slot_form=None
    ):
        slot = model.Pickupslot.FromPrimary(self.connection, slotID)

        if not appointment_form:
            appointment_form = forms.setup_pickup_slot_appointment_form(
                client_model.Client, self.connection, self.post, slotID  # type: ignore
            )

        if not pickup_slot_form:
            pickup_slot_form = forms.PickupSlotForm(data=slot)

        return dict(
            slot=slot,
            appointments=list(
                model.PickupSlotAppointment.List(
                    self.connection, conditions=f"pickupslot={slotID}"
                )
            ),
            appointment_form=appointment_form,
            pickup_slot_form=pickup_slot_form,
        )

    @loggedin
    @uweb3.decorators.checkxsrf
    @NotExistsErrorCatcher
    def RequestUpdateAppointment(self, slotID):
        slot = model.Pickupslot.FromPrimary(self.connection, slotID)
        pickup_slot_form = forms.PickupSlotForm(self.post, data=slot)

        if self.post and pickup_slot_form.validate():
            slot.update(pickup_slot_form.data)
            try:
                slot.Save()
                return uweb3.Redirect(f"/pickupslot/{slotID}", httpcode=303)
            except model.PickupSlotModifyError as exc:
                pickup_slot_form.slots.errors.append(exc)

        return self.RequestManagePickupSlot(slotID, pickup_slot_form=pickup_slot_form)

    @loggedin
    @uweb3.decorators.checkxsrf
    @NotExistsErrorCatcher
    def RequestCreateAppointment(self, slotID):
        appointment_form = forms.setup_pickup_slot_appointment_form(
            client_model.Client, self.connection, self.post, slotID  # type: ignore
        )

        if appointment_form.validate():
            try:
                model.PickupSlotAppointment.Create(
                    self.connection, appointment_form.data
                )
                return uweb3.Redirect(f"/pickupslot/{slotID}", httpcode=303)
            except (
                model.PickupTimeError,
                model.PickupAppointmentSlotUnavailable,
            ) as exc:
                appointment_form.time.errors.append(exc)

        return self.RequestManagePickupSlot(slotID, appointment_form=appointment_form)

    @loggedin
    @uweb3.decorators.checkxsrf
    @NotExistsErrorCatcher
    def RequestDeleteAppointment(self, slotID, appointmentID):
        appointment = model.PickupSlotAppointment.FromPrimary(
            self.connection,
            (
                appointmentID,
                slotID,
            ),
        )
        appointment.Delete()
        return uweb3.Redirect(f"/pickupslot/{slotID}", httpcode=303)

    @loggedin
    @uweb3.decorators.checkxsrf
    @NotExistsErrorCatcher
    def RequestCompleteAppointment(self, slotID, appointmentID):
        appointment = model.PickupSlotAppointment.FromPrimary(
            self.connection,
            (
                appointmentID,
                slotID,
            ),
        )
        appointment.set_status(model.AppointmentStatus.COMPLETE)
        return uweb3.Redirect(f"/pickupslot/{slotID}", httpcode=303)

    @loggedin
    @NotExistsErrorCatcher
    @uweb3.decorators.checkxsrf
    @uweb3.decorators.TemplateParser("appointment.html")
    def RequestAppointment(self, slotID, appointmentID):
        appointment = model.PickupSlotAppointment.FromPrimary(
            self.connection,
            (
                appointmentID,
                slotID,
            ),
        )

        appointment_form = forms.setup_pickup_slot_appointment_form(
            client_model.Client, self.connection, self.post, slotID, data=appointment  # type: ignore
        )

        return dict(
            appointment_form=appointment_form,
        )
