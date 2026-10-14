"""Make legacy generated board visit layers honor the selected map date range."""

import frappe

from field_service_management.field_service_management.page.api import (
    _expedition_layer_script_for_visits,
)


def execute():
    if not frappe.db.exists("DocType", "Expedition Map"):
        return

    map_name = frappe.db.get_value(
        "Expedition Map", {"title": "Today Board - Field Operations"}, "name"
    )
    if not map_name:
        return

    map_doc = frappe.get_doc("Expedition Map", map_name)
    updated = False
    for row in map_doc.get("layers", []):
        if not row.layer:
            continue
        layer = frappe.get_doc("Expedition Layer", row.layer)
        if layer.data_source_type != "Client Script (JS)":
            continue
        legacy_script = _expedition_layer_script_for_visits(
            layer.title, include_date_range=False
        )
        if layer.js_script != legacy_script:
            continue  # Preserve layers customized by an administrator.
        frappe.db.set_value(
            "Expedition Layer",
            layer.name,
            "js_script",
            _expedition_layer_script_for_visits(layer.title),
        )
        updated = True
    if updated:
        frappe.clear_cache(doctype="Expedition Layer")
