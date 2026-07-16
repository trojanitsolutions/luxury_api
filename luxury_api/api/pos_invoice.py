import frappe
from datetime import datetime
from frappe import _
import json
from typing import Union, Optional


@frappe.whitelist(methods=["POST"])
def create_pos_invoice(
	customer: Optional[str] = None,
	company: Optional[str] = None,
	pos_profile: Optional[str] = None,
	items: Optional[Union[str, list]] = None,
	payments: Optional[Union[str, list]] = None,
	warehouse: Optional[str] = None,
	posting_date: Optional[str] = None,
	remarks: Optional[str] = None,
):
	"""Create and submit a POS Invoice."""

	# Parse items and payments if they come as JSON strings (form-data)
	if isinstance(items, str):
		try:
			items = json.loads(items)
		except (json.JSONDecodeError, TypeError):
			frappe.throw(_("Invalid items format. Must be valid JSON array."))

	if isinstance(payments, str):
		try:
			payments = json.loads(payments)
		except (json.JSONDecodeError, TypeError):
			frappe.throw(_("Invalid payments format. Must be valid JSON array."))

	# Normalize string inputs
	customer = (customer or "").strip()
	company = (company or "").strip()
	pos_profile = (pos_profile or "").strip()
	warehouse = (warehouse or "").strip() if warehouse else None
	remarks = (remarks or "").strip() if remarks else None

	if not customer:
		frappe.throw(_("Customer is required."))
	if not company:
		frappe.throw(_("Company is required."))
	if not pos_profile:
		frappe.throw(_("POS Profile is required."))

	if not isinstance(items, list) or not items:
		frappe.throw(_("Items list is required and must not be empty."))

	for idx, item in enumerate(items, 1):
		if not item.get("item_code"):
			frappe.throw(_("Row {0}: item_code is required.").format(idx))

		qty = item.get("qty")
		try:
			qty = float(qty)
		except (TypeError, ValueError):
			frappe.throw(_("Row {0}: qty must be a valid number.").format(idx))
		if qty <= 0:
			frappe.throw(_("Row {0}: qty must be greater than 0.").format(idx))

		rate = item.get("rate")
		try:
			rate = float(rate)
		except (TypeError, ValueError):
			frappe.throw(_("Row {0}: rate must be a valid number.").format(idx))
		if rate <= 0:
			frappe.throw(_("Row {0}: rate must be greater than 0.").format(idx))

	if not isinstance(payments, list) or not payments:
		frappe.throw(_("Payments list is required and must not be empty."))

	for idx, payment in enumerate(payments, 1):
		if not payment.get("mode_of_payment"):
			frappe.throw(_("Row {0}: mode_of_payment is required.").format(idx))
		amount = payment.get("amount")
		try:
			amount = float(amount)
		except (TypeError, ValueError):
			frappe.throw(_("Row {0}: amount must be a valid number.").format(idx))
		if amount <= 0:
			frappe.throw(_("Row {0}: amount must be greater than 0.").format(idx))

	try:
		doc = frappe.get_doc({
			"doctype": "POS Invoice",
			"customer": customer,
			"company": company,
			"pos_profile": pos_profile,
			"is_pos": 1,
			"posting_date": posting_date,
			"remarks": remarks,
			"set_warehouse": warehouse,
			"items": [{"item_code": i["item_code"], "qty": i["qty"], "rate": i["rate"]} for i in items],
			"payments": [{"mode_of_payment": p["mode_of_payment"], "amount": p["amount"]} for p in payments],
		})
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
	return {
		"success": True,
		"message": "POS Invoice created successfully.",
		"data": doc.as_dict(),
	}


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_pos_invoice(invoice: str):
	"""Fetch a single POS Invoice."""
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
	company: Optional[str] = None,
	customer: Optional[str] = None,
	posting_date: Optional[str] = None,
	from_date: Optional[str] = None,
	to_date: Optional[str] = None,
	status: Optional[str] = None,
	pos_profile: Optional[str] = None,
	page: Union[int, str] = 1,
	page_length: Union[int, str] = 20,
	order_by: str = "posting_date",
	order: str = "desc",
):
	"""Fetch POS Invoices with optional filters."""
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

	if from_date:
		try:
			datetime.strptime(from_date, "%Y-%m-%d")
		except ValueError:
			frappe.local.response.http_status_code = 400
			return {"success": False, "message": "Invalid from_date format. Use YYYY-MM-DD."}
		filters.append(["posting_date", ">=", from_date])
		applied_filters["from_date"] = from_date

	if to_date:
		try:
			datetime.strptime(to_date, "%Y-%m-%d")
		except ValueError:
			frappe.local.response.http_status_code = 400
			return {"success": False, "message": "Invalid to_date format. Use YYYY-MM-DD."}
		filters.append(["posting_date", "<=", to_date])
		applied_filters["to_date"] = to_date

	if company:
		filters.append(["company", "=", company])
		applied_filters["company"] = company

	if customer:
		filters.append(["customer", "=", customer])
		applied_filters["customer"] = customer

	if status:
		filters.append(["status", "=", status])
		applied_filters["status"] = status

	if pos_profile:
		filters.append(["pos_profile", "=", pos_profile])
		applied_filters["pos_profile"] = pos_profile

	allowed_order_by = {"posting_date", "grand_total", "customer", "status", "modified"}
	if order_by not in allowed_order_by:
		frappe.local.response.http_status_code = 400
		return {"success": False, "message": f"Invalid order_by. Allowed: {', '.join(sorted(allowed_order_by))}"}

	if order not in ("asc", "desc"):
		frappe.local.response.http_status_code = 400
		return {"success": False, "message": "Invalid order. Must be 'asc' or 'desc'."}

	try:
		page = int(page)
		page_length = int(page_length)
		if page < 1 or page_length < 1:
			raise ValueError
	except (TypeError, ValueError):
		frappe.local.response.http_status_code = 400
		return {"success": False, "message": "page and page_length must be positive integers."}

	try:
		data = frappe.get_list(
			"POS Invoice",
			filters=filters or None,
			fields=[
				"name",
				"customer",
				"company",
				"pos_profile",
				"posting_date",
				"grand_total",
				"status",
				"docstatus",
			],
			order_by=f"{order_by} {order}",
			limit_start=(page - 1) * page_length,
			limit_page_length=page_length,
		)

		return {
			"success": True,
			"count": len(data),
			"filters": applied_filters,
			"data": data,
		}
	except Exception as e:
		frappe.log_error(title="pos_invoice.list_pos_invoices", message=str(e))
		frappe.local.response.http_status_code = 500
		return {"success": False, "message": str(e)}


@frappe.whitelist(methods=["POST"])
def cancel_pos_invoice(invoice: str):
	"""Cancel a submitted POS Invoice."""
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
	"""Create a return POS Invoice from an existing submitted invoice."""
	invoice = (invoice or "").strip()

	if not invoice:
		frappe.local.response.http_status_code = 400
		return {"success": False, "message": "Invoice name is required."}

	if not frappe.db.exists("POS Invoice", invoice):
		frappe.local.response.http_status_code = 404
		return {"success": False, "message": _("POS Invoice '{0}' does not exist.").format(invoice)}

	docstatus = frappe.db.get_value("POS Invoice", invoice, "docstatus")
	if docstatus != 1:
		frappe.local.response.http_status_code = 409
		return {
			"success": False,
			"message": _("Can only create return for a submitted POS Invoice."),
		}

	try:
		from erpnext.accounts.doctype.pos_invoice.pos_invoice import make_sales_return

		return_doc = make_sales_return(invoice)
		return_doc.insert()
		return_doc.submit()
	except frappe.ValidationError as e:
		frappe.db.rollback()
		frappe.local.response.http_status_code = 400
		return {"success": False, "message": str(e)}
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="luxury_api.pos_invoice.create_return_invoice")
		frappe.local.response.http_status_code = 500
		return {"success": False, "message": "Failed to create return POS Invoice. Please try again."}

	frappe.local.response.http_status_code = 201
	return {
		"success": True,
		"message": "Return POS Invoice created successfully.",
		"data": return_doc.as_dict(),
	}
