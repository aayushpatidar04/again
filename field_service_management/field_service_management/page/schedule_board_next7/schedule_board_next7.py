import frappe
from frappe import _
import json
from datetime import datetime
from datetime import timedelta
from frappe.contacts.doctype.address.address import get_address_display


@frappe.whitelist()
def get_context(context=None):
   context = context or {}
   user = frappe.session.user


   issues = []
   technicians = []


   role_profile = frappe.db.get_value("User", user, "role_profile_name")
   if "BMSCG Admin" in frappe.get_roles(frappe.session.user):
       issues = frappe.get_all(
           "Maintenance Visit",
           filters={"_assign": ""},
           fields=["name", "subject", "status", "creation", "maintenance_type",
                    "_assign", "description", "maintenance_description",
                    "customer_address", "completion_status", "customer"],
       )
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
       issues = frappe.get_all(
           "Maintenance Visit",
           filters={"territory": ["in", territory_list], "_assign": ""},
           fields=["name", "subject", "status", "creation", "maintenance_type",
                    "_assign", "description", "maintenance_description",
                    "customer_address", "completion_status", "customer"],
       )
       technicians = frappe.get_all(
           "User",
           filters={"role_profile_name": "Service Technician Role Profile"},
           fields=["email", "user_image", "full_name"],
       )
       technician_list = []
       for tech in technicians:
           tech_territory = frappe.db.get_value(
               "User Permission", {"user": tech["email"], "allow": "Territory"}, "for_value"
           )
           if tech_territory in territory_list:
               technician_list.append(tech)
       technicians = technician_list


   for issue in issues:
       if issue._assign:
           try:
               assign_list = json.loads(issue._assign)
               issue.assigned = assign_list
               issue._assign = " | ".join(assign_list)
           except json.JSONDecodeError:
               issue._assign = "No one assigned"
       else:
           issue._assign = "No one assigned"


       geolocation = frappe.get_all('Address', filters={'name': issue.customer_address}, fields=['geolocation'])
       if geolocation and geolocation[0].geolocation:
           geo = json.loads(geolocation[0].geolocation)
           issue.geolocation = json.dumps(geo['features']).replace('"', "'")
       else:
           issue.geolocation = None


       checklist = frappe.get_all(
           "Maintenance Visit Checklist", filters={"parent": issue.name},
           fields=['item_code', 'item_name', 'heading', 'work_done', 'done_by']
       )
       checklist_tree = {}
       for problem in checklist:
           checklist_tree.setdefault(problem.item_code, []).append(problem)
       html_content = ""
       for item_code, products in checklist_tree.items():
           if products:
               html_content += f"<p><strong>{item_code}: {products[0].item_name}</strong></p>"
               for product in products:
                   checked_attribute = "checked" if product.work_done == "Yes" else ""
                   html_content += (f"<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                                     f"<input type='checkbox' {checked_attribute} disabled> "
                                     f"&nbsp;&nbsp;&nbsp;&nbsp;{product.heading}<br>")
               html_content += "</p>"
       issue.checklist_tree = html_content


       issue.products = frappe.get_all(
           "Maintenance Visit Purpose", filters={"parent": issue.name},
           fields=['item_code', 'item_name', 'custom_image']
       )
       issue.spare_items = frappe.get_all(
           "Spare Part", filters={"parent": issue.name},
           fields=['item_code', 'description', 'periodicity', 'uom']
       )


       symptoms = frappe.get_all(
           "Maintenance Visit Symptoms", filters={"parent": issue.name},
           fields=['item_code', 'symptom_code', 'resolution', 'image']
       )
       symptoms_res = {}
       for symptom in symptoms:
           symptoms_res.setdefault(symptom.item_code, []).append(symptom)
       html_content = ""
       for item_code, resolutions in symptoms_res.items():
           if resolutions:
               html_content += f"<p><strong>{item_code}:</strong></p>"
               for resolution in resolutions:
                   html_content += (f"<p>&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;"
                                     f"<img src='{resolution.image}' style='max-width: 100px;'> --> "
                                     f"<strong>{resolution.symptom_code}</strong> --> {resolution.resolution}<br>")
               html_content += "</p>"
       issue.symptoms_res = html_content


   context["issues"] = issues


   current_date = datetime.now().date()
   dates = [(current_date + timedelta(days=i)) for i in range(7)]


   # Base slot definitions — treated as READ-ONLY templates from here on.
   # Never mutate these dicts inside the loop below; that was corrupting
   # times across technicians and dates.
   BASE_TIME_SLOTS = [
       {"label": "09", "time": timedelta(hours=9)},
       {"label": "10", "time": timedelta(hours=10)},
       {"label": "11", "time": timedelta(hours=11)},
       {"label": "12", "time": timedelta(hours=12)},
       {"label": "01", "time": timedelta(hours=13)},
       {"label": "02", "time": timedelta(hours=14)},
       {"label": "03", "time": timedelta(hours=15)},
       {"label": "04", "time": timedelta(hours=16)},
       {"label": "05", "time": timedelta(hours=17)},
       {"label": "06", "time": timedelta(hours=18)},
       {"label": "07", "time": timedelta(hours=19)},
       {"label": "08", "time": timedelta(hours=20)},
   ]


   # --- Precompute per-date data ONCE, shared across all technicians ---
   # (not_available doesn't depend on which technician we're rendering,
   # so it should never have been queried inside the tech loop.)
   assigned_tasks_by_date = {}
   for date in dates:
       assigned_tasks_by_date[date] = frappe.get_all(
           "Assigned Tasks",
           filters={"date": date},
           fields=["issue_code", "stime", "etime", "technician"],
       )


   def get_not_available(date, slot_time):
       return [
           t.technician for t in assigned_tasks_by_date[date]
           if t.stime <= slot_time and t.etime > slot_time
       ]


   # Cache Maintenance Visit docs so each is fetched at most once,
   # instead of once per slot per task.
   maintenance_doc_cache = {}
   def get_maintenance_doc(issue_code):
       if issue_code not in maintenance_doc_cache:
           maintenance_doc_cache[issue_code] = frappe.get_doc("Maintenance Visit", issue_code)
       return maintenance_doc_cache[issue_code]


   for tech in technicians:
       html_content = ""
       tasks = frappe.get_all(
           "Assigned Tasks",
           filters={"date": ["in", dates], "technician": tech.email},
           fields=["issue_code", "stime", "etime", "date"],
           order_by="date, stime"
       )
       tasks_by_date = {date: [] for date in dates}
       for task in tasks:
           time_diff = task.etime - task.stime
           task.duration_in_hours = time_diff.total_seconds() / 3600
           task.flag = 0
           tasks_by_date[task.date].append(task)


       total_hours = 0


       for date in dates:
           tss = tasks_by_date[date]


           employee = frappe.db.get_value("Employee", {"prefered_email": tech.email}, "employee")
           leaves = []
           if employee:
               leaves = frappe.db.sql(
                   """
                   SELECT description, half_day, from_date, to_date, select_half_day
                   FROM `tabLeave Application`
                   WHERE employee = %(employee)s AND status = 'Approved'
                     AND from_date <= %(date)s AND to_date >= %(date)s;
                   """,
                   {"employee": employee, "date": date}, as_dict=True,
               )


           afternoon = 0
           if leaves:
               for leave in leaves:
                   if leave.half_day == 1:
                       if leave.select_half_day == 'Morning':
                           count = 3
                           html_content += (f'<div style="width: 75px; border-right: 1px solid #000; '
                                             f'color: white; background-color: red;" data-tech="{tech.email}" '
                                             f'class="px-1">{leave.description if leave.description else "Leave"}</div>')
                       else:
                           count = 0
                           afternoon = 1
                   else:
                       count = 12
                       html_content += (f'<div style="width: 300px; border-right: 1px solid #000; '
                                         f'color: white; background-color: red;" data-tech="{tech.email}" '
                                         f'class="px-1">{leave.description if leave.description else "Leave"}</div>')
           else:
               count = 0


           for slot in BASE_TIME_SLOTS:
               # Work off a LOCAL copy of the slot's time so nothing here
               # ever mutates BASE_TIME_SLOTS.
               slot_label = slot['label']
               slot_time = slot['time']


               if count == -0.5:
                   # This is the leftover half-hour right after a task that
                   # ended exactly on a half-hour boundary. Must be a real
                   # drop-zone just like every other open half-hour cell.
                   ttt = slot_time - timedelta(minutes=30)
                   not_available = get_not_available(date, ttt)
                   html_content += (
                       f'<div style="width: 12.5px; border-right: 1px solid #000; background-color: #78D6FF; '
                       f'border: 2px dashed #ccc; min-height: 40px;" data-time="{ttt}" data-date="{date}" '
                       f'data-tech="{tech.email}" data-na="{not_available}" class="px-1 drop-zone">-</div>'
                   )
                   count += 0.5


               if slot_label == '01' and afternoon == 1:
                   count += 8
                   html_content += (f'<div style="width: 200px; border-right: 1px solid #000; color: white; '
                                     f'background-color: red;" data-tech="{tech.email}" class="px-1">Leave</div>')


               if slot_label == '12':
                   if count >= 1:
                       count -= 1
                   elif count == 0.5:
                       html_content += (f'<div style="width: 12.5px; border-right: 1px solid #000; color: white; '
                                         f'background-color: red;" data-time="{slot_time}" data-tech="{tech.email}" '
                                         f'class="px-1">Lunch Time</div>')
                       count -= 0.5
                   else:
                       html_content += (f'<div style="width: 25px; border-right: 1px solid #000; color: white; '
                                         f'background-color: red;" data-time="{slot_time}" data-tech="{tech.email}" '
                                         f'class="px-1">Lunch Time</div>')
               else:
                   not_available = get_not_available(date, slot_time)


                   task_in_slot = None
                   for task in tss:
                       if task.flag == 0 and task.stime <= slot_time and task.etime > slot_time:
                           task_in_slot = task
                           task.flag = 1
                           break


                   if task_in_slot:
                       maintenance = get_maintenance_doc(task_in_slot['issue_code'])
                       total_hours += task_in_slot['duration_in_hours']
                       html_content += f"""
                       <div style="width: {task_in_slot['duration_in_hours'] * 25}px; background-color: red; border-right: 1px solid #000;" class="px-1 py-2 text-white text-center drag" data-type="type2" draggable="true" id="task-{task_in_slot['issue_code']}" data-duration="{task_in_slot['duration_in_hours']}">
                           <a href="javascript:void(0)"
                               class="text-white" data-id="taskModaltask-{task_in_slot['issue_code']}">{task_in_slot['issue_code']}</a>
                       </div>
                       """
                       html_content += f"""
                       <div class="modal hide" id="taskModaltask-{task_in_slot['issue_code']}" tabindex="-1" role="dialog"
                           aria-labelledby="taskModalLabel{task_in_slot['issue_code']}" aria-hidden="true">
                           <div class="modal-dialog" role="document" style="max-width: 80%; margin: 1.75rem auto">
                               <div class="modal-content">
                                   <div class="modal-header">
                                       <h5 class="modal-title" id="taskModalLabel{task_in_slot['issue_code']}">{task_in_slot['issue_code']}</h5>
                                       <button type="button" class="close" data-dismiss="modal" aria-label="Close">
                                           <span aria-hidden="true">&times;</span>
                                       </button>
                                   </div>
                                   <div class="modal-body">
                                       <form id="custom2-form-{task_in_slot['issue_code']}" class="custom-form" method="POST">
                                           <label for="code">Maintenance Visit Code:</label>
                                           <input class="form-control code clickable-code" type="text" name="code" value="{task_in_slot['issue_code']}" required
                                               readonly style="cursor: pointer;" onclick="window.open('/app/maintenance-visit/{task_in_slot['issue_code']}', '_blank')"><br><br>
                                           <label for="technician">Select Co-Technicians (<span class="text-danger">only if more than one technician required</span>):</label><br>
                                           <select class="form-select technician" style="width:100%" name="technician[]" multiple="multiple" required>"""
                       for item in technicians:
                           selected = 'selected' if maintenance._assign and item.email in maintenance._assign else ''
                           html_content += f'<option value="{item.email}" {selected}>{item.email}</option>'
                       html_content += """ </select><br><br>
                                           <label for="date">Date:</label>
                                           <input class="form-control date" type="date" name="date" value="{date}" required><br><br>
                                           <label for="stime">Start Time</label>
                                           <input class="form-control stime" type="time" name="stime" value="{stime}" required readonly><br><br>
                                           <label for="etime">End Time:</label>
                                           <input class="form-control etime" type="time" name="etime" value="{etime}" required readonly>
                                           <small><span class="text-danger etime-error"></span></small><br><br>
                                           <button type="button" class="update btn btn-success"
                                               data-issue="{issue_code}">Update</button>
                                       </form>
                                   </div>
                               </div>
                           </div>
                       </div>""".format(issue_code=task_in_slot['issue_code'], date=date,
                                         stime=task_in_slot['stime'], etime=task_in_slot['etime'])
                       count += task_in_slot["duration_in_hours"] - 1
                   else:
                       if count == 0:
                           html_content += (f'<div style="width: 25px; border-right: 1px solid #000; '
                                             f'background-color: #78D6FF; min-height: 40px;" data-time="{slot_time}" '
                                             f'data-date="{date}" data-tech="{tech.email}" data-na="{not_available}" '
                                             f'class="px-1 drop-zone">-</div>')
                       elif count % 1 == 0.5:
                           display_time = slot_time + timedelta(minutes=30)  # local, not a mutation
                           html_content += (f'<div style="width: 12.5px; border-right: 1px solid #000; '
                                             f'background-color: #78D6FF; min-height: 40px;" data-time="{display_time}" '
                                             f'data-date="{date}" data-tech="{tech.email}" data-na="{not_available}" '
                                             f'class="px-1 drop-zone">-</div>')
                           count -= 0.5
                       else:
                           count -= 1


       tech.html_content = html_content
       tech.total_hours = round(total_hours / 77 * 100, 2)  # computed once, after both loops


   context["dates"] = dates
   context["technicians"] = technicians
   context["slots"] = BASE_TIME_SLOTS
   context["message"] = "Welcome to your schedule board!"
   return context




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
        if eminutes % 30 != 0:
            frappe.throw("Please select a time that is a multiple of 30 minutes.")
        if stime >= etime:
            frappe.throw("Please select a time that is greater than the start time.")
        for tech in technicians:
            assigned_tasks = frappe.get_all(
                "Assigned Tasks",
                filters={"technician": tech, "date": date},
                fields=["issue_code", "stime", "etime"],
            )
            for task in assigned_tasks:
                if (
                    (stime > task.stime and stime < task.etime)
                    or (etime > task.stime and etime < task.etime)
                    or (task.stime > stime and task.stime < etime)
                ):
                    return {
                        "error": "error",
                        "message": f"Time Slot Clash for technician: {tech}",
                    }

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

            frappe.db.sql(
                """
                UPDATE `tabMaintenance Visit` SET `_assign` = %s, `maintenance_type` = %s, `visit_count` = %s, `mntc_date` = %s WHERE name = %s
            """,
                (json.dumps(existing_techs), 'Scheduled', issue_doc.visit_count, date, code),
            )

            frappe.db.commit()
        return {"success": "success"}
    except Exception as e:
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


        tasks = frappe.get_all("Assigned Tasks", filters={"issue_code": code}, fields=["name"])

        if tasks:
            for task in tasks:
                frappe.delete_doc("Assigned Tasks", task.name, force=True)
            frappe.db.commit()



        for tech in technicians:
            assigned_tasks = frappe.get_all(
                "Assigned Tasks",
                filters={"technician": tech, "date": date},
                fields=["issue_code", "stime", "etime"],
            )
            for task in assigned_tasks:
                if (
                    (stime > task.stime and stime < task.etime)
                    or (etime > task.stime and etime < task.etime)
                    or (task.stime > stime and task.stime < etime)
                ):
                    return {
                        "error": "error",
                        "message": f"Time Slot Clash for technician: {tech}",
                    }

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
            existing_techs = []
            for tech in technicians:
                if tech not in existing_techs:
                    existing_techs.append(tech)
            if existing_techs:
                issue_doc._assign = json.dumps(existing_techs)
                issue_doc.mntc_date = date
                frappe.db.sql(
                    """
                    UPDATE `tabMaintenance Visit` SET `_assign` = %s, `mntc_date` = %s WHERE name = %s
                    """,
                    (json.dumps(existing_techs), date, code),
                )
            else:
                issue_doc._assign = ""
                issue_doc.visit_count = int(issue_doc.visit_count or 1) - 1
                frappe.db.sql(
                """
                    UPDATE `tabMaintenance Visit` SET `_assign` = %s, `maintenance_type` = %s, `visit_count` = %s WHERE name = %s
                """,
                    ("", 'Unscheduled', issue_doc.visit_count, code),
                )

            frappe.db.commit()
        return {"success": "success"}
    except Exception as e:
        return {"error": "error", "message": str(e)}
