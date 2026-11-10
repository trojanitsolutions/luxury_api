import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

CUSTOM_FIELDS = {
    "POS Profile": [
        {
            "fieldname": "branch",
            "fieldtype": "Data",
            "label": "Branch",
            "insert_after": "company_address",
            "fetch_from": "warehouse.branch",
            "read_only": 1,
        },
        {
            "fieldname": "commission_expense_account",
            "fieldtype": "Link",
            "options": "Account",
            "label": "Commission Expense Account",
            "insert_after": "branch",
            "description": "Debited when Sales Person commission is paid on the spot.",
        },
        {
            "fieldname": "auto_cancel_commission_payment",
            "fieldtype": "Select",
            "options": "Yes\nNo",
            "default": "Yes",
            "label": "Auto Cancel Commission Payment",
            "insert_after": "commission_expense_account",
            "description": "Yes: cancelling an invoice also cancels its commission payment. "
            "No: the POS must say whether the sales person keeps the commission.",
        },
        {
            "fieldname": "auto_recover_commission_on_return",
            "fieldtype": "Select",
            "options": "Yes\nNo",
            "default": "Yes",
            "label": "Auto Recover Commission on Return",
            "insert_after": "auto_cancel_commission_payment",
            "description": "Yes: a return automatically records the sales person giving back the returned share in cash. "
            "No: the POS must say whether the sales person gives it back.",
        },
    ],
    "Sales Invoice": [
        {
            "fieldname": "commission_paid",
            "fieldtype": "Check",
            "label": "Commission Paid",
            "insert_after": "total_commission",
            "read_only": 1,
            "no_copy": 1,
        },
        {
            "fieldname": "commission_mode_of_payment",
            "fieldtype": "Link",
            "options": "Mode of Payment",
            "label": "Commission Mode of Payment",
            "insert_after": "commission_paid",
            "read_only": 1,
            "no_copy": 1,
        },
        {
            "fieldname": "commission_journal_entry",
            "fieldtype": "Link",
            "options": "Journal Entry",
            "label": "Commission Journal Entry",
            "insert_after": "commission_mode_of_payment",
            "read_only": 1,
            "no_copy": 1,
            "allow_on_submit": 1,
        },
    ],
    "Journal Entry": [
        {
            "fieldname": "commission_sales_invoice",
            "fieldtype": "Link",
            "options": "Sales Invoice",
            "label": "Commission for Sales Invoice",
            "insert_after": "voucher_type",
            "read_only": 1,
            "no_copy": 1,
            "depends_on": "eval:doc.commission_sales_invoice",
        },
    ],
}

# Fields from an earlier version that duplicated ERPNext's own Commission section
OBSOLETE_FIELDS = {
    "Sales Invoice": [
        "commission_details_section",
        "commission_sales_person",
        "commission_amount",
        "commission_column_break",
    ],
}



def create_custom_fields():
    for doctype, fields in CUSTOM_FIELDS.items():
        for field in fields:
            cf_name = f"{doctype}-{field['fieldname']}"
            if frappe.db.exists("Custom Field", cf_name):
                frappe.db.set_value("Custom Field", cf_name, {"fieldtype": field["fieldtype"], "insert_after": field["insert_after"]})
            else:
                create_custom_field(doctype, field)
            frappe.db.commit()
            frappe.clear_cache(doctype=doctype)

def remove_obsolete_fields():
    for doctype, fieldnames in OBSOLETE_FIELDS.items():
        for fieldname in fieldnames:
            cf_name = f"{doctype}-{fieldname}"
            if frappe.db.exists("Custom Field", cf_name):
                frappe.delete_doc("Custom Field", cf_name, ignore_missing=True)
        frappe.clear_cache(doctype=doctype)
    frappe.db.commit()


def backfill_commission_fields():
    """Link old commission JEs back to their invoice (made before the JE field existed)."""
    rows = frappe.get_all(
        "Sales Invoice",
        filters={"commission_journal_entry": ["is", "set"]},
        fields=["name", "commission_journal_entry"],
    )
    for row in rows:
        if not frappe.db.get_value("Journal Entry", row.commission_journal_entry, "commission_sales_invoice"):
            frappe.db.set_value(
                "Journal Entry", row.commission_journal_entry, "commission_sales_invoice", row.name, update_modified=False
            )
    frappe.db.commit()


def after_migrate():
    remove_obsolete_fields()
    create_custom_fields()
    backfill_commission_fields()


def delete_custom_fields():
    for doctype, fields in CUSTOM_FIELDS.items():
        for field in fields:
            cf_name = f"{doctype}-{field['fieldname']}"
            if frappe.db.exists("Custom Field", cf_name):
                frappe.delete_doc("Custom Field", cf_name, ignore_missing=True)
                frappe.db.commit()
                frappe.clear_cache(doctype=doctype)
