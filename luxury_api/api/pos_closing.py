import frappe
from datetime import datetime
from erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry import (
	get_payments,
	get_taxes,
)
from frappe import _
from frappe.utils import flt
from frappe.query_builder import DocType
from frappe.query_builder import functions as fn
from frappe.query_builder.custom import ConstantColumn


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
				"sales_invoices": [
					{
						"sales_invoice": d.sales_invoice,
						"posting_date": str(d.posting_date) if d.posting_date else None,
						"customer": d.customer,
						"grand_total": d.grand_total,
						"is_return": d.is_return,
						"return_against": d.return_against,
					}
					for d in doc.sales_invoices
				],
				"pos_invoices": [
					{
						"pos_invoice": d.pos_invoice,
						"posting_date": str(d.posting_date) if d.posting_date else None,
						"customer": d.customer,
						"grand_total": d.grand_total,
						"is_return": d.is_return,
						"return_against": d.return_against,
					}
					for d in doc.pos_invoices
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
		closing_entry = _make_closing_entry_from_opening_multi_user(opening_entry)

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


def _build_invoice_query(invoice_doctype, pos_profile, start, end):
	"""Build invoice query without owner filter, to support multi-cashier POS sessions."""
	InvoiceDocType = DocType(invoice_doctype)
	query = (
		frappe.qb.from_(InvoiceDocType)
		.select(
			InvoiceDocType.name,
			InvoiceDocType.customer,
			InvoiceDocType.posting_date,
			InvoiceDocType.grand_total,
			InvoiceDocType.net_total,
			InvoiceDocType.total_qty,
			InvoiceDocType.total_taxes_and_charges,
			InvoiceDocType.change_amount,
			InvoiceDocType.account_for_change_amount,
			InvoiceDocType.is_return,
			InvoiceDocType.return_against,
			fn.Timestamp(InvoiceDocType.posting_date, InvoiceDocType.posting_time).as_("timestamp"),
			ConstantColumn(invoice_doctype).as_("doctype"),
		)
		.where(
			(InvoiceDocType.docstatus == 1)
			& (InvoiceDocType.is_pos == 1)
			& (InvoiceDocType.pos_profile == pos_profile)
			& (
				(fn.Timestamp(InvoiceDocType.posting_date, InvoiceDocType.posting_time) >= start)
				& (fn.Timestamp(InvoiceDocType.posting_date, InvoiceDocType.posting_time) <= end)
			)
		)
	)

	if invoice_doctype == "POS Invoice":
		query = query.where(fn.IfNull(InvoiceDocType.consolidated_invoice, "").eq(""))
	else:
		query = query.where(
			(InvoiceDocType.is_created_using_pos == 1)
			& fn.IfNull(InvoiceDocType.pos_closing_entry, "").eq("")
		)

	return query


def _get_invoices_multi_user(start, end, pos_profile):
	"""Fetch invoices without owner filter, supporting multi-cashier POS sessions."""
	sales_inv_query = _build_invoice_query("Sales Invoice", pos_profile, start, end)
	pos_inv_query = _build_invoice_query("POS Invoice", pos_profile, start, end)
	query = (sales_inv_query + pos_inv_query).orderby(sales_inv_query.timestamp)
	invoices = query.run(as_dict=1)
	return {"invoices": invoices, "payments": get_payments(invoices), "taxes": get_taxes(invoices)}


def _make_closing_entry_from_opening_multi_user(opening_entry):
	"""Build closing entry including invoices from all users in the POS Profile."""
	closing_entry = frappe.new_doc("POS Closing Entry")
	closing_entry.pos_opening_entry = opening_entry.name
	closing_entry.period_start_date = opening_entry.period_start_date
	closing_entry.period_end_date = frappe.utils.get_datetime()
	closing_entry.pos_profile = opening_entry.pos_profile
	closing_entry.user = opening_entry.user
	closing_entry.company = opening_entry.company
	closing_entry.grand_total = 0
	closing_entry.net_total = 0
	closing_entry.total_quantity = 0
	closing_entry.total_taxes_and_charges = 0

	data = _get_invoices_multi_user(
		closing_entry.period_start_date,
		closing_entry.period_end_date,
		closing_entry.pos_profile,
	)

	pos_invoices = []
	sales_invoices = []
	taxes = [
		frappe._dict({"account_head": tx.account_head, "amount": tx.tax_amount}) for tx in data.get("taxes")
	]
	payments = [
		frappe._dict(
			{
				"mode_of_payment": p.mode_of_payment,
				"opening_amount": 0,
				"expected_amount": p.amount,
			}
		)
		for p in data.get("payments")
	]

	for d in data.get("invoices"):
		invoice = "pos_invoice" if d.doctype == "POS Invoice" else "sales_invoice"
		invoice_data = frappe._dict(
			{
				invoice: d.name,
				"posting_date": d.posting_date,
				"grand_total": d.grand_total,
				"customer": d.customer,
				"is_return": d.is_return,
				"return_against": d.return_against,
			}
		)
		if d.doctype == "POS Invoice":
			pos_invoices.append(invoice_data)
		else:
			sales_invoices.append(invoice_data)

		closing_entry.grand_total += flt(d.grand_total)
		closing_entry.net_total += flt(d.net_total)
		closing_entry.total_quantity += flt(d.total_qty)
		closing_entry.total_taxes_and_charges += flt(d.total_taxes_and_charges)

	closing_entry.set("pos_invoices", pos_invoices)
	closing_entry.set("sales_invoices", sales_invoices)
	closing_entry.set("payment_reconciliation", payments)
	closing_entry.set("taxes", taxes)

	return closing_entry
