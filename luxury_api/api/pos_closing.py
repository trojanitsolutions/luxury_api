import frappe
from datetime import datetime
from erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry import make_closing_entry_from_opening
from frappe import _
from frappe.utils import flt


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_pos_closing_entries(
	pos_profile: str | None = None,
	company: str | None = None,
	posting_date: str | None = None,
	status: str | None = None,
	pos_opening_entry: str | None = None,
):
	"""Fetch POS Closing Entries with optional filters."""
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

	if pos_profile:
		filters.append(["pos_profile", "=", pos_profile])
		applied_filters["pos_profile"] = pos_profile

	if company:
		filters.append(["company", "=", company])
		applied_filters["company"] = company

	if status:
		filters.append(["status", "=", status])
		applied_filters["status"] = status

	if pos_opening_entry:
		filters.append(["pos_opening_entry", "=", pos_opening_entry])
		applied_filters["pos_opening_entry"] = pos_opening_entry

	try:
		names = frappe.db.get_list(
			"POS Closing Entry",
			filters=filters or None,
			pluck="name",
			order_by="posting_date desc",
		)

		entries = []
		for name in names:
			doc = frappe.get_doc("POS Closing Entry", name)
			entries.append({
				"name": doc.name,
				"company": doc.company,
				"pos_profile": doc.pos_profile,
				"user": doc.user,
				"pos_opening_entry": doc.pos_opening_entry,
				"posting_date": str(doc.posting_date),
				"period_start_date": str(doc.period_start_date),
				"period_end_date": str(doc.period_end_date),
				"status": doc.status,
				"grand_total": doc.grand_total,
				"net_total": doc.net_total,
				"total_quantity": doc.total_quantity,
				"payment_reconciliation": [
					{
						"mode_of_payment": d.mode_of_payment,
						"opening_amount": d.opening_amount,
						"expected_amount": d.expected_amount,
						"closing_amount": d.closing_amount,
						"difference": d.difference,
					}
					for d in doc.payment_reconciliation
				],
			})

		return {
			"success": True,
			"count": len(entries),
			"filters": applied_filters,
			"data": entries,
		}
	except Exception as e:
		frappe.log_error(title="pos_closing.get_pos_closing_entries", message=str(e))
		frappe.local.response.http_status_code = 500
		return {"success": False, "message": str(e)}


@frappe.whitelist(methods=["POST"])
def create_pos_closing_entry(
	pos_opening_entry: str,
	payment_reconciliation: list | None = None,
	submit: int = 0,
):
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

		_add_invoices_to_closing_entry(closing_entry, opening_entry)
		_seed_opening_amounts(closing_entry, opening_entry)
		_apply_default_closing_amounts(closing_entry)
		if payment_reconciliation:
			_apply_user_closing_amounts(closing_entry, payment_reconciliation)

		closing_entry.insert()
		if int(submit or 0) == 1:
			closing_entry.submit()
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


def _fetch_pos_invoices(opening_entry):
	"""Fetch all submitted POS Invoices from the opening session that are not yet linked to a closing entry."""
	already_linked = frappe.get_all(
		"POS Invoice Reference",
		filters={},
		fields=["pos_invoice"],
		distinct=True,
	)
	linked_invoice_names = {row.pos_invoice for row in already_linked}

	invoices = frappe.get_all(
		"POS Invoice",
		filters={
			"company": opening_entry.company,
			"pos_profile": opening_entry.pos_profile,
			"docstatus": 1,
			"posting_date": [">=", opening_entry.period_start_date],
		},
		fields=["name"],
		order_by="posting_date asc",
	)

	open_invoices = [inv for inv in invoices if inv.name not in linked_invoice_names]

	if not open_invoices:
		frappe.throw(_("No POS Invoices found for this opening session."))

	return open_invoices


def _add_invoices_to_closing_entry(closing_entry, opening_entry):
	"""Fetch and add POS Invoices to the closing entry."""
	# Only add invoices if not already populated by make_closing_entry_from_opening()
	if closing_entry.pos_invoices:
		return

	invoices = _fetch_pos_invoices(opening_entry)

	for invoice in invoices:
		closing_entry.append("pos_invoices", {
			"pos_invoice": invoice.name,
		})


def _seed_opening_amounts(closing_entry, opening_entry):
	for balance_detail in opening_entry.balance_details:
		mode = balance_detail.mode_of_payment
		opening_amount = balance_detail.opening_amount

		row = next((r for r in closing_entry.payment_reconciliation if r.mode_of_payment == mode), None)
		if row:
			row.opening_amount = opening_amount
			row.expected_amount += opening_amount
		else:
			closing_entry.append("payment_reconciliation", {
				"mode_of_payment": mode,
				"opening_amount": opening_amount,
				"expected_amount": opening_amount,
			})


def _apply_default_closing_amounts(closing_entry):
	for row in closing_entry.payment_reconciliation:
		row.closing_amount = row.expected_amount
		row.difference = row.closing_amount - row.expected_amount


def _apply_user_closing_amounts(closing_entry, payment_reconciliation):
	for user_entry in payment_reconciliation:
		mode = user_entry.get("mode_of_payment")
		closing_amount = user_entry.get("closing_amount")

		if closing_amount is None:
			frappe.throw(_("closing_amount is required for mode_of_payment '{0}'.").format(mode))

		row = next((r for r in closing_entry.payment_reconciliation if r.mode_of_payment == mode), None)
		if not row:
			frappe.throw(_("Mode of payment '{0}' not found in payment reconciliation.").format(mode))

		row.closing_amount = flt(closing_amount)
		row.difference = row.closing_amount - row.expected_amount
