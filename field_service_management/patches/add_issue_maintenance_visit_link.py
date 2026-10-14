import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    create_custom_fields(
        {
            "Issue": [
                {
                    "fieldname": "custom_maintenance_visit",
                    "label": "Maintenance Visit",
                    "fieldtype": "Link",
                    "options": "Maintenance Visit",
                    "insert_after": "customer",
                    "in_list_view": 1,
                    "in_standard_filter": 1,
                    "read_only": 1,
                    "no_copy": 1,
                }
            ]
        },
        update=True,
    )
    frappe.clear_cache(doctype="Issue")
