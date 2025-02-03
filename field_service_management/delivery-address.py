
import frappe


@frappe.whitelist(allow_guest=True)
def get_delivery_notes(customer, doctype, txt, searchfield, start, page_len, filters):
    addresses = frappe.db.get_all(
        "Address",
        filters={"link_doctype": "Customer", "link_name": customer},
        fields=["address_line1", "address_line2", "ward_name", "district", "town", "province", "country", "phone", "fax"]
    )
    
    formatted_addresses = []
    
    for address in addresses:
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
        
        formatted_addresses.append(address_string)

    return formatted_addresses


@frappe.whitelist(allow_guest=True)
def get_items_for_address(doctype, txt, searchfield, start, page_len, filters):

    # Extract the shipping_address from filters
    shipping_address = filters.get('shipping_address') if filters else None

    if not shipping_address:
        return []

    # Fetch delivery notes with the selected shipping address
    serial_no_cards = frappe.db.get_all(
        "Serial No",
        filters={"custom_item_current_installation_address": shipping_address},
        fields=["name"]
    )

    # Fetch items and their serial numbers from Delivery Note Items
    items = []
    for note in serial_no_cards:
        delivery_items = frappe.db.get_all(
            "Serial No",
            filters={"name": note.name},  # Link between Delivery Note and Delivery Note Item
            fields=["item_code", "item_name", "name"]
        )
        # items.extend(delivery_note_items)

        item_codes = [item["item_code"] for item in delivery_items]
        flags = frappe.db.get_all(
            "Item",
            filters={"item_code": ["in", item_codes]},
            fields=["item_code", "custom_flag"]
        )
        flag_map = {f["item_code"]: f["custom_flag"] for f in flags}
        filtered_items = [item for item in delivery_items if flag_map.get(item["item_code"]) == '1']
        items.extend(filtered_items)

    # Return the items in the expected format (value and description)
    return [
        (item["item_code"], f"<b>{item['item_name']}</b> | {item.get('name', 'None')}")  # Passing the whole item object
        for item in items
    ]


@frappe.whitelist(allow_guest=True)
def get_delivery_note_data(delivery_address, item_code):

    # Fetch matching Delivery Notes
    items = frappe.get_list(
        "Serial No",
        filters={"custom_item_current_installation_address": delivery_address},
        fields=["item_code", "item_name", "name"]
    )
    if not items:
        return []

    return items


@frappe.whitelist(allow_guest=True)
def get_item_table(name):
    # childs = frappe.db.get_all(
    #     "Item Maintenance Table",
    #     filters = {"parent": name},
    #     fields = ["heading", "content"]
    # )
    # return childs
    childs = frappe.db.sql(
        """
        SELECT heading, content
        FROM `tabItem Maintenance Table`
        WHERE parent = %s
        """,
        (name,),
        as_dict=True
    )
    return childs


@frappe.whitelist(allow_guest=True)
def get_symptoms_table(name):
    # childs = frappe.db.get_all(
    #     "Symptom Resolution Table",
    #     filters = {"parent": name},
    #     fields = ["symptom_code", "resolution", "attach_image"]
    # )
    # return childs
    childs = frappe.db.sql(
        """
        SELECT symptom_code, resolution, attach_image
        FROM `tabSymptom Resolution Table`
        WHERE parent = %s
        """,
        (name,),
        as_dict=True
    )
    return childs


@frappe.whitelist(allow_guest=True)
def get_spare_items(name):
    # childs = frappe.db.get_all(
    #     "Spare Part",
    #     filters = {"parent": name},
    #     fields = ["item_code", "description", "rate", "rate_eur", "periodicity", "frequency_in_years", "uom"]
    # )
    # return childs
    childs = frappe.db.sql(
        """
        SELECT item_code, description, rate, rate_eur, periodicity, frequency_in_years, uom
        FROM `tabSpare Part`
        WHERE parent = %s
        """,
        (name,),
        as_dict=True
    )
    return childs

@frappe.whitelist(allow_guest=True)
def get_item(name):
    childs = frappe.get_doc('Item', name)
    return childs



@frappe.whitelist(allow_guest=True)
def get_item_code_from_child_table(cdn):
    if frappe.has_permission('Maintenance Visit Purpose', 'read'):
        item_code = frappe.db.get_value('Maintenance Visit Purpose', cdn, 'item_code')
        return item_code
    else:
        frappe.throw(_("You do not have permission to access this resource."))


@frappe.whitelist(allow_guest=True)
def site_survey(name):
    # childs = frappe.db.get_all(
    #     "Item Maintenance Table",
    #     filters = {"parent": name},
    #     fields = ["heading", "content"]
    # )
    # return childs
    childs = frappe.db.sql(
        """
        SELECT heading, content
        FROM `tabItem Maintenance Table`
        WHERE parent = %s
        """,
        (name,),
        as_dict=True
    )
    return childs


@frappe.whitelist(allow_guest=True)
def update_maintenance_visit(maintenance_visit, name):
    if not maintenance_visit:
        return
    try:
        frappe.db.sql("""
            UPDATE `tabMaintenance Visit`
            SET _assign = %s, maintenance_type = %s
            WHERE name = %s
        """, ('', 'Rescheduled', maintenance_visit))  # Empty _assign and set maintenance_type to Rescheduled
        
        # Commit the transaction to ensure changes are saved
        frappe.db.commit()

        print("Maintenance Visit updated successfully.")
    except Exception as e:
        print(f"Error updating Maintenance Visit: {e}")

    reschedule_doc = frappe.get_doc("Reschedule Requests", name)
    reschedule_doc.approval = 'Approved'
    reschedule_doc.approval_status = '1'
    reschedule_doc.save(ignore_permissions=True)

    return {"success": True}

@frappe.whitelist(allow_guest=True)
def get_customer_addresses(customer):
    return frappe.db.sql(
        """
        SELECT 
            addr.name, addr.address_line1, addr.address_line2, addr.ward_name, addr.district,
            addr.town, addr.province, addr.country, addr.phone
        FROM `tabAddress` addr
        JOIN `tabDynamic Link` link ON link.parent = addr.name
        WHERE link.link_doctype = 'Customer' AND link.link_name = %s
        """,
        (customer),
        as_dict=True
    )