"""Replace the legacy unscoped technician layer on the schedule-board map.

The old Python layer queried all live locations directly. The replacement
calls the board API, which applies the coordinator's territory permissions.
Only the dedicated board map is changed; the old layer record remains intact.
"""

import frappe

from field_service_management.field_service_management.page.api import (
    _expedition_layer_script_for_technicians,
)


def execute():
    map_name = frappe.db.get_value(
        "Expedition Map", {"title": "Today Board - Field Operations"}, "name"
    )
    if not map_name:
        return

    map_doc = frappe.get_doc("Expedition Map", map_name)
    changed = False
    for row in map_doc.get("layers", []):
        if not row.layer:
            continue
        layer = frappe.get_doc("Expedition Layer", row.layer)
        if (layer.title or "").strip() != "Live Technician Locations":
            continue
        if layer.data_source_type != "Python Script":
            continue

        replacement = frappe.get_doc({
            "doctype": "Expedition Layer",
            "title": layer.title,
            "enabled": 1,
            "data_source_type": "Client Script (JS)",
            "js_script": _expedition_layer_script_for_technicians(),
            "location_source": "Direct Fields",
            "color": layer.color or "#10B981",
            "icon": layer.icon or "pin-truck",
            "size": layer.size or "l",
            "cluster": layer.cluster or 0,
            "click_action": layer.click_action or "popup",
            "use_source_permissions": 1,
        })
        replacement.insert(ignore_permissions=True)
        row.layer = replacement.name
        changed = True

    if changed:
        map_doc.save(ignore_permissions=True)
        frappe.clear_cache(doctype="Expedition Map")
