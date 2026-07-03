import math

import frappe
from frappe import _
from frappe.utils import get_url


@frappe.whitelist(allow_guest=False)
def get_items(item_group=None, search=None, page=1, page_size=20):

	if item_group:
		_validate_item_group(item_group)

	page = max(1, int(page))
	page_size = min(100, max(1, int(page_size)))

	filters = {"is_sales_item": 1}
	if item_group:
		filters["item_group"] = item_group

	or_filters = _build_search_or_filters(search) if search else None

	total = frappe.get_all(
		"Item",
		filters=filters,
		or_filters=or_filters,
		fields=[{"COUNT": "name", "as": "total"}],
	)[0].total

	rows = frappe.get_all(
		"Item",
		filters=filters,
		or_filters=or_filters,
		fields=["name", "item_name", "item_group", "description", "stock_uom", "image", "disabled"],
		order_by="item_name asc",
		limit_start=(page - 1) * page_size,
		limit=page_size,
	)

	item_codes = [row.name for row in rows]
	stock_map = _fetch_warehouse_stock(item_codes)
	price_map = _fetch_selling_prices(item_codes)
	barcode_map = _fetch_barcodes(item_codes)
	attachment_map = _fetch_attachments(item_codes)

	items = [_build_item_payload(row, stock_map, price_map, barcode_map, attachment_map) for row in rows]

	return {
		"items": items,
		"pagination": {
			"page": page,
			"page_size": page_size,
			"total_records": total,
			"total_pages": math.ceil(total / page_size) if total else 0,
			"has_next": page * page_size < total,
			"has_previous": page > 1,
		},
	}


def _validate_item_group(item_group):
	
	if not frappe.db.exists("Item Group", item_group):
		frappe.throw(_("Item Group '{0}' does not exist.").format(item_group), frappe.DoesNotExistError)


def _build_search_or_filters(search):
	
	or_filters = [
		["name", "like", f"%{search}%"],
		["item_name", "like", f"%{search}%"],
	]
	barcode_item_codes = frappe.get_all(
		"Item Barcode",
		filters={"barcode": ["like", f"%{search}%"]},
		pluck="parent",
	)
	if barcode_item_codes:
		or_filters.append(["name", "in", barcode_item_codes])
	return or_filters


def _fetch_warehouse_stock(item_codes):

	if not item_codes:
		return {}
	rows = frappe.db.sql(
		"""SELECT item_code, warehouse, actual_qty
		FROM `tabBin`
		WHERE item_code IN %(codes)s""",
		{"codes": item_codes},
		as_dict=True,
	)
	stock_map = {}
	for row in rows:
		stock_map.setdefault(row.item_code, []).append(
			{"warehouse": row.warehouse, "actual_qty": row.actual_qty}
		)
	return stock_map


def _fetch_selling_prices(item_codes):
	
	if not item_codes:
		return {}
	selling_price_list = frappe.db.get_single_value("Selling Settings", "selling_price_list") or "Standard Selling"
	rows = frappe.get_all(
		"Item Price",
		filters={"item_code": ["in", item_codes], "price_list": selling_price_list, "selling": 1},
		fields=["item_code", "price_list_rate"],
	)
	return {row.item_code: row.price_list_rate for row in rows}


def _fetch_barcodes(item_codes):
	
	if not item_codes:
		return {}
	rows = frappe.get_all(
		"Item Barcode",
		filters={"parent": ["in", item_codes]},
		fields=["parent", "barcode", "barcode_type"],
	)
	barcode_map = {}
	for row in rows:
		barcode_map.setdefault(row.parent, []).append(
			{"barcode": row.barcode, "barcode_type": row.barcode_type}
		)
	return barcode_map


def _fetch_attachments(item_codes):
	
	if not item_codes:
		return {}
	rows = frappe.get_all(
		"File",
		filters={"attached_to_doctype": "Item", "attached_to_name": ["in", item_codes]},
		fields=["attached_to_name", "file_url"],
	)
	attachment_map = {}
	for row in rows:
		attachment_map.setdefault(row.attached_to_name, []).append(get_url(row.file_url))
	return attachment_map


def _build_item_payload(row, stock_map, price_map, barcode_map, attachment_map):
	warehouse_stock = stock_map.get(row.name, [])
	attachments = attachment_map.get(row.name, [])
	image = get_url(row.image) if row.image else (attachments[0] if attachments else None)
	return {
		"item_code": row.name,
		"item_name": row.item_name,
		"item_group": row.item_group,
		"description": row.description,
		"stock_uom": row.stock_uom,
		"disabled": row.disabled,
		"image": image,
		"selling_rate": price_map.get(row.name, 0),
		"warehouse_stock": warehouse_stock,
		"total_available_qty": sum(w["actual_qty"] for w in warehouse_stock),
		"attachments": attachments,
		"barcodes": barcode_map.get(row.name, []),
	}
