import frappe
import json
from datetime import datetime
from frappe import _
from frappe.utils import flt, cint

FIELDS = ("customer", "company", "pos_profile", "items", "payments", "warehouse", "posting_date", "remarks")
RETURN_FIELDS = ("original_invoice", "posting_date", "posting_time", "remarks", "update_stock", "set_posting_time", "items")

def _get_original_items_map(original_invoice):
	"""Build a map of item rows by item_code from the original invoice."""
	original_doc = frappe.get_doc("POS Invoice", original_invoice)
	items_map = {}
	for row in original_doc.items:
		item_code = row.item_code
		if item_code not in items_map:
			items_map[item_code] = []
		items_map[item_code].append(row)
	return items_map


def _get_payload(kwargs, fields=FIELDS):
	if frappe.request.method == "POST" and not any(kwargs.get(f) for f in fields):
		try:
			body = json.loads(frappe.request.data.decode()) if frappe.request.data else {}
		except (json.JSONDecodeError, ValueError):
			body = {}
		kwargs = {f: kwargs.get(f) or body.get(f) for f in fields}
	return kwargs


def _validate_rows(rows, label, text_field, num_field):
	if not isinstance(rows, list) or not rows:
		frappe.throw(_("{0} list is required and must not be empty.").format(label))
	for idx, row in enumerate(rows, 1):
		if not row.get(text_field):
			frappe.throw(_("Row {0}: {1} is required.").format(idx, text_field))
		try:
			if float(row.get(num_field)) <= 0:
				frappe.throw(_("Row {0}: {1} must be greater than 0.").format(idx, num_field))
		except (TypeError, ValueError):
			frappe.throw(_("Row {0}: {1} must be a valid number.").format(idx, num_field))


def _prorate_payments(payments, ratio, precision):
	if not payments or ratio == 0:
		return payments

	multiplier = 10 ** precision
	total_original = sum(float(p.get("amount") or 0) for p in payments)
	target_total = round(total_original * ratio * multiplier) / multiplier

	proroted = []
	sum_non_last = 0.0

	for idx, payment in enumerate(payments):
		is_last = idx == len(payments) - 1
		amount = float(payment.get("amount") or 0)
		base_amount = float(payment.get("base_amount") or 0)

		if is_last and len(payments) > 1:
			scaled_amount = target_total - sum_non_last
			scaled_base_amount = base_amount * ratio if amount != 0 else 0.0
		else:
			scaled_amount = round(amount * ratio * multiplier) / multiplier
			scaled_base_amount = round(base_amount * ratio * multiplier) / multiplier
			if not is_last:
				sum_non_last += scaled_amount

		proroted.append({
			"mode_of_payment": payment.get("mode_of_payment"),
			"type": payment.get("type"),
			"amount": scaled_amount,
			"base_amount": scaled_base_amount,
			"account": payment.get("account"),
			"default": payment.get("default"),
		})

	return proroted


@frappe.whitelist(methods=["POST"])
def create_pos_invoice(**kwargs):
	data = _get_payload(kwargs)
	customer, company, pos_profile = ((data.get(f) or "").strip() for f in FIELDS[:3])

	for value, label in ((customer, "Customer"), (company, "Company"), (pos_profile, "POS Profile")):
		if not value:
			frappe.throw(_("{0} is required.").format(label))

	_validate_rows(data.get("items"), "Items", "item_code", "qty")
	_validate_rows(data.get("payments"), "Payments", "mode_of_payment", "amount")

	try:
		doc = frappe.get_doc({
			"doctype": "POS Invoice",
			"customer": customer,
			"company": company,
			"pos_profile": pos_profile,
			"is_pos": 1,
			"posting_date": data.get("posting_date"),
			"remarks": data.get("remarks"),
			"set_warehouse": data.get("warehouse"),
			"items": [{"item_code": i["item_code"], "qty": i["qty"]} for i in data["items"]],
			"payments": [{"mode_of_payment": p["mode_of_payment"], "amount": p["amount"]} for p in data["payments"]],
		})
		doc.set_missing_values()
		doc.set_account_for_mode_of_payment()
		doc.insert()
		doc.submit()
	except frappe.ValidationError as e:
		frappe.db.rollback()
		frappe.local.response.http_status_code = 400
		return {"success": False, "message": str(e)}
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="luxury_api.pos_invoice.create_pos_invoice")
		frappe.local.response.http_status_code = 500
		return {"success": False, "message": "Failed to create POS Invoice. Please try again."}

	frappe.local.response.http_status_code = 201
	return {"success": True, "message": "POS Invoice created successfully.", "data": doc.as_dict()}

@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_pos_invoice(invoice: str):
	
	invoice = (invoice or "").strip()

	if not invoice:
		frappe.local.response.http_status_code = 400
		return {"success": False, "message": "Invoice name is required."}

	if not frappe.db.exists("POS Invoice", invoice):
		frappe.local.response.http_status_code = 404
		return {"success": False, "message": _("POS Invoice '{0}' does not exist.").format(invoice)}

	try:
		doc = frappe.get_doc("POS Invoice", invoice)
		doc.check_permission("read")
	except frappe.PermissionError:
		frappe.local.response.http_status_code = 403
		return {"success": False, "message": "Access Denied."}
	except Exception as e:
		frappe.local.response.http_status_code = 500
		return {"success": False, "message": str(e)}

	return {
		"success": True,
		"data": doc.as_dict(),
	}


@frappe.whitelist(allow_guest=False, methods=["GET"])
def list_pos_invoices(
	company: str | None = None,
	customer: str | None = None,
	posting_date: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
	status: str | None = None,
	pos_profile: str | None = None,
	page: int | str = 1,
	page_length: int | str = 20,
	order_by: str = "posting_date",
	order: str = "desc",
):
	def respond(code, message):
		frappe.local.response.http_status_code = code
		return {"success": False, "message": message}

	filters, applied = [], {}

	for key, op, value in (("posting_date", "=", posting_date), ("from_date", ">=", from_date), ("to_date", "<=", to_date)):
		if value:
			try:
				datetime.strptime(value, "%Y-%m-%d")
			except ValueError:
				return respond(400, f"Invalid {key} format. Use YYYY-MM-DD.")
			filters.append(["posting_date", op, value])
			applied[key] = value

	for key, value in (("company", company), ("customer", customer), ("status", status), ("pos_profile", pos_profile)):
		if value:
			filters.append([key, "=", value])
			applied[key] = value

	allowed_order_by = {"posting_date", "grand_total", "customer", "status", "modified"}
	if order_by not in allowed_order_by:
		return respond(400, f"Invalid order_by. Allowed: {', '.join(sorted(allowed_order_by))}")
	if order not in ("asc", "desc"):
		return respond(400, "Invalid order. Must be 'asc' or 'desc'.")

	try:
		page, page_length = int(page), int(page_length)
		if page < 1 or page_length < 1:
			raise ValueError
	except (TypeError, ValueError):
		return respond(400, "page and page_length must be positive integers.")

	try:
		data = frappe.get_list(
			"POS Invoice",
			filters=filters or None,
			fields=["name", "customer", "company", "pos_profile", "posting_date", "grand_total", "status", "docstatus"],
			order_by=f"{order_by} {order}",
			limit_start=(page - 1) * page_length,
			limit_page_length=page_length,
		)
		return {"success": True, "count": len(data), "filters": applied, "data": data}
	except Exception as e:
		frappe.log_error(title="pos_invoice.list_pos_invoices", message=str(e))
		return respond(500, str(e))


@frappe.whitelist(methods=["POST"])
def cancel_pos_invoice(invoice: str):
	
	invoice = (invoice or "").strip()

	if not invoice:
		frappe.local.response.http_status_code = 400
		return {"success": False, "message": "Invoice name is required."}

	if not frappe.db.exists("POS Invoice", invoice):
		frappe.local.response.http_status_code = 404
		return {"success": False, "message": _("POS Invoice '{0}' does not exist.").format(invoice)}

	try:
		doc = frappe.get_doc("POS Invoice", invoice)

		if doc.docstatus != 1:
			frappe.local.response.http_status_code = 409
			return {
				"success": False,
				"message": _("POS Invoice can only be cancelled if it is submitted."),
			}

		doc.cancel()
	except frappe.ValidationError as e:
		frappe.local.response.http_status_code = 400
		return {"success": False, "message": str(e)}
	except Exception as e:
		frappe.log_error(title="luxury_api.pos_invoice.cancel_pos_invoice")
		frappe.local.response.http_status_code = 500
		return {"success": False, "message": str(e)}

	frappe.local.response.http_status_code = 200
	return {
		"success": True,
		"message": "POS Invoice cancelled successfully.",
		"data": {"name": doc.name, "status": doc.status},
	}

@frappe.whitelist(methods=["POST"])
def create_return_invoice(invoice: str):
	def respond(status, message, data=None):
		frappe.local.response.http_status_code = status
		return {"success": status < 400, "message": message, **({"data": data} if data else {})}

	invoice = (invoice or "").strip()

	if not invoice:
		return respond(400, _("Invoice name is required."))
	if not frappe.db.exists("POS Invoice", invoice):
		return respond(404, _("POS Invoice '{0}' does not exist.").format(invoice))
	if frappe.db.get_value("POS Invoice", invoice, "docstatus") != 1:
		return respond(409, _("Can only create return for a submitted POS Invoice."))

	try:
		from erpnext.accounts.doctype.pos_invoice.pos_invoice import make_sales_return

		return_doc = make_sales_return(invoice)
		return_doc.insert()
		return_doc.submit()
	except frappe.ValidationError as e:
		frappe.db.rollback()
		return respond(400, str(e))
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="luxury_api.pos_invoice.create_return_invoice")
		return respond(500, _("Failed to create return POS Invoice. Please try again."))

	return respond(201, _("Return POS Invoice created successfully."), return_doc.as_dict())


@frappe.whitelist(methods=["POST"])
def create_return(**kwargs):
	"""Create a partial/full Return POS Invoice against a submitted original invoice."""
	def respond(status, message, data=None):
		frappe.local.response.http_status_code = status
		return {"success": status < 400, "message": message, **({"data": data} if data else {})}

	data = _get_payload(kwargs, RETURN_FIELDS)
	original_invoice = (data.get("original_invoice") or "").strip()

	if not original_invoice:
		return respond(400, _("Original invoice name is required."))
	if not frappe.db.exists("POS Invoice", original_invoice):
		return respond(404, _("POS Invoice '{0}' does not exist.").format(original_invoice))

	docstatus, is_return = frappe.db.get_value("POS Invoice", original_invoice, ["docstatus", "is_return"])
	if docstatus != 1:
		return respond(409, _("Can only create return for a submitted POS Invoice."))
	if is_return:
		return respond(400, _("Cannot create a return for an invoice that is already a return."))

	try:
		_validate_rows(data.get("items"), "Items", "item_code", "qty")

		items_list = data.get("items", [])
		seen = set()
		for idx, item in enumerate(items_list, 1):
			item_code = item.get("item_code")
			if item_code in seen:
				frappe.throw(_("Row {0}: Duplicate item {1}.").format(idx, item_code))
			seen.add(item_code)

		from erpnext.accounts.doctype.pos_invoice.pos_invoice import make_sales_return

		return_doc = make_sales_return(original_invoice)
		full_return_total = flt(return_doc.grand_total)

		original_items_map = _get_original_items_map(original_invoice)
		return_map = {d.pos_invoice_item: d for d in return_doc.items}

		request_map = {}
		for item_req in items_list:
			item_code = item_req.get("item_code")
			if item_code not in original_items_map:
				frappe.throw(_("Item {0} does not exist in POS Invoice {1}.").format(item_code, original_invoice))

			original_rows = original_items_map[item_code]
			requested_qty = flt(item_req.get("qty"))

			if len(original_rows) > 1:
				frappe.throw(_("Item {0} appears multiple times in the invoice. Cannot process partial return.").format(item_code))

			original_row = original_rows[0]
			original_row_name = original_row.name

			if original_row_name not in return_map:
				frappe.throw(_("Item {0} not found in return mapping.").format(item_code))

			return_row = return_map[original_row_name]
			remaining_qty = abs(flt(return_row.qty))

			if requested_qty > remaining_qty:
				frappe.throw(
					_("Item {0} exceeds returnable quantity. Maximum: {1}, Requested: {2}.").format(
						item_code, remaining_qty, requested_qty
					)
				)

			request_map[original_row_name] = requested_qty

		kept_items = []
		for item_row in return_doc.items:
			if item_row.pos_invoice_item in request_map:
				requested_qty = request_map[item_row.pos_invoice_item]
				remaining_qty = abs(flt(item_row.qty))
				item_row.qty = -requested_qty
				if remaining_qty > 0:
					ratio = requested_qty / remaining_qty
					item_row.stock_qty = flt(item_row.stock_qty * ratio)
				kept_items.append(item_row)

		return_doc.set("items", kept_items)
		return_doc.run_method("calculate_taxes_and_totals")
		new_total = flt(return_doc.grand_total)

		if full_return_total != 0:
			ratio = new_total / full_return_total
		else:
			ratio = 0

		precision = return_doc.precision("paid_amount")
		proroted = _prorate_payments(return_doc.payments, ratio, precision)
		return_doc.set("payments", [])
		for p in proroted:
			return_doc.append("payments", p)

		return_doc.paid_amount = new_total
		return_doc.base_paid_amount = flt(new_total * return_doc.conversion_rate, precision)

		if data.get("posting_date"):
			return_doc.posting_date = data.get("posting_date")
		if data.get("remarks"):
			return_doc.remarks = data.get("remarks")
		if data.get("set_posting_time"):
			return_doc.set_posting_time = cint(data.get("set_posting_time"))
			if data.get("posting_time"):
				return_doc.posting_time = data.get("posting_time")
		if data.get("update_stock") is not None:
			return_doc.update_stock = cint(data.get("update_stock"))

		return_doc.insert()
		return_doc.submit()

	except frappe.ValidationError as e:
		frappe.db.rollback()
		return respond(400, str(e))
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="luxury_api.pos_invoice.create_return")
		return respond(500, _("Failed to create return POS Invoice. Please try again."))

	return respond(201, _("POS Return Invoice created successfully."), {
		"return_invoice": return_doc.name,
		"original_invoice": original_invoice,
	})


