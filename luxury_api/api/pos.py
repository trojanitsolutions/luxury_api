import frappe
from frappe import _


@frappe.whitelist(methods=["GET"], allow_guest=False)
def get_pos_profile(branch: str = None, pos_profile: str = None):
	names = _resolve_pos_profile_names(branch, pos_profile)

	rows = frappe.get_all(
		"POS Profile",
		filters={"name": ["in", names]},
		fields=["name", "company", "company_address", "branch", "warehouse", "disabled"],
	)

	address_map = _fetch_addresses([row.company_address for row in rows])
	payments_map = _fetch_payments(rows)
	users_map = _fetch_applicable_users(names)

	data = [_build_pos_profile_payload(row, address_map, payments_map, users_map) for row in rows]

	return {"success": True, "data": data}



def _resolve_pos_profile_names(branch, pos_profile):
	filters = {}

	if pos_profile:
		if not frappe.db.exists("POS Profile", pos_profile):
			frappe.throw(_("POS Profile '{0}' does not exist.").format(pos_profile), frappe.DoesNotExistError)
		return [pos_profile]

	if branch:
		filters["branch"] = branch

	names = frappe.get_all("POS Profile", filters=filters, pluck="name")
	if not names:
		if branch:
			frappe.throw(_("No POS Profile found for Branch '{0}'.").format(branch), frappe.DoesNotExistError)
		else:
			frappe.throw(_("No POS Profile found."), frappe.DoesNotExistError)
	return names


def _fetch_addresses(address_names):
	address_names = list({name for name in address_names if name})
	if not address_names:
		return {}

	fields = ["name", "address_title", "address_line1", "address_line2", "city", "state", "country", "pincode", "phone", "email_id"]
	has_gstin = frappe.get_meta("Address").has_field("gstin")
	if has_gstin:
		fields.append("gstin")

	rows = frappe.get_all("Address", filters={"name": ["in", address_names]}, fields=fields)
	return {row.name: row for row in rows}


def _fetch_payments(profile_rows):
	company_by_profile = {row.name: row.company for row in profile_rows}
	names = list(company_by_profile.keys())

	payment_rows = frappe.get_all(
		"POS Payment Method",
		filters={"parent": ["in", names]},
		fields=["parent", "mode_of_payment", "default"],
	)
	if not payment_rows:
		return {}

	modes = list({row.mode_of_payment for row in payment_rows})
	companies = list({company_by_profile[row.parent] for row in payment_rows})

	account_rows = frappe.get_all(
		"Mode of Payment Account",
		filters={"parent": ["in", modes], "company": ["in", companies]},
		fields=["parent", "company", "default_account"],
	)
	account_map = {(row.parent, row.company): row.default_account for row in account_rows}

	payments_map = {}
	for row in payment_rows:
		company = company_by_profile[row.parent]
		payments_map.setdefault(row.parent, []).append(
			{
				"mode_of_payment": row.mode_of_payment,
				"default": row.default,
				"account": account_map.get((row.mode_of_payment, company)),
			}
		)
	return payments_map


def _fetch_applicable_users(names):
	user_rows = frappe.get_all(
		"POS Profile User",
		filters={"parent": ["in", names]},
		fields=["parent", "user"],
	)
	if not user_rows:
		return {}

	user_ids = list({row.user for row in user_rows})
	user_details = frappe.get_all(
		"User", filters={"name": ["in", user_ids]}, fields=["name", "full_name", "email"]
	)
	user_detail_map = {row.name: row for row in user_details}

	users_map = {}
	for row in user_rows:
		detail = user_detail_map.get(row.user, {})
		users_map.setdefault(row.parent, []).append(
			{
				"user": row.user,
				"full_name": detail.get("full_name"),
				"email": detail.get("email"),
			}
		)
	return users_map


def _build_pos_profile_payload(row, address_map, payments_map, users_map):
	address = address_map.get(row.company_address)
	payload = {
		"pos_profile": row.name,
		"company": row.company,
		"company_address": dict(address) if address else None,
		"branch": row.branch,
		"warehouse": row.warehouse,
		"disabled": row.disabled,
		"payments": payments_map.get(row.name, []),
		"applicable_for_users": users_map.get(row.name, []),
	}
	if payload["company_address"]:
		payload["company_address"].pop("name", None)
	return payload
