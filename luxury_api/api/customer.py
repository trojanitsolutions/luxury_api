import math

import frappe


@frappe.whitelist(methods=["GET"], allow_guest=False)
def get_customers(search: str = None, page=1, page_size=20):
	search = (search or "").strip()

	page = max(1, int(page))
	page_size = min(100, max(1, int(page_size)))

	or_filters = None
	if search:
		or_filters = [
			["name", "like", f"%{search}%"],
			["customer_name", "like", f"%{search}%"],
		]
		contact_customer_ids = _find_customers_by_contact(search)
		if contact_customer_ids:
			or_filters.append(["name", "in", contact_customer_ids])

	total = frappe.get_all(
		"Customer",
		or_filters=or_filters,
		fields=[{"COUNT": "name", "as": "total"}],
	)[0].total

	if not total:
		return {"success": True, "data": [], "message": "No customers found."}

	rows = frappe.get_all(
		"Customer",
		or_filters=or_filters,
		fields=["name", "customer_name", "customer_type", "customer_primary_contact", "territory", "disabled"],
		order_by="customer_name asc",
		limit_start=(page - 1) * page_size,
		limit=page_size,
	)

	contact_map = _fetch_primary_contacts([row.customer_primary_contact for row in rows])
	data = [_build_customer_payload(row, contact_map) for row in rows]

	return {
		"success": True,
		"data": data,
		"pagination": {
			"page": page,
			"page_size": page_size,
			"total_records": total,
			"total_pages": math.ceil(total / page_size),
			"has_next": page * page_size < total,
			"has_previous": page > 1,
		},
	}


@frappe.whitelist(methods=["POST"])
def create_customer(customer_name: str = None, mobile_no: str = None, email_id: str = None):
	customer_name = (customer_name or "").strip()
	mobile_no = (mobile_no or "").strip()
	email_id = (email_id or "").strip() or None

	if not customer_name or not mobile_no:
		frappe.local.response.http_status_code = 400
		return {"success": False, "message": "Customer Name and Mobile Number are mandatory."}

	existing_customer = _find_existing_customer(mobile_no)
	if existing_customer:
		frappe.local.response.http_status_code = 409
		return {
			"success": False,
			"message": "Customer with this mobile number already exists.",
			"customer": existing_customer,
		}

	try:
		customer = _create_customer(customer_name)
		contact = _create_primary_contact(customer, mobile_no, email_id)
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title="luxury_api.customer.create_customer")
		frappe.local.response.http_status_code = 500
		return {"success": False, "message": "Failed to create customer. Please try again."}

	frappe.local.response.http_status_code = 201
	return {
		"success": True,
		"message": "Customer created successfully.",
		"customer": {
			"name": customer.name,
			"customer_name": customer.customer_name,
			"customer_type": customer.customer_type,
		},
		"contact": {
			"name": contact.name,
			"mobile_no": contact.mobile_no,
			"email_id": contact.email_id,
		},
	}

def _find_customers_by_contact(search):
	contact_names = frappe.get_all(
		"Contact",
		or_filters=[
			["mobile_no", "like", f"%{search}%"],
			["phone", "like", f"%{search}%"],
			["email_id", "like", f"%{search}%"],
		],
		pluck="name",
	)
	if not contact_names:
		return []

	return frappe.get_all(
		"Dynamic Link",
		filters={"parenttype": "Contact", "parent": ["in", contact_names], "link_doctype": "Customer"},
		pluck="link_name",
	)


def _fetch_primary_contacts(contact_names):
	contact_names = [name for name in contact_names if name]
	if not contact_names:
		return {}

	rows = frappe.get_all(
		"Contact",
		filters={"name": ["in", contact_names]},
		fields=["name", "mobile_no", "email_id"],
	)
	return {row.name: row for row in rows}


def _build_customer_payload(row, contact_map):
	contact = contact_map.get(row.customer_primary_contact, {})
	return {
		"customer_id": row.name,
		"customer_name": row.customer_name,
		"customer_type": row.customer_type,
		"mobile_no": contact.get("mobile_no"),
		"email_id": contact.get("email_id"),
		"primary_contact": row.customer_primary_contact,
		"territory": row.territory,
		"disabled": row.disabled,
	}


def _find_existing_customer(mobile_no):
	contact_names = frappe.get_all("Contact Phone", filters={"phone": mobile_no}, pluck="parent")
	if not contact_names:
		return None

	links = frappe.get_all(
		"Dynamic Link",
		filters={"parenttype": "Contact", "parent": ["in", contact_names], "link_doctype": "Customer"},
		fields=["link_name"],
	)
	if not links:
		return None

	customer = frappe.db.get_value(
		"Customer", links[0].link_name, ["name", "customer_name"], as_dict=True
	)
	return customer


def _create_customer(customer_name):
	customer = frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": customer_name,
			"customer_type": "Individual",
		}
	)
	customer.insert()
	return customer


def _create_primary_contact(customer, mobile_no, email_id):
	contact = frappe.get_doc(
		{
			"doctype": "Contact",
			"first_name": customer.customer_name,
			"is_primary_contact": 1,
			"phone_nos": [{"phone": mobile_no, "is_primary_phone": 1, "is_primary_mobile_no": 1}],
			"links": [{"link_doctype": "Customer", "link_name": customer.name}],
		}
	)
	if email_id:
		contact.append("email_ids", {"email_id": email_id, "is_primary": 1})
	contact.insert()

	customer.customer_primary_contact = contact.name
	customer.save()

	return contact
