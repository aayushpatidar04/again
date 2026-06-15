import frappe
import json
from frappe.contacts.doctype.address.address import get_address_display


MAINTENANCE_VISITS_CACHE_KEY = "fsm:map_maintenance_visits:v1"
MAINTENANCE_VISITS_CACHE_TTL = 60


@frappe.whitelist()
def get_technicians():
    query = """
    SELECT ll.technician, ll.latitude, ll.longitude, ll.time, ll.employee_name AS technician_name
    FROM `tabLive Location` ll
    JOIN (
        SELECT technician, MAX(time) AS latest_time
        FROM `tabLive Location`
        GROUP BY technician
    ) latest
        ON latest.technician = ll.technician
        AND latest.latest_time = ll.time
    JOIN `tabUser` u
        ON u.name = ll.technician
    WHERE u.enabled = 1
    """
    technicians = frappe.db.sql(query, as_dict=True)

    return technicians


@frappe.whitelist()
def get_cords():
    return get_technicians()


def _parse_geolocation(address_name, geolocation):
    if not geolocation:
        return None

    if isinstance(geolocation, dict):
        return geolocation

    if not isinstance(geolocation, str):
        frappe.log_error(
            f"Unexpected geolocation format for address: {address_name}",
            "Field Service Management",
        )
        return None

    try:
        return json.loads(geolocation)
    except json.JSONDecodeError:
        frappe.log_error(
            f"Invalid geolocation data for address: {address_name}",
            "Field Service Management",
        )
        return None


def _get_cached_maintenance_visits():
    cached = frappe.cache().get_value(MAINTENANCE_VISITS_CACHE_KEY)
    if not cached:
        return None

    if isinstance(cached, str):
        try:
            return json.loads(cached)
        except json.JSONDecodeError:
            frappe.cache().delete_value(MAINTENANCE_VISITS_CACHE_KEY)
            return None

    return cached


def _set_cached_maintenance_visits(maintenance_visits):
    frappe.cache().set_value(
        MAINTENANCE_VISITS_CACHE_KEY,
        json.dumps(maintenance_visits),
        expires_in_sec=MAINTENANCE_VISITS_CACHE_TTL,
    )


def get_maintenance_visits(use_cache=True):
    if use_cache:
        cached = _get_cached_maintenance_visits()
        if cached is not None:
            return cached

    maintenance_records = frappe.db.sql(
        """
        SELECT name, delivery_addres, customer, maintenance_type, completion_status
        FROM `tabMaintenance Visit`
        WHERE completion_status != 'Fully Completed'
            AND docstatus != 2
    """,
        as_dict=True,
    )

    if not maintenance_records:
        return []

    delivery_addresses = {
        visit.delivery_addres for visit in maintenance_records if visit.delivery_addres
    }
    customers = {visit.customer for visit in maintenance_records if visit.customer}

    serial_address_by_delivery_address = {}
    if delivery_addresses:
        serial_rows = frappe.get_all(
            "Serial No",
            filters={
                "custom_item_current_installation_address": [
                    "in",
                    list(delivery_addresses),
                ]
            },
            fields=[
                "custom_item_current_installation_address",
                "custom_item_current_installation_address_name",
            ],
        )
        serial_address_by_delivery_address = {
            row.custom_item_current_installation_address: row.custom_item_current_installation_address_name
            for row in serial_rows
            if row.custom_item_current_installation_address
            and row.custom_item_current_installation_address_name
        }

    customer_address_names = {}
    if customers:
        dynamic_links = frappe.get_all(
            "Dynamic Link",
            filters={
                "link_doctype": "Customer",
                "link_name": ["in", list(customers)],
                "parenttype": "Address",
            },
            fields=["parent", "link_name"],
        )
        for link in dynamic_links:
            customer_address_names.setdefault(link.link_name, []).append(link.parent)

    address_names = set(serial_address_by_delivery_address.values())
    for names in customer_address_names.values():
        address_names.update(names)

    addresses_by_name = {}
    if address_names:
        address_rows = frappe.get_all(
            "Address",
            filters={"name": ["in", list(address_names)]},
            fields=["name", "geolocation"],
        )
        addresses_by_name = {row.name: row for row in address_rows}

    display_by_address_name = {}
    unresolved_visits = [
        visit
        for visit in maintenance_records
        if not serial_address_by_delivery_address.get(visit.delivery_addres)
        and visit.delivery_addres
        and visit.customer
    ]
    for visit in unresolved_visits:
        for address_name in customer_address_names.get(visit.customer, []):
            if address_name not in display_by_address_name:
                display_by_address_name[address_name] = get_address_display(
                    address_name
                )
            if display_by_address_name[address_name] == visit.delivery_addres:
                serial_address_by_delivery_address[visit.delivery_addres] = address_name
                break

    maintenance_visits = []
    for visit in maintenance_records:
        address_name = serial_address_by_delivery_address.get(visit.delivery_addres)
        geolocation = None
        if address_name and address_name in addresses_by_name:
            address = addresses_by_name[address_name]
            geolocation = _parse_geolocation(address.name, address.geolocation)

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

    if use_cache:
        _set_cached_maintenance_visits(maintenance_visits)

    return maintenance_visits


@frappe.whitelist()
def get_live_locations():
    technicians = get_technicians()
    maintenance_visits = get_maintenance_visits()
    return {"technicians": technicians, "maintenance": maintenance_visits}


@frappe.whitelist()
def get_live_technicians():
    return get_technicians()


@frappe.whitelist()
def get_map_maintenance_visits():
    return get_maintenance_visits()


@frappe.whitelist()
def clear_map_maintenance_visits_cache():
    frappe.cache().delete_value(MAINTENANCE_VISITS_CACHE_KEY)
    return {"success": True}
