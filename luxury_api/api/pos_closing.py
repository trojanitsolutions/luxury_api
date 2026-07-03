import frappe
from erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry import make_closing_entry_from_opening
from frappe import _


@frappe.whitelist(methods=["POST"])
def create_pos_closing_entry(pos_opening_entry: str = None):
	pos_opening_entry = (pos_opening_entry or "").strip()

	if not pos_opening_entry:
		frappe.local.response.http_status_code = 400
		return {"success": False, "message": "POS Opening Entry is mandatory."}

	if not frappe.db.exists("POS Opening Entry", pos_opening_entry):
		frappe.local.response.http_status_code = 404
		return {
			"success": False,
			"message": _("POS Opening Entry '{0}' does not exist.").format(pos_opening_entry),
		}

	status = frappe.db.get_value("POS Opening Entry", pos_opening_entry, "status")
	if status == "Closed":
		frappe.local.response.http_status_code = 409
		return {
			"success": False,
			"message": _("POS Opening Entry '{0}' is already closed.").format(pos_opening_entry),
		}
	if status != "Open":
		frappe.local.response.http_status_code = 400
		return {
			"success": False,
			"message": _("POS Opening Entry '{0}' must be Open to be closed.").format(pos_opening_entry),
		}

	try:
		opening_entry = frappe.get_doc("POS Opening Entry", pos_opening_entry)
		closing_entry = make_closing_entry_from_opening(opening_entry)
		_apply_default_closing_amounts(closing_entry)
		closing_entry.insert()
	except frappe.ValidationError as e:
		frappe.db.rollback()
		frappe.local.response.http_status_code = 400
		return {"success": False, "message": str(e)}
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="luxury_api.pos_closing.create_pos_closing_entry")
		frappe.local.response.http_status_code = 500
		return {"success": False, "message": "Failed to create POS Closing Entry. Please try again."}

	frappe.local.response.http_status_code = 201
	return {
		"success": True,
		"message": "POS Closing Entry created successfully.",
		"pos_closing_entry": closing_entry.as_dict(),
	}


def _apply_default_closing_amounts(closing_entry):
	for row in closing_entry.payment_reconciliation:
		row.closing_amount = row.expected_amount
		row.difference = 0
