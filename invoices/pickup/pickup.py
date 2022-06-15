import os

import uweb3

from invoices import basepages
from invoices.clients import model as client_model
from invoices.common.decorators import loggedin
from invoices.pickup import forms, helpers, model


class PageMaker(basepages.PageMaker):
    TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")

    @loggedin
    @uweb3.decorators.TemplateParser("slots.html")
    def RequestPickupSlots(self):
        pickup_slot_form = forms.PickupSlotForm(self.post)

        if self.post and pickup_slot_form.validate():
            model.Pickupslot.Create(self.connection, pickup_slot_form.data)
            return uweb3.Redirect("/pickupslots", httpcode=303)

        return dict(
            pickup_slot_form=pickup_slot_form,
            slots=model.Pickupslot.List(self.connection),
        )

    @loggedin
    @uweb3.decorators.TemplateParser("manage_appointments.html")
    def RequestManagePickupSlot(self, slotID):
        slot = model.Pickupslot.FromPrimary(self.connection, slotID)
        appointments = model.PickupSlotAppointment.List(
            self.connection, conditions=f"ID={slotID}"
        )
        clients = client_model.Client.List(self.connection)
        appointment_form = forms.PickupSlotAppointmentForm(self.post)
        appointment_form.client.choices = [
            (c["clientNumber"], c["name"]) for c in clients
        ]
        appointment_form.pickupslot.data = slotID

        return dict(
            slot=slot, appointments=appointments, appointment_form=appointment_form
        )
