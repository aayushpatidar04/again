import frappe


def execute():
    frappe.db.add_index(
        "Live Location", ["technician", "time"], "live_location_technician_time_idx"
    )
