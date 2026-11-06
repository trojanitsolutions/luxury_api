import frappe
from datetime import datetime
from frappe import _
from frappe.query_builder.functions import Count, Sum
from frappe.utils import flt

from luxury_api.customizations.sales_invoice_commission import paid_commission_query

SUMMARY_FIELDS = ("net_total", "amount_eligible_for_commission", "total_commission", "commission_paid")


def _respond(code, message):
	frappe.local.response.http_status_code = code
	return {"success": False, "message": message}


def _get_branch_pos_profiles(branch):
	return frappe.get_all("POS Profile", filters={"branch": branch}, pluck="name")


def _apply_filters(query, si, st, filters, pos_profiles):
	if filters.get("from_date"):
		query = query.where(si.posting_date >= filters["from_date"])
	if filters.get("to_date"):
		query = query.where(si.posting_date <= filters["to_date"])
	for field in ("company", "pos_profile", "channel"):
		if filters.get(field):
			query = query.where(si[field] == filters[field])
	if filters.get("sales_person"):
		query = query.where(st.sales_person == filters["sales_person"])
	if pos_profiles is not None:
		query = query.where(si.pos_profile.isin(pos_profiles))
	return query


def _fetch_paid_map(filters, pos_profiles):
	"""Commission actually paid (submitted JE) per sales person, including cancelled invoices whose payment was kept."""
	si, st, query = paid_commission_query()
	query = query.select(st.sales_person, Sum(st.incentives).as_("paid")).groupby(st.sales_person)
	rows = _apply_filters(query, si, st, filters, pos_profiles).run(as_dict=True)
	return {r.sales_person: flt(r.paid) for r in rows}


def _merge_paid(rows, paid_map):
	"""Add commission_paid to each row. A sales person may only have paid rows (all invoices cancelled)."""
	by_person = {r.sales_person: r for r in rows}
	for person, paid in paid_map.items():
		if person not in by_person:
			by_person[person] = frappe._dict(
				sales_person=person, invoice_count=0, net_total=0, amount_eligible_for_commission=0, total_commission=0
			)
		by_person[person].commission_paid = paid
	for row in by_person.values():
		row.setdefault("commission_paid", 0)
	return [by_person[p] for p in sorted(by_person)]


def _fetch_commission_rows(filters, pos_profiles):
	"""One grouped query: commission totals per Sales Person (Sales Team row) for submitted POS invoices."""
	si = frappe.qb.DocType("Sales Invoice")
	st = frappe.qb.DocType("Sales Team")
	query = (
		frappe.qb.from_(si)
		.inner_join(st)
		.on((st.parent == si.name) & (st.parenttype == "Sales Invoice"))
		.select(
			st.sales_person,
			Count(si.name).distinct().as_("invoice_count"),
			Sum(si.base_net_total * st.allocated_percentage / 100).as_("net_total"),
			Sum(st.allocated_amount).as_("amount_eligible_for_commission"),
			Sum(st.incentives).as_("total_commission"),
		)
		.where(si.docstatus == 1)
		.where(si.is_pos == 1)
		.where(si.is_created_using_pos == 1)
		.groupby(st.sales_person)
		.orderby(st.sales_person)
	)
	return _apply_filters(query, si, st, filters, pos_profiles).run(as_dict=True)


@frappe.whitelist(allow_guest=False, methods=["GET"])
def list_sales_persons():
	try:
		data = frappe.get_list(
			"Sales Person",
			filters={"enabled": 1, "is_group": 0},
			fields=["name", "sales_person_name", "employee", "department"],
			order_by="sales_person_name asc",
			limit_page_length=0,
		)
	except frappe.PermissionError:
		return _respond(403, "Access Denied.")

	return {"success": True, "count": len(data), "data": data}


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_commission_summary(
	from_date: str | None = None,
	to_date: str | None = None,
	company: str | None = None,
	sales_person: str | None = None,
	pos_profile: str | None = None,
	channel: str | None = None,
	branch: str | None = None,
):
	"""Commission per Sales Person.

	total_commission = earned, net of returns (submitted invoices only).
	commission_paid = paid on the spot through a submitted Journal Entry.
	"""
	frappe.has_permission("Sales Invoice", "read", throw=True)

	applied = {}
	for key, value in (("from_date", from_date), ("to_date", to_date)):
		if value:
			try:
				datetime.strptime(value, "%Y-%m-%d")
			except ValueError:
				return _respond(400, f"Invalid {key} format. Use YYYY-MM-DD.")
			applied[key] = value

	for key, value in (
		("company", company),
		("sales_person", sales_person),
		("pos_profile", pos_profile),
		("channel", channel),
		("branch", branch),
	):
		if value:
			applied[key] = value

	pos_profiles = None
	if branch:
		pos_profiles = _get_branch_pos_profiles(branch)
		if not pos_profiles:
			return _respond(404, _("No POS Profile found for branch '{0}'.").format(branch))

	try:
		rows = _merge_paid(
			_fetch_commission_rows(applied, pos_profiles), _fetch_paid_map(applied, pos_profiles)
		)
	except Exception:
		frappe.log_error(title="luxury_api.sales_person.get_commission_summary")
		return _respond(500, "Failed to get commission summary.")

	totals = {"invoice_count": sum(r.invoice_count for r in rows)}
	for field in SUMMARY_FIELDS:
		totals[field] = sum(flt(r[field]) for r in rows)

	return {"success": True, "filters": applied, "data": rows, "totals": totals}
