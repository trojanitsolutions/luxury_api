import math

import frappe
from frappe import _

ITEM_PRICE_FIELDS = [
	"name",
	"item_code",
	"item_name",
	"item_description",
	"uom",
	"price_list",
	"price_list_rate",
	"currency",
	"selling",
	"buying",
	"valid_from",
	"valid_upto",
	"customer",
	"batch_no",
]


@frappe.whitelist(methods=["GET"], allow_guest=False)
def get_item_prices(branch: str = None, price_list: str = None, item_code: str = None, search: str = None, page=None, page_size=None):
	branch_price_lists, common_price_lists = _resolve_price_lists(branch, price_list)
	rows = _fetch_item_prices(branch_price_lists + common_price_lists, item_code, search)
	rows = _prefer_branch_prices(rows, set(branch_price_lists))

	response = {
		"success": True,
		"branch_price_lists": branch_price_lists,
		"common_price_lists": common_price_lists,
		"data": rows,
		"message": None if rows else "No item prices found.",
	}
	if page or page_size:
		response["data"], response["pagination"] = _paginate(rows, page, page_size)
	return response


def _paginate(rows, page, page_size):
	page = max(1, int(page or 1))
	page_size = min(500, max(1, int(page_size or 20)))
	total = len(rows)
	start = (page - 1) * page_size

	return rows[start : start + page_size], {
		"page": page,
		"page_size": page_size,
		"total_records": total,
		"total_pages": math.ceil(total / page_size),
		"has_next": page * page_size < total,
		"has_previous": page > 1,
	}


def _resolve_price_lists(branch, price_list):
	if price_list:
		if not frappe.db.exists("Price List", price_list):
			frappe.throw(_("Price List '{0}' does not exist.").format(price_list), frappe.DoesNotExistError)
		return [price_list], []

	common_price_lists = frappe.get_all(
		"Price List",
		filters={"enabled": 1, "selling": 1, "branch": ["is", "not set"]},
		pluck="name",
	)
	if not branch:
		return [], common_price_lists

	if not frappe.db.exists("Branch", branch):
		frappe.throw(_("Branch '{0}' does not exist.").format(branch), frappe.DoesNotExistError)

	branch_price_lists = frappe.get_all(
		"Price List",
		filters={"enabled": 1, "selling": 1, "branch": branch},
		pluck="name",
	)
	if not branch_price_lists and not common_price_lists:
		frappe.throw(_("No Price List found for Branch '{0}'.").format(branch), frappe.DoesNotExistError)
	return branch_price_lists, common_price_lists


def _fetch_item_prices(price_lists, item_code, search):
	if not price_lists:
		return []

	filters = {"price_list": ["in", price_lists]}
	if item_code:
		filters["item_code"] = item_code

	or_filters = None
	search = (search or "").strip()
	if search:
		or_filters = [
			["item_code", "like", f"%{search}%"],
			["item_name", "like", f"%{search}%"],
		]

	return frappe.get_all(
		"Item Price",
		filters=filters,
		or_filters=or_filters,
		fields=ITEM_PRICE_FIELDS,
		order_by="item_code asc",
	)


def _prefer_branch_prices(rows, branch_price_lists):
	branch_keys = {(row.item_code, row.uom) for row in rows if row.price_list in branch_price_lists}

	result = []
	for row in rows:
		row.is_branch_price = row.price_list in branch_price_lists
		if not row.is_branch_price and (row.item_code, row.uom) in branch_keys:
			continue
		result.append(row)
	return result
