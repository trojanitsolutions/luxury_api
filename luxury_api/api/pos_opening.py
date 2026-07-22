import frappe
from datetime import datetime


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_pos_opening_entries(posting_date: str | None = None, status: str | None = None, pos_profile: str | None = None):
	"""Fetch POS Opening Entries with optional filters."""
	filters = []
	applied_filters = {}

	if posting_date:
		try:
			datetime.strptime(posting_date, "%Y-%m-%d")
		except ValueError:
			frappe.local.response.http_status_code = 400
			return {"success": False, "message": "Invalid posting_date format. Use YYYY-MM-DD."}
		filters.append(["posting_date", "=", posting_date])
		applied_filters["posting_date"] = posting_date

	if status:
		filters.append(["status", "=", status])
		applied_filters["status"] = status

	if pos_profile:
		filters.append(["pos_profile", "=", pos_profile])
		applied_filters["pos_profile"] = pos_profile

	try:
		names = frappe.db.get_list(
			"POS Opening Entry",
			filters=filters or None,
			pluck="name",
			order_by="posting_date desc",
		)

		entries = []
		for name in names:
			doc = frappe.get_doc("POS Opening Entry", name)
			entries.append({
				"name": doc.name,
				"company": doc.company,
				"pos_profile": doc.pos_profile,
				"user": doc.user,
				"posting_date": str(doc.posting_date),
				"period_start_date": str(doc.period_start_date),
				"status": doc.status,
				"balance_details": [
					{"mode_of_payment": d.mode_of_payment, "opening_amount": d.opening_amount}
					for d in doc.balance_details
				],
			})

		return {
			"success": True,
			"count": len(entries),
			"filters": applied_filters,
			"data": entries,
		}
	except Exception as e:
		frappe.log_error(title="pos_opening.get_pos_opening_entries", message=str(e))
		frappe.local.response.http_status_code = 500
		return {"success": False, "message": str(e)}


@frappe.whitelist(methods=["POST"])
def create_pos_opening_entry(
	pos_profile: str,
	user: str,
	company: str,
	period_start_date: str,
	balance_details: list,
):
	
	try:
		doc = frappe.get_doc({
			"doctype": "POS Opening Entry",
			"pos_profile": pos_profile,
			"user": user,
			"company": company,
			"period_start_date": period_start_date,
			"balance_details": balance_details,
		})
		doc.insert()
		doc.submit()

		frappe.local.response.http_status_code = 201
		return {
			"success": True,
			"message": "POS Opening Entry created successfully.",
			"name": doc.name,
		}
	except frappe.ValidationError as e:
		frappe.local.response.http_status_code = 400
		return {"success": False, "message": str(e)}
	except Exception as e:
		frappe.log_error(title="pos_opening.create_pos_opening_entry", message=str(e))
		frappe.local.response.http_status_code = 500
		return {"success": False, "message": str(e)}
