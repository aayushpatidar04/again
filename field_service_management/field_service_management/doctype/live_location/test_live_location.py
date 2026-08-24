# Copyright (c) 2024, Aayush Patidar and Contributors
# See license.txt

import uuid
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime

from field_service_management.api import (
    _insert_live_location,
    _upsert_live_location_health,
)


class TestLiveLocation(FrappeTestCase):
    def setUp(self):
        self.event_id = str(uuid.uuid4())

    def tearDown(self):
        frappe.db.delete("Live Location", {"event_id": self.event_id})
        frappe.db.delete(
            "Live Location Device Health",
            {"installation_id": "test-installation"},
        )

    def _event(self, **overrides):
        event = {
            "event_id": self.event_id,
            "sequence": 1,
            "captured_at": "2026-08-21T10:30:00.000Z",
            "latitude": 22.75,
            "longitude": 75.89,
            "accuracy_m": 8.5,
            "source": "fresh",
        }
        event.update(overrides)
        return event

    def test_batch_event_is_idempotent_and_preserves_capture_time(self):
        event = self._event()
        device = {"installation_id": "test-installation"}

        self.assertEqual(
            _insert_live_location("Administrator", {}, event, device), "accepted"
        )
        self.assertEqual(
            _insert_live_location("Administrator", {}, event, device), "duplicate"
        )

        location = frappe.get_last_doc(
            "Live Location", filters={"event_id": self.event_id}
        )
        self.assertEqual(location.event_id, self.event_id)
        self.assertEqual(location.installation_id, "test-installation")
        self.assertEqual(location.time, location.captured_at)
        self.assertIsNotNone(location.received_at)

    def test_invalid_coordinates_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "latitude"):
            _insert_live_location(
                "Administrator", {}, self._event(latitude=91), {}
            )

    @patch("field_service_management.api.frappe.get_doc")
    @patch("field_service_management.api.frappe.db.exists")
    def test_concurrent_event_insert_is_an_idempotent_duplicate(
        self, exists, get_doc
    ):
        exists.return_value = False
        document = MagicMock()
        document.insert.side_effect = frappe.UniqueValidationError(
            "Live Location", self.event_id
        )
        get_doc.return_value = document

        result = _insert_live_location(
            "Administrator",
            {},
            self._event(),
            {"installation_id": "test-installation"},
        )

        self.assertEqual(result, "duplicate")

    def test_device_health_is_updated_per_installation(self):
        device = {
            "installation_id": "test-installation",
            "device_model": "Google Pixel 9a",
            "android_version": "Android 16",
            "android_sdk": 36,
            "app_version": "1.1.6+17",
            "platform": "android",
        }
        state = {
            "tracking_enabled": True,
            "service_running": True,
            "location_service_enabled": True,
            "permission": "always",
            "precise": True,
            "battery_optimization_disabled": True,
            "network_connected": True,
            "pending_count": 0,
            "last_capture_at": "2026-08-21T10:30:00.000Z",
        }

        first = _upsert_live_location_health(
            "Administrator", {}, device=device, tracking_state=state
        )
        state["location_service_enabled"] = False
        second = _upsert_live_location_health(
            "Administrator", {}, device=device, tracking_state=state
        )

        self.assertEqual(first.name, second.name)
        self.assertEqual(second.device_model, "Google Pixel 9a")
        self.assertEqual(second.health_status, "Blocked")
        self.assertEqual(second.pending_count, 0)

    def test_concurrent_health_insert_updates_the_winning_record(self):
        document = MagicMock()
        document.is_new.return_value = True
        document.insert.side_effect = frappe.DuplicateEntryError(
            "Live Location Device Health", "health-key"
        )

        with (
            patch(
                "field_service_management.api.frappe.db.get_value",
                return_value=None,
            ),
            patch(
                "field_service_management.api.frappe.new_doc",
                return_value=document,
            ),
            patch(
                "field_service_management.api.frappe.db.sql",
                return_value=[("existing-health",)],
            ),
            patch("field_service_management.api.frappe.db.set_value") as set_value,
        ):
            result = _upsert_live_location_health(
                "Administrator",
                {},
                device={"installation_id": "test-installation"},
                tracking_state={"tracking_enabled": True},
            )

        self.assertEqual(result.name, "existing-health")
        set_value.assert_called_once()
