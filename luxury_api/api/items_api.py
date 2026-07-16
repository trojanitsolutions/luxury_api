import frappe

@frappe.whitelist()
def search_items(search):
	search = (search or "").strip()
	if not search:
		frappe.throw("search parameter is required")

	return frappe.get_all(
		"Item",
		filters={"disabled": 0},
		or_filters=[
			["item_code", "like", f"%{search}%"],
			["item_name", "like", f"%{search}%"],
		],
		fields=["item_code", "item_name", "item_group", "stock_uom", "description"],
		order_by="item_name asc",
		limit=20,
	)