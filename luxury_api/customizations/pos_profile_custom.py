import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

def create_custom_fields():
    custom_fields = {
        "POS Profile": [
            {
                "fieldname": "branch",
                "fieldtype": "Data",
                "label": "Branch",
                "insert_after": "company_address",
                "fetch_from": "warehouse.branch",
                "read_only": 1,
            }
        ]
    }

    for doctype, fields in custom_fields.items():
        for field in fields:
            cf_name = f"{doctype}-{field['fieldname']}"
            if frappe.db.exists("Custom Field", cf_name):
                frappe.db.set_value("Custom Field", cf_name, {"fieldtype": field["fieldtype"]})
            else:
                create_custom_field(doctype, field)
            frappe.db.commit()
            frappe.clear_cache(doctype=doctype)

def delete_custom_fields(): 
    custom_fields_to_delete = { "POS Profile": ["branch"] }  

    for doctype, fields in custom_fields_to_delete.items(): 
        for field_name in fields: 
            if frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": field_name}): 
                frappe.delete_doc("Custom Field", f"{doctype}-{field_name}", ignore_missing=True) 
                frappe.db.commit() 
                frappe.clear_cache(doctype=doctype)      