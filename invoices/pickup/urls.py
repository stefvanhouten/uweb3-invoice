from invoices.pickup.pickup import PageMaker

urls = [
    ("/pickupslots", (PageMaker, "RequestPickupSlots")),
    ("/pickupslot/(\d+)", (PageMaker, "RequestManagePickupSlot")),
]
