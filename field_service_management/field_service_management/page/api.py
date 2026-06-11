import frappe
import json


@frappe.whitelist()
def get_cords():
    query = """
    SELECT technician, latitude, longitude, time, employee_name as technician_name
    FROM `tabLive Location` 
    WHERE (technician, time) IN (
        SELECT technician, MAX(time) 
        FROM `tabLive Location` 
        GROUP BY technician
    )
    """
    technicians = frappe.db.sql(query, as_dict=True)

    return technicians


@frappe.whitelist()
def get_live_locations():
    technicians = get_cords()
    maintenance_visits = []

    maintenance_records = frappe.db.sql(
        """
        SELECT name, delivery_addres, customer, maintenance_type, completion_status
        FROM `tabMaintenance Visit`
        WHERE completion_status != 'Fully Completed and docstatus != 2'
    """,
        as_dict=True,
    )

    for visit in maintenance_records:
        visit_doc = frappe.get_doc("Maintenance Visit", visit.name)
        # geolocation

        delivery_note_name = frappe.get_value(
            "Serial No",
            {"custom_item_current_installation_address": visit_doc.delivery_addres},
            "custom_item_current_installation_address_name",
        )

        geolocation = None
        if delivery_note_name:
            address = frappe.get_doc("Address", delivery_note_name)
            geolocation = address.geolocation
            if geolocation:
                # Check if geolocation is a string that needs to be loaded as JSON
                if isinstance(geolocation, str):
                    try:
                        geolocation = json.loads(geolocation)
                    except json.JSONDecodeError:
                        frappe.log_error(
                            f"Invalid geolocation data for address: {address.name}",
                            "Field Service Management",
                        )
                        geolocation = None
                elif not isinstance(geolocation, dict):
                    frappe.log_error(
                        f"Unexpected geolocation format for address: {address.name}",
                        "Field Service Management",
                    )
                    geolocation = None

        maintenance_visits.append(
            {
                "visit_id": visit.name,
                "geolocation": geolocation,
                "address": visit.delivery_addres,
                "customer": visit.customer,
                "type": visit.maintenance_type,
                "status": visit.completion_status,
            }
        )
    return {"technicians": technicians, "maintenance": maintenance_visits}
