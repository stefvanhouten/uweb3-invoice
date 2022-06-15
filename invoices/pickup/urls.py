from invoices.pickup.pickup import PageMaker

urls = [
    ("/pickupslots", (PageMaker, "RequestPickupSlots")),
    ("/pickupslot/(\d+)", (PageMaker, "RequestManagePickupSlot"), "GET"),
    ("/pickupslot/(\d+)", (PageMaker, "RequestUpdateAppointment"), "POST"),
    ("/pickupslot/(\d+)/appointment", (PageMaker, "RequestCreateAppointment"), "POST"),
    ("/pickupslot/(\d+)/appointment/(\d+)", (PageMaker, "RequestAppointment")),
    (
        "/pickupslot/(\d+)/appointment/(\d+)/delete",
        (PageMaker, "RequestDeleteAppointment"),
    ),
    (
        "/pickupslot/(\d+)/appointment/(\d+)/complete",
        (PageMaker, "RequestCompleteAppointment"),
    ),
]
