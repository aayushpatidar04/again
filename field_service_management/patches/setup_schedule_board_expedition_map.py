"""Create the schedule-board map on a new site without replacing admin changes.

The board reads its layers from Expedition Map. Those records are site data, so
they must be seeded when this app is deployed to a site that has not configured
the board yet. Once a map has layers, administrators remain its source of truth.
"""

import json

import frappe

from field_service_management.field_service_management.page.api import (
    _expedition_layer_script_for_technicians,
    _expedition_layer_script_for_visits,
)


BOARD_MAP_TITLE = "Today Board - Field Operations"
VISIT_LAYERS = (
    ("Fresh Installation", "#1EB89C", ""),
    ("Site Survey", "#B8AE1E", ""),
    ("Regular Maintenance", "#B81E4F", ""),
    ("Scheduled", "#691EB8", "pin-marker"),
    ("Product delivery -  for installation by BMS later", "#B89C1E", "pin-star"),
    ("Product delivery - for client self-installation", "#1E2DB8", ""),
)


def execute():
    if not frappe.db.exists("DocType", "Expedition Map") or not frappe.db.exists(
        "DocType", "Expedition Layer"
    ):
        frappe.throw(
            "Expedition Map and Expedition Layer must be installed before "
            "the schedule board map is set up."
        )

    map_name = frappe.db.get_value("Expedition Map", {"title": BOARD_MAP_TITLE}, "name")
    if map_name:
        map_doc = frappe.get_doc("Expedition Map", map_name)
        if map_doc.get("layers"):
            return  # Never replace or restore administrator-managed layers.
    else:
        map_doc = frappe.get_doc(
            {
                "doctype": "Expedition Map",
                "title": BOARD_MAP_TITLE,
                "basemap_style": "ofm-liberty",
                "viewport": json.dumps({"center": [106.3, 16.2], "zoom": 5.2}),
                "is_public": 1,
                "public_access": "Read Only",
            }
        )
        map_doc.insert(ignore_permissions=True)

    for sequence, (title, color, icon) in enumerate(VISIT_LAYERS, start=1):
        layer = frappe.get_doc(
            {
                "doctype": "Expedition Layer",
                "title": title,
                "enabled": 1,
                "data_source_type": "Client Script (JS)",
                "js_script": _expedition_layer_script_for_visits(title),
                "location_source": "Direct Fields",
                "color": color,
                "icon": icon,
                "size": "m",
                "cluster": 1,
                "click_action": "popup",
                "use_source_permissions": 1,
            }
        )
        layer.insert(ignore_permissions=True)
        map_doc.append(
            "layers", {"layer": layer.name, "sequence": sequence, "enabled": 1}
        )

    technician_layer = frappe.get_doc(
        {
            "doctype": "Expedition Layer",
            "title": "Live Technician Locations",
            "enabled": 1,
            "data_source_type": "Client Script (JS)",
            "js_script": _expedition_layer_script_for_technicians(),
            "location_source": "Direct Fields",
            "color": "#10B981",
            "icon": "pin-truck",
            "size": "l",
            "cluster": 0,
            "click_action": "popup",
            "use_source_permissions": 1,
        }
    )
    technician_layer.insert(ignore_permissions=True)
    map_doc.append(
        "layers", {"layer": technician_layer.name, "sequence": 7, "enabled": 1}
    )
    map_doc.save(ignore_permissions=True)
