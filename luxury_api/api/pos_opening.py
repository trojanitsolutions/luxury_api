import frappe
from frappe import _


@frappe.whitelist(methods=["POST"])
def create_pos_opening_entry(
	pos_profile: str = None,
	user: str = None,
	company: str = None,
	period_start_date: str = None,
	balance_details=None,
):
	pos_profile = (pos_profile or "").strip()
	user = (user or "").strip()
	company = (company or "").strip()
	balance_details = _parse_balance_details(balance_details)

	if not pos_profile or not user or not company or not balance_details:
		frappe.local.response.http_status_code = 400
		return {
			"success": False,
			"message": "POS Profile, User, Company and Balance Details (with at least one payment mode) are mandatory.",
		}

	if not frappe.db.exists("POS Profile", pos_profile):
		frappe.local.response.http_status_code = 404
		return {"success": False, "message": _("POS Profile '{0}' does not exist.").format(pos_profile)}

	if not _is_user_assigned_to_profile(pos_profile, user):
		frappe.local.response.http_status_code = 400
		return {
			"success": False,
			"message": _("User '{0}' is not assigned to POS Profile '{1}'.").format(user, pos_profile),
		}

	try:
		opening_entry = _create_opening_entry(pos_profile, user, company, period_start_date, balance_details)
	except frappe.ValidationError as e:
		frappe.db.rollback()
		frappe.local.response.http_status_code = 409
		return {"success": False, "message": str(e)}
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="luxury_api.pos_opening.create_pos_opening_entry")
		frappe.local.response.http_status_code = 500
		return {"success": False, "message": "Failed to create POS Opening Entry. Please try again."}

	frappe.local.response.http_status_code = 201
	return {
		"success": True,
		"message": "POS Opening Entry created successfully.",
		"pos_opening_entry": {
			"name": opening_entry.name,
			"pos_profile": opening_entry.pos_profile,
			"user": opening_entry.user,
			"company": opening_entry.company,
			"status": opening_entry.status,
			"period_start_date": opening_entry.period_start_date,
		},
	}


def _parse_balance_details(balance_details):
	if isinstance(balance_details, str):
		balance_details = frappe.parse_json(balance_details)
	return balance_details or []


def _is_user_assigned_to_profile(pos_profile, user):
	return frappe.db.exists("POS Profile User", {"parent": pos_profile, "user": user})


def _create_opening_entry(pos_profile, user, company, period_start_date, balance_details):
	opening_entry = frappe.get_doc(
		{
			"doctype": "POS Opening Entry",
			"pos_profile": pos_profile,
			"user": user,
			"company": company,
			"period_start_date": period_start_date or frappe.utils.now(),
			"balance_details": balance_details,
		}
	)
	opening_entry.insert()
	opening_entry.submit()
	return opening_entry
