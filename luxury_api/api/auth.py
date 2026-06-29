import frappe
from frappe import _
from frappe.auth import LoginManager


@frappe.whitelist(allow_guest=True)
def login(usr, pwd):
	"""
	Authenticate a user and return enriched session data.

	Performs standard Frappe credential validation via LoginManager, then
	appends the authenticated user's roles and User Permission records to the
	response so the caller does not need a second round-trip.

	Args:
	    usr (str): Username or email address.
	    pwd (str): Plain-text password.

	Returns:
	    dict: Frappe-standard login fields plus:
	        - name             — User ID (email)
	        - email            — User email
	        - full_name        — Display name
	        - roles            — List of role names
	        - user_permissions — List of permission dicts
	"""
	manager = LoginManager()
	manager.authenticate(user=usr, pwd=pwd)
	manager.post_login()

	user = frappe.session.user
	user_doc = frappe.db.get_value("User", user, ["name", "email", "full_name"], as_dict=True)

	return {
		"message": "Logged In",
		"home_page": "desk",
		"name": user_doc.name,
		"email": user_doc.email,
		"full_name": user_doc.full_name,
		"roles": _get_roles(user),
		"user_permissions": _get_user_permissions(user),
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
