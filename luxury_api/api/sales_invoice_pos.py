import frappe
import json
from datetime import datetime
from frappe import _
from frappe.utils import flt, cint

from luxury_api.customizations.sales_invoice_commission import (
	auto_cancel_enabled,
	auto_recover_enabled,
	get_active_commission_je,
	get_commission_amount,
	get_sales_person,
)

FIELDS = ("customer", "company", "pos_profile", "items", "payments", "warehouse", "posting_date", "remarks", "update_stock", "discount_type", "discount_percentage", "discount_amount", "channel", "sales_person", "commission_amount", "commission_paid")
RETURN_FIELDS = ("original_invoice", "posting_date", "posting_time", "remarks", "update_stock", "set_posting_time", "items", "recover_commission")


def _get_original_items_map(original_invoice):
	"""Build a map of item rows by item_code from the original invoice."""
	original_doc = frappe.get_doc("Sales Invoice", original_invoice)
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


def _validate_credit_payments(rows):
	"""Credit sales may send no payments, or payment rows with amount 0 or more."""
	if rows in (None, ""):
		return
	if not isinstance(rows, list):
		frappe.throw(_("Payments must be a list."))
	for idx, row in enumerate(rows, 1):
		if not row.get("mode_of_payment"):
			frappe.throw(_("Row {0}: mode_of_payment is required.").format(idx))
		try:
			if float(row.get("amount") or 0) < 0:
				frappe.throw(_("Row {0}: amount must not be negative.").format(idx))
		except (TypeError, ValueError):
			frappe.throw(_("Row {0}: amount must be a valid number.").format(idx))


def _is_credit_channel(channel):
	"""Return True if the Channel allows credit sales. No channel means no credit."""
	if not channel:
		return False
	allow_credit = frappe.db.get_value("Channel", channel, "allow_credit")
	if allow_credit is None:
		frappe.throw(_("Channel '{0}' does not exist.").format(channel), frappe.DoesNotExistError)
	return bool(cint(allow_credit))


def _validate_credit_sale(customer, pos_profile):
	"""Credit needs a real customer and a POS Profile that allows partial payment."""
	default_customer, allow_partial_payment = frappe.db.get_value(
		"POS Profile", pos_profile, ["customer", "allow_partial_payment"]
	) or (None, 0)
	if default_customer and customer == default_customer:
		frappe.throw(_("Credit sales are not allowed for the default customer '{0}'.").format(customer))
	if not cint(allow_partial_payment):
		frappe.throw(_("POS Profile '{0}' must have 'Allow Partial Payment' enabled for credit sales.").format(pos_profile))


def _get_default_mode_of_payment(pos_profile):
	modes = frappe.get_all(
		"POS Payment Method",
		filters={"parent": pos_profile, "parenttype": "POS Profile"},
		fields=["mode_of_payment", "default"],
		order_by="idx asc",
	)
	if not modes:
		frappe.throw(_("POS Profile '{0}' has no payment methods.").format(pos_profile))
	return next((m.mode_of_payment for m in modes if m.default), modes[0].mode_of_payment)


def _resolve_discount(payload, label):
	"""Resolve discount_type (No Discount/Percentage/Amount) into ERPNext fields.

	Args:
		payload: dict with optional discount_type, discount_percentage, discount_amount.
		label: string prefix for error messages (e.g., "Item 1", "Invoice").

	Returns:
		dict with discount fields to merge (e.g., {"discount_percentage": 10}) or {} if No Discount.
		Throws frappe.ValidationError on invalid discount_type, missing/out-of-range values.
	"""
	discount_type = (payload.get("discount_type") or "").strip() or "No Discount"

	if discount_type not in ("No Discount", "Percentage", "Amount"):
		frappe.throw(_("{0}: Invalid discount_type '{1}'. Must be 'No Discount', 'Percentage', or 'Amount'.").format(label, discount_type))

	if discount_type == "No Discount":
		return {}

	if discount_type == "Percentage":
		try:
			discount_percentage = float(payload.get("discount_percentage") or 0)
		except (TypeError, ValueError):
			frappe.throw(_("{0}: discount_percentage must be a valid number.").format(label))
		if discount_percentage <= 0 or discount_percentage > 100:
			frappe.throw(_("{0}: discount_percentage must be between 0 and 100.").format(label))
		return {"discount_percentage": discount_percentage}

	if discount_type == "Amount":
		try:
			discount_amount = float(payload.get("discount_amount") or 0)
		except (TypeError, ValueError):
			frappe.throw(_("{0}: discount_amount must be a valid number.").format(label))
		if discount_amount <= 0:
			frappe.throw(_("{0}: discount_amount must be greater than 0.").format(label))
		return {"discount_amount": discount_amount}


def _get_invoice_discount_fields(data):
	"""Resolve invoice-level discount into ERPNext fields."""
	discount_fields = _resolve_discount(data, _("Invoice"))
	if discount_fields:
		discount_fields["apply_discount_on"] = "Grand Total"
	return discount_fields


def _resolve_commission(data):
	"""Resolve the Sales Partner commission. Commission is always a fixed amount sent by the POS.

	Returns (fields, amount). fields is {} when there is no sales person. The amount is applied on the
	invoice by the apply_fixed_commission validate hook, after ERPNext's own rate calculation.
	"""
	sales_person = (data.get("sales_person") or "").strip()
	amount = data.get("commission_amount")
	has_amount = amount not in (None, "")

	if not sales_person:
		if has_amount:
			frappe.throw(_("sales_person is required when commission_amount is given."))
		return {}, None

	person = frappe.db.get_value("Sales Person", sales_person, ["enabled", "is_group"], as_dict=True)
	if not person:
		frappe.throw(_("Sales Person '{0}' does not exist.").format(sales_person), frappe.DoesNotExistError)
	if not person.enabled:
		frappe.throw(_("Sales Person '{0}' is disabled.").format(sales_person))
	if person.is_group:
		frappe.throw(_("Sales Person '{0}' is a group. Select an individual sales person.").format(sales_person))

	if not has_amount:
		frappe.throw(_("commission_amount is required when sales_person is given."))
	try:
		amount = float(amount)
	except (TypeError, ValueError):
		frappe.throw(_("commission_amount must be a valid number."))
	if amount <= 0:
		frappe.throw(_("commission_amount must be greater than 0."))

	return {"sales_team": [{"sales_person": sales_person, "allocated_percentage": 100}]}, amount


def _get_cash_mode_of_payment(pos_profile):
	"""Commission is always paid in cash: first POS Profile payment method whose type is Cash."""
	modes = frappe.get_all(
		"POS Payment Method",
		filters={"parent": pos_profile, "parenttype": "POS Profile"},
		pluck="mode_of_payment",
		order_by="idx asc",
	)
	cash_modes = set(
		frappe.get_all("Mode of Payment", filters={"name": ["in", modes or [""]], "type": "Cash"}, pluck="name")
	)
	mode = next((m for m in modes if m in cash_modes), None)
	if not mode:
		frappe.throw(_("POS Profile '{0}' has no Cash mode of payment to pay commission.").format(pos_profile))
	return mode


def _resolve_commission_payment(data, company, pos_profile):
	"""Resolve the on-the-spot commission payment. commission_paid defaults to 1.

	Validates accounts before the invoice is created, so a bad setup never leaves a half-done sale.
	Returns {"commission_paid": 0} when not paid now.
	"""
	paid = data.get("commission_paid")
	if not cint(1 if paid in (None, "") else paid):
		return {"commission_paid": 0}

	mode = _get_cash_mode_of_payment(pos_profile)

	expense_account, cost_center = frappe.db.get_value(
		"POS Profile", pos_profile, ["commission_expense_account", "cost_center"]
	) or (None, None)
	if not expense_account:
		frappe.throw(_("Set 'Commission Expense Account' on POS Profile '{0}'.").format(pos_profile))
	account = frappe.db.get_value("Account", expense_account, ["company", "is_group", "disabled"], as_dict=True)
	if not account or account.company != company or account.is_group or account.disabled:
		frappe.throw(
			_("Commission Expense Account '{0}' must be an enabled ledger account of company '{1}'.").format(
				expense_account, company
			)
		)

	from erpnext.accounts.doctype.sales_invoice.sales_invoice import get_bank_cash_account

	return {
		"commission_paid": 1,
		"commission_mode_of_payment": mode,
		"expense_account": expense_account,
		"paid_from_account": get_bank_cash_account(mode, company)["account"],
		"cost_center": cost_center or frappe.get_cached_value("Company", company, "cost_center"),
	}


def _make_commission_journal_entry(invoice, payment):
	"""Submit a Cash Entry linked to the invoice.

	Sale:   Dr Commission Expense / Cr Cash  (commission paid to the sales person)
	Return: Dr Cash / Cr Commission Expense  (sales person gives back the returned share)
	The amount is abs(Sales Team incentives), which is negative on a return.
	"""
	from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_accounting_dimensions

	amount = abs(get_commission_amount(invoice))
	cost_center = payment["cost_center"] or invoice.cost_center
	dimensions = {d: invoice.get(d) for d in get_accounting_dimensions() if invoice.get(d)}
	debit_account, credit_account = payment["expense_account"], payment["paid_from_account"]
	remark = _("Commission paid to Sales Person {0} against {1}")
	if invoice.is_return:
		debit_account, credit_account = credit_account, debit_account
		remark = _("Commission recovered from Sales Person {0} for return {1}")

	je = frappe.get_doc({
		"doctype": "Journal Entry",
		"voucher_type": "Cash Entry",
		"company": invoice.company,
		"posting_date": invoice.posting_date,
		"user_remark": remark.format(get_sales_person(invoice), invoice.name),
		"accounts": [
			{"account": debit_account, "debit_in_account_currency": amount, "cost_center": cost_center, **dimensions},
			{"account": credit_account, "credit_in_account_currency": amount, "cost_center": cost_center, **dimensions},
		],
	})
	je.flags.ignore_permissions = True
	je.insert()
	je.submit()
	invoice.db_set("commission_journal_entry", je.name)
	return je.name


def _get_original_commission_payment(original_je):
	"""Accounts of the original commission JE, so the recovery reverses exactly the same accounts."""
	rows = frappe.get_all(
		"Journal Entry Account",
		filters={"parent": original_je},
		fields=["account", "cost_center", "debit_in_account_currency"],
		order_by="idx asc",
	)
	expense = next(r for r in rows if flt(r.debit_in_account_currency) > 0)
	cash = next(r for r in rows if flt(r.debit_in_account_currency) <= 0)
	return {"expense_account": expense.account, "paid_from_account": cash.account, "cost_center": expense.cost_center}


def _commission_recovery_check(original_invoice, recover_commission):
	"""Decide whether a return recovers the sales person's commission share.

	Returns (original_je, recover, ask_response). original_je is None when no commission was paid.
	ask_response is a 409 payload when the POS must ask the cashier (POS Profile set to "No"
	and no recover_commission sent). An explicit recover_commission always wins.
	"""
	original = frappe.db.get_value(
		"Sales Invoice", original_invoice, ["commission_journal_entry", "pos_profile"], as_dict=True
	)
	original_je = get_active_commission_je(original)
	if not original_je:
		return None, False, None
	if recover_commission not in (None, ""):
		return original_je, bool(cint(recover_commission)), None
	if auto_recover_enabled(original.pos_profile):
		return original_je, True, None

	frappe.local.response.http_status_code = 409
	return original_je, False, {
		"success": False,
		"requires_commission_decision": True,
		"message": _(
			"Commission was paid for this invoice. Send recover_commission = 1 if the sales person gives back "
			"the returned share, or 0 if the sales person keeps it."
		),
		"data": {"commission_journal_entry": original_je, **_get_commission_info([original_invoice])[original_invoice]},
	}


def _recover_commission(return_doc, original_je):
	"""Submit the recovery Cash Entry for a return and record the cash mode on the return invoice."""
	if get_commission_amount(return_doc) >= 0:
		return
	payment = _get_original_commission_payment(original_je)
	original_mode = frappe.db.get_value("Sales Invoice", return_doc.return_against, "commission_mode_of_payment")
	return_doc.db_set("commission_mode_of_payment", original_mode)
	_make_commission_journal_entry(return_doc, payment)


def _get_commission_info(invoice_names):
	"""{invoice: {"sales_person", "commission_amount"}} from the Sales Team rows, in one query."""
	info = {name: {"sales_person": None, "commission_amount": 0} for name in invoice_names}
	if not invoice_names:
		return info
	rows = frappe.get_all(
		"Sales Team",
		filters={"parent": ["in", invoice_names], "parenttype": "Sales Invoice"},
		fields=["parent", "sales_person", "incentives"],
		order_by="idx asc",
	)
	for row in rows:
		entry = info[row.parent]
		entry["sales_person"] = entry["sales_person"] or row.sales_person
		entry["commission_amount"] += flt(row.incentives)
	return info


def _prorate_payments(payments, ratio, precision):
	if not payments:
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
			"amount": -abs(scaled_amount),
			"base_amount": -abs(scaled_base_amount),
			"account": payment.get("account"),
			"default": payment.get("default"),
		})

	return proroted


@frappe.whitelist(methods=["POST"])
def create_sales_invoice(**kwargs):
	data = _get_payload(kwargs)
	customer, company, pos_profile = ((data.get(f) or "").strip() for f in FIELDS[:3])

	for value, label in ((customer, "Customer"), (company, "Company"), (pos_profile, "POS Profile")):
		if not value:
			frappe.throw(_("{0} is required.").format(label))

	channel = (data.get("channel") or "").strip() or None
	is_credit = _is_credit_channel(channel)

	_validate_rows(data.get("items"), "Items", "item_code", "qty")
	if is_credit:
		_validate_credit_sale(customer, pos_profile)
		_validate_credit_payments(data.get("payments"))
	else:
		_validate_rows(data.get("payments"), "Payments", "mode_of_payment", "amount")

	item_discounts = [_resolve_discount(item, _("Item {0}").format(idx)) for idx, item in enumerate(data["items"], 1)]
	invoice_discount = _get_invoice_discount_fields(data)
	commission, commission_amount = _resolve_commission(data)
	payment = _resolve_commission_payment(data, company, pos_profile) if commission else {}
	if commission:
		commission["commission_paid"] = payment["commission_paid"]
		commission["commission_mode_of_payment"] = payment.get("commission_mode_of_payment")

	try:
		doc = frappe.get_doc({
			"doctype": "Sales Invoice",
			"customer": customer,
			"company": company,
			"pos_profile": pos_profile,
			"channel": channel,
			"is_pos": 1,
			"is_created_using_pos": 1,
			"posting_date": data.get("posting_date"),
			"remarks": data.get("remarks"),
			"set_warehouse": data.get("warehouse"),
			"items": [
				{"item_code": i["item_code"], "qty": i["qty"], **item_discounts[idx]}
				for idx, i in enumerate(data["items"])
			],
			**invoice_discount,
			**commission,
		})
		if commission:
			doc.flags.commission_amount = commission_amount
		doc.set_missing_values()

		# Properly add payment rows (using append for correct child table registration)
		doc.set("payments", [])
		for p in data.get("payments") or []:
			payment_amount = flt(p.get("amount") or 0)
			doc.append("payments", {
				"mode_of_payment": p.get("mode_of_payment"),
				"amount": payment_amount,
			})

		if is_credit:
			# ERPNext needs at least one payment row on a POS invoice, even if nothing is paid now
			if not doc.payments:
				doc.append("payments", {"mode_of_payment": _get_default_mode_of_payment(pos_profile), "amount": 0})
			invoice_total = flt(doc.rounded_total) or flt(doc.grand_total)
			if sum(flt(p.amount) for p in doc.payments) > invoice_total:
				frappe.throw(_("Total payment cannot be more than the invoice total {0} for a credit sale.").format(invoice_total))
		elif doc.payments:
			# Auto-fill payment amount from grand_total if not explicitly provided or insufficient
			total_paid = sum(flt(p.amount or 0) for p in doc.payments)
			if not total_paid or total_paid < flt(doc.grand_total or 0):
				doc.payments[0].amount = flt(doc.grand_total or 0)

		# Override update_stock if provided in request
		if data.get("update_stock") is not None:
			doc.update_stock = cint(data.get("update_stock"))

		doc.set_account_for_mode_of_payment()
		doc.insert()
		doc.submit()

		# Same transaction: if the JE fails, the invoice is rolled back too
		if payment.get("commission_paid"):
			_make_commission_journal_entry(doc, payment)
	except frappe.ValidationError as e:
		frappe.db.rollback()
		frappe.local.response.http_status_code = 400
		return {"success": False, "message": str(e)}
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="luxury_api.sales_invoice_pos.create_sales_invoice")
		frappe.local.response.http_status_code = 500
		return {"success": False, "message": "Failed to create Sales Invoice. Please try again."}

	frappe.local.response.http_status_code = 201
	return {"success": True, "message": "Sales Invoice created successfully.", "data": doc.as_dict()}


@frappe.whitelist(allow_guest=False, methods=["GET"])
def get_sales_invoice(invoice: str):
	invoice = (invoice or "").strip()

	if not invoice:
		frappe.local.response.http_status_code = 400
		return {"success": False, "message": "Invoice name is required."}

	if not frappe.db.exists("Sales Invoice", invoice):
		frappe.local.response.http_status_code = 404
		return {"success": False, "message": _("Sales Invoice '{0}' does not exist.").format(invoice)}

	try:
		doc = frappe.get_doc("Sales Invoice", invoice)
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
def list_sales_invoices(
	company: str | None = None,
	customer: str | None = None,
	posting_date: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
	status: str | None = None,
	pos_profile: str | None = None,
	channel: str | None = None,
	sales_person: str | None = None,
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

	for key, value in (("company", company), ("customer", customer), ("status", status), ("pos_profile", pos_profile), ("channel", channel)):
		if value:
			filters.append([key, "=", value])
			applied[key] = value

	if sales_person:
		invoices_of_person = frappe.get_all(
			"Sales Team",
			filters={"sales_person": sales_person, "parenttype": "Sales Invoice"},
			pluck="parent",
		)
		filters.append(["name", "in", invoices_of_person or [""]])
		applied["sales_person"] = sales_person

	# Filter to only POS-created invoices
	filters.append(["is_pos", "=", 1])
	filters.append(["is_created_using_pos", "=", 1])

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
			"Sales Invoice",
			filters=filters or None,
			fields=["name", "customer", "company", "pos_profile", "channel", "posting_date", "grand_total", "outstanding_amount", "status", "docstatus", "commission_paid", "commission_journal_entry"],
			order_by=f"{order_by} {order}",
			limit_start=(page - 1) * page_length,
			limit_page_length=page_length,
		)
		commission = _get_commission_info([row.name for row in data])
		for row in data:
			row.update(commission[row.name])
		return {"success": True, "count": len(data), "filters": applied, "data": data}
	except Exception as e:
		frappe.log_error(title="sales_invoice_pos.list_sales_invoices", message=str(e))
		return respond(500, str(e))


def _commission_cancel_decision(doc, keep_commission_payment):
	"""Decide whether to cancel the commission JE together with the invoice.

	Returns True/False, or None when the POS must ask the cashier (POS Profile set to "No"
	and no keep_commission_payment sent). An explicit keep_commission_payment always wins.
	"""
	if keep_commission_payment not in (None, ""):
		return not cint(keep_commission_payment)
	if auto_cancel_enabled(doc.pos_profile):
		return True
	return None


@frappe.whitelist(methods=["POST"])
def cancel_sales_invoice(invoice: str, keep_commission_payment: int | str | None = None):
	invoice = (invoice or "").strip()

	if not invoice:
		frappe.local.response.http_status_code = 400
		return {"success": False, "message": "Invoice name is required."}

	if not frappe.db.exists("Sales Invoice", invoice):
		frappe.local.response.http_status_code = 404
		return {"success": False, "message": _("Sales Invoice '{0}' does not exist.").format(invoice)}

	try:
		doc = frappe.get_doc("Sales Invoice", invoice)

		if doc.docstatus != 1:
			frappe.local.response.http_status_code = 409
			return {
				"success": False,
				"message": _("Sales Invoice can only be cancelled if it is submitted."),
			}

		commission_je = get_active_commission_je(doc)
		if commission_je:
			cancel_je = _commission_cancel_decision(doc, keep_commission_payment)
			if cancel_je is None:
				frappe.local.response.http_status_code = 409
				return {
					"success": False,
					"requires_commission_decision": True,
					"message": _(
						"This invoice has a commission cash entry. Send keep_commission_payment = 1 to keep "
						"it, or 0 to cancel it together with the invoice."
					),
					"data": {
						"commission_journal_entry": commission_je,
						"sales_person": get_sales_person(doc),
						"commission_amount": get_commission_amount(doc),
					},
				}
			doc.flags.cancel_commission_je = cancel_je

		doc.cancel()
	except frappe.ValidationError as e:
		frappe.db.rollback()
		frappe.local.response.http_status_code = 400
		return {"success": False, "message": str(e)}
	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(title="luxury_api.sales_invoice_pos.cancel_sales_invoice")
		frappe.local.response.http_status_code = 500
		return {"success": False, "message": str(e)}

	frappe.local.response.http_status_code = 200
	return {
		"success": True,
		"message": "Sales Invoice cancelled successfully.",
		"data": {
			"name": doc.name,
			"status": doc.status,
			"commission_journal_entry": doc.get("commission_journal_entry"),
			"commission_payment_cancelled": bool(doc.get("commission_journal_entry"))
			and frappe.db.get_value("Journal Entry", doc.commission_journal_entry, "docstatus") == 2,
		},
	}


@frappe.whitelist(methods=["POST"])
def create_sales_invoice_return(invoice: str, recover_commission: int | str | None = None):
	def respond(status, message, data=None):
		frappe.local.response.http_status_code = status
		return {"success": status < 400, "message": message, **({"data": data} if data else {})}

	invoice = (invoice or "").strip()

	if not invoice:
		return respond(400, _("Invoice name is required."))
	if not frappe.db.exists("Sales Invoice", invoice):
		return respond(404, _("Sales Invoice '{0}' does not exist.").format(invoice))
	if frappe.db.get_value("Sales Invoice", invoice, "docstatus") != 1:
		return respond(409, _("Can only create return for a submitted Sales Invoice."))

	original_je, recover, ask = _commission_recovery_check(invoice, recover_commission)
	if ask:
		return ask

	try:
		from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return

		return_doc = make_sales_return(invoice)
		return_doc.insert()
		return_doc.submit()
		if recover:
			_recover_commission(return_doc, original_je)
	except frappe.ValidationError as e:
		frappe.db.rollback()
		return respond(400, str(e))
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="luxury_api.sales_invoice_pos.create_sales_invoice_return")
		return respond(500, _("Failed to create return Sales Invoice. Please try again."))

	return respond(201, _("Return Sales Invoice created successfully."), return_doc.as_dict())


@frappe.whitelist(methods=["POST"])
def create_partial_sales_return(**kwargs):
	"""Create a partial/full Return Sales Invoice against a submitted original invoice."""
	def respond(status, message, data=None):
		frappe.local.response.http_status_code = status
		return {"success": status < 400, "message": message, **({"data": data} if data else {})}

	data = _get_payload(kwargs, RETURN_FIELDS)
	original_invoice = (data.get("original_invoice") or "").strip()

	if not original_invoice:
		return respond(400, _("Original invoice name is required."))
	if not frappe.db.exists("Sales Invoice", original_invoice):
		return respond(404, _("Sales Invoice '{0}' does not exist.").format(original_invoice))

	docstatus, is_return = frappe.db.get_value("Sales Invoice", original_invoice, ["docstatus", "is_return"])
	if docstatus != 1:
		return respond(409, _("Can only create return for a submitted Sales Invoice."))
	if is_return:
		return respond(400, _("Cannot create a return for an invoice that is already a return."))

	original_je, recover, ask = _commission_recovery_check(original_invoice, data.get("recover_commission"))
	if ask:
		return ask

	try:
		_validate_rows(data.get("items"), "Items", "item_code", "qty")

		items_list = data.get("items", [])
		seen = set()
		for idx, item in enumerate(items_list, 1):
			item_code = item.get("item_code")
			if item_code in seen:
				frappe.throw(_("Row {0}: Duplicate item {1}.").format(idx, item_code))
			seen.add(item_code)

		from erpnext.accounts.doctype.sales_invoice.sales_invoice import make_sales_return

		return_doc = make_sales_return(original_invoice)
		full_return_total = flt(return_doc.grand_total)

		original_items_map = _get_original_items_map(original_invoice)
		return_map = {d.sales_invoice_item: d for d in return_doc.items}

		request_map = {}
		for item_req in items_list:
			item_code = item_req.get("item_code")
			if item_code not in original_items_map:
				frappe.throw(_("Item {0} does not exist in Sales Invoice {1}.").format(item_code, original_invoice))

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
			if item_row.sales_invoice_item in request_map:
				requested_qty = request_map[item_row.sales_invoice_item]
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
		if recover:
			_recover_commission(return_doc, original_je)

	except frappe.ValidationError as e:
		frappe.db.rollback()
		return respond(400, str(e))
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="luxury_api.sales_invoice_pos.create_partial_sales_return")
		return respond(500, _("Failed to create return Sales Invoice. Please try again."))

	return respond(201, _("Return Sales Invoice created successfully."), {
		"return_invoice": return_doc.name,
		"original_invoice": original_invoice,
		"sales_person": get_sales_person(return_doc),
		"commission_amount": get_commission_amount(return_doc),
		"commission_journal_entry": return_doc.get("commission_journal_entry"),
	})
