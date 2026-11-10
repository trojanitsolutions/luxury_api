import frappe
from datetime import datetime

from luxury_api.api.sales_invoice_pos import _get_commission_info

ALLOWED_ORDER_BY = {"posting_date", "grand_total", "customer", "status", "modified"}
INVOICE_FIELDS = [
	"name",
	"customer",
	"customer_name",
	"company",
	"pos_profile",
	"channel",
	"posting_date",
	"grand_total",
	"outstanding_amount",
	"status",
	"docstatus",
	"is_return",
]
ITEM_FIELDS = ["parent", "item_code", "item_name", "qty", "rate", "amount"]


@frappe.whitelist(allow_guest=False, methods=["GET"])
def search_sales_invoices(
	customer_name: str | None = None,
	item_code: str | None = None,
	posting_date: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
	page: int | str = 1,
	page_length: int | str = 20,
	order_by: str = "posting_date",
	order: str = "desc",
):
	customer_name = (customer_name or "").strip()
	item_code = (item_code or "").strip()

	if not any((customer_name, item_code, posting_date, from_date, to_date)):
		return _respond(
			400, "Provide at least one of customer_name, item_code, posting_date, from_date, to_date."
		)

	try:
		filters, applied = _build_date_filters(posting_date, from_date, to_date)
		page, page_length = _validate_paging(page, page_length, order_by, order)
	except ValueError as e:
		return _respond(400, str(e))

	filters.append(["pos_profile", "is", "set"])
	or_filters = None

	if customer_name:
		or_filters = _customer_or_filters(customer_name)
		applied["customer_name"] = customer_name

	if item_code:
		filters.append(["name", "in", _invoices_with_item(item_code) or [""]])
		applied["item_code"] = item_code

	try:
		data = frappe.get_list(
			"Sales Invoice",
			filters=filters,
			or_filters=or_filters,
			fields=INVOICE_FIELDS,
			order_by=f"{order_by} {order}",
			limit_start=(page - 1) * page_length,
			limit_page_length=page_length,
		)
		names = [row.name for row in data]
		commission = _get_commission_info(names)
		items_map = _fetch_items_map(names)
		for row in data:
			row.update(commission[row.name])
			row["items"] = items_map.get(row.name, [])
		return {"success": True, "count": len(data), "filters": applied, "data": data}
	except Exception as e:
		frappe.log_error(title="sales_invoice_find.search_sales_invoices", message=str(e))
		return _respond(500, str(e))


def _respond(code, message):
	frappe.local.response.http_status_code = code
	return {"success": False, "message": message}


def _parse_date(key, value):
	try:
		return datetime.strptime(value, "%Y-%m-%d").date()
	except (TypeError, ValueError):
		raise ValueError(f"Invalid {key} format. Use YYYY-MM-DD.")


def _build_date_filters(posting_date, from_date, to_date):
	filters, applied, parsed = [], {}, {}
	for key, op, value in (
		("posting_date", "=", posting_date),
		("from_date", ">=", from_date),
		("to_date", "<=", to_date),
	):
		if value:
			parsed[key] = _parse_date(key, value)
			filters.append(["posting_date", op, value])
			applied[key] = value

	if "from_date" in parsed and "to_date" in parsed and parsed["from_date"] > parsed["to_date"]:
		raise ValueError("from_date cannot be after to_date.")
	return filters, applied


def _validate_paging(page, page_length, order_by, order):
	if order_by not in ALLOWED_ORDER_BY:
		raise ValueError(f"Invalid order_by. Allowed: {', '.join(sorted(ALLOWED_ORDER_BY))}")
	if order not in ("asc", "desc"):
		raise ValueError("Invalid order. Must be 'asc' or 'desc'.")
	try:
		page, page_length = int(page), int(page_length)
	except (TypeError, ValueError):
		page = page_length = 0
	if page < 1 or page_length < 1:
		raise ValueError("page and page_length must be positive integers.")
	return page, page_length


def _customer_or_filters(customer_name):
	pattern = f"%{customer_name}%"
	return [["customer_name", "like", pattern], ["customer", "like", pattern]]


def _invoices_with_item(item_code):
	return frappe.get_all(
		"Sales Invoice Item",
		filters={"item_code": item_code, "parenttype": "Sales Invoice"},
		pluck="parent",
		distinct=True,
	)


def _fetch_items_map(invoice_names):
	items_map = {}
	if not invoice_names:
		return items_map
	rows = frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": ["in", invoice_names], "parenttype": "Sales Invoice"},
		fields=ITEM_FIELDS,
		order_by="idx asc",
	)
	for row in rows:
		items_map.setdefault(row.pop("parent"), []).append(row)
	return items_map
