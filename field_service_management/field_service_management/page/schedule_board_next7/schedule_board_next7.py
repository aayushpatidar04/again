import frappe
from frappe import _
import json
from datetime import datetime
from datetime import timedelta
from field_service_management.field_service_management.page.api import (
    _get_schedule_board_scope,
    assert_visible_schedule_board_technician,
    get_visible_schedule_board_visit_names,
)


def format_board_datetime(value):
    """Drop fractional seconds from values displayed on the Today board."""
    return str(value).split(".", 1)[0] if value else ""


def format_board_time(value):
    """Return a browser-compatible 24-hour time value for time inputs."""
    if value is None or value == "":
        return ""
    if isinstance(value, timedelta):
        total_minutes = int(value.total_seconds() // 60)
        hours, minutes = divmod(total_minutes, 60)
        return f"{hours:02d}:{minutes:02d}"
    parts = str(value).split(".", 1)[0].split(":")
    try:
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
    except (IndexError, TypeError, ValueError):
        return str(value)




@frappe.whitelist()
def get_context(context=None, board_date=None):
 context = context or {}
 user = frappe.session.user
 from field_service_management.field_service_management.page.api import get_unassigned_schedule_board_visit_names
 role_profile = frappe.db.get_value("User", user, "role_profile_name")
 board_roles = frappe.get_roles(user)
 unassigned_visit_names = (
     get_unassigned_schedule_board_visit_names()
     if "BMSCG Admin" in board_roles or role_profile == "Service Coordinator Profile"
     else []
 )




 issues = []
 lead_issues = []
 technicians = []
 maintenance_visit_fields = [
     "name", "subject", "status", "creation", "maintenance_type",
     "custom_scheduling_status", "_assign", "completion_status",
     "customer", "custom_lead", "mntc_date", "mntc_time", "territory",
 ]




 territory_options = []
 if "BMSCG Admin" in board_roles:
     territory_options = sorted(frappe.get_all("Territory", pluck="name"))
     issues = frappe.get_all(
         "Maintenance Visit",
         filters={"name": ["in", unassigned_visit_names], "docstatus": ["!=", 2]},
         fields=maintenance_visit_fields,
     ) if unassigned_visit_names else []
     # OLD: All assigned visits were loaded into `lead_issues`, although the
     # Today board template does not render that collection. Calendar entries
     # are loaded from Assigned Tasks below.
     technicians = frappe.get_all(
         "User",
         filters={"role_profile_name": "Service Technician Role Profile"},
         fields=["email", "user_image", "full_name"],
     )
 if role_profile == "Service Coordinator Profile":
     territories = frappe.db.get_all(
         "User Permission",
         filters={"user": user, "allow": "Territory"},
         fields=["for_value"]
     )
     territory_list = [t["for_value"] for t in territories]
     territory_options = sorted(set(territory_list))
     if territory_options and unassigned_visit_names:
         issues = frappe.get_all(
             "Maintenance Visit",
             filters={"name": ["in", unassigned_visit_names], "territory": ["in", territory_options], "docstatus": ["!=", 2]},
             fields=maintenance_visit_fields,
         )
     # OLD: Assigned Maintenance Visits were redundantly loaded here. The
     # technician calendar uses Assigned Tasks and remains unchanged.
     technicians = frappe.get_all(
         "User",
         filters={"role_profile_name": "Service Technician Role Profile"},
         fields=["email", "user_image", "full_name"],
     )
     # OLD: A separate User Permission query ran for every technician.
     technician_emails = [tech.email for tech in technicians]
     permitted_technician_emails = set()
     if technician_emails:
         permitted_technician_emails = set(frappe.get_all(
             "User Permission",
             filters={
                 "user": ["in", technician_emails],
                 "allow": "Territory",
                 "for_value": ["in", territory_list],
             },
             pluck="user",
         ))
     technicians = [
         tech for tech in technicians
         if tech.email in permitted_technician_emails
     ]




 # Only show technicians explicitly enabled on their Employee record.
 technician_emails = [tech.email for tech in technicians]
 if technician_emails:
     displayable_emails = set(frappe.get_all(
         "Employee",
         filters={
             "user_id": ["in", technician_emails],
             "custom_display_on_scheduling_board": 1,
         },
         pluck="user_id",
     ))
     technicians = [tech for tech in technicians if tech.email in displayable_emails]

 lead_ids = {issue.custom_lead for issue in issues if issue.custom_lead}
 lead_name_by_id = {}
 if lead_ids:
     lead_name_by_id = {
         lead.name: lead.lead_name
         for lead in frappe.get_all(
             "Lead",
             filters={"name": ["in", list(lead_ids)]},
             fields=["name", "lead_name"],
         )
     }


 def group_by(rows, fieldname):
     grouped_rows = {}
     for row in rows:
         grouped_rows.setdefault(row.get(fieldname), []).append(row)
     return grouped_rows


 # The queue only needs summary fields. Fetch child tables and related details
 # from get_maintenance_visit_board_details when the user opens a visit.
 address_geolocation_by_name = {}
 checklist_by_visit = {}
 products_by_visit = {}
 spare_items_by_visit = {}
 symptoms_by_visit = {}
 comments_by_visit = {}
 attachments_by_visit = {}
 symptom_requests_by_visit = {}
 sub_step_work_logs_by_visit = {}




 # OLD: def enrich_issue(issue):
 def enrich_issue(issue, include_inline_details=False):
     issue.can_write = frappe.has_permission("Maintenance Visit", "write", doc=issue.name)
     issue.mntc_time_display = format_board_datetime(issue.mntc_time)
     issue.creation_display = format_board_datetime(issue.creation)
     if issue.customer:
         issue.party_label = "Customer"
         issue.party_name = issue.customer
     elif issue.custom_lead:
         issue.party_label = "Lead"
         lead_name = lead_name_by_id.get(issue.custom_lead)
         issue.party_name = (
             f"{issue.custom_lead} ({lead_name})"
             if lead_name else issue.custom_lead
         )
     else:
         issue.party_label = "Customer"
         issue.party_name = ""

     address_display = (issue.address_display or "").replace("<br>", ", ").replace("<br />", ", ")
     contact_display = (issue.contact_display or "").replace("<br>", ", ").replace("<br />", ", ")
     issue.address_text = frappe.utils.strip_html(address_display).strip(" ,")
     issue.contact_text = frappe.utils.strip_html(contact_display).strip(" ,")

     if issue._assign:
         try:
             assign_list = json.loads(issue._assign)
             issue.assigned = assign_list
             issue._assign = " | ".join(assign_list)
         except json.JSONDecodeError:
             issue._assign = "No one assigned"
     else:
         issue._assign = "No one assigned"




     geolocation = address_geolocation_by_name.get(issue.customer_address)
     if geolocation:
         geo = json.loads(geolocation)
         issue.geolocation = json.dumps(geo.get('features', [])).replace('"', "'")
     else:
         issue.geolocation = None




     checklist = checklist_by_visit.get(issue.name, [])

     def parse_sub_steps(value):
         if not value:
             return []
         try:
             parsed = json.loads(value) if isinstance(value, str) else value
         except (TypeError, ValueError, json.JSONDecodeError):
             return []
         if isinstance(parsed, dict):
             for key in ("sub_steps", "steps", "data"):
                 if isinstance(parsed.get(key), list):
                     return parsed.get(key)
             return []
         return parsed if isinstance(parsed, list) else []

     def get_sub_step_label(sub_step):
         if not isinstance(sub_step, dict):
             return str(sub_step or "Sub-step")
         for fieldname in (
             "sub_step", "sub_step_description", "sub_step_text",
             "sub_step_label", "description", "heading", "activity", "title",
             "subject", "step", "step_name", "name", "sub_step_name",
         ):
             value = sub_step.get(fieldname)
             if value:
                 return str(value)
         return "Sub-step"

     def is_sub_step_completed(sub_step):
         if not isinstance(sub_step, dict):
             return False
         status = (
             sub_step.get("work_done")
             or sub_step.get("completed")
             or sub_step.get("is_completed")
             or sub_step.get("status")
         )
         return str(status).strip().lower() in (
             "yes", "true", "1", "completed", "fully completed"
         )

     checklist_tree = {}
     for problem in checklist:
         checklist_tree.setdefault(problem.item_code, []).append(problem)
     completed_checklist_rows = len([
         row for row in checklist if row.work_done == "Yes"
     ])
     issue.progress_percentage = (
         round((completed_checklist_rows / len(checklist)) * 100)
         if checklist else 0
     )
     sub_step_work_logs = sub_step_work_logs_by_visit.get(issue.name, [])
     work_logs_by_checklist = {}
     for work_log in sub_step_work_logs:
         work_logs_by_checklist.setdefault(
             work_log.get("parent_checklist_row"), []
         ).append(work_log)

     def find_sub_step_work_log(checklist_row_name, sub_step):
         if not isinstance(sub_step, dict):
             sub_step = {"name": str(sub_step)}
         sub_step_names = {
             str(value).strip()
             for value in (
                 sub_step.get("name"),
                 sub_step.get("sub_step_name"),
                 sub_step.get("sub_step_original_name"),
             )
             if value
         }
         for work_log in work_logs_by_checklist.get(checklist_row_name, []):
             log_names = {
                 str(value).strip()
                 for value in (
                     work_log.get("sub_step_name"),
                     work_log.get("sub_step_original_name"),
                 )
                 if value
             }
             if sub_step_names.intersection(log_names):
                 return work_log
             if (
                 sub_step.get("idx")
                 and work_log.get("idx") == sub_step.get("idx")
             ):
                 return work_log
         return None

     def render_status_badge(completed):
         status_class = "is-complete" if completed else "is-pending"
         status_label = "Completed" if completed else "Pending"
         return (
             f'<span class="checklist-status-badge {status_class}">'
             f'{status_label}</span>'
         )

     def render_image_button(image_url, label="View image"):
         if not image_url:
             return ""
         escaped_image_url = frappe.utils.escape_html(str(image_url))
         escaped_label = frappe.utils.escape_html(label)
         return (
             f'<button type="button" class="checklist-preview-image-button" '
             f'data-image="{escaped_image_url}">{escaped_label}</button>'
         )

     # OLD: Checklist headings and sub-steps were rendered as a permanently
     # expanded list of disabled checkboxes without work-log details or images.
     html_content = ""
     checklist_step_counter = 0
     for item_code, products in checklist_tree.items():
         if products:
             escaped_item_code = frappe.utils.escape_html(item_code or "")
             item_code_link = (
                 f'<a href="/app/item/{escaped_item_code}" target="_blank" '
                 f'rel="noopener">{escaped_item_code}</a>'
                 if item_code else "Not specified"
             )
             escaped_item_name = frappe.utils.escape_html(products[0].item_name or "")
             html_content += (
                 f'<section class="checklist-preview-group">'
                 f'<h6 class="checklist-preview-title">{item_code_link}: {escaped_item_name}</h6>'
             )
             for product in products:
                 checklist_step_counter += 1
                 step_body_id = (
                     f'checklist-step-{frappe.scrub(issue.name)}-'
                     f'{checklist_step_counter}'
                 )
                 parent_completed = product.work_done == "Yes"
                 escaped_heading = frappe.utils.escape_html(product.heading or "Checklist item")
                 escaped_serial_no = frappe.utils.escape_html(
                     product.get("serial_no") or "Not specified"
                 )
                 serial_no_display = (
                     f'<a href="/app/serial-no/{escaped_serial_no}" target="_blank" '
                     f'rel="noopener">{escaped_serial_no}</a>'
                     if product.get("serial_no") else escaped_serial_no
                 )
                 escaped_periodicity = frappe.utils.escape_html(
                     product.get("periodicity") or "Not specified"
                 )
                 escaped_location = frappe.utils.escape_html(
                     product.get("item_location") or "Not specified"
                 )
                 escaped_done_by = frappe.utils.escape_html(
                     product.get("done_by") or "Not completed"
                 )
                 escaped_remark = frappe.utils.escape_html(
                     product.get("remark") or "No remark"
                 )
                 details = product.get("details") or ""
                 safe_details = frappe.utils.sanitize_html(details)
                 parent_image = (
                     product.get("attachment") or product.get("checklist_image")
                 )
                 html_content += (
                     f'<article class="checklist-preview-step-card">'
                     f'<button type="button" class="checklist-preview-step-toggle" '
                     f'aria-expanded="false" aria-controls="{step_body_id}">'
                     f'<span class="checklist-preview-chevron" aria-hidden="true">&#9656;</span>'
                     f'<span class="checklist-preview-step-heading">{escaped_heading}</span>'
                     f'{render_status_badge(parent_completed)}'
                     f'</button>'
                     f'<div class="checklist-preview-step-body" id="{step_body_id}" hidden>'
                     f'<div class="checklist-preview-metadata">'
                     f'<span><strong>Serial No:</strong> {serial_no_display}</span>'
                     f'<span><strong>Periodicity:</strong> {escaped_periodicity}</span>'
                     f'<span><strong>Location:</strong> {escaped_location}</span>'
                     f'<span><strong>Done By:</strong> {escaped_done_by}</span>'
                     f'</div>'
                 )

                 if safe_details:
                     html_content += (
                         f'<div class="checklist-preview-details"><strong>Task List:</strong>'
                         f'<div>{safe_details}</div></div>'
                     )

                 html_content += (
                     f'<div class="checklist-preview-parent-footer">'
                     f'<span><strong>Remark:</strong> {escaped_remark}</span>'
                     f'{render_image_button(parent_image, "View checklist image")}'
                     f'</div>'
                 )

                 json_sub_steps = parse_sub_steps(product.get("sub_steps_json"))
                 if not json_sub_steps:
                     json_sub_steps = parse_sub_steps(
                         product.get("sub_steps_format_for_mobile_apk")
                     )

                 html_content += (
                     '<div class="checklist-preview-substeps">'
                     '<div class="checklist-preview-substeps-title">Sub-steps</div>'
                 )

                 for sub_step in json_sub_steps:
                     if not isinstance(sub_step, dict):
                         sub_step = {"name": str(sub_step)}
                     work_log = find_sub_step_work_log(product.name, sub_step)
                     work_log_status = work_log.get("work_done") if work_log else None
                     sub_step_completed = (
                         str(work_log_status).strip().lower() == "yes"
                         if work_log_status else is_sub_step_completed(sub_step)
                     )
                     sub_label = frappe.utils.escape_html(get_sub_step_label(sub_step))
                     sub_done_by = frappe.utils.escape_html(
                         (work_log.get("done_by") if work_log else None)
                         or sub_step.get("done_by")
                         or "Not completed"
                     )
                     sub_remark = frappe.utils.escape_html(
                         (work_log.get("remark") if work_log else None)
                         or sub_step.get("remark")
                         or ""
                     )
                     sub_image = (
                         (work_log.get("attachment") if work_log else None)
                         or sub_step.get("image")
                         or sub_step.get("attachment")
                     )
                     html_content += (
                         f'<div class="checklist-preview-substep">'
                         f'<div class="checklist-preview-substep-main">'
                         f'<span>{sub_label}</span>'
                         f'{render_status_badge(sub_step_completed)}'
                         f'</div>'
                         f'<div class="checklist-preview-substep-meta">'
                         f'<span><strong>Done By:</strong> {sub_done_by}</span>'
                         f'{f"<span><strong>Remark:</strong> {sub_remark}</span>" if sub_remark else ""}'
                         f'{render_image_button(sub_image, "View image")}'
                         f'</div></div>'
                     )

                 if not json_sub_steps:
                     html_content += (
                         '<div class="maintenance-inline-empty compact">'
                         'No sub-steps are available for this checklist item.</div>'
                     )

                 html_content += "</div></div></article>"
             html_content += "</section>"
     issue.checklist_tree = html_content




     issue.products = products_by_visit.get(issue.name, [])
     issue.spare_items = spare_items_by_visit.get(issue.name, [])




     symptoms = symptoms_by_visit.get(issue.name, [])
     issue.symptoms = symptoms
     symptoms_res = {}
     for symptom in symptoms:
         symptoms_res.setdefault(symptom.item_code, []).append(symptom)
     html_content = ""
     for item_code, resolutions in symptoms_res.items():
         if resolutions:
             escaped_item_code = frappe.utils.escape_html(item_code or "Not specified")
             item_code_link = (
                 f'<a href="/app/item/{escaped_item_code}" target="_blank" '
                 f'rel="noopener">{escaped_item_code}</a>'
                 if item_code else "Not specified"
             )
             html_content += f"<p><strong>{item_code_link}:</strong></p>"
             for resolution in resolutions:
                 html_content += (f"<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                                   f"<img src='{resolution.image}' style='max-width: 100px;'> --> "
                                   f"<strong>{resolution.symptom_code}</strong> --> {resolution.resolution}<br>")
             html_content += "</p>"
     issue.symptoms_res = html_content


     # Inline detail panel data is needed only for Maintenance Visit rows.
     # Avoid these queries for the separate Lead list, which can be very large.
     if include_inline_details:
         issue.comments = comments_by_visit.get(issue.name, [])
         for comment in issue.comments:
             comment.creation_display = format_board_datetime(comment.creation)
         issue.attachments = attachments_by_visit.get(issue.name, [])
         issue.symptom_requests = symptom_requests_by_visit.get(issue.name, [])
     else:
         issue.comments = []
         issue.attachments = []
         issue.symptom_requests = []




 visit_names_for_assignment = [issue.name for issue in issues]
 assigned_visit_names = set()
 assigned_technicians_by_visit = {}
 if visit_names_for_assignment:
     assigned_task_rows = frappe.get_all(
         "Assigned Tasks",
         filters={"issue_code": ["in", visit_names_for_assignment]},
         fields=["issue_code", "technician"],
     )
     for assignment in assigned_task_rows:
         assigned_visit_names.add(assignment.issue_code)
         if assignment.technician:
             assigned_technicians_by_visit.setdefault(assignment.issue_code, []).append(assignment.technician)

 for issue in issues:
     assigned_users = issue.get("_assign") or "[]"
     try:
         assigned_users = json.loads(assigned_users) if isinstance(assigned_users, str) else assigned_users
     except (TypeError, json.JSONDecodeError):
         assigned_users = [assigned_users] if assigned_users else []
     issue.is_assigned = bool(assigned_users) or issue.name in assigned_visit_names
     enrich_issue(issue, include_inline_details=False)
     if issue.is_assigned:
         assigned_labels = issue.get("assigned") or assigned_technicians_by_visit.get(issue.name, [])
         issue.assigned_display = ", ".join(sorted(set(assigned_labels)))
 # OLD: Assigned visits were fully enriched even though `lead_issues` is not
 # rendered by this page, causing unnecessary child-table queries and work.




 context["issues"] = issues
 context["territory_options"] = territory_options
 context["lead_issues"] = lead_issues
 completion_field = frappe.get_meta("Maintenance Visit").get_field("completion_status")
 context["completion_status_options"] = [
     option.strip()
     for option in (completion_field.options or "").splitlines()
     if option.strip()
 ] if completion_field else []




 today_date = frappe.utils.getdate()
 requested_board_date = board_date or frappe.form_dict.get("board_date")
 date = today_date
 if requested_board_date:
     try:
         requested_date = datetime.strptime(str(requested_board_date), "%Y-%m-%d").date()
         if today_date <= requested_date <= today_date + timedelta(days=6):
             date = requested_date
     except (TypeError, ValueError):
         pass
 context["board_date"] = date.isoformat()
 context["today_date"] = today_date.isoformat()
 context["calendar_dates"] = [
     {
         "iso": (today_date + timedelta(days=offset)).isoformat(),
         "label": (today_date + timedelta(days=offset)).strftime("%a %d %b"),
         "selected": (today_date + timedelta(days=offset)) == date,
     }
     for offset in range(7)
 ]


 # Summary data and the calendar remain scoped to today; the visit list keeps
 # its original behavior without a date filter.
 visit_summary = frappe.db.sql(
     """
     SELECT
         COUNT(*) AS total_visits,
         SUM(CASE WHEN custom_scheduling_status = 'Unscheduled' THEN 1 ELSE 0 END) AS unscheduled,
         SUM(CASE WHEN completion_status = 'Partially Completed' THEN 1 ELSE 0 END) AS in_progress,
         SUM(CASE WHEN completion_status = 'Fully Completed' THEN 1 ELSE 0 END) AS completed
     FROM `tabMaintenance Visit`
     WHERE mntc_date = %s
       AND docstatus != 2
     """,
     (date,),
     as_dict=True,
 )[0]
 context["visit_summary"] = {
     "total_visits": visit_summary.total_visits or 0,
     "unscheduled": visit_summary.unscheduled or 0,
     "in_progress": visit_summary.in_progress or 0,
     "completed": visit_summary.completed or 0,
 }


 # Build one summary card for every configured Maintenance Visit Type. Types
 # found on existing records are retained even if an option was later removed.
 visit_type_counts = frappe.db.sql(
     """
     SELECT
         COALESCE(NULLIF(maintenance_type, ''), 'Not specified') AS visit_type,
         COUNT(*) AS visit_count
     FROM `tabMaintenance Visit`
     WHERE mntc_date = %s
       AND docstatus != 2
     GROUP BY COALESCE(NULLIF(maintenance_type, ''), 'Not specified')
     """,
     (date,),
     as_dict=True,
 )
 visit_type_count_by_name = {
     row.visit_type: row.visit_count for row in visit_type_counts
 }
 maintenance_type_field = frappe.get_meta("Maintenance Visit").get_field("maintenance_type")
 configured_visit_types = []
 if maintenance_type_field and maintenance_type_field.options:
     configured_visit_types = [
         option.strip()
         for option in maintenance_type_field.options.split("\n")
         if option.strip()
     ]
 for visit_type in visit_type_count_by_name:
     if visit_type not in configured_visit_types:
         configured_visit_types.append(visit_type)
 context["visit_type_summary"] = [
     {
         "label": visit_type,
         "count": visit_type_count_by_name.get(visit_type, 0),
     }
     for visit_type in configured_visit_types
 ]




 # Same half-hour grid as the Next 7 Days board (READ-ONLY from here on).
 BASE_TIME_SLOTS = []
 for h in range(9, 21):
     BASE_TIME_SLOTS.append({"label": f"{h:02d}", "display_label": f"{h:02d}", "time": timedelta(hours=h), "is_hour": True})
     if h != 20:
         BASE_TIME_SLOTS.append({"label": "", "display_label": "", "time": timedelta(hours=h, minutes=30), "is_hour": False})




 slot_width_percent = 100 / len(BASE_TIME_SLOTS)




 assigned_tasks_today = frappe.get_all(
     "Assigned Tasks",
     filters={"date": date},
     fields=["issue_code", "stime", "etime", "technician"],
     order_by="technician, stime",
 )
 task_issue_codes = {task.issue_code for task in assigned_tasks_today if task.issue_code}
 visible_visit_names = (
     get_visible_schedule_board_visit_names(task_issue_codes)
     if technicians else set()
 )
 visible_tasks = [
     task for task in assigned_tasks_today if task.issue_code in visible_visit_names
 ]
 hidden_tasks = [
     task for task in assigned_tasks_today if task.issue_code not in visible_visit_names
 ]
 tasks_by_technician = group_by(visible_tasks, "technician")
 hidden_tasks_by_technician = group_by(hidden_tasks, "technician")




 def get_not_available(slot_time):
     return [t.technician for t in assigned_tasks_today if t.stime <= slot_time < t.etime]




 # OLD: Each task loaded its Maintenance Visit document separately.
 maintenance_assignments_by_issue = {}
 if visible_visit_names:
     maintenance_assignments_by_issue = {
         row.name: row._assign
         for row in frappe.get_all(
             "Maintenance Visit",
             filters={"name": ["in", list(visible_visit_names)]},
             fields=["name", "_assign"],
         )
     }

 def get_maintenance_doc(issue_code):
     return frappe._dict(
         _assign=maintenance_assignments_by_issue.get(issue_code)
     )


 # Load employee links and approved leave once for the complete technician list.
 technician_emails = [tech.email for tech in technicians]
 employee_by_email = {}
 if technician_emails:
     employee_fields = ["employee", "user_id", "prefered_email"]
     employee_rows = frappe.get_all(
         "Employee",
         filters={"user_id": ["in", technician_emails]},
         fields=employee_fields,
     )
     employees_by_name = {row.employee: row for row in employee_rows}
     for employee_row in frappe.get_all(
         "Employee",
         filters={"prefered_email": ["in", technician_emails]},
         fields=employee_fields,
     ):
         employees_by_name[employee_row.employee] = employee_row
     employee_rows = list(employees_by_name.values())
     for employee_row in employee_rows:
         if employee_row.user_id:
             employee_by_email[employee_row.user_id] = employee_row.employee
         if employee_row.prefered_email:
             employee_by_email[employee_row.prefered_email] = employee_row.employee

 employee_ids = list({
     employee for employee in employee_by_email.values() if employee
 })
 leaves_by_employee = {}
 if employee_ids:
     leaves_by_employee = group_by(
         frappe.get_all(
             "Leave Application",
             filters={
                 "employee": ["in", employee_ids],
                 "status": "Approved",
                 "from_date": ["<=", date],
                 "to_date": [">=", date],
             },
             fields=[
                 "employee", "description", "half_day", "from_date",
                 "to_date", "select_half_day",
             ],
         ),
         "employee",
     )




 LUNCH_START = timedelta(hours=12)
 LUNCH_END = timedelta(hours=13)




 for tech in technicians:
     html_content = ""
     # OLD: Assigned Tasks were queried again for every technician.
     tasks = tasks_by_technician.get(tech.email, [])
     unavailable_tasks = hidden_tasks_by_technician.get(tech.email, [])
     for task in tasks:
         time_diff = task.etime - task.stime
         task.duration_in_hours = time_diff.total_seconds() / 3600
         task.flag = 0
     for task in unavailable_tasks:
         task.flag = 0
     tech.tasks = tasks




     total_hours = 0




     # OLD: Employee and leave records were queried separately per technician.
     employee = employee_by_email.get(tech.email)
     leaves = leaves_by_employee.get(employee, []) if employee else []




     full_day_leave = None
     morning_leave = None
     afternoon_leave = None
     for leave in leaves:
         if leave.half_day == 1:
             if leave.select_half_day == 'Morning':
                 morning_leave = leave
             else:
                 afternoon_leave = leave
         else:
             full_day_leave = leave




     if full_day_leave:
         leave_text = full_day_leave.description or "Leave"
         html_content += (f'<div style="width: 100%; border-right: 1px solid #fff; color: white; '
                           f'background-color: #7c3aed; border-radius: 4px; overflow: hidden; '
                           f'white-space: nowrap; text-overflow: ellipsis; text-align: center;" '
                           f'data-tech="{tech.email}" class="px-1" title="{leave_text}">'
                           f'{leave_text}</div>')
         tech.html_content = html_content
         tech.total_hours = 0
         continue




     if morning_leave:
         leave_text = morning_leave.description or "Leave"
         html_content += (f'<div style="width: {slot_width_percent * 6}%; border-right: 1px solid #fff; color: white; '
                           f'background-color: #7c3aed; border-radius: 4px; overflow: hidden; '
                           f'white-space: nowrap; text-overflow: ellipsis; text-align: center;" '
                           f'data-tech="{tech.email}" class="px-1" title="{leave_text}">'
                           f'{leave_text}</div>')




     i = 0
     while i < len(BASE_TIME_SLOTS):
         slot = BASE_TIME_SLOTS[i]
         slot_time = slot['time']




         if morning_leave and slot_time < LUNCH_START:
             i += 1
             continue




         if slot_time == LUNCH_START:
             lunch_slots = int((LUNCH_END - LUNCH_START).total_seconds() // 1800)
             lunch_width = lunch_slots * slot_width_percent
             html_content += (f'<div style="width: {lunch_width}%; border-right: 1px solid #fff; color: white; '
                               f'background-color: #f59e0b; border-radius: 4px; overflow: hidden; '
                               f'white-space: nowrap; text-overflow: ellipsis; text-align: center;" '
                               f'data-time="{slot_time}" data-tech="{tech.email}" class="px-1" '
                               f'title="Lunch Break">Lunch</div>')
             i += lunch_slots
             continue




         if LUNCH_START < slot_time < LUNCH_END:
             i += 1
             continue




         if afternoon_leave and slot_time >= LUNCH_END:
             leave_text = afternoon_leave.description or "Leave"
             html_content += (f'<div style="width: {slot_width_percent * 15}%; border-right: 1px solid #fff; color: white; '
                               f'background-color: #7c3aed; border-radius: 4px; overflow: hidden; '
                               f'white-space: nowrap; text-overflow: ellipsis; text-align: center;" '
                               f'data-tech="{tech.email}" class="px-1" title="{leave_text}">'
                               f'{leave_text}</div>')
             break




         task_in_slot = None
         for task in tasks:
             if task.flag == 0 and task.stime <= slot_time < task.etime:
                 task_in_slot = task
                 task.flag = 1
                 break




         if task_in_slot:
             maintenance = get_maintenance_doc(task_in_slot['issue_code'])
             total_hours += task_in_slot['duration_in_hours']
             html_content += f"""
             <div style="width: {task_in_slot['duration_in_hours'] * 2 * slot_width_percent}%; background-color: #ef4444; border-right: 1px solid #fff; border-radius: 4px; overflow: hidden; cursor: pointer;" class="px-1 py-2 text-white text-center drag calendar-task-card" data-type="type2" data-issue="{task_in_slot['issue_code']}" draggable="true" id="task-{task_in_slot['issue_code']}" data-duration="{task_in_slot['duration_in_hours']}" data-modal-id="taskModaltask-{task_in_slot['issue_code']}" title="{task_in_slot['issue_code']}" role="button" tabindex="0">
                 <a href="javascript:void(0)"
                     class="text-white" data-id="taskModaltask-{task_in_slot['issue_code']}" style="display: block; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{task_in_slot['issue_code']}</a>
             </div>
             """
             html_content += f"""
             <div class="modal calendar-task-modal hide" id="taskModaltask-{task_in_slot['issue_code']}" tabindex="-1" role="dialog"
                 aria-labelledby="taskModalLabel{task_in_slot['issue_code']}" aria-hidden="true">
                 <div class="modal-dialog schedule-board-form-dialog" role="document">
                     <div class="modal-content schedule-board-form-content">
                         <div class="modal-header schedule-board-form-header">
                             <div>
                                 <div class="calendar-task-kicker">Schedule maintenance visit</div>
                                 <h5 class="modal-title" id="taskModalLabel{task_in_slot['issue_code']}">{task_in_slot['issue_code']}</h5>
                             </div>
                             <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                                 <span aria-hidden="true">&times;</span>
                             </button>
                         </div>
                         <div class="modal-body schedule-board-form-body">
                             <form id="custom2-form-{task_in_slot['issue_code']}" class="custom-form calendar-task-form" method="POST">
                                 <div class="calendar-task-field-group">
                                     <label class="calendar-task-label" for="code-{task_in_slot['issue_code']}">Maintenance visit code</label>
                                     <input id="code-{task_in_slot['issue_code']}" class="form-control code clickable-code calendar-task-readonly" type="text" name="code" value="{task_in_slot['issue_code']}" required
                                         readonly onclick="window.open('/app/maintenance-visit/{task_in_slot['issue_code']}', '_blank')">
                                 </div>
                                 <div class="calendar-task-field-group">
                                     <label class="calendar-task-label" for="technician-{task_in_slot['issue_code']}">Co-technicians <span class="calendar-task-help">Optional, use when more than one technician is needed</span></label>
                                 <select id="technician-{task_in_slot['issue_code']}" class="form-select technician" style="width:100%" name="technician[]" multiple="multiple" size="4" required>"""
             for item in technicians:
                 selected = 'selected' if maintenance._assign and item.email in maintenance._assign else ''
                 technician_label = item.full_name or item.email
                 html_content += f'<option value="{item.email}" {selected}>{technician_label} ({item.email})</option>'
             html_content += """ </select>
                                 </div>
                                 <div class="calendar-task-time-grid">
                                     <div class="calendar-task-field-group">
                                         <label class="calendar-task-label" for="date-{issue_code}">Date</label>
                                         <input id="date-{issue_code}" class="form-control date" type="date" name="date" value="{date}" required>
                                     </div>
                                     <div class="calendar-task-field-group">
                                         <label class="calendar-task-label" for="stime-{issue_code}">Start time</label>
                                         <input id="stime-{issue_code}" class="form-control stime calendar-task-readonly" type="time" name="stime" value="{stime}" required readonly>
                                     </div>
                                     <div class="calendar-task-field-group">
                                         <label class="calendar-task-label" for="etime-{issue_code}">End time</label>
                                         <input id="etime-{issue_code}" class="form-control etime" type="time" name="etime" value="{etime}" required readonly step="1800">
                                     </div>
                                 </div>
                                 <div class="calendar-task-error"><small><span class="text-danger etime-error"></span></small></div>
                                 <div class="calendar-task-footer">
                                     <button type="button" class="calendar-task-cancel">Cancel</button>
                                     <button type="button" class="update btn calendar-task-submit"
                                         data-issue="{issue_code}">Save changes</button>
                                 </div>
                             </form>
                         </div>
                     </div>
                 </div>
             </div>""".format(issue_code=task_in_slot['issue_code'], date=date,
                               stime=format_board_time(task_in_slot['stime']),
                               etime=format_board_time(task_in_slot['etime']))




             end_time = task_in_slot['etime']
             while i < len(BASE_TIME_SLOTS) and BASE_TIME_SLOTS[i]['time'] < end_time:
                 i += 1
             continue




         # Keep other-territory bookings occupied without exposing their visit details.
         unavailable_task = next(
             (task for task in unavailable_tasks
              if task.flag == 0 and task.stime <= slot_time < task.etime),
             None,
         )
         if unavailable_task:
             unavailable_task.flag = 1
             next_slot = i
             while (next_slot < len(BASE_TIME_SLOTS)
                    and BASE_TIME_SLOTS[next_slot]['time'] < unavailable_task.etime):
                 next_slot += 1
             busy_width = (next_slot - i) * slot_width_percent
             total_hours += (next_slot - i) * 0.5
             html_content += (
                 f'<div style="width: {busy_width}%; min-height: 40px; '
                 f'background-color: #64748b; border-right: 1px solid #fff; '
                 f'border-radius: 4px; color: white; text-align: center; '
                 f'overflow: hidden; white-space: nowrap; text-overflow: ellipsis;" '
                 f'class="px-1 py-2 calendar-unavailable" title="Unavailable" '
                 f'aria-label="Unavailable">Busy</div>'
             )
             i = next_slot
             continue

         not_available = get_not_available(slot_time)
         html_content += (f'<div style="width: {slot_width_percent}%; border-right: 1px solid #bae6fd; '
                           f'background-color: #e0f2fe; min-height: 40px;" data-time="{slot_time}" '
                           f'data-date="{date}" data-tech="{tech.email}" data-na="{not_available}" '
                           f'class="px-1 drop-zone" title="Available">&nbsp;</div>')
         i += 1




     tech.html_content = html_content
     tech.total_hours = round(total_hours / 11 * 100, 2)




 context["technicians"] = technicians
 context["slots"] = BASE_TIME_SLOTS
 context["message"] = "Welcome to your schedule board!"
 return context




@frappe.whitelist()
def get_maintenance_visit_board_details(visit_name):
    """Load the larger detail payload only when a board visit is opened."""
    if not visit_name or not frappe.db.exists("Maintenance Visit", visit_name):
        frappe.throw(_("Maintenance Visit not found"), frappe.DoesNotExistError)

    visit_doc = frappe.get_doc("Maintenance Visit", visit_name)
    visit_doc.check_permission("read")

    visit_fields = [
        "name", "subject", "status", "creation", "maintenance_type",
        "custom_scheduling_status", "completion_status", "customer",
        "customer_name", "custom_lead", "company", "maintenance_schedule",
        "contact_person", "contact_display", "contact_mobile", "contact_email",
        "customer_address", "address_display", "territory", "customer_group",
        "description", "service_tech_notes", "mntc_date", "mntc_time",
        "customer_query", "maintenance_description",
    ]
    visit_meta = frappe.get_meta("Maintenance Visit")
    visit = {
        fieldname: visit_doc.get(fieldname)
        for fieldname in visit_fields
        if visit_meta.get_field(fieldname)
    }
    visit["name"] = visit_doc.name
    visit["creation_display"] = format_board_datetime(visit_doc.creation)
    visit["mntc_time_display"] = format_board_datetime(visit_doc.get("mntc_time"))
    visit["address_text"] = frappe.utils.strip_html(
        (visit_doc.get("address_display") or "").replace("<br>", ", ").replace("<br />", ", ")
    ).strip(" ,")
    visit["contact_text"] = frappe.utils.strip_html(
        (visit_doc.get("contact_display") or "").replace("<br>", ", ").replace("<br />", ", ")
    ).strip(" ,")
    visit["party_label"] = "Customer" if visit_doc.get("customer") else "Lead"
    visit["party_name"] = (
        visit_doc.get("customer") or visit_doc.get("custom_lead") or ""
    )
    visit["assigned"] = visit_doc.get("_assign") or ""
    visit["can_write"] = visit_doc.has_permission("write")

    def get_rows(doctype, fields, filters, order_by="parent, idx asc"):
        if not frappe.db.exists("DocType", doctype):
            return []
        meta = frappe.get_meta(doctype)
        available_fields = [
            fieldname for fieldname in fields
            if fieldname in ("name", "parent", "parenttype", "parentfield", "idx")
            or meta.get_field(fieldname)
        ]
        if "name" not in available_fields:
            available_fields.insert(0, "name")
        return frappe.get_all(
            doctype,
            filters=filters,
            fields=available_fields,
            order_by=order_by,
        )

    checklist = get_rows(
        "Maintenance Visit Checklist",
        [
            "parent", "item_code", "item_name", "heading", "work_done", "done_by",
            "serial_no", "item_location", "periodicity", "details", "attachment",
            "remark", "checklist_image", "sub_steps_json",
            "sub_steps_format_for_mobile_apk",
        ],
        {"parent": visit_name},
    )
    products = get_rows(
        "Maintenance Visit Purpose",
        ["parent", "item_code", "item_name", "serial_no", "custom_image"],
        {"parent": visit_name},
    )
    spare_items = get_rows(
        "Spare Part",
        ["parent", "item_code", "description", "periodicity", "uom"],
        {"parent": visit_name},
    )
    symptoms = get_rows(
        "Maintenance Visit Symptoms",
        ["parent", "item_code", "symptom_code", "resolution", "image", "serial_no"],
        {"parent": visit_name},
    )
    attachments = get_rows(
        "Attachments",
        ["parent", "image", "caption"],
        {"parent": visit_name, "parenttype": "Maintenance Visit", "parentfield": "attachments"},
    )
    symptom_requests = get_rows(
        "Symptoms Requests",
        ["parent", "item_code", "symptom_code", "resolution", "image", "status"],
        {"parent": visit_name, "parenttype": "Maintenance Visit", "parentfield": "symptoms_requests"},
    )
    comments = frappe.get_all(
        "Comment",
        filters={
            "reference_doctype": "Maintenance Visit",
            "reference_name": visit_name,
            "comment_type": "Comment",
        },
        fields=["content", "comment_by", "owner", "creation"],
        order_by="creation desc",
    )
    for comment in comments:
        comment.creation_display = format_board_datetime(comment.creation)

    sub_step_work_logs = get_rows(
        "Maintenance Visit Sub Step Work",
        [
            "parent", "parent_checklist_row", "sub_step_name", "sub_step_original_name",
            "idx", "work_done", "done_by", "attachment", "remark",
        ],
        {"parent": visit_name},
    )

    return {
        "visit": visit,
        "checklist": checklist,
        "products": products,
        "spare_items": spare_items,
        "symptoms": symptoms,
        "comments": comments,
        "attachments": attachments,
        "symptom_requests": symptom_requests,
        "sub_step_work_logs": sub_step_work_logs,
    }


@frappe.whitelist()
def update_visit_board_completion_status(visit_name, completion_status):
    """Update completion status from the board using normal visit validation."""
    if not visit_name or not frappe.db.exists("Maintenance Visit", visit_name):
        frappe.throw(_("Maintenance Visit not found"), frappe.DoesNotExistError)

    visit = frappe.get_doc("Maintenance Visit", visit_name)
    visit.check_permission("write")
    requested_status = (completion_status or "").strip()
    allowed_statuses = [
        option.strip()
        for option in (visit.meta.get_field("completion_status").options or "").splitlines()
        if option.strip()
    ]
    if requested_status not in allowed_statuses and not (
        requested_status == "Approval Pending"
        and visit.get("completion_status") == "Approval Pending"
    ):
        frappe.throw(_("Invalid completion status"), frappe.ValidationError)

    visit.completion_status = requested_status
    visit.save()
    return {"completion_status": visit.get("completion_status") or "Pending"}


@frappe.whitelist()
def approve_visit_symptom_request(visit_name, request_name):
    """Approve a visit symptom request and add it to the item symptom masters."""
    if not visit_name or not frappe.db.exists("Maintenance Visit", visit_name):
        frappe.throw(_("Maintenance Visit not found"), frappe.DoesNotExistError)

    visit = frappe.get_doc("Maintenance Visit", visit_name)
    visit.check_permission("write")
    request_row = next(
        (row for row in (visit.get("symptoms_requests") or []) if row.name == request_name),
        None,
    )
    if not request_row:
        frappe.throw(_("Symptom request not found for this visit"), frappe.DoesNotExistError)
    if request_row.status == "Approved":
        return {"status": "Approved", "already_approved": True}
    if request_row.status != "UnApproved":
        frappe.throw(_("Only unapproved symptom requests can be approved"), frappe.ValidationError)
    if not request_row.item_code or not request_row.symptom_code:
        frappe.throw(_("The request must have an item and symptom code before approval"), frappe.ValidationError)

    symptom_code_name = frappe.db.get_value(
        "Symptom Code", {"symptom_code": request_row.symptom_code}, "name"
    )
    if not symptom_code_name:
        frappe.get_doc({
            "doctype": "Symptom Code",
            "symptom_code": request_row.symptom_code,
            "resolution": request_row.resolution,
            "company": visit.company,
            "item": [{"item": request_row.item_code}],
        }).insert()

    item_doc = frappe.get_doc("Item", request_row.item_code)
    item_doc.check_permission("write")
    resolution_exists = any(
        row.symptom_code == request_row.symptom_code
        and row.resolution == request_row.resolution
        for row in item_doc.get("symptom_resolution_table") or []
    )
    if not resolution_exists:
        item_doc.append("symptom_resolution_table", {
            "item_code": request_row.item_code,
            "symptom_code": request_row.symptom_code,
            "resolution": request_row.resolution,
            "attach_image": request_row.image,
        })
        item_doc.save()

    request_row.status = "Approved"
    visit.save()
    return {"status": "Approved", "already_approved": False}


@frappe.whitelist()
def get_technician_day_visits(technician, date=None):
    """Return this board day's scheduled visits for a visible technician."""
    user = frappe.session.user
    role_profile = frappe.db.get_value("User", user, "role_profile_name")
    is_admin = "BMSCG Admin" in frappe.get_roles(user)
    if not is_admin and role_profile != "Service Coordinator Profile":
        frappe.throw(_("You do not have permission to view technician schedules."), frappe.PermissionError)

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
        frappe.throw(_("This technician is not available on the schedule board."), frappe.PermissionError)

    if not is_admin:
        coordinator_territories = frappe.get_all(
            "User Permission",
            filters={"user": user, "allow": "Territory"},
            pluck="for_value",
        )
        technician_territories = frappe.get_all(
            "User Permission",
            filters={
                "user": technician,
                "allow": "Territory",
                "for_value": ["in", coordinator_territories or ["__none__"]],
            },
            pluck="for_value",
        )
        if not technician_territories:
            frappe.throw(_("You do not have permission to view this technician schedule."), frappe.PermissionError)

    try:
        board_date = datetime.strptime(str(date), "%Y-%m-%d").date() if date else frappe.utils.getdate()
    except (TypeError, ValueError):
        frappe.throw(_("Please select a valid date."))
    assignments = frappe.get_all(
        "Assigned Tasks",
        filters={"technician": technician, "date": board_date},
        fields=["issue_code", "stime", "etime", "status"],
        order_by="stime asc",
    )
    visit_names = get_visible_schedule_board_visit_names(
        row.issue_code for row in assignments if row.issue_code
    )
    visits_by_name = {}
    if visit_names:
        visits_by_name = {
            row.name: row
            for row in frappe.get_all(
                "Maintenance Visit",
                filters={"name": ["in", visit_names], "docstatus": ["<", 2]},
                fields=[
                    "name", "subject", "maintenance_type", "completion_status",
                    "customer", "customer_name", "customer_address", "address_display",
                ],
            )
        }

    result = []
    for assignment in assignments:
        visit = visits_by_name.get(assignment.issue_code)
        if not visit:
            continue
        result.append({
            "name": visit.name,
            "subject": visit.subject,
            "maintenance_type": visit.maintenance_type,
            "completion_status": visit.completion_status,
            "customer": visit.customer_name or visit.customer,
            "customer_link": visit.customer,
            "address": visit.address_display or visit.customer_address,
            "start_time": format_board_datetime(assignment.stime),
            "end_time": format_board_datetime(assignment.etime),
            "status": assignment.status,
        })
    return result


@frappe.whitelist()
def get_scheduling_conflicts(technician, date, stime=None, etime=None, exclude_issue=None):
    """Return the blocked intervals for a technician before a visit is assigned."""
    scope = _get_schedule_board_scope()
    if not technician or not date:
        return {"technician": technician, "intervals": [], "conflicts": [], "working_hours": {"start": "09:00", "end": "20:00"}}
    assert_visible_schedule_board_technician(technician, scope)

    try:
        selected_date = datetime.strptime(str(date), "%Y-%m-%d").date()
    except (TypeError, ValueError):
        frappe.throw(_("Please select a valid date."))

    def minutes_from_time(value):
        if value is None or value == "":
            return None
        if isinstance(value, timedelta):
            return int(value.total_seconds() // 60)
        parts = str(value).split(".", 1)[0].split(":")
        try:
            return int(parts[0]) * 60 + int(parts[1])
        except (IndexError, TypeError, ValueError):
            return None

    def time_label(minutes):
        minutes = max(0, min(24 * 60, int(minutes)))
        return f"{minutes // 60:02d}:{minutes % 60:02d}"

    intervals = []
    assigned_tasks = frappe.get_all(
        "Assigned Tasks",
        filters={"technician": technician, "date": selected_date},
        fields=["issue_code", "stime", "etime"],
        order_by="stime asc",
    )
    visible_booking_names = get_visible_schedule_board_visit_names(
        task.issue_code for task in assigned_tasks if task.issue_code
    )
    for task in assigned_tasks:
        if (exclude_issue and task.issue_code == exclude_issue
                and task.issue_code in visible_booking_names):
            continue
        start = minutes_from_time(task.stime)
        end = minutes_from_time(task.etime)
        if start is None or end is None or end <= start:
            continue
        intervals.append({
            "kind": "booked",
            "label": "Booked",
            "detail": (
                task.issue_code if task.issue_code in visible_booking_names
                else "Existing booking"
            ),
            "start": time_label(start),
            "end": time_label(end),
            "start_minutes": start,
            "end_minutes": end,
        })

    employee = frappe.db.get_value("Employee", {"user_id": technician}, "name")
    if not employee:
        employee = frappe.db.get_value("Employee", {"prefered_email": technician}, "name")
    if employee:
        leaves = frappe.get_all(
            "Leave Application",
            filters={
                "employee": employee,
                "status": "Approved",
                "from_date": ["<=", selected_date],
                "to_date": [">=", selected_date],
            },
            fields=["description", "half_day", "select_half_day"],
        )
        for leave in leaves:
            if leave.half_day == 1 and leave.select_half_day == "Morning":
                start, end = 9 * 60, 12 * 60
            elif leave.half_day == 1:
                start, end = 13 * 60, 20 * 60
            else:
                start, end = 0, 24 * 60
            intervals.append({
                "kind": "leave",
                "label": "Leave",
                "detail": leave.description or "Approved leave",
                "start": time_label(start),
                "end": time_label(end),
                "start_minutes": start,
                "end_minutes": end,
            })

    intervals.append({
        "kind": "lunch",
        "label": "Lunch",
        "detail": "Lunch break",
        "start": "12:00",
        "end": "13:00",
        "start_minutes": 12 * 60,
        "end_minutes": 13 * 60,
    })
    intervals.sort(key=lambda interval: (interval["start_minutes"], interval["end_minutes"]))

    selected_conflicts = []
    selected_start = minutes_from_time(stime)
    selected_end = minutes_from_time(etime)
    if selected_start is not None and selected_end is not None and selected_end > selected_start:
        if selected_start < 9 * 60:
            selected_conflicts.append({
                "kind": "outside_hours",
                "label": "Outside working hours",
                "detail": "Working hours start at 09:00",
                "start": "00:00",
                "end": "09:00",
            })
        if selected_end > 20 * 60:
            selected_conflicts.append({
                "kind": "outside_hours",
                "label": "Outside working hours",
                "detail": "Working hours end at 20:00",
                "start": "20:00",
                "end": "24:00",
            })
        for interval in intervals:
            if selected_start < interval["end_minutes"] and selected_end > interval["start_minutes"]:
                selected_conflicts.append({key: value for key, value in interval.items() if not key.endswith("_minutes")})

    for interval in intervals:
        interval.pop("start_minutes", None)
        interval.pop("end_minutes", None)

    return {
        "technician": technician,
        "intervals": intervals,
        "conflicts": selected_conflicts,
        "working_hours": {"start": "09:00", "end": "20:00"},
    }


def _scheduling_conflict_message(technicians, date, stime, etime, exclude_issue=None):
    messages = []
    for technician in technicians or []:
        availability = get_scheduling_conflicts(
            technician, date, stime, etime, exclude_issue=exclude_issue
        )
        for conflict in availability.get("conflicts", []):
            label = conflict.get("label") or "Unavailable"
            period = "{}–{}".format(conflict.get("start", ""), conflict.get("end", ""))
            detail = conflict.get("detail")
            suffix = " · {}".format(detail) if detail else ""
            messages.append("{}: {} · {}{}".format(technician, label, period, suffix))
    if messages:
        return "Selected time is unavailable: " + "; ".join(messages)
    return ""


@frappe.whitelist()
def save_form_data(form_data):
 # Parse the form_data from the request
 try:
     form_data = json.loads(form_data)
     technicians = form_data["technicians"]
     code = form_data["code"]
     date = form_data["date"]
     etime = form_data["etime"]
     stime = form_data["stime"]
     ehours, eminutes = map(int, etime.split(":"))
     etime = timedelta(hours=ehours, minutes=eminutes)
     shours, sminutes = map(int, stime.split(":"))
     stime = timedelta(hours=shours, minutes=sminutes)
     if stime.total_seconds() % 1800 != 0 or etime.total_seconds() % 1800 != 0:
         frappe.throw("Please select start and end times in half-hour increments.")
     if stime >= etime:
         frappe.throw("Please select a time that is greater than the start time.")
     conflict_message = _scheduling_conflict_message(technicians, date, stime, etime, code)
     if conflict_message:
         return {"error": "error", "message": conflict_message}




     for tech in technicians:




         new_doc = frappe.get_doc(
             {
                 "doctype": "Assigned Tasks",
                 "issue_code": code,
                 "technician": tech,
                 "date": date,
                 "etime": etime,
                 "stime": stime,
             }
         )
         new_doc.insert()




     # Optionally, you can update the Issue doctype as well
     issue_doc = frappe.get_doc("Maintenance Visit", code)
     if issue_doc:
         existing_techs = json.loads(issue_doc._assign) if issue_doc._assign else []
         for tech in technicians:
             if tech not in existing_techs:
                 existing_techs.append(tech)
         issue_doc._assign = json.dumps(existing_techs)
         issue_doc.visit_count = int(issue_doc.visit_count or 0) + 1
         issue_doc.mntc_date = date
         # frappe.db.sql(
         #     """
         #     UPDATE `tabMaintenance Visit` SET `_assign` = %s, `maintenance_type` = %s, `visit_count` = %s, `mntc_date` = %s WHERE name = %s
         # """,
         #     (json.dumps(existing_techs), 'Scheduled', issue_doc.visit_count, date, code),
         # )

         frappe.db.set_value(
             "Maintenance Visit",
             code,
             {
                 "_assign": json.dumps(existing_techs),
                 "custom_scheduling_status": "Scheduled",
                 "visit_count": issue_doc.visit_count,
                 "mntc_date": date,
             },
         )




         frappe.db.commit()
     return {"success": "success"}
 except Exception as e:
     frappe.db.rollback()
     return {"error": "error", "message": str(e)}




@frappe.whitelist()
def update_form_data(form_data):
 # # Parse the form_data from the request
 # pass
 try:
     form_data = json.loads(form_data)
     technicians = form_data["technicians"]
     code = form_data["code"]
     date = form_data["date"]
     etime = form_data["etime"]
     stime = form_data["stime"]
     if(len(etime) > 5):
         hours, minutes, seconds = map(int, etime.split(":"))
     else:
         hours, minutes = map(int, etime.split(":"))
     etime = timedelta(hours=hours, minutes=minutes)
     if(len(stime) > 5):
         hours, minutes, seconds = map(int, stime.split(":"))
     else:
         hours, minutes = map(int, stime.split(":"))




     stime = timedelta(hours=hours, minutes=minutes)




     if stime.total_seconds() % 1800 != 0 or etime.total_seconds() % 1800 != 0:
         frappe.throw("Please select start and end times in half-hour increments.")
     if stime >= etime:
         frappe.throw("Please select a time that is greater than the start time.")
     conflict_message = _scheduling_conflict_message(technicians, date, stime, etime, code)
     if conflict_message:
         return {"error": "error", "message": conflict_message}

     tasks = frappe.get_all("Assigned Tasks", filters={"issue_code": code}, fields=["name"])




     for tech in technicians:




         new_doc = frappe.get_doc(
             {
                 "doctype": "Assigned Tasks",
                 "issue_code": code,
                 "technician": tech,
                 "date": date,
                 "etime": etime,
                 "stime": stime,
             }
         )
         new_doc.insert()

     # Replace the existing booking only after validation and all new rows succeed.
     for task in tasks:
         frappe.delete_doc("Assigned Tasks", task.name, force=True)




     # Optionally, you can update the Issue doctype as well
     issue_doc = frappe.get_doc("Maintenance Visit", code)
     if issue_doc:
         existing_techs = []
         for tech in technicians:
             if tech not in existing_techs:
                 existing_techs.append(tech)
         if existing_techs:
             issue_doc._assign = json.dumps(existing_techs)
             issue_doc.mntc_date = date
             # frappe.db.sql(
             #     """
             #     UPDATE `tabMaintenance Visit` SET `_assign` = %s, `mntc_date` = %s WHERE name = %s
             #     """,
             #     (json.dumps(existing_techs), date, code),
             # )
             frappe.db.set_value(
                 "Maintenance Visit",
                 code,
                 {
                     "_assign": json.dumps(existing_techs),
                     "custom_scheduling_status": "Rescheduled",
                     "mntc_date": date,
                 },
             )
         else:
             issue_doc._assign = ""
             # frappe.db.sql(
             # """
             #     UPDATE `tabMaintenance Visit` SET `_assign` = %s, `maintenance_type` = %s, `visit_count` = `visit_count` - 1 WHERE name = %s
             # """,
             #     ("", 'Unscheduled', code),
             # )
             issue_doc.visit_count = max(int(issue_doc.visit_count or 1) - 1, 0)
             frappe.db.set_value(
                 "Maintenance Visit",
                 code,
                 {
                     "_assign": "",
                     "custom_scheduling_status": "Unscheduled",
                     "visit_count": issue_doc.visit_count,
                 },
             )




         frappe.db.commit()
     return {"success": "success"}
 except Exception as e:
     frappe.db.rollback()
     return {"error": "error", "message": str(e)}
