import frappe
from frappe import _
from frappe.auth import LoginManager
from frappe.utils.password import check_password as _check_password


@frappe.whitelist(allow_guest=True)
def login(usr, pwd):
	
	try:
		user_name = _check_password(usr, pwd)
	except frappe.AuthenticationError:
		frappe.throw(_("Invalid credentials"), frappe.AuthenticationError)

	user_doc = frappe.db.get_value("User", user_name, ["name", "email", "full_name", "enabled"], as_dict=True)
	active = bool(user_doc.enabled)

	if active:
		manager = LoginManager()
		manager.authenticate(user=usr, pwd=pwd)
		manager.post_login()

	return {
		"message": "Logged In",
		"home_page": "desk",
		"name": user_doc.name,
		"email": user_doc.email,
		"full_name": user_doc.full_name,
		"active": active,
		"roles": _get_roles(user_name),
		"user_permissions": _get_user_permissions(user_name),
	}


def _get_roles(user):
	rows = frappe.get_all(
		"Has Role",
		filters={"parent": user, "parenttype": "User"},
		pluck="role",
	)
	return rows


def _get_user_permissions(user):
	rows = frappe.get_all(
		"User Permission",
		filters={"user": user},
		fields=["name", "allow", "for_value", "applicable_for", "hide_descendants", "is_default"],
	)
	for row in rows:
		row["applicable_for"] = row["applicable_for"] or ""
	return rows
