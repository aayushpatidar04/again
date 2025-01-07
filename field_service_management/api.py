import jwt
import frappe
from frappe import _
import json
from frappe.utils import now
import math
from frappe.utils import now_datetime, random_string, get_site_path
import os
import base64
import imghdr
from frappe.utils.file_manager import save_file

@frappe.whitelist(allow_guest=True)
def login(email, password):
    # Authenticate user
    if not email or not password:
        return {
            "status": "error",
            "message": _("Email and password are required.")
        }

    try:
        # Attempt to log in using the email and password
        login_manager = frappe.local.login_manager
        login_manager.authenticate(email, password)

        # If authentication is successful, get user info
        user = frappe.get_doc("User", email)
        if user:
            if not user.api_key:
                return{
                    "status": "failed",
                    "message": "API access is not given to the user"
                }
            api_secret = frappe.utils.password.get_decrypted_password('User', user.name, 'api_secret')
            return {
                "status": "success",
                "message": _("Login successful"),
                "user": {
                    "email": user.email,
                    "full_name": user.full_name,
                    "api_key": user.api_key,
                    "api_secret": api_secret
                }
            }
        else:
            return {
                "status": "failed",
                "message": "Invalid Credentials"
            }
    except frappe.AuthenticationError:
        return {
            "status": "error",
            "message": _("Invalid email or password.")
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist(allow_guest=True)
def get_maintenance():
    authorization_header = frappe.get_request_header("Authorization")
    if not authorization_header:
        return { "status": "error", "message": "Missing Authorization header"}
    api_key = frappe.get_request_header("Authorization").split(" ")[1].split(":")[0]
    # Find the user associated with the API key
    user = frappe.db.get_value("User", {"api_key": api_key}, "name")
    
    if not user:
        return {"status": "failed", "message": "Invalid API key"}
    
    maintenance_visits = frappe.get_all(
        "Maintenance Visit",
        filters={
            "_assign": ["like", f'%"{user}"%']
        },
        fields="name"
    )
   
    visits_with_details = []
    for visit in maintenance_visits:
        visit_doc = frappe.get_doc("Maintenance Visit", visit.name)

        #visit-start-time
        latest_visit_start = frappe.db.get_value(
            "Visit Start Maintenance",
            {
                "parent": visit.name,
                "technician": user,
            },
            "visit_start_at",
            order_by="visit_start_at DESC"
        )
        visit_doc.update({
            "visit_start": latest_visit_start if latest_visit_start else "",
        })

        #start-end time
        assigned_task = frappe.get_all(
            "Assigned Tasks",
            filters={
                "technician": user, "status": "Pending", "issue_code": visit.name
            },
            limit_page_length=1,
            order_by='creation desc',
            fields=['*']
        )
        visit_data = visit_doc.as_dict()
        visit_data['start_time'] = assigned_task[0].stime if assigned_task else ""
        visit_data['end_time'] = assigned_task[0].etime if assigned_task else ""


        #punch-in-punch-out
        latest_punch_in = frappe.db.get_value(
            "Punch In Punch Out",
            {
                "parent": visit.name,
                "technician": user,
                "punch_in": ["is", "set"]
            },
            "punch_in",
            order_by="punch_in DESC"
        )
        latest_punch_out = frappe.db.get_value(
            "Punch In Punch Out",
            {
                "parent": visit.name,
                "technician": user,
                "punch_out": ["is", "set"]
            },
            "punch_out",
            order_by="punch_out DESC"
        )
        visit_data["latest_punch_in"] = latest_punch_in if latest_punch_in else ""
        visit_data["latest_punch_out"] = latest_punch_out if latest_punch_out else ""


        #geolocation
        delivery_note_name = frappe.get_value(
            "Serial No",
            {"custom_item_current_installation_address": visit_doc.delivery_addres},
            "custom_item_current_installation_address_name"
        )
        if not delivery_note_name:
            frappe.throw(f"No Serial No found for address: {visit_doc.delivery_addres}")
        address = frappe.get_doc("Address", delivery_note_name)
        geolocation = address.geolocation

        if not geolocation:
            frappe.throw(f"No geolocation found for address: {address.name}")

        # Parse geolocation and assign it to the visit_doc
        geolocation = json.loads(geolocation)
        visit_data["geolocation"] = geolocation
        
        # Initialize a new dictionary for checktree_description
        checktree_description = {}
        for item in visit_doc.checktree_description:
            item_code = item.item_code
            if item_code not in checktree_description:
                checktree_description[item_code] = []
            checktree_description[item_code].append(item.as_dict())
        
        # Initialize a new dictionary for symptoms_table
        symptoms_table = {}
        for item in visit_doc.symptoms_table:
            item_code = item.item_code
            if item_code not in symptoms_table:
                symptoms_table[item_code] = []
            symptoms_table[item_code].append(item.as_dict())
        
        # Create a dictionary for the current visit, including the reformatted child tables
        visit_data['checktree_description'] = checktree_description
        visit_data['symptoms_table'] = symptoms_table
        
        # Append the reformatted data to the final output
        visits_with_details.append(visit_data)
    
    return visits_with_details


@frappe.whitelist(allow_guest=True)
def update_spare_item(status, name):
    authorization_header = frappe.get_request_header("Authorization")
    if not authorization_header:
        return { "status": "error", "message": "Missing Authorization header"}
    api_key = frappe.get_request_header("Authorization").split(" ")[1].split(":")[0]
    # Find the user associated with the API key
    user = frappe.db.get_value("User", {"api_key": api_key}, "name")
    
    if not user:
        return {"status": "failed", "message": "Invalid API key"}
    spare_item = frappe.get_doc("Spare Items", name)
    if not spare_item:
        return {"status": "error", "message": f"Spare Item with name '{name}' not found"}

    # Update the 'collected' field with the provided status
    if status == 'yes':
        spare_item.collected = 'yes'
    else:
        spare_item.collected = 'no'
    spare_item.flags.ignore_permissions = True
    spare_item.save()
    # Commit the changes to the database
    frappe.db.commit()

    return {"status": "success", "message": f"Spare Item '{name}' updated successfully", "collected": status}

@frappe.whitelist(allow_guest=True)
def start_maintenance_visit(name):
    authorization_header = frappe.get_request_header("Authorization")
    if not authorization_header:
        return { "status": "error", "message": "Missing Authorization header"}
    api_key = frappe.get_request_header("Authorization").split(" ")[1].split(":")[0]
    # Find the user associated with the API key
    user = frappe.db.get_value("User", {"api_key": api_key}, "name")
    
    if not user:
        return {"status": "failed", "message": "Invalid API key"}
    
    if not name:
        return {"status": "error", "message": "Maintenance Visit name is required"}

    try:
        # Fetch the Maintenance Visit document
        maintenance = frappe.get_doc("Maintenance Visit", name)
        if not maintenance:
            return {"status":"Failed", "message":"Maintenance Visit not found."}
        
        # Convert the technician email/ID to a user record
        technician_user = frappe.get_value("User", user)
        if not technician_user:
            return {"status": "Failed", "message":"Technician not found."}
        if not maintenance:
            return {"status": "error", "message": f"Maintenance Visit '{name}' not found"}
        
        # Update the visit_start field with the current timestamp
        new_record = frappe.get_doc({
            "doctype": "Visit Start Maintenance",
            "parent": name,
            "parenttype": "Maintenance Visit",
            "parentfield": "visit_start_records",
            "maintenance_visit": name,
            "technician": technician_user,
            "visit_start_at": now_datetime(),
        })
        new_record.insert(ignore_permissions=True)
        frappe.db.commit()

        maintenance.reload()
        if maintenance.visit_start is None:
            maintenance.visit_start = now()
        maintenance.flags.ignore_permissions = True
        maintenance.save()
        
        return {"status": "success", "message": f"Visit '{name}' started successfully", "visit_start": maintenance.visit_start}
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Start Maintenance Visit Error")
        return {"status": "error", "message": str(e)}
    
def is_within_radius(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
    
    R = 6371e3

    φ1 = math.radians(lat1)
    φ2 = math.radians(lat2)
    Δφ = math.radians(lat2 - lat1)
    Δλ = math.radians(lon2 - lon1)

    a = math.sin(Δφ / 2) * math.sin(Δφ / 2) + math.cos(φ1) * math.cos(φ2) * math.sin(Δλ / 2) * math.sin(Δλ / 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance = R * c
    return distance

@frappe.whitelist(allow_guest=True)
def check_300m_radius(lat1, lon1, lat2, lon2):
    radius = 300
    # Calculate the distance between the two points
    distance = is_within_radius(lat1, lon1, lat2, lon2)
    
    # Check if the distance is less than or equal to the given radius
    return {"status": "success", "distance": f"Distance between customer location and technician location is '{distance}'.", "message": distance <= radius}


@frappe.whitelist(allow_guest=True)
def update_punch_in_out(maintenance_visit, punch_in=None, punch_out=None, visit_type="First Visit", is_completed='no'):
    authorization_header = frappe.get_request_header("Authorization")
    if not authorization_header:
        return { "status": "error", "message": "Missing Authorization header"}
    api_key = frappe.get_request_header("Authorization").split(" ")[1].split(":")[0]
    # Find the user associated with the API key
    user = frappe.db.get_value("User", {"api_key": api_key}, "name")

    if not user:
        return {"status": "failed", "message": "Invalid API key"}

    # Ensure the Maintenance Visit exists
    maintenance = frappe.get_doc("Maintenance Visit", maintenance_visit)
    if not maintenance:
        return {"status":"Failed", "message":"Maintenance Visit not found."}
    
    # Convert the technician email/ID to a user record
    technician_user = frappe.get_value("User", user)
    if not technician_user:
        return {"status": "Failed", "message":"Technician not found."}
    # Fetch existing records for the current visit and technician with an open status
    existing_records = frappe.get_all("Punch In Punch Out", filters={
        "parent": maintenance_visit,
        "parenttype": "Maintenance Visit",
        "maintenance_visit": maintenance_visit,
        "technician": technician_user,
        "type": visit_type,
        "punch_out": None  # Only consider records where punch_out is not set
    }, fields=["name"])

    # Case 1: Punching In (for First Visit or Rescheduled Visit)
    if punch_in:
        if visit_type == "First Visit" and not existing_records:
            # Create a new record for the first visit if none exists
            new_record = frappe.get_doc({
                "doctype": "Punch In Punch Out",
                "parent": maintenance_visit,
                "parenttype": "Maintenance Visit",
                "parentfield": "punch_in_punch_out",
                "maintenance_visit": maintenance_visit,
                "technician": technician_user,
                "punch_in": now_datetime(),
                "type": "First Visit",
                "is_completed": 'no'
            })
            new_record.insert(ignore_permissions=True)
            frappe.db.commit()
            return {"status": "success", "message": "Punch-in recorded for First Visit"}

        elif visit_type == "Rescheduled Visit":
            # Create a new record for a rescheduled visit
            new_record = frappe.get_doc({
                "doctype": "Punch In Punch Out",
                "parent": maintenance_visit,
                "parenttype": "Maintenance Visit",
                "parentfield": "punch_in_punch_out",
                "maintenance_visit": maintenance_visit,
                "technician": technician_user,
                "punch_in": now_datetime(),
                "type": "Rescheduled Visit",
                "is_completed": False
            })
            new_record.insert(ignore_permissions=True)
            frappe.db.commit()
            return {"status": "success", "message": "Punch-in recorded for Rescheduled Visit"}

    # Case 2: Punching Out (for an ongoing visit)
    if punch_out:
        if existing_records:
            # Update the latest active record with punch_out time and is_completed flag
            record_name = existing_records[0]['name']
            existing_record = frappe.get_doc("Punch In Punch Out", record_name)
            existing_record.punch_out = now_datetime()
            existing_record.completed = 'yes'
            existing_record.save(ignore_permissions=True)
            frappe.db.commit()
            status_msg = "Punch-out recorded"
            status_msg += " and visit marked as Approval Pending"
            frappe.db.sql(
            """
                UPDATE `tabMaintenance Visit` SET `completion_status` = %s WHERE name = %s
            """,
                ('Approval Pending', maintenance_visit),
            )
            return {"status": "success", "message": status_msg}
        else:
            frappe.throw("No active punch-in record found to update.")

    return {"status": "failed", "message": "Invalid operation"}

@frappe.whitelist(allow_guest=True)
def get_maintenance_(name = None):

    authorization_header = frappe.get_request_header("Authorization")
    if not authorization_header:
        return { "status": "error", "message": "Missing Authorization header"}
    api_key = frappe.get_request_header("Authorization").split(" ")[1].split(":")[0]
    # Find the user associated with the API key
    user = frappe.db.get_value("User", {"api_key": api_key}, "name")
    
    if not user:
        return {"status": "failed", "message": "Invalid API key"}
    
    visit_doc = frappe.get_doc("Maintenance Visit", name)

    #visit-start-time
    latest_visit_start = frappe.db.get_value(
        "Visit Start Maintenance",
        {
            "parent": name,
            "technician": user,
        },
        "visit_start_at",
        order_by="visit_start_at DESC"
    )
    visit_doc.update({
        "visit_start": latest_visit_start if latest_visit_start else "",
    })


    #start-end time
    assigned_task = frappe.get_all(
        "Assigned Tasks",
        filters={
            "technician": user, "status": "Pending", "issue_code": name
        },
        limit_page_length=1,
        order_by='creation desc',
        fields=['*']
    )

    

    visit_data = visit_doc.as_dict()
    visit_data["start_time"] = assigned_task[0].stime if assigned_task else ""
    visit_data["end_time"] = assigned_task[0].etime if assigned_task else ""

    #punch-in-punch-out
    latest_punch_in = frappe.db.get_value(
        "Punch In Punch Out",
        {
            "parent": name,
            "technician": user,
            "punch_in": ["is", "set"],
            "completed": 'no'
        },
        "punch_in",
        order_by="punch_in DESC"
    )
    latest_punch_out = frappe.db.get_value(
        "Punch In Punch Out",
        {
            "parent": name,
            "technician": user,
            "punch_out": ["is", "set"]
        },
        "punch_out",
        order_by="punch_out DESC"
    )
    visit_data["latest_punch_in"] = latest_punch_in if latest_punch_in else ""
    visit_data["latest_punch_out"] = latest_punch_out if latest_punch_out else ""

    #geolocation
    delivery_note_name = frappe.get_value(
        "Serial No",
        {"custom_item_current_installation_address": visit_doc.delivery_addres},
        "custom_item_current_installation_address_name"
    )
    if not delivery_note_name:
        frappe.throw(f"No Serial No found for address: {visit_doc.delivery_addres}")
    address = frappe.get_doc("Address", delivery_note_name)
    geolocation = address.geolocation
    if not geolocation:
        frappe.throw(f"No geolocation found for address: {address.name}")
    # Parse geolocation and assign it to the visit_doc
    geolocation = json.loads(geolocation)
    visit_data["geolocation"] = geolocation
    
    # Initialize a new dictionary for checktree_description
    checktree_description = {}
    for item in visit_doc.checktree_description:
        item_code = item.item_code
        if item_code not in checktree_description:
            checktree_description[item_code] = []
        checktree_description[item_code].append(item.as_dict())
    
    # Initialize a new dictionary for symptoms_table
    symptoms_table = {}
    for item in visit_doc.symptoms_table:
        item_code = item.item_code
        if item_code not in symptoms_table:
            symptoms_table[item_code] = []
        symptoms_table[item_code].append(item.as_dict())
    
    # Create a dictionary for the current visit, including the reformatted child tables
    visit_data['checktree_description'] = checktree_description
    visit_data['symptoms_table'] = symptoms_table

    return visit_data


@frappe.whitelist(allow_guest=True)
def update_checktree(status, name):
    authorization_header = frappe.get_request_header("Authorization")
    if not authorization_header:
        return { "status": "error", "message": "Missing Authorization header"}
    api_key = frappe.get_request_header("Authorization").split(" ")[1].split(":")[0]
    # Find the user associated with the API key
    user = frappe.db.get_value("User", {"api_key": api_key}, "name")
    
    if not user:
        return {"status": "failed", "message": "Invalid API key"}
    checklist = frappe.get_doc("Maintenance Visit Checklist", name)
    if not checklist:
        return {"status": "error", "message": f"Checklist with name '{name}' not found"}

    # Update the 'collected' field with the provided status
    if status == 'yes':
        checklist.work_done = 'Yes'
        checklist.done_by = user
    else:
        checklist.work_done = 'No'
        checklist.done_by = None
    checklist.flags.ignore_permissions = True
    checklist.save()
    # Commit the changes to the database
    frappe.db.commit()

    return {"status": "success", "message": f"Checklist '{name}' updated successfully", "work done": status}

@frappe.whitelist(allow_guest=True)
def live_location(lat, lon):
    authorization_header = frappe.get_request_header("Authorization")
    if not authorization_header:
        return { "status": "error", "message": "Missing Authorization header"}
    api_key = frappe.get_request_header("Authorization").split(" ")[1].split(":")[0]
    # Find the user associated with the API key
    user = frappe.db.get_value("User", {"api_key": api_key}, "name")

    if not user:
        return {"status": "failed", "message": "Invalid API key"}
    new_record = frappe.get_doc({
        "doctype": "Live Location",
        "latitude": lat,
        "longitude": lon,
        "technician": user,
        "time": now_datetime(),
    })
    new_record.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "success", "message": "Updated live Location"}

@frappe.whitelist(allow_guest=True)
def attachment(maintenance_visit):
    authorization_header = frappe.get_request_header("Authorization")
    if not authorization_header:
        return { "status": "error", "message": "Missing Authorization header"}
    api_key = frappe.get_request_header("Authorization").split(" ")[1].split(":")[0]
    # Find the user associated with the API key
    user = frappe.db.get_value("User", {"api_key": api_key}, "name")
    
    if not user:
        return {"status": "failed", "message": "Invalid API key"}
    if not maintenance_visit:
        return {"status": "Failed", "message": "Maintenance Visit not provided."}

    try:
        # Step 1: Validate if the Maintenance Visit exists
        maintenance = frappe.get_doc("Maintenance Visit", maintenance_visit)
        if not maintenance:
            return {"status": "Failed", "message": "Maintenance Visit not found."}

        # Step 2: Check if the image file is present in the request
        if 'image' not in frappe.request.files:
            return {"status": "Failed", "message": "Image file not found in the request."}

        # Step 3: Get the uploaded file from the request
        uploaded_file = frappe.request.files['image']
        file_content = uploaded_file.stream.read()

        # Step 4: Get the file extension from the content
        file_extension = imghdr.what(None, file_content)
        if not file_extension:
            return {"status": "Failed", "message": "Invalid image format"}

        # Step 5: Generate a unique filename
        unique_filename = f"{random_string(10)}.{file_extension}"

        # Step 6: Define the path to save the file in the public folder
        public_files_path = get_site_path("public", "files")
        file_path = os.path.join(public_files_path, unique_filename)

        # Step 7: Ensure the directory exists, create if not
        if not os.path.exists(public_files_path):
            os.makedirs(public_files_path)

        # Step 8: Save the file in the public folder
        with open(file_path, "wb") as f:
            f.write(file_content)

        # Step 9: Create a new record in the File Doctype
        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": unique_filename,
            "file_url": f"/files/{unique_filename}",
            "attached_to_doctype": "Maintenance Visit",
            "attached_to_name": maintenance_visit,
            "is_private": 0  # Make the file publicly accessible
        })
        file_doc.insert(ignore_permissions=True)

        # Step 10: Insert a record in the Attachments child table
        new_attachment = frappe.get_doc({
            "doctype": "Attachments",
            "parent": maintenance_visit,
            "parenttype": "Maintenance Visit",
            "parentfield": "attachments",
            "maintenance_visit": maintenance_visit,
            "image": file_doc.file_url
        })
        new_attachment.insert(ignore_permissions=True)
        frappe.db.commit()

        return {
            "status": "success",
            "message": "Image uploaded and records updated successfully",
            "file_url": file_doc.file_url
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Upload Attachment Error")
        return {"status": "Failed", "message": str(e)}

@frappe.whitelist(allow_guest=True)
def technician_notes(maintenance_visit, note):
    authorization_header = frappe.get_request_header("Authorization")
    if not authorization_header:
        return { "status": "error", "message": "Missing Authorization header"}
    api_key = frappe.get_request_header("Authorization").split(" ")[1].split(":")[0]
    # Find the user associated with the API key
    user = frappe.db.get_value("User", {"api_key": api_key}, "name")
    
    if not user:
        return {"status": "failed", "message": "Invalid API key"}
    maintenance = frappe.get_doc("Maintenance Visit", maintenance_visit)
    if not maintenance:
        return {"status": "Failed", "message": f"Maintenance Visit '{maintenance_visit}' not found."}
    
    # Update the service_tech_notes field
    maintenance.service_tech_notes = note
    maintenance.flags.ignore_permissions = True  # Avoid permission checks
    maintenance.save()  # Save the updated document
    
    return {"status": "Success", "message": f"Service Tech Notes updated for Maintenance Visit '{maintenance_visit}'."}


@frappe.whitelist(allow_guest=True)
def add_symptom_requests(maintenance_visit, item_code, symptoms=None):
    authorization_header = frappe.get_request_header("Authorization")
    if not authorization_header:
        return { "status": "error", "message": "Missing Authorization header"}
    api_key = frappe.get_request_header("Authorization").split(" ")[1].split(":")[0]
    # Find the user associated with the API key
    user = frappe.db.get_value("User", {"api_key": api_key}, "name")
    
    if not user:
        return {"status": "failed", "message": "Invalid API key"}
    # Get Maintenance Visit document
    maintenance = frappe.get_doc("Maintenance Visit", maintenance_visit)
    if not maintenance:
        return {"status": "Failed", "message": f"Maintenance Visit '{maintenance_visit}' not found."}

    # Initialize a list to hold symptom requests
    symptom_requests = []
    # Loop over all the symptoms in the request
    idx = 0
    while True:
        # Fetch the symptom fields
        symptom_code_key = f'symptoms[{idx}][symptom_code]'
        resolution_key = f'symptoms[{idx}][resolution]'
        
        if symptom_code_key in frappe.request.form and resolution_key in frappe.request.form:
            symptom_code = frappe.request.form.get(f'symptoms[{idx}][symptom_code]')
            resolution = frappe.request.form.get(f'symptoms[{idx}][resolution]')
            
            # Handle the image if it exists
            image_field = f'symptoms[{idx}][image]'
            image_url = None
            if image_field in frappe.request.files:
                uploaded_file = frappe.request.files[image_field]
                file_content = uploaded_file.stream.read()

                # Step 4: Get the file extension from the content
                file_extension = imghdr.what(None, file_content)
                if not file_extension:
                    return {"status": "Failed", "message": "Invalid image format"}

                # Step 5: Generate a unique filename using the random_string function from frappe.utils
                unique_filename = random_string(10) + "." + file_extension

                # Step 6: Define the path to save the file in the public folder
                public_files_path = get_site_path("public", "files")
                file_path = os.path.join(public_files_path, unique_filename)

                # Step 7: Ensure the directory exists, create if not
                if not os.path.exists(public_files_path):
                    os.makedirs(public_files_path)

                # Step 8: Save the file in the public folder
                with open(file_path, "wb") as f:
                    f.write(file_content)

                # Step 9: Create a new record in the File Doctype
                file_doc = frappe.get_doc({
                    "doctype": "File",
                    "file_name": unique_filename,
                    "file_url": f"/files/{unique_filename}",
                    "attached_to_doctype": "Maintenance Visit",
                    "attached_to_name": maintenance_visit,
                    "is_private": 0  # Make the file publicly accessible
                })
                file_doc.insert(ignore_permissions=True)

                # Set the file URL
                image_url = file_doc.file_url

            # Create the symptom data to insert into the child table
            symptom_data = {
                "item_code": item_code,
                "maintenance_visit": maintenance.name,
                "symptom_code": symptom_code,
                "resolution": resolution,
                "image": image_url,
            }

            # Append the processed symptom data to the list of symptom requests
            symptom_requests.append(symptom_data)

            # Increment the index to move to the next symptom
            idx += 1
        else:
            break
    # Insert all the symptom requests into the Maintenance Visit child table
    for symptom_data in symptom_requests:
        try:
            new_record = frappe.get_doc({
                "doctype": "Symptoms Requests",
                "item_code": symptom_data['item_code'],
                "maintenance_visit": symptom_data['maintenance_visit'],
                "symptom_code": symptom_data['symptom_code'],
                "resolution": symptom_data['resolution'],
                "image": symptom_data.get('image'),
                "parent": maintenance.name,
                "parenttype": "Maintenance Visit",
                "parentfield": "symptoms_requests",
            })
            new_record.insert(ignore_permissions=True)
        except Exception as e:
            frappe.throw(f"Error inserting symptom request: {str(e)}")

    # Commit the changes to the database
    frappe.db.commit()

    return {"status": "success", "message": "Symptom requests added successfully."}

@frappe.whitelist(allow_guest=True)
def add_reschedule_requests(maintenance_visit, type, reason, date, hours):
    authorization_header = frappe.get_request_header("Authorization")
    if not authorization_header:
        return { "status": "error", "message": "Missing Authorization header"}
    api_key = frappe.get_request_header("Authorization").split(" ")[1].split(":")[0]
    # Find the user associated with the API key
    user = frappe.db.get_value("User", {"api_key": api_key}, "name")
    
    if not user:
        return {"status": "failed", "message": "Invalid API key"}
    # Get Maintenance Visit document
    maintenance = frappe.get_doc("Maintenance Visit", maintenance_visit)
    if not maintenance:
        return {"status": "Failed", "message": f"Maintenance Visit '{maintenance_visit}' not found."}

    reschedule_request = frappe.get_doc({
        "doctype": "Reschedule Requests",
        "type": type,
        "reason": reason,
        "technician": user,
        "date": date,
        "hours": hours,
        "maintenance_visit": maintenance_visit,
        "parent": maintenance_visit,
        "parenttype": "Maintenance Visit",
        "parentfield": "reschedule_requests",
    })
    reschedule_request.insert(ignore_permissions=True)
    frappe.db.commit()
    return {"status": "success", "message": "Reschedule Request submitted successfully!"}

@frappe.whitelist(allow_guest=True)
def update_shipping_address():
    # Get all rows with a valid delivery_document_no
    records = frappe.get_all(
        'Serial No',
        filters={'delivery_document_no': ['is', 'set']},
        fields=['name', 'delivery_document_no']
    )
    updated_count = 0
    
    for record in records:
        # Fetch the shipping_address from Delivery Note
        
        shipping_address_name = frappe.db.get_value(
            'Delivery Note',
            record.delivery_document_no,
            'shipping_address_name'
        )
        address = frappe.db.get_value(
            "Address",
            shipping_address_name,
            ["address_line1", "address_line2", "ward_name", "district", "town", "province", "country", "phone", "fax"],
            as_dict=True
        )

        if not address:
            shipping_address = None
        else:
        # Construct the address in the desired format
            address_string = f"{address['address_line1']}<br>"
            
            if address['address_line2']:
                address_string += f"{address['address_line2']}<br>"
            
            if address['ward_name']:
                address_string += f"{address['ward_name']}<br>"
            
            if address['district']:
                address_string += f"{address['district']}<br>"
            
            address_string += f"{address['town']}<br>"
            
            if address['province']:
                address_string += f"{address['province']}<br>"
            
            address_string += f"{address['country']}<br>"
            
            if address['phone']:
                address_string += f"Phone: {address['phone']}<br>"
            
            if address['fax']:
                address_string += f"Fax: {address['fax']}<br>"
            
            shipping_address = address_string
    
        if shipping_address:
            # Update the shipping_address field in your Doctype
            frappe.db.set_value('Serial No', record.name, 'custom_item_current_installation_address', shipping_address)
            frappe.db.set_value('Serial No', record.name, 'custom_item_current_installation_address_name', shipping_address_name)
            frappe.db.commit()
            updated_count += 1
    
    return {"message": f"{updated_count} rows updated successfully."}

@frappe.whitelist(allow_guest=True)
def populate_initial_serial_card_history():
    
    serial_cards = frappe.get_all('Serial No', fields=['name', 'customer', 'custom_item_current_installation_address_name'])
    updated_count = 0

    for serial_card in serial_cards:
        # Check if there is already an entry in the Serial Card History for this Serial Card
        existing_history = frappe.get_all(
            'Serial Card History',
            filters={
                'parent': serial_card.name,
                'parentfield': 'custom_serial_card_history',
                'parenttype': 'Serial No'
            },
            fields=['name']
        )
        
        if not existing_history:
            frappe.db.sql("""
                INSERT INTO `tabSerial Card History`
                (name, parent, parentfield, parenttype, customer, address, serial_no)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                frappe.generate_hash("Serial Card History", 10),  # Generate unique name
                serial_card.name,  # Parent Serial No
                'custom_serial_card_history',  # Parent field
                'Serial No',  # Parent type
                serial_card.customer,  # Customer
                serial_card.custom_item_current_installation_address_name,  # Address
                serial_card.name  # Serial No
            ))
            frappe.db.commit()
            updated_count += 1

    return {
        "message": f"{updated_count} Serial No records updated successfully."
    }


@frappe.whitelist(allow_guest=True)
def delete_all_serial_card_history():
    try:
        # Delete all records from the 'Serial Card History' table
        frappe.db.sql("DELETE FROM `tabSerial Card History`")
        frappe.db.commit()
        
        return {"message": "All records from 'Serial Card History' table have been deleted successfully."}
    except Exception as e:
        frappe.log_error(message=str(e), title="Error Deleting Serial Card History")
        frappe.throw(f"An error occurred while deleting records: {str(e)}")
