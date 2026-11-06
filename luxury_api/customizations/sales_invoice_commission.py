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
	"""True if a return automatically recovers the sales person's commission share (Select Yes/No, default Yes)."""
	if not pos_profile:
		return True
	return frappe.db.get_value("POS Profile", pos_profile, "auto_recover_commission_on_return") != "No"


def get_active_commission_je(invoice):
	"""Return the linked commission JE name if it is submitted, else None."""
	je_name = invoice.get("commission_journal_entry")
	if je_name and frappe.db.get_value("Journal Entry", je_name, "docstatus") == 1:
		return je_name
	return None


def get_commission_amount(doc):
	"""Sales Person commission on the invoice: sum of Sales Team incentives (negative on a return)."""
	return sum(flt(row.incentives) for row in doc.get("sales_team") or [])


def get_sales_person(doc):
	"""The invoice's sales person (the API sets a single Sales Team row)."""
	team = doc.get("sales_team") or []
	return team[0].sales_person if team else None


def paid_commission_query():
	"""Base query: invoices whose commission JE is submitted, joined to their Sales Team row.

	Includes cancelled invoices whose JE was kept.
	"""
	si = frappe.qb.DocType("Sales Invoice")
	st = frappe.qb.DocType("Sales Team")
	je = frappe.qb.DocType("Journal Entry")
	query = (
		frappe.qb.from_(si)
		.inner_join(st)
		.on((st.parent == si.name) & (st.parenttype == "Sales Invoice"))
		.inner_join(je)
		.on(je.name == si.commission_journal_entry)
		.where(je.docstatus == 1)
		.where(si.docstatus.isin([1, 2]))
		.where(si.is_pos == 1)
		.where(si.is_created_using_pos == 1)
	)
	return si, st, query


def apply_fixed_commission(doc, method=None):
	"""Sales Invoice validate hook. Runs after ERPNext's calculate_contribution.

	- Sale from the API (doc.flags.commission_amount): the Sales Team row incentives = that fixed amount.
	- Return against an invoice with commission: incentives = minus the same share of the original
	  commission as the returned eligible value, capped so all returns never exceed it.
	"""
	team = doc.get("sales_team") or []
	if not team:
		return
	fixed = doc.flags.get("commission_amount")
	if fixed is not None:
		_set_fixed_commission(doc, team[0], flt(fixed))
	elif doc.is_return and doc.return_against:
		_set_return_commission_share(doc, team[0])


def _set_fixed_commission(doc, row, amount):
	eligible = flt(doc.amount_eligible_for_commission)
	if eligible <= 0:
		frappe.throw(_("No item on this invoice is eligible for commission (Item 'Grant Commission' is off)."))
	if amount > eligible:
		frappe.throw(
			_("Commission amount {0} cannot be more than the commission-eligible amount {1}.").format(amount, eligible)
		)
	row.incentives = flt(amount, doc.precision("incentives", row))


def _set_return_commission_share(doc, row):
	original_eligible = flt(frappe.db.get_value("Sales Invoice", doc.return_against, "amount_eligible_for_commission"))
	original_commission = sum(
		flt(r.incentives)
		for r in frappe.get_all(
			"Sales Team",
			filters={"parent": doc.return_against, "parenttype": "Sales Invoice"},
			fields=["incentives"],
		)
	)
	if original_commission <= 0 or original_eligible <= 0:
		return

	share = original_commission * abs(flt(doc.amount_eligible_for_commission)) / original_eligible
	si = frappe.qb.DocType("Sales Invoice")
	st = frappe.qb.DocType("Sales Team")
	result = (
		frappe.qb.from_(si)
		.inner_join(st)
		.on((st.parent == si.name) & (st.parenttype == "Sales Invoice"))
		.select(Sum(st.incentives))
		.where(si.return_against == doc.return_against)
		.where(si.docstatus == 1)
		.where(si.name != (doc.name or ""))
	).run()
	already_returned = -flt(result[0][0] if result else 0)
	share = min(share, original_commission - already_returned)
	row.incentives = -flt(max(share, 0), doc.precision("incentives", row))


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
			_("Commission payment {0} was kept. Cancel it manually if the sales person returned the money.").format(
				je_name
			),
			alert=True,
		)
		return

	je = frappe.get_doc("Journal Entry", je_name)
	je.flags.ignore_permissions = True
	je.cancel()
