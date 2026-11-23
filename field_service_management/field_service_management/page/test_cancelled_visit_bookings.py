from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import call, patch

from field_service_management.field_service_management.page.api import (
    filter_active_schedule_board_bookings,
)
from field_service_management.maintenance_visit_booking import (
    clear_cancelled_visit_bookings,
    queue_cancelled_visit_booking_cleanup,
)


class TestCancelledVisitBookings(TestCase):
    @patch("field_service_management.field_service_management.page.api.frappe.get_all")
    def test_cancelled_bookings_do_not_occupy_board_or_conflict_checks(self, get_all):
        get_all.return_value = [SimpleNamespace(name="ACTIVE", status="Scheduled")]
        active = SimpleNamespace(issue_code="ACTIVE")
        cancelled = SimpleNamespace(issue_code="CANCELLED")

        self.assertEqual(
            filter_active_schedule_board_bookings([active, cancelled]), [active]
        )
        self.assertEqual(get_all.call_args.kwargs["filters"]["docstatus"], ["<", 2])

    @patch("field_service_management.maintenance_visit_booking.frappe")
    def test_cancellation_queues_calendar_cleanup(self, frappe):
        frappe.db.exists.return_value = "BOOKING"
        queue_cancelled_visit_booking_cleanup(
            SimpleNamespace(name="CANCELLED", docstatus=2, status="Cancelled")
        )
        frappe.enqueue.assert_called_once()
        self.assertTrue(frappe.enqueue.call_args.kwargs["enqueue_after_commit"])

    @patch("field_service_management.maintenance_visit_booking.frappe")
    def test_cleanup_deletes_calendar_event_before_booking(self, frappe):
        frappe.db.get_value.return_value = SimpleNamespace(docstatus=2, status="Cancelled")
        frappe.get_all.side_effect = [["BOOKING"], ["EVENT"]]
        frappe.get_doc.return_value = SimpleNamespace(
            custom_sync_with_ms_calendar=1, custom_outlook_event_id="remote-id"
        )

        clear_cancelled_visit_bookings("CANCELLED")

        self.assertEqual(
            frappe.delete_doc.call_args_list,
            [
                call("Event", "EVENT", ignore_permissions=True),
                call("Assigned Tasks", "BOOKING", ignore_permissions=True),
            ],
        )

    @patch("field_service_management.maintenance_visit_booking.frappe")
    def test_unsynced_event_is_not_deleted_from_remote_calendar(self, frappe):
        frappe.db.get_value.return_value = SimpleNamespace(docstatus=2, status="Cancelled")
        frappe.get_all.side_effect = [["BOOKING"], ["EVENT"]]
        event = SimpleNamespace(
            custom_sync_with_ms_calendar=1,
            custom_outlook_event_id=None,
            save=frappe.save_event,
        )
        frappe.get_doc.return_value = event

        clear_cancelled_visit_bookings("CANCELLED")

        self.assertEqual(event.custom_sync_with_ms_calendar, 0)
        event.save.assert_called_once_with(ignore_permissions=True)
