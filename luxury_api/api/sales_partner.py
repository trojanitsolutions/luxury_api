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


def _apply_filters(query, si, filters, pos_profiles):
	if filters.get("from_date"):
		query = query.where(si.posting_date >= filters["from_date"])
	if filters.get("to_date"):
		query = query.where(si.posting_date <= filters["to_date"])
	for field in ("company", "sales_partner", "pos_profile", "channel"):
		if filters.get(field):
			query = query.where(si[field] == filters[field])
	if pos_profiles is not None:
		query = query.where(si.pos_profile.isin(pos_profiles))
	return query


def _fetch_paid_map(filters, pos_profiles):
	"""Commission actually paid (submitted JE) per partner, including cancelled invoices whose payment was kept."""
	si, query = paid_commission_query()
	query = query.select(si.sales_partner, Sum(si.total_commission).as_("paid")).groupby(si.sales_partner)
	rows = _apply_filters(query, si, filters, pos_profiles).run(as_dict=True)
	return {r.sales_partner: flt(r.paid) for r in rows}


def _merge_paid(rows, paid_map):
	"""Add commission_paid to each partner row. A partner may only have paid rows (all invoices cancelled)."""
	by_partner = {r.sales_partner: r for r in rows}
	for partner, paid in paid_map.items():
		if partner not in by_partner:
			by_partner[partner] = frappe._dict(
				sales_partner=partner, invoice_count=0, net_total=0, amount_eligible_for_commission=0, total_commission=0
			)
		by_partner[partner].commission_paid = paid
	for row in by_partner.values():
		row.setdefault("commission_paid", 0)
	return [by_partner[p] for p in sorted(by_partner)]


def _fetch_commission_rows(filters, pos_profiles):
	"""One grouped query: commission totals per Sales Partner for submitted POS invoices."""
	si = frappe.qb.DocType("Sales Invoice")
	query = (
		frappe.qb.from_(si)
		.select(
			si.sales_partner,
			Count(si.name).as_("invoice_count"),
			Sum(si.base_net_total).as_("net_total"),
			Sum(si.amount_eligible_for_commission).as_("amount_eligible_for_commission"),
			Sum(si.total_commission).as_("total_commission"),
		)
		.where(si.docstatus == 1)
		.where(si.is_pos == 1)
		.where(si.is_created_using_pos == 1)
		.where(si.sales_partner.isnotnull())
		.where(si.sales_partner != "")
		.groupby(si.sales_partner)
		.orderby(si.sales_partner)
	)
	return _apply_filters(query, si, filters, pos_profiles).run(as_dict=True)


@frappe.whitelist(allow_guest=False, methods=["GET"])
def list_sales_partners():
	try:
		data = frappe.get_list(
			"Sales Partner",
			fields=["name", "partner_name", "partner_type", "territory"],
			order_by="partner_name asc",
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
	sales_partner: str | None = None,
	pos_profile: str | None = None,
	channel: str | None = None,
	branch: str | None = None,
):
	"""Commission per Sales Partner.

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
		("sales_partner", sales_partner),
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
		frappe.log_error(title="luxury_api.sales_partner.get_commission_summary")
		return _respond(500, "Failed to get commission summary.")

	totals = {"invoice_count": sum(r.invoice_count for r in rows)}
	for field in SUMMARY_FIELDS:
		totals[field] = sum(flt(r[field]) for r in rows)

	return {"success": True, "filters": applied, "data": rows, "totals": totals}
