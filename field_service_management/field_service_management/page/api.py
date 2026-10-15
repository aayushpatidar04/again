import frappe
from frappe import _
import json
import hashlib
import re
from frappe.contacts.doctype.address.address import get_address_display


MAINTENANCE_VISITS_CACHE_KEY = "fsm:map_maintenance_visits:v2"
MAINTENANCE_VISITS_CACHE_TTL = 60
# These are scheduling states retained in legacy field options, not visit
# categories that need a separate operational-map layer.
TODAY_BOARD_EXCLUDED_MAP_TYPES = {"Rescheduled", "Unscheduled", "Breakdown"}


def _get_schedule_board_scope():
    """Return the board visibility scope for the current user or deny access."""
    user = frappe.session.user
    roles = frappe.get_roles(user)
    if "BMSCG Admin" in roles:
        return {"is_admin": True, "territories": None}

    role_profile = frappe.db.get_value("User", user, "role_profile_name")
    if role_profile != "Service Coordinator Profile":
        frappe.throw(
            _("You do not have permission to view the schedule board map."),
            frappe.PermissionError,
        )

    territories = frappe.get_all(
        "User Permission",
        filters={"user": user, "allow": "Territory"},
        pluck="for_value",
    )
    return {"is_admin": False, "territories": sorted(set(territories))}


def assert_visible_schedule_board_technician(technician, scope=None):
    """Deny access to schedules for technicians outside the current board scope."""
    scope = scope or _get_schedule_board_scope()
    is_visible_technician = frappe.db.exists(
        "User",
        {
            "name": technician,
            "enabled": 1,
            "role_profile_name": "Service Technician Role Profile",
        },
    )
    is_board_enabled = frappe.db.exists(
        "Employee",
        {"user_id": technician, "custom_display_on_scheduling_board": 1},
    )
    if not is_visible_technician or not is_board_enabled:
        frappe.throw(
            _("This technician is not available on the schedule board."),
            frappe.PermissionError,
        )

    if not scope["is_admin"]:
        technician_territories = frappe.get_all(
            "User Permission",
            filters={
                "user": technician,
                "allow": "Territory",
                "for_value": ["in", scope["territories"] or ["__none__"]],
            },
            pluck="for_value",
        )
        if not technician_territories:
            frappe.throw(
                _("You do not have permission to view this technician schedule."),
                frappe.PermissionError,
            )


def _get_schedule_board_visit_rows(assignment_status, fields):
    """Fetch only the requested assignment state for the schedule-board queue."""
    scope = _get_schedule_board_scope()
    assignment_status = (assignment_status or "unassigned").strip().lower()
    if assignment_status not in {"unassigned", "assigned", "all"}:
        frappe.throw(_("Invalid visit assignment filter."), frappe.ValidationError)

    conditions = ["mv.docstatus != 2"]
    if assignment_status == "unassigned":
        conditions.extend(
            [
                "REPLACE(COALESCE(NULLIF(TRIM(mv._assign), ''), '[]'), ' ', '') IN ('[]', 'null')",
                "NOT EXISTS (SELECT 1 FROM `tabAssigned Tasks` at "
                "WHERE at.issue_code = mv.name)",
            ]
        )
    elif assignment_status == "assigned":
        conditions.append(
            "(REPLACE(COALESCE(NULLIF(TRIM(mv._assign), ''), '[]'), ' ', '') NOT IN ('[]', 'null') "
            "OR EXISTS (SELECT 1 FROM `tabAssigned Tasks` at "
            "WHERE at.issue_code = mv.name))"
        )

    query_values = {}
    if not scope["is_admin"]:
        territories = scope["territories"]
        if not territories:
            return []
        conditions.append("mv.territory IN %(territories)s")
        query_values["territories"] = tuple(territories)

    selected_fields = ", ".join(f"mv.`{field}`" for field in fields)
    return frappe.db.sql(
        f"""
        SELECT {selected_fields}
        FROM `tabMaintenance Visit` mv
        WHERE {' AND '.join(conditions)}
        ORDER BY mv.modified DESC
        """,
        query_values,
        as_dict=True,
    )


def get_unassigned_schedule_board_visit_names():
    """Names used to render the default, unassigned-only board queue."""
    return [
        row.name
        for row in _get_schedule_board_visit_rows("unassigned", ["name"])
    ]


def get_visible_schedule_board_visit_names(visit_names):
    """Return visit names this board user may see in technician schedules."""
    names = list(set(visit_names or []))
    if not names:
        return set()

    scope = _get_schedule_board_scope()
    filters = {"name": ["in", names], "docstatus": ["<", 2]}
    if not scope["is_admin"]:
        if not scope["territories"]:
            return set()
        filters["territory"] = ["in", scope["territories"]]

    return set(frappe.get_all("Maintenance Visit", filters=filters, pluck="name"))


def assert_editable_schedule_board_visit(visit_name):
    """Require board visibility and document write access for assignment changes."""
    visit_name = (visit_name or "").strip()
    if not visit_name or visit_name not in get_visible_schedule_board_visit_names([visit_name]):
        frappe.throw(_("This Maintenance Visit is not available on your schedule board."), frappe.PermissionError)

    visit = frappe.get_doc("Maintenance Visit", visit_name)
    if not frappe.has_permission("Maintenance Visit", "write", doc=visit):
        frappe.throw(_("You cannot change this Maintenance Visit's assignment."), frappe.PermissionError)
    return visit


@frappe.whitelist()
def send_visit_back_to_scheduler(visit_name):
    """Remove every technician booking for a visit and return it to the queue."""
    visit = assert_editable_schedule_board_visit(visit_name)
    visit_name = visit.name

    task_names = frappe.get_all(
        "Assigned Tasks", filters={"issue_code": visit_name}, pluck="name"
    )
    if not task_names and (visit.get("_assign") or "").strip() in ("", "[]", "null"):
        frappe.throw(_("This Maintenance Visit is already unassigned."), frappe.ValidationError)

    for task_name in task_names:
        frappe.delete_doc("Assigned Tasks", task_name, force=True, ignore_permissions=True)

    values = {"_assign": "", "custom_scheduling_status": "Unscheduled"}
    if task_names and visit.get("visit_count") is not None:
        values["visit_count"] = max(int(visit.visit_count or 0) - 1, 0)
    frappe.db.set_value("Maintenance Visit", visit_name, values)
    return {"success": True, "visit_name": visit_name}


@frappe.whitelist()
def get_schedule_board_queue_rows(assignment_status="assigned"):
    """Load assigned/all queue rows only when a user selects those filters."""
    rows = _get_schedule_board_visit_rows(
        assignment_status,
        [
            "name", "subject", "maintenance_type", "completion_status",
            "custom_scheduling_status", "customer", "custom_lead", "mntc_date",
            "mntc_time", "territory", "_assign",
        ],
    )
    if not rows:
        return []

    visit_names = [row.name for row in rows]
    assignment_rows = frappe.get_all(
        "Assigned Tasks",
        filters={"issue_code": ["in", visit_names]},
        fields=["issue_code", "technician"],
    )
    assigned_technicians = {}
    for assignment in assignment_rows:
        if assignment.technician:
            assigned_technicians.setdefault(assignment.issue_code, []).append(
                assignment.technician
            )

    lead_ids = {row.custom_lead for row in rows if row.custom_lead}
    lead_names = {}
    if lead_ids:
        lead_names = {
            lead.name: lead.lead_name
            for lead in frappe.get_all(
                "Lead",
                filters={"name": ["in", list(lead_ids)]},
                fields=["name", "lead_name"],
            )
        }

    queue_rows = []
    can_write_visits = frappe.has_permission("Maintenance Visit", "write")
    for row in rows:
        assigned_from_field = row.get("_assign") or "[]"
        try:
            assigned_from_field = (
                json.loads(assigned_from_field)
                if isinstance(assigned_from_field, str)
                else assigned_from_field
            )
        except (TypeError, json.JSONDecodeError):
            assigned_from_field = [assigned_from_field] if assigned_from_field else []
        if not isinstance(assigned_from_field, list):
            assigned_from_field = []

        technicians = assigned_technicians.get(row.name) or assigned_from_field
        is_assigned = bool(technicians) or row.name in assigned_technicians
        customer = row.customer or ""
        lead = row.custom_lead or ""
        queue_rows.append(
            {
                "name": row.name,
                "subject": row.subject or "",
                "maintenance_type": row.maintenance_type or "",
                "completion_status": row.completion_status or "Pending",
                "customer": customer,
                "custom_lead": lead,
                "party_label": "Customer" if customer else "Lead",
                "party_name": customer or (
                    f"{lead} ({lead_names[lead]})" if lead in lead_names else lead
                ),
                "mntc_date": str(row.mntc_date or ""),
                "mntc_time_display": str(row.mntc_time or "").split(".", 1)[0],
                "territory": row.territory or "",
                "assigned_display": ", ".join(sorted(set(technicians))),
                "is_assigned": is_assigned,
                "can_write": can_write_visits,
            }
        )
    return queue_rows


@frappe.whitelist()
def get_technicians():
    scope = _get_schedule_board_scope()
    conditions = [
        "u.enabled = 1",
        "u.role_profile_name = 'Service Technician Role Profile'",
        "EXISTS (SELECT 1 FROM `tabEmployee` emp "
        "WHERE emp.user_id = u.name AND emp.custom_display_on_scheduling_board = 1)",
    ]
    query_values = {}
    if not scope["is_admin"]:
        territories = scope["territories"]
        if not territories:
            return []
        conditions.append(
            "EXISTS (SELECT 1 FROM `tabUser Permission` up "
            "WHERE up.user = u.name AND up.allow = 'Territory' "
            "AND up.for_value IN %(territories)s)"
        )
        query_values["territories"] = tuple(territories)

    query = f"""
    SELECT ll.technician, ll.latitude, ll.longitude, ll.time,
        ll.employee_name AS technician_name, ll.is_mocked, ll.location_source
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
    WHERE {' AND '.join(conditions)}
    """
    technicians = frappe.db.sql(
        query,
        query_values,
        as_dict=True,
    )

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


def get_maintenance_visits(start_date=None, end_date=None, use_cache=True):
    scope = _get_schedule_board_scope()
    use_global_cache = use_cache and scope["is_admin"]
    # Date-ranged board requests bypass the unfiltered map cache; otherwise a
    # cached all-dates result could leak pins between board users or date windows.
    if use_global_cache and not start_date and not end_date:
        cached = _get_cached_maintenance_visits()
        if cached is not None:
            return cached

    conditions = ["docstatus != 2"]
    query_values = {}
    if start_date:
        conditions.append("mntc_date >= %(start_date)s")
        query_values["start_date"] = start_date
    if end_date:
        conditions.append("mntc_date <= %(end_date)s")
        query_values["end_date"] = end_date
    if not scope["is_admin"]:
        territories = scope["territories"]
        if not territories:
            return []
        conditions.append("territory IN %(territories)s")
        query_values["territories"] = tuple(territories)
    maintenance_records = frappe.db.sql(
        f"""
        SELECT name, delivery_addres, customer, maintenance_type, completion_status, territory
        FROM `tabMaintenance Visit`
        WHERE {' AND '.join(conditions)}
    """,
        query_values,
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
            if address_name not in addresses_by_name:
                # Old Dynamic Links can point at deleted Addresses. They must
                # not break the entire map response for otherwise valid visits.
                continue
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

    if use_global_cache and not start_date and not end_date:
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
def get_map_maintenance_visits(start_date=None, end_date=None):
    """Return visit pins for an optional board map date range."""
    if not start_date and not end_date:
        return get_maintenance_visits()

    try:
        start_date = frappe.utils.getdate(start_date) if start_date else None
        end_date = frappe.utils.getdate(end_date) if end_date else None
    except (TypeError, ValueError):
        frappe.throw(_("Please select a valid map date range."))
    if start_date and end_date and start_date > end_date:
        frappe.throw(_("The map start date must be on or before the end date."))
    return get_maintenance_visits(start_date, end_date, use_cache=False)


@frappe.whitelist()
def get_map_maintenance_visit_types():
    """Return every configured Maintenance Visit type for the map layer controls."""
    maintenance_type_field = frappe.get_meta("Maintenance Visit").get_field(
        "maintenance_type"
    )
    configured_types = []
    if maintenance_type_field and maintenance_type_field.options:
        configured_types = [
            option.strip()
            for option in maintenance_type_field.options.split("\n")
            if option.strip()
        ]

    # Retain a historical/custom value already used by a non-cancelled visit,
    # even if an administrator has subsequently removed it from field options.
    existing_types = frappe.get_all(
        "Maintenance Visit",
        filters={"docstatus": ["!=", 2], "maintenance_type": ["!=", ""]},
        pluck="maintenance_type",
    )
    for visit_type in existing_types:
        if visit_type and visit_type not in configured_types:
            configured_types.append(visit_type)

    return configured_types


def _board_map_visit_coordinates(visit):
    """Kept in the browser-side Expedition layer scripts; this only builds them."""
    return """
const geolocation = row.geolocation;
const items = Array.isArray(geolocation && geolocation.features) ? geolocation.features : [];
for (const item of items) {
  const coordinates = item && item.geometry && item.geometry.coordinates;
  const pointType = item && item.properties && item.properties.point_type;
  if (item && item.geometry && item.geometry.type === 'Point' && pointType !== 'circle'
      && Array.isArray(coordinates) && coordinates.length >= 2) return coordinates;
}
return null;
"""


def _expedition_layer_script_for_visits(visit_type, include_date_range=True):
    """Return an Expedition Client Script layer for one Maintenance Visit type."""
    date_range_args = """,
  args: {
    start_date: options?.context?.map_start_date || undefined,
    end_date: options?.context?.map_end_date || undefined
  }""" if include_date_range else ""
    return """
return frappe.call({
  method: 'field_service_management.field_service_management.page.api.get_map_maintenance_visits'%s
}).then((result) => {
const rows = Array.isArray(result.message) ? result.message : [];
const expectedType = %s;
function coordinatesFor(row) {
  %s
}
return {
  type: 'FeatureCollection',
  features: rows.filter((row) => String(row.type || '') === expectedType).map((row) => {
    const coordinates = coordinatesFor(row);
    if (!coordinates) return null;
    return {
      type: 'Feature',
      geometry: { type: 'Point', coordinates },
      properties: {
        _doctype: 'Maintenance Visit',
        _name: String(row.visit_id || ''),
        _label: String(row.visit_id || 'Maintenance Visit'),
        visit_id: String(row.visit_id || ''),
        maintenance_type: expectedType,
        completion_status: String(row.status || 'Pending'),
        customer: String(row.customer || ''),
        address: String(row.address || '')
      }
    };
  }).filter(Boolean)
};
});
""" % (date_range_args, json.dumps(visit_type), _board_map_visit_coordinates(visit_type))


def _expedition_layer_script_for_technicians():
    """Return the native Expedition layer script for latest technician locations."""
    return """
return frappe.call({
  method: 'field_service_management.field_service_management.page.api.get_live_technicians'
}).then((result) => {
const rows = Array.isArray(result.message) ? result.message : [];
return {
  type: 'FeatureCollection',
  features: rows.map((row) => {
    const latitude = Number(row.latitude);
    const longitude = Number(row.longitude);
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
    const userId = String(row.technician || '');
    return {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [longitude, latitude] },
      properties: {
        _label: userId || String(row.technician_name || 'Technician'),
        technician: userId,
        technician_name: String(row.technician_name || ''),
        time: String(row.time || ''),
        location_source: String(row.location_source || '')
      }
    };
  }).filter(Boolean)
};
});
"""


def _board_layer_colour(key):
    """Stable, sufficiently separated hex colour for an Expedition layer."""
    hue = int(hashlib.sha1(key.encode()).hexdigest()[:8], 16) % 360
    saturation = 0.72
    lightness = 0.42
    chroma = (1 - abs(2 * lightness - 1)) * saturation
    second = chroma * (1 - abs((hue / 60) % 2 - 1))
    red = green = blue = 0
    if hue < 60:
        red, green = chroma, second
    elif hue < 120:
        red, green = second, chroma
    elif hue < 180:
        green, blue = chroma, second
    elif hue < 240:
        green, blue = second, chroma
    elif hue < 300:
        red, blue = second, chroma
    else:
        red, blue = chroma, second
    offset = lightness - chroma / 2
    channels = [round((channel + offset) * 255) for channel in (red, green, blue)]
    return "#" + "".join(f"{channel:02X}" for channel in channels)


def _configured_board_visit_type(layer):
    """Identify a visit type from a map layer's visit-data script, if present."""
    script = layer.get("js_script") or ""
    if (layer.get("data_source_type") != "Client Script (JS)"
            or "get_map_maintenance_visits" not in script):
        return None
    match = re.search(r"const expectedType = (\"(?:\\.|[^\"\\])*\");", script)
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


@frappe.whitelist()
def ensure_today_board_expedition_map():
    """Return the dedicated Today Board map and its configured layer rows.

    Expedition Map is the source of truth for this embedded board.  Do not
    create, delete, or rewrite layer documents here: administrators can add,
    remove, reorder, enable, and configure layers from Expedition itself.
    """
    scope = _get_schedule_board_scope()
    if not frappe.db.exists("DocType", "Expedition Map"):
        return {"name": None, "title": None}

    map_title = "Today Board - Field Operations"
    map_name = frappe.db.get_value("Expedition Map", {"title": map_title}, "name")
    if map_name:
        map_doc = frappe.get_doc("Expedition Map", map_name)
    else:
        map_doc = frappe.get_doc({
            "doctype": "Expedition Map",
            "title": map_title,
            "basemap_style": "light",
            "is_public": 1,
            "public_access": "Read Only",
            "viewport": {"center": [106.3, 16.2], "zoom": 5.2},
        })
        map_doc.insert(ignore_permissions=True)

    from expedition.api.map import list_for_user
    from expedition.api.permission import map_permission
    available_maps = {row.name for row in list_for_user(include_public=1)}
    if not map_permission(map_doc.name, "read") or map_doc.name not in available_maps:
        frappe.throw(
            _("You do not have permission to open the schedule-board map."),
            frappe.PermissionError,
        )

    layer_configs = []
    for row in sorted(map_doc.get("layers", []), key=lambda item: item.sequence or 0):
        if not row.enabled or not row.layer or not frappe.db.exists("Expedition Layer", row.layer):
            continue
        layer = frappe.get_doc("Expedition Layer", row.layer)
        visit_type = _configured_board_visit_type(layer)
        is_technician_layer = (
            layer.data_source_type == "Client Script (JS)"
            and "get_live_technicians" in (layer.js_script or "")
        )
        if not scope["is_admin"] and not (visit_type or is_technician_layer):
            frappe.throw(
                _("The schedule-board map contains a layer outside field operations. "
                  "Ask an administrator to remove it before using the map."),
                frappe.PermissionError,
            )
        layer_configs.append({
            "name": row.layer,
            "title": layer.title or row.layer,
            "visit_type": visit_type,
            "sequence": row.sequence or 0,
            "enabled": 1,
        })

    return {
        "name": map_doc.name,
        "title": map_doc.title,
        "layers": layer_configs,
    }


@frappe.whitelist()
def clear_map_maintenance_visits_cache():
    frappe.cache().delete_value(MAINTENANCE_VISITS_CACHE_KEY)
    return {"success": True}
