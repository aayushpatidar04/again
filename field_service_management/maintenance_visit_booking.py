"""Release technician bookings when a Maintenance Visit is cancelled."""

import frappe


def queue_cancelled_visit_booking_cleanup(doc, method=None):
    """Keep cancellation responsive while calendar events are removed remotely."""
    if doc.docstatus != 2 and doc.status != "Cancelled":
        return
    if not frappe.db.exists("Assigned Tasks", {"issue_code": doc.name}):
        return

    frappe.enqueue(
        "field_service_management.maintenance_visit_booking.clear_cancelled_visit_bookings",
        queue="short",
        enqueue_after_commit=True,
        job_id=f"clear_cancelled_visit_bookings:{doc.name}",
        deduplicate=True,
        visit_name=doc.name,
    )


def clear_cancelled_visit_bookings(visit_name):
    """Delete linked calendar events first, then their cancelled visit bookings."""
    visit = frappe.db.get_value(
        "Maintenance Visit", visit_name, ["docstatus", "status"], as_dict=True
    )
    if not visit or (visit.docstatus != 2 and visit.status != "Cancelled"):
        return

    booking_names = frappe.get_all(
        "Assigned Tasks", filters={"issue_code": visit_name}, pluck="name"
    )
    for booking_name in booking_names:
        event_names = frappe.get_all(
            "Event",
            filters=[
                ["Event Participants", "reference_doctype", "=", "Assigned Tasks"],
                ["Event Participants", "reference_docname", "=", booking_name],
            ],
            pluck="name",
        )
        for event_name in event_names:
            event = frappe.get_doc("Event", event_name)
            if event.custom_sync_with_ms_calendar and not event.custom_outlook_event_id:
                # An event that was never synced has nothing to delete remotely.
                event.custom_sync_with_ms_calendar = 0
                event.save(ignore_permissions=True)
            frappe.delete_doc("Event", event_name, ignore_permissions=True)

        frappe.delete_doc("Assigned Tasks", booking_name, ignore_permissions=True)
