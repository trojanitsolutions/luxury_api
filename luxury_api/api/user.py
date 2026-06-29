import frappe
from frappe import _


@frappe.whitelist()
def get_users(role=None):
	"""
	Fetch enabled System Users (excluding Website Users) with their roles and permissions.

	Args:
	    role (str, optional): When supplied, only users assigned this role are returned.
	                          The role must exist; an error is raised otherwise.

	Returns:
	    list[dict]: Ordered by full_name. Each entry contains:
	        - name           — User ID (email)
	        - full_name      — Display name
	        - roles          — List of role names assigned to the user
	        - user_permissions — List of User Permission records for the user
	"""
	if role:
		_validate_role(role)

	users = _fetch_users(role)
	if not users:
		return []

	user_names = [u["name"] for u in users]

	roles_map = _fetch_roles_map(user_names)
	perms_map = _fetch_permissions_map(user_names)

	base_url = frappe.utils.get_url()
	for user in users:
		user["login_url"] = f"{base_url}/login?user={user['name']}"
		user["roles"] = roles_map.get(user["name"], [])
		user["user_permissions"] = perms_map.get(user["name"], [])

	return users


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _validate_role(role):
	"""Raise DoesNotExistError if *role* is not a valid Role document."""
	if not frappe.db.exists("Role", role):
		frappe.throw(_("Role '{0}' does not exist.").format(role), frappe.DoesNotExistError)


def _fetch_users(role=None):
	"""
	Return enabled System Users ordered by full_name.

	When *role* is given the result is pre-filtered to users that appear in
	Has Role for that role; duplicates are removed with set().
	"""
	filters = {
		"enabled": 1,
		"user_type": ["!=", "Website User"],
		"name": ["!=", "Administrator"],
	}

	if role:
		role_user_names = frappe.get_all(
			"Has Role",
			filters={"role": role, "parenttype": "User"},
			pluck="parent",
		)
		if not role_user_names:
			return []
		# Deduplicate and exclude Administrator before passing to the IN filter
		eligible = list(set(role_user_names) - {"Administrator"})
		if not eligible:
			return []
		filters["name"] = ["in", eligible]

	return frappe.get_all(
		"User",
		filters=filters,
		fields=["name", "full_name"],
		order_by="full_name asc",
	)


def _fetch_roles_map(user_names):
	"""
	Fetch all Has Role rows for *user_names* in a single query.

	Returns:
	    dict[str, list[str]]: Maps user name → list of role names.
	"""
	rows = frappe.get_all(
		"Has Role",
		filters={"parent": ["in", user_names], "parenttype": "User"},
		fields=["parent", "role"],
	)
	roles_map = {}
	for row in rows:
		roles_map.setdefault(row["parent"], []).append(row["role"])
	return roles_map


def _fetch_permissions_map(user_names):
	"""
	Fetch all User Permission rows for *user_names* in a single query.

	Returns:
	    dict[str, list[dict]]: Maps user name → list of permission dicts.
	"""
	rows = frappe.get_all(
		"User Permission",
		filters={"user": ["in", user_names]},
		fields=["name", "user", "allow", "for_value", "applicable_for", "hide_descendants", "is_default"],
	)
	perms_map = {}
	for row in rows:
		perms_map.setdefault(row["user"], []).append(
			{
				"name": row["name"],
				"allow": row["allow"],
				"for_value": row["for_value"],
				"applicable_for": row["applicable_for"] or "",
				"hide_descendants": row["hide_descendants"],
				"is_default": row["is_default"],
			}
		)
	return perms_map
