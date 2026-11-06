"""Commission payment (Journal Entry) linked to POS Sales Invoices."""

import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import flt


def auto_cancel_enabled(pos_profile):
	"""True if the POS Profile cancels the commission JE automatically.

	The field is a Select (Yes/No, default Yes). Only "No" turns auto-cancel off.
	"""
	if not pos_profile:
		return True
	return frappe.db.get_value("POS Profile", pos_profile, "auto_cancel_commission_payment") != "No"


def auto_recover_enabled(pos_profile):
	"""True if a return automatically recovers the partner's commission share (Select Yes/No, default Yes)."""
	if not pos_profile:
		return True
	return frappe.db.get_value("POS Profile", pos_profile, "auto_recover_commission_on_return") != "No"


def get_active_commission_je(invoice):
	"""Return the linked commission JE name if it is submitted, else None."""
	je_name = invoice.get("commission_journal_entry")
	if je_name and frappe.db.get_value("Journal Entry", je_name, "docstatus") == 1:
		return je_name
	return None


def paid_commission_query():
	"""Base query: invoices whose commission JE is submitted. Includes cancelled invoices whose JE was kept."""
	si = frappe.qb.DocType("Sales Invoice")
	je = frappe.qb.DocType("Journal Entry")
	query = (
		frappe.qb.from_(si)
		.inner_join(je)
		.on(je.name == si.commission_journal_entry)
		.where(je.docstatus == 1)
		.where(si.docstatus.isin([1, 2]))
		.where(si.is_pos == 1)
		.where(si.is_created_using_pos == 1)
	)
	return si, query


def apply_fixed_commission(doc, method=None):
	"""Sales Invoice validate hook. Runs after ERPNext's calculate_commission (rate × eligible amount).

	- Sale from the API (doc.flags.commission_amount): total_commission = that fixed amount.
	- Return against an invoice with commission: total_commission = minus the same share of the
	  original commission as the returned eligible value, capped so all returns never exceed it.
	commission_rate is set to the matching % for information only.
	"""
	fixed = doc.flags.get("commission_amount")
	if fixed is not None:
		_set_fixed_commission(doc, flt(fixed))
	elif doc.is_return and doc.return_against and doc.sales_partner:
		_set_return_commission_share(doc)


def _set_fixed_commission(doc, amount):
	eligible = flt(doc.amount_eligible_for_commission)
	if eligible <= 0:
		frappe.throw(_("No item on this invoice is eligible for commission (Item 'Grant Commission' is off)."))
	if amount > eligible:
		frappe.throw(
			_("Commission amount {0} cannot be more than the commission-eligible amount {1}.").format(amount, eligible)
		)
	doc.total_commission = flt(amount, doc.precision("total_commission"))
	doc.commission_rate = flt(amount / eligible * 100, doc.precision("commission_rate"))


def _set_return_commission_share(doc):
	original = frappe.db.get_value(
		"Sales Invoice", doc.return_against, ["total_commission", "amount_eligible_for_commission"], as_dict=True
	)
	if not original or flt(original.total_commission) <= 0 or flt(original.amount_eligible_for_commission) <= 0:
		return

	share = flt(original.total_commission) * abs(flt(doc.amount_eligible_for_commission)) / flt(
		original.amount_eligible_for_commission
	)
	si = frappe.qb.DocType("Sales Invoice")
	result = (
		frappe.qb.from_(si)
		.select(Sum(si.total_commission))
		.where(si.return_against == doc.return_against)
		.where(si.docstatus == 1)
		.where(si.name != (doc.name or ""))
	).run()
	already_returned = -flt(result[0][0] if result else 0)
	share = min(share, flt(original.total_commission) - already_returned)
	doc.total_commission = -flt(max(share, 0), doc.precision("total_commission"))


def cancel_commission_journal_entry(doc, method=None):
	"""Sales Invoice on_cancel hook.

	The API sets doc.flags.cancel_commission_je. Without it (for example a Desk cancel),
	the POS Profile setting decides.
	"""
	je_name = get_active_commission_je(doc)
	if not je_name:
		return

	decision = doc.flags.get("cancel_commission_je")
	if decision is None:
		decision = auto_cancel_enabled(doc.pos_profile)

	if not decision:
		frappe.msgprint(
			_("Commission payment {0} was kept. Cancel it manually if the partner returned the money.").format(
				je_name
			),
			alert=True,
		)
		return

	je = frappe.get_doc("Journal Entry", je_name)
	je.flags.ignore_permissions = True
	je.cancel()
