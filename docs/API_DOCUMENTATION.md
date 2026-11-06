# Luxury API — REST API Documentation

Base URL placeholder used throughout this document: `{base_url}` (e.g. `https://your-site.example.com`). Never hardcode a domain — substitute your site's actual URL.

All endpoints are Frappe whitelisted methods, called as:

```
{METHOD} {base_url}/api/method/luxury_api.api.<module>.<function>
```

---

## Table of Contents

1. [Module Overview](#module-overview)
2. [Authentication APIs](#authentication-apis)
   - [login](#login)
3. [User APIs](#user-apis)
   - [get_users](#get_users)
4. [Customer APIs](#customer-apis)
   - [get_customers](#get_customers)
   - [create_customer](#create_customer)
5. [Item APIs](#item-apis)
   - [get_items](#get_items)
6. [Item Price APIs](#item-price-apis)
   - [get_item_prices](#get_item_prices)
7. [POS APIs](#pos-apis)
   - [get_pos_profile](#get_pos_profile)
8. [POS Opening APIs](#pos-opening-apis)
   - [create_pos_opening_entry](#create_pos_opening_entry)
9. [POS Closing APIs](#pos-closing-apis)
   - [create_pos_closing_entry](#create_pos_closing_entry)
10. [Credit Sales](#credit-sales)
   - [Credit option on create_sales_invoice](#credit-option-on-create_sales_invoice)
11. [Sales Person Commission](#sales-person-commission)
   - [Commission option on create_sales_invoice](#commission-option-on-create_sales_invoice)
   - [list_sales_persons](#list_sales_persons)
   - [get_commission_summary](#get_commission_summary)
12. [Error Reference](#error-reference)
13. [API Summary Table](#api-summary-table)

---

## Module Overview

### Auth APIs (`api/auth.py`)
Handles user login. Verifies credentials, establishes a full Frappe desk session (cookies), and returns the user's profile, roles, and User Permissions in one call.

### User APIs (`api/user.py`)
Directory lookup of enabled System Users (excluding Administrator and Website Users), optionally filtered by Role, with roles and User Permissions attached per user.

### Customer APIs (`api/customer.py`)
Paginated customer search/listing (matches on name, customer name, or linked contact's phone/email) and customer creation (Customer + primary Contact in one call), with duplicate-mobile-number detection.

### Item APIs (`api/item.py`)
Paginated sales item listing with search (name/barcode), per-warehouse stock (`Bin`), selling price (`Item Price`), barcodes, and image resolution (explicit `image` field or first attached `File`).

### Item Price APIs (`api/item_price.py`)
Item Price lookup by branch or Price List. Price Lists with no branch are common to all branches; a branch price overrides the common price for the same item and UOM. Pagination is optional.

### POS APIs (`api/pos.py`)
Read-only lookup of one or more POS Profiles (by name or branch) with resolved company address, configured payment modes (with default GL account), and the list of users the profile applies to.

### POS Opening APIs (`api/pos_opening.py`)
Creates and submits a POS Opening Entry (opening cash/payment-mode balances) for a user against a POS Profile.

### POS Closing APIs (`api/pos_closing.py`)
Creates a POS Closing Entry from an open POS Opening Entry, defaulting each payment mode's closing amount to its system-expected amount (zero difference).

### Credit Sales (`api/sales_invoice_pos.py`)
Credit (unpaid or partly paid) sales through `create_sales_invoice` for channels that allow credit.

### Sales Person Commission (`api/sales_invoice_pos.py`, `api/sales_person.py`)
Records a fixed Sales Person commission on POS invoices (Sales Team table), pays it in cash, lists Sales Persons, and returns net commission per sales person.

---

## Authentication APIs

### login

#### Purpose
Authenticates a user by username/password, establishes a normal Frappe session (sets session cookies via the standard `LoginManager` flow), and returns the user's profile together with their roles and User Permissions — used as the single call a client makes to log in and bootstrap app state.

#### Endpoint
```
POST {base_url}/api/method/luxury_api.api.auth.login
```

#### Authentication
Guest access (`allow_guest=True`) — no prior session or API key required. This endpoint *creates* the session.

#### Request Headers
```http
Content-Type: application/json
```

#### Request Payload

| Parameter | Type | Required | Description |
|---|---|---|---|
| `usr` | string | Yes | Username / email |
| `pwd` | string | Yes | Password |

```json
{
  "usr": "sales.rep@example.com",
  "pwd": "secret123"
}
```

#### Sample cURL
```bash
curl --location '{base_url}/api/method/luxury_api.api.auth.login' \
--header 'Content-Type: application/json' \
--data '{
    "usr": "sales.rep@example.com",
    "pwd": "secret123"
}'
```

#### Success Response
```json
{
    "message": {
        "message": "Logged In",
        "home_page": "desk",
        "name": "sales.rep@example.com",
        "email": "sales.rep@example.com",
        "full_name": "Sales Rep",
        "active": true,
        "roles": ["Sales Rep", "Employee"],
        "user_permissions": [
            {
                "name": "UP-0001",
                "allow": "Territory",
                "for_value": "North",
                "applicable_for": "",
                "hide_descendants": 0,
                "is_default": 1
            }
        ]
    }
}
```

If the user account is disabled, the same 200 response shape is returned but **no session is created**:
```json
{
    "message": {
        "message": "Logged In",
        "home_page": "desk",
        "name": "disabled.user@example.com",
        "email": "disabled.user@example.com",
        "full_name": "Disabled User",
        "active": false,
        "roles": [],
        "user_permissions": []
    }
}
```

#### Error Responses

Invalid credentials (raised as `frappe.AuthenticationError`, HTTP 401):
```json
{
    "exc_type": "AuthenticationError",
    "_server_messages": "[\"Invalid credentials\"]"
}
```

#### Business Logic
1. `frappe.utils.password.check_password(usr, pwd)` verifies the credential pair against the stored password hash and returns the canonical user name. Raises `frappe.AuthenticationError` on mismatch, which is caught and re-thrown as a user-facing "Invalid credentials" error.
2. Loads `name, email, full_name, enabled` for the resolved user.
3. If `enabled` is truthy, runs the full Frappe login flow: `LoginManager().authenticate(usr, pwd)` followed by `post_login()` — this sets `frappe.session`, session cookies, updates last-login timestamps, and fires login hooks, identical to logging in via the desk `/login` page.
4. If the user is disabled, this step is skipped entirely — the credentials are still validated in step 1, but no session is established.
5. Regardless of `active`, the response always includes the user's roles (`_get_roles`) and User Permissions (`_get_user_permissions`).

#### Database / DocTypes Used
- `User` — profile lookup (`name`, `email`, `full_name`, `enabled`).
- `Has Role` — role list (filtered by `parent=user`, `parenttype=User`).
- `User Permission` — permission rows for the user.

#### Input Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `usr` | string | Yes | Login ID / email |
| `pwd` | string | Yes | Plaintext password, checked against stored hash |

#### Response Fields

| Field | Type | Description |
|---|---|---|
| `message` | string | Static `"Logged In"` |
| `home_page` | string | Static `"desk"` |
| `name` | string | User ID |
| `email` | string | Email address |
| `full_name` | string | Display name |
| `active` | boolean | Whether the user account is enabled (and thus whether a session was created) |
| `roles` | array\<string\> | Role names assigned to the user |
| `user_permissions` | array\<object\> | User Permission rows: `name`, `allow`, `for_value`, `applicable_for`, `hide_descendants`, `is_default` |

#### Sequence Flow
1. Receive `usr`, `pwd`.
2. Verify password via `check_password` → resolve canonical `user_name`.
3. Fetch user profile fields from `User`.
4. If enabled: run `LoginManager.authenticate` + `post_login()` → session cookies set on the response.
5. Fetch roles (`Has Role`) and User Permissions (`User Permission`).
6. Return combined JSON payload.

#### Functional Notes
- Used as the app's single sign-in call; the mobile/front-end client should store the returned session cookie for subsequent authenticated calls.
- `roles` and `user_permissions` let the client immediately gate UI (e.g. only show POS screens to users with the `Sales Rep`/POS-related role) without a second round trip.

#### Technical Notes
- **HTTP Method:** POST (default; not restricted via `methods=`)
- **Python Function:** `luxury_api.api.auth.login`
- **Whitelisted path:** `luxury_api.api.auth.login`
- **Guest access:** Yes (`allow_guest=True`) — required since no session exists yet.
- **Session handling:** Delegates entirely to `frappe.auth.LoginManager` — no custom token/JWT issuance.
- **Queries:** One `frappe.db.get_value` (User), plus two `frappe.get_all` calls (`Has Role`, `User Permission`) — no batching needed since it's single-user.
- **No pagination.**

---

## User APIs

### get_users

#### Purpose
Returns a directory of enabled System Users (excluding `Administrator` and Website Users), each annotated with their roles and User Permissions, optionally filtered to users holding a specific Role.

#### Endpoint
```
GET {base_url}/api/method/luxury_api.api.user.get_users
```
(No `methods=` restriction is declared, so GET or POST both work; GET is the conventional choice for a read-only lookup.)

#### Authentication
Login session required (`allow_guest` defaults to `False`). Send session cookies or `Authorization: token <api_key>:<api_secret>`.

#### Request Headers
```http
Authorization: token <api_key>:<api_secret>
```

#### Request Payload / Query Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `role` | string | No | Restrict results to users assigned this Role. Must be an existing Role name. |

```json
{
  "role": "Sales Rep"
}
```

#### Sample cURL
```bash
curl --location '{base_url}/api/method/luxury_api.api.user.get_users?role=Sales%20Rep' \
--header 'Authorization: token api_key:api_secret'
```

#### Success Response
```json
{
    "message": [
        {
            "name": "sales.rep@example.com",
            "full_name": "Sales Rep",
            "login_url": "{base_url}/login?user=sales.rep@example.com",
            "roles": ["Sales Rep", "Employee"],
            "user_permissions": [
                {
                    "name": "UP-0002",
                    "allow": "Territory",
                    "for_value": "North",
                    "applicable_for": "",
                    "hide_descendants": 0,
                    "is_default": 1
                }
            ]
        }
    ]
}
```

If no users match: `{"message": []}`

#### Error Responses

Role does not exist (`frappe.DoesNotExistError`, HTTP 404):
```json
{
    "exc_type": "DoesNotExistError",
    "_server_messages": "[\"Role 'Nonexistent Role' does not exist.\"]"
}
```

#### Business Logic
1. If `role` is passed, `_validate_role` confirms it exists via `frappe.db.exists("Role", role)`; throws `DoesNotExistError` otherwise.
2. `_fetch_users(role)`:
   - Base filter: `enabled=1`, `user_type != "Website User"`, `name != "Administrator"`.
   - If `role` given: looks up all `Has Role` rows for that role (`parenttype="User"`), deduplicates with `set()`, removes `Administrator`, and adds `name IN [...]` to the filter. If no users hold the role, returns `[]` immediately.
   - Returns `User` rows (`name`, `full_name`) ordered by `full_name asc`.
3. If no users found, returns `[]` immediately (skips the batch lookups).
4. `_fetch_roles_map` and `_fetch_permissions_map` each issue **one** batched query (`Has Role` / `User Permission` with `parent`/`user IN [...]`) across all matched users, rather than one query per user.
5. Builds `login_url` per user as `{site_url}/login?user=<name>`.
6. Stitches roles/permissions back onto each user dict in Python and returns the list.

#### Database / DocTypes Used
- `User`
- `Has Role`
- `User Permission`
- `Role` (existence check only)

#### Input Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `role` | string | No | Filter to users assigned this Role; validated to exist |

#### Response Fields

| Field | Type | Description |
|---|---|---|
| `name` | string | User ID (email) |
| `full_name` | string | Display name |
| `login_url` | string | Convenience deep link to the desk login page pre-filled with this user |
| `roles` | array\<string\> | Role names |
| `user_permissions` | array\<object\> | `name`, `allow`, `for_value`, `applicable_for`, `hide_descendants`, `is_default` |

#### Sequence Flow
1. Validate `role` if provided.
2. Fetch matching `User` rows (single query, optionally pre-filtered by role membership).
3. Short-circuit to `[]` if no users.
4. Batch-fetch roles map and permissions map (2 queries total, independent of user count).
5. Merge into each user record, add `login_url`.
6. Return list.

#### Functional Notes
- Used for admin/user-management screens and for populating "assign to user" pickers filtered by role (e.g. list all `Sales Rep` users for a POS Profile assignment UI).

#### Technical Notes
- **HTTP Method:** Unrestricted (`@frappe.whitelist()` with no `methods=`)
- **Python Function:** `luxury_api.api.user.get_users`
- **Batching pattern:** Exactly 2 additional queries regardless of result-set size (`_fetch_roles_map`, `_fetch_permissions_map`) — the documented convention for any new list endpoint in this app.
- **No pagination** — returns the full filtered set.
- **Sorting:** `full_name asc`.

---

## Customer APIs

### get_customers

#### Purpose
Paginated, searchable listing of Customers. Search matches against the Customer's own `name`/`customer_name`, or against a linked Contact's mobile number, phone, or email.

#### Endpoint
```
GET {base_url}/api/method/luxury_api.api.customer.get_customers
```

#### Authentication
Login session required (`allow_guest=False`).

#### Request Headers
```http
Authorization: token <api_key>:<api_secret>
```

#### Request Payload / Query Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `search` | string | No | Free-text match against customer name/ID or linked contact's mobile/phone/email |
| `page` | int | No (default `1`) | Page number, clamped to minimum 1 |
| `page_size` | int | No (default `20`) | Page size, clamped between 1 and 100 |

```json
{
  "search": "9876543210",
  "page": 1,
  "page_size": 20
}
```

#### Sample cURL
```bash
curl --location '{base_url}/api/method/luxury_api.api.customer.get_customers?search=john&page=1&page_size=20' \
--header 'Authorization: token api_key:api_secret'
```

#### Success Response
```json
{
    "message": {
        "success": true,
        "data": [
            {
                "customer_id": "CUST-0001",
                "customer_name": "John Doe",
                "customer_type": "Individual",
                "mobile_no": "9876543210",
                "email_id": "john@example.com",
                "primary_contact": "CONT-0001",
                "territory": "North",
                "disabled": 0
            }
        ],
        "pagination": {
            "page": 1,
            "page_size": 20,
            "total_records": 1,
            "total_pages": 1,
            "has_next": false,
            "has_previous": false
        }
    }
}
```

No results:
```json
{
    "message": {
        "success": true,
        "data": [],
        "message": "No customers found."
    }
}
```

#### Error Responses
No explicit validation errors are raised by this endpoint; malformed `page`/`page_size` values that can't cast to `int` raise a standard `ValueError` (HTTP 500).

#### Business Logic
1. Normalize `search` (trim), clamp `page` to `>= 1`, clamp `page_size` to `1..100`.
2. If `search` given, build `or_filters` matching `Customer.name` or `Customer.customer_name` via `LIKE %search%`, plus (if any) Customer IDs resolved from `_find_customers_by_contact`.
3. `_find_customers_by_contact`: searches `Contact` for `mobile_no`/`phone`/`email_id` matches, then resolves those Contacts to linked Customers via `Dynamic Link` (`link_doctype="Customer"`).
4. Counts total matching rows first; if zero, returns early with an empty list and a friendly message (skips the detail query and contact batching).
5. Fetches the paginated page of `Customer` rows ordered by `customer_name asc`.
6. Batch-fetches primary contact details (`mobile_no`, `email_id`) for all `customer_primary_contact` values on the page in one query (`_fetch_primary_contacts`).
7. Builds each customer's payload, pulling `mobile_no`/`email_id` from the batched contact map.

#### Database / DocTypes Used
- `Customer`
- `Contact`
- `Contact Phone` (only in `create_customer`'s duplicate check, not here)
- `Dynamic Link`

#### Input Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `search` | string | No | Matches customer name/ID or contact mobile/phone/email |
| `page` | int | No | Default 1, minimum 1 |
| `page_size` | int | No | Default 20, range 1–100 |

#### Response Fields

| Field | Type | Description |
|---|---|---|
| `success` | boolean | Always `true` on this path |
| `data[].customer_id` | string | Customer document name |
| `data[].customer_name` | string | Customer's display name |
| `data[].customer_type` | string | e.g. `Individual`, `Company` |
| `data[].mobile_no` | string\|null | From primary contact |
| `data[].email_id` | string\|null | From primary contact |
| `data[].primary_contact` | string | Linked Contact name |
| `data[].territory` | string | Territory |
| `data[].disabled` | int (0/1) | Whether the customer is disabled |
| `pagination.page` | int | Current page |
| `pagination.page_size` | int | Page size used |
| `pagination.total_records` | int | Total matching customers |
| `pagination.total_pages` | int | `ceil(total / page_size)` |
| `pagination.has_next` | boolean | Whether another page exists |
| `pagination.has_previous` | boolean | Whether a previous page exists |

#### Sequence Flow
1. Parse and clamp pagination params.
2. Build search `or_filters` (including contact-based Customer ID resolution) if `search` given.
3. Count total matches.
4. If zero, return empty result immediately.
5. Fetch the page of `Customer` rows.
6. Batch-fetch primary contact details for the page.
7. Assemble and return payload with pagination metadata.

#### Functional Notes
- Used by customer search/autocomplete screens (e.g. searching a customer by phone number while creating a Sales Order in the mobile app).

#### Technical Notes
- **HTTP Method:** GET (`methods=["GET"]`)
- **Python Function:** `luxury_api.api.customer.get_customers`
- **Pagination:** Standard offset pagination via `limit_start`/`limit`.
- **Performance:** Two `Customer` queries (count + page) plus up to 3 extra queries only when `search` is non-empty (`Contact` search, `Dynamic Link` resolution, primary-contact batch fetch) — no per-row queries.
- **Sorting:** `customer_name asc`.

---

### create_customer

#### Purpose
Creates a new Customer along with a primary Contact (holding mobile number and optional email) in a single call, rejecting the request if a Customer already exists with the given mobile number.

#### Endpoint
```
POST {base_url}/api/method/luxury_api.api.customer.create_customer
```

#### Authentication
Login session required (no `allow_guest` override, so default `False`).

#### Request Headers
```http
Content-Type: application/json
Authorization: token <api_key>:<api_secret>
```

#### Request Payload

| Parameter | Type | Required | Description |
|---|---|---|---|
| `customer_name` | string | Yes | Customer's display name |
| `mobile_no` | string | Yes | Mobile number; used for duplicate detection |
| `email_id` | string | No | Optional email address for the primary contact |

```json
{
  "customer_name": "John Doe",
  "mobile_no": "9876543210",
  "email_id": "john@example.com"
}
```

#### Sample cURL
```bash
curl --location '{base_url}/api/method/luxury_api.api.customer.create_customer' \
--header 'Authorization: token api_key:api_secret' \
--header 'Content-Type: application/json' \
--data '{
    "customer_name": "John Doe",
    "mobile_no": "9876543210",
    "email_id": "john@example.com"
}'
```

#### Success Response (HTTP 201)
```json
{
    "message": {
        "success": true,
        "message": "Customer created successfully.",
        "customer": {
            "name": "CUST-0002",
            "customer_name": "John Doe",
            "customer_type": "Individual"
        },
        "contact": {
            "name": "CONT-0002",
            "mobile_no": "9876543210",
            "email_id": "john@example.com"
        }
    }
}
```

#### Error Responses

Missing mandatory fields (HTTP 400):
```json
{
    "success": false,
    "message": "Customer Name and Mobile Number are mandatory."
}
```

Duplicate mobile number (HTTP 409):
```json
{
    "success": false,
    "message": "Customer with this mobile number already exists.",
    "customer": {
        "name": "CUST-0001",
        "customer_name": "John Doe"
    }
}
```

Unexpected failure during creation (HTTP 500) — transaction is rolled back and the error is logged to the Error Log (`title="luxury_api.customer.create_customer"`):
```json
{
    "success": false,
    "message": "Failed to create customer. Please try again."
}
```

#### Business Logic
1. Trim `customer_name` and `mobile_no`; normalize empty `email_id` to `None`.
2. If `customer_name` or `mobile_no` is empty, return 400.
3. `_find_existing_customer(mobile_no)`: looks up `Contact Phone` rows by exact `phone` match, resolves the owning Contacts to linked Customers via `Dynamic Link`, and returns the first match. If found, return 409 with the existing customer's `name`/`customer_name`.
4. Otherwise, in a try block:
   - `_create_customer`: inserts a new `Customer` with `customer_type="Individual"`.
   - `_create_primary_contact`: inserts a `Contact` with `first_name=customer_name`, `is_primary_contact=1`, a `phone_nos` row marked as primary phone/mobile, an `email_ids` row if `email_id` was given, and a `links` row pointing back to the new Customer. Then sets `customer.customer_primary_contact = contact.name` and saves the Customer again.
5. Any exception during creation triggers `frappe.db.rollback()`, logs to Error Log, and returns 500.
6. On success, returns 201 with both the new Customer and Contact summaries.

#### Database / DocTypes Used
- `Customer` (created)
- `Contact` (created, and updated back onto `Customer.customer_primary_contact`)
- `Contact Phone` (duplicate lookup)
- `Dynamic Link` (duplicate lookup)

#### Input Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `customer_name` | string | Yes | Non-empty after trim |
| `mobile_no` | string | Yes | Non-empty after trim; checked for existing duplicates |
| `email_id` | string | No | Added to the Contact's `email_ids` child table if present |

#### Response Fields

| Field | Type | Description |
|---|---|---|
| `success` | boolean | Whether creation succeeded |
| `message` | string | Human-readable result/error message |
| `customer.name` | string | New (or existing, on 409) Customer ID |
| `customer.customer_name` | string | Customer name |
| `customer.customer_type` | string | Always `"Individual"` for newly created customers |
| `contact.name` | string | New Contact ID |
| `contact.mobile_no` | string | Contact's mobile number |
| `contact.email_id` | string\|null | Contact's email, if provided |

#### Sequence Flow
1. Validate and normalize input.
2. Check for an existing Customer via the mobile number (Contact Phone → Dynamic Link).
3. If duplicate, return 409.
4. Create Customer document.
5. Create Contact document (phone, optional email, link to Customer).
6. Save Customer with `customer_primary_contact` set to the new Contact.
7. Return 201 with created records, or roll back and return 500 on any exception.

#### Functional Notes
- Used by the "Add New Customer" flow in the mobile Sales Rep app, typically invoked from within Sales Order creation when a customer isn't found by `get_customers`.

#### Technical Notes
- **HTTP Method:** POST (`methods=["POST"]`)
- **Python Function:** `luxury_api.api.customer.create_customer`
- **Transaction handling:** Explicit `frappe.db.rollback()` on any exception during the two-document creation; both `Customer` and `Contact` inserts happen inside the same try block so a failure partway through is rolled back together.
- **Error logging:** `frappe.log_error(title="luxury_api.customer.create_customer")` on unexpected exceptions.
- **HTTP status codes:** 400 (missing fields), 409 (duplicate), 500 (unexpected failure), 201 (success) — set explicitly via `frappe.local.response.http_status_code`.

---

## Item APIs

### get_items

#### Purpose
Paginated listing of sales items (`is_sales_item=1`) with optional item-group filter and text/barcode search, enriched with per-warehouse stock, selling price, barcodes, and resolved image URL.

#### Endpoint
```
GET {base_url}/api/method/luxury_api.api.item.get_items
```

#### Authentication
Login session required (`allow_guest=False`).

#### Request Headers
```http
Authorization: token <api_key>:<api_secret>
```

#### Request Payload / Query Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `item_group` | string | No | Must be an existing Item Group; filters results |
| `search` | string | No | Matches item code, item name, or a barcode |
| `page` | int | No (default `1`) | Page number, clamped to minimum 1 |
| `page_size` | int | No (default `20`) | Page size, clamped between 1 and 100 |

```json
{
  "item_group": "All Item Groups",
  "search": "",
  "page": 1,
  "page_size": 20
}
```

#### Sample cURL
```bash
curl --location '{base_url}/api/method/luxury_api.api.item.get_items?item_group=Watches&page=1&page_size=20' \
--header 'Authorization: token api_key:api_secret'
```

#### Success Response
```json
{
    "message": {
        "items": [
            {
                "item_code": "ITEM-001",
                "item_name": "Gold Watch",
                "item_group": "Watches",
                "description": "18k gold wristwatch",
                "stock_uom": "Nos",
                "disabled": 0,
                "image": "{base_url}/files/gold-watch.jpg",
                "selling_rate": 50000.0,
                "warehouse_stock": [
                    {"warehouse": "Stores - LS", "actual_qty": 5}
                ],
                "total_available_qty": 5,
                "attachments": ["{base_url}/files/gold-watch.jpg"],
                "barcodes": [
                    {"barcode": "8901234567890", "barcode_type": "EAN"}
                ]
            }
        ],
        "pagination": {
            "page": 1,
            "page_size": 20,
            "total_records": 1,
            "total_pages": 1,
            "has_next": false,
            "has_previous": false
        }
    }
}
```

#### Error Responses

Invalid Item Group (`frappe.DoesNotExistError`, HTTP 404):
```json
{
    "exc_type": "DoesNotExistError",
    "_server_messages": "[\"Item Group 'Nonexistent' does not exist.\"]"
}
```

#### Business Logic
1. If `item_group` given, `_validate_item_group` confirms it exists, else throws.
2. Clamp `page`/`page_size`.
3. Base filter: `is_sales_item=1`, plus `item_group` if given.
4. If `search` given, `_build_search_or_filters` matches `name`/`item_name` via `LIKE`, plus item codes resolved from `Item Barcode` where the barcode matches.
5. Counts total matches, then fetches the page of `Item` rows ordered by `item_name asc`.
6. For the page's item codes, batch-fetches in parallel-independent queries:
   - `_fetch_warehouse_stock`: raw SQL against `tabBin` grouped by item, returning a list of `{warehouse, actual_qty}` per item.
   - `_fetch_selling_prices`: `Item Price` filtered to the Selling Settings' default `selling_price_list` (fallback `"Standard Selling"`) and `selling=1`.
   - `_fetch_barcodes`: `Item Barcode` rows per item.
   - `_fetch_attachments`: `File` rows attached to each Item, URL-resolved via `get_url`.
7. `_build_item_payload` per item: resolves `image` as the Item's own `image` field (URL-resolved) if set, else falls back to the first attachment; computes `total_available_qty` as the sum of `actual_qty` across all warehouses.

#### Database / DocTypes Used
- `Item`
- `Item Group` (existence check)
- `Item Barcode`
- `Bin` (raw SQL, `tabBin`)
- `Item Price`
- `Selling Settings` (single, for default price list)
- `File` (attachments)

#### Input Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `item_group` | string | No | Validated Item Group name |
| `search` | string | No | Matches item code/name/barcode |
| `page` | int | No | Default 1 |
| `page_size` | int | No | Default 20, max 100 |

#### Response Fields

| Field | Type | Description |
|---|---|---|
| `items[].item_code` | string | Item name/ID |
| `items[].item_name` | string | Display name |
| `items[].item_group` | string | Item Group |
| `items[].description` | string | Item description |
| `items[].stock_uom` | string | Stock unit of measure |
| `items[].disabled` | int (0/1) | Disabled flag |
| `items[].image` | string\|null | Resolved absolute image URL |
| `items[].selling_rate` | float | Price from the default selling price list (0 if none) |
| `items[].warehouse_stock` | array\<object\> | `{warehouse, actual_qty}` per warehouse with a Bin row |
| `items[].total_available_qty` | number | Sum of `actual_qty` across all warehouses |
| `items[].attachments` | array\<string\> | All resolved File URLs attached to the item |
| `items[].barcodes` | array\<object\> | `{barcode, barcode_type}` |
| `pagination.*` | — | Same shape as `get_customers` |

#### Sequence Flow
1. Validate `item_group` if provided.
2. Clamp pagination.
3. Build filters/or_filters (including barcode-based search).
4. Count total, fetch page of `Item` rows.
5. Batch-fetch stock, price, barcodes, attachments for the page's item codes (4 queries, independent of page size).
6. Assemble per-item payload and return with pagination metadata.

#### Functional Notes
- Used by the POS/Sales Order item-picker screen: browsing by item group, searching by name or scanning a barcode, and displaying live stock/price/image.

#### Technical Notes
- **HTTP Method:** Unrestricted (`allow_guest=False`, no `methods=` — GET/POST both work; GET is conventional)
- **Python Function:** `luxury_api.api.item.get_items`
- **SQL:** One raw `frappe.db.sql` query against `tabBin` for stock (parameterized `IN %(codes)s` — safe from SQL injection).
- **Performance:** Detail queries (stock/price/barcode/attachment) are batched per page (4 queries total) rather than per item, regardless of `page_size`.
- **Pricing source:** Uses `Selling Settings.selling_price_list`, falling back to `"Standard Selling"` if not configured.
- **Sorting:** `item_name asc`.

---

## Item Price APIs

### get_item_prices

#### Purpose
Returns Item Price records for a branch or a specific Price List. Price Lists with no branch are common: their prices apply to all branches. When an item has both a branch price and a common price for the same UOM, the branch price wins. Pagination is optional.

#### Endpoint
```
GET {base_url}/api/method/luxury_api.api.item_price.get_item_prices
```

#### Authentication
Login session required (`allow_guest=False`).

#### Request Headers
```http
Authorization: token <api_key>:<api_secret>
```

#### Request Payload / Query Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `branch` | string | No | Existing Branch. Returns that branch's price lists plus common price lists |
| `price_list` | string | No | Existing Price List. Returns only this list; takes priority over `branch` |
| `item_code` | string | No | Exact item code filter |
| `search` | string | No | Matches item code or item name (`LIKE`) |
| `page` | int | No | Page number. If `page` or `page_size` is sent, the response is paginated |
| `page_size` | int | No | Page size (default `20` when paginating, max `500`) |

If neither `branch` nor `price_list` is sent, only common price lists are used.
If neither `page` nor `page_size` is sent, all matching rows are returned.

#### Sample cURL
```bash
# All prices for a branch (no pagination)
curl --location '{base_url}/api/method/luxury_api.api.item_price.get_item_prices?branch=Branch%20-%201' \
--header 'Authorization: token api_key:api_secret'

# Paginated
curl --location '{base_url}/api/method/luxury_api.api.item_price.get_item_prices?branch=Branch%20-%201&page=1&page_size=50' \
--header 'Authorization: token api_key:api_secret'

# Specific price list
curl --location '{base_url}/api/method/luxury_api.api.item_price.get_item_prices?price_list=Standard%20Selling' \
--header 'Authorization: token api_key:api_secret'
```

#### Success Response
```json
{
    "message": {
        "success": true,
        "branch_price_lists": ["Branch 1 Selling"],
        "common_price_lists": ["Common Selling"],
        "data": [
            {
                "name": "ITEM-PRICE-0001",
                "item_code": "ITEM-001",
                "item_name": "Gold Watch",
                "item_description": "18k gold wristwatch",
                "uom": "Nos",
                "price_list": "Branch 1 Selling",
                "price_list_rate": 48000.0,
                "currency": "INR",
                "selling": 1,
                "buying": 0,
                "valid_from": "2026-01-01",
                "valid_upto": null,
                "customer": null,
                "batch_no": null,
                "is_branch_price": true
            },
            {
                "name": "ITEM-PRICE-0002",
                "item_code": "ITEM-002",
                "item_name": "Silver Ring",
                "item_description": "Sterling silver ring",
                "uom": "Nos",
                "price_list": "Common Selling",
                "price_list_rate": 5000.0,
                "currency": "INR",
                "selling": 1,
                "buying": 0,
                "valid_from": "2026-01-01",
                "valid_upto": null,
                "customer": null,
                "batch_no": null,
                "is_branch_price": false
            }
        ],
        "message": null,
        "pagination": {
            "page": 1,
            "page_size": 50,
            "total_records": 2,
            "total_pages": 1,
            "has_next": false,
            "has_previous": false
        }
    }
}
```

`pagination` is present only when `page` or `page_size` is sent. When no rows match, `data` is `[]` and `message` is `"No item prices found."`.

#### Error Responses

Price List does not exist (`frappe.DoesNotExistError`, HTTP 404):
```json
{
    "exc_type": "DoesNotExistError",
    "_server_messages": "[\"Price List 'Nonexistent' does not exist.\"]"
}
```

Branch does not exist (`frappe.DoesNotExistError`, HTTP 404):
```json
{
    "exc_type": "DoesNotExistError",
    "_server_messages": "[\"Branch 'Nonexistent' does not exist.\"]"
}
```

No branch or common price list available (`frappe.DoesNotExistError`, HTTP 404):
```json
{
    "exc_type": "DoesNotExistError",
    "_server_messages": "[\"No Price List found for Branch 'Branch - 1'.\"]"
}
```

#### Business Logic
1. `_resolve_price_lists`:
   - If `price_list` is given, validate it exists and use only it.
   - Else fetch common price lists: enabled, `selling=1`, `branch` not set.
   - If `branch` is given, validate it exists and fetch its price lists: enabled, `selling=1`, `branch=<branch>`. Throw if neither branch nor common price lists exist.
2. `_fetch_item_prices`: fetch `Item Price` rows for all resolved price lists, with optional `item_code` and `search` filters, ordered by `item_code asc`.
3. `_prefer_branch_prices`: for each `(item_code, uom)` that has a branch price, drop the common price row. Mark each row with `is_branch_price`.
4. If `page` or `page_size` is sent, `_paginate` slices the result and adds pagination metadata.

#### Database / DocTypes Used
- `Price List` (custom field `branch`)
- `Branch` (existence check)
- `Item Price`

#### Input Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `branch` | string | No | Branch name |
| `price_list` | string | No | Price List name; overrides `branch` |
| `item_code` | string | No | Exact item code |
| `search` | string | No | Item code/name search |
| `page` | int | No | Enables pagination; default 1 |
| `page_size` | int | No | Enables pagination; default 20, max 500 |

#### Response Fields

| Field | Type | Description |
|---|---|---|
| `success` | bool | Always `true` on success |
| `branch_price_lists` | array\<string\> | Branch price lists used (or the requested `price_list`) |
| `common_price_lists` | array\<string\> | Common (no-branch) price lists used |
| `data[].name` | string | Item Price ID |
| `data[].item_code` | string | Item code |
| `data[].item_name` | string | Item name |
| `data[].item_description` | string | Item description |
| `data[].uom` | string | Unit of measure |
| `data[].price_list` | string | Price List the rate came from |
| `data[].price_list_rate` | float | Rate |
| `data[].currency` | string | Currency |
| `data[].selling` / `data[].buying` | int (0/1) | Price type flags |
| `data[].valid_from` / `data[].valid_upto` | date\|null | Validity period |
| `data[].customer` | string\|null | Customer-specific price |
| `data[].batch_no` | string\|null | Batch-specific price |
| `data[].is_branch_price` | bool | `true` if from a branch price list, `false` if from a common one |
| `message` | string\|null | `"No item prices found."` when `data` is empty |
| `pagination.*` | — | Same shape as `get_customers`; present only when paginating |

#### Sequence Flow
1. Resolve branch and common price lists.
2. Fetch matching Item Price rows.
3. Remove common prices that a branch price overrides.
4. Paginate if `page` or `page_size` is sent.
5. Return the response.

#### Functional Notes
- Used by POS to load prices for the current branch. Items without a branch price use the common price, so the same price applies across all branches.
- To make a price list common, leave its `branch` field empty.

#### Technical Notes
- **HTTP Method:** `GET` only (`methods=["GET"]`). Send parameters in the query string.
- **Python Function:** `luxury_api.api.item_price.get_item_prices`
- **Performance:** All matching rows are fetched before branch/common deduplication; pagination is applied in Python after that.
- **Sorting:** `item_code asc`.

---

## POS APIs

### get_pos_profile

#### Purpose
Returns one or more POS Profiles (by exact name or by branch) with resolved company address, configured payment modes (each with its default GL account for the profile's company), and the users the profile applies to.

#### Endpoint
```
GET {base_url}/api/method/luxury_api.api.pos.get_pos_profile
```

#### Authentication
Login session required (`allow_guest=False`).

#### Request Headers
```http
Authorization: token <api_key>:<api_secret>
```

#### Request Payload / Query Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `branch` | string | No | Filter POS Profiles by Branch |
| `pos_profile` | string | No | Look up one specific POS Profile by name (takes precedence over `branch`) |

If neither is given, all POS Profiles are returned.

```json
{
  "branch": "Main Branch"
}
```

#### Sample cURL
```bash
curl --location '{base_url}/api/method/luxury_api.api.pos.get_pos_profile?pos_profile=Main%20POS' \
--header 'Authorization: token api_key:api_secret'
```

#### Success Response
```json
{
    "message": {
        "success": true,
        "data": [
            {
                "pos_profile": "Main POS",
                "company": "Luxury Retail LLC",
                "company_address": {
                    "address_title": "Head Office",
                    "address_line1": "123 Main St",
                    "address_line2": null,
                    "city": "Dubai",
                    "state": "Dubai",
                    "country": "United Arab Emirates",
                    "pincode": "00000",
                    "phone": "+971500000000",
                    "email_id": "info@example.com",
                    "gstin": null
                },
                "branch": "Main Branch",
                "warehouse": "Stores - LS",
                "disabled": 0,
                "payments": [
                    {"mode_of_payment": "Cash", "default": 1, "account": "Cash - LS"},
                    {"mode_of_payment": "Card", "default": 0, "account": "Bank - LS"}
                ],
                "applicable_for_users": [
                    {"user": "sales.rep@example.com", "full_name": "Sales Rep", "email": "sales.rep@example.com"}
                ]
            }
        ]
    }
}
```

#### Error Responses

Named POS Profile not found (`frappe.DoesNotExistError`, HTTP 404):
```json
{
    "exc_type": "DoesNotExistError",
    "_server_messages": "[\"POS Profile 'Bad Name' does not exist.\"]"
}
```

No POS Profile found for a branch (HTTP 404):
```json
{
    "exc_type": "DoesNotExistError",
    "_server_messages": "[\"No POS Profile found for Branch 'Bad Branch'.\"]"
}
```

No POS Profiles exist at all (HTTP 404):
```json
{
    "exc_type": "DoesNotExistError",
    "_server_messages": "[\"No POS Profile found.\"]"
}
```

#### Business Logic
1. `_resolve_pos_profile_names(branch, pos_profile)`:
   - If `pos_profile` given: verify it exists, return `[pos_profile]` — ignores `branch` entirely.
   - Else if `branch` given: filter POS Profiles by `branch`.
   - Fetch matching names; throw a branch-specific or generic "not found" error if empty.
2. Fetch the `POS Profile` rows for the resolved names.
3. `_fetch_addresses`: batch-fetches `Address` rows for all distinct `company_address` values; conditionally includes `gstin` only if the `Address` doctype has that custom field (`frappe.get_meta("Address").has_field("gstin")`).
4. `_fetch_payments`: batch-fetches `POS Payment Method` rows for all profiles, then resolves each mode's default account via `Mode of Payment Account` keyed by `(mode_of_payment, company)`.
5. `_fetch_applicable_users`: batch-fetches `POS Profile User` rows, then batch-fetches `User` details (`full_name`, `email`) for all distinct users.
6. `_build_pos_profile_payload` assembles each profile's payload; strips the `name` key out of the embedded `company_address` dict.

#### Database / DocTypes Used
- `POS Profile`
- `Address`
- `POS Payment Method`
- `Mode of Payment Account`
- `POS Profile User`
- `User`

#### Input Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `branch` | string | No | Filters by Branch; ignored if `pos_profile` given |
| `pos_profile` | string | No | Exact POS Profile name; validated to exist |

#### Response Fields

| Field | Type | Description |
|---|---|---|
| `data[].pos_profile` | string | POS Profile name |
| `data[].company` | string | Company |
| `data[].company_address` | object\|null | Address fields (minus `name`); includes `gstin` only if the field exists on the site |
| `data[].branch` | string | Branch |
| `data[].warehouse` | string | Default warehouse |
| `data[].disabled` | int (0/1) | Disabled flag |
| `data[].payments[].mode_of_payment` | string | Payment mode name |
| `data[].payments[].default` | int (0/1) | Whether this is the profile's default mode |
| `data[].payments[].account` | string\|null | Default GL account for this mode + company |
| `data[].applicable_for_users[].user` | string | User ID |
| `data[].applicable_for_users[].full_name` | string | Display name |
| `data[].applicable_for_users[].email` | string | Email |

#### Sequence Flow
1. Resolve the set of POS Profile names to return (by exact name, by branch, or all).
2. Fetch base `POS Profile` rows.
3. Batch-fetch addresses, payment methods + accounts, and applicable users.
4. Assemble and return the payload array.

#### Functional Notes
- Used at app startup / POS-profile selection to bootstrap the POS screen with company info, accepted payment modes, and to confirm the current user is authorized for a given profile before allowing a POS Opening Entry.

#### Technical Notes
- **HTTP Method:** GET (`methods=["GET"]`)
- **Python Function:** `luxury_api.api.pos.get_pos_profile`
- **Performance:** 3 batched detail queries regardless of how many profiles are returned (addresses, payments+accounts, users), no per-profile queries.
- **Schema flexibility:** Conditionally includes `gstin` based on `frappe.get_meta` — tolerates sites without that custom field instead of failing.

---

## POS Opening APIs

### create_pos_opening_entry

#### Purpose
Creates and submits a POS Opening Entry, recording the opening cash/payment-mode balances for a user starting a POS shift against a given POS Profile.

#### Endpoint
```
POST {base_url}/api/method/luxury_api.api.pos_opening.create_pos_opening_entry
```

#### Authentication
Login session required (no `allow_guest` override; default `False`).

#### Request Headers
```http
Content-Type: application/json
Authorization: token <api_key>:<api_secret>
```

#### Request Payload

| Parameter | Type | Required | Description |
|---|---|---|---|
| `pos_profile` | string | Yes | Must exist; the user must be assigned to it |
| `user` | string | Yes | Must be listed in the POS Profile's applicable users |
| `company` | string | Yes | Company for the opening entry |
| `period_start_date` | string (datetime) | No | Defaults to `frappe.utils.now()` if omitted |
| `balance_details` | array\<object\> or JSON string | Yes (at least one entry) | Opening balance per payment mode |

```json
{
  "pos_profile": "Main POS",
  "user": "sales.rep@example.com",
  "company": "Luxury Retail LLC",
  "period_start_date": "2026-07-03 09:00:00",
  "balance_details": [
    {"mode_of_payment": "Cash", "opening_amount": 1000.0}
  ]
}
```

Note: `balance_details` may be sent as an actual JSON array or as a JSON-encoded string; the endpoint parses strings via `frappe.parse_json`.

#### Sample cURL
```bash
curl --location '{base_url}/api/method/luxury_api.api.pos_opening.create_pos_opening_entry' \
--header 'Authorization: token api_key:api_secret' \
--header 'Content-Type: application/json' \
--data '{
    "pos_profile": "Main POS",
    "user": "sales.rep@example.com",
    "company": "Luxury Retail LLC",
    "balance_details": [{"mode_of_payment": "Cash", "opening_amount": 1000.0}]
}'
```

#### Success Response (HTTP 201)
```json
{
    "message": {
        "success": true,
        "message": "POS Opening Entry created successfully.",
        "pos_opening_entry": {
            "name": "POS-OPEN-0001",
            "pos_profile": "Main POS",
            "user": "sales.rep@example.com",
            "company": "Luxury Retail LLC",
            "status": "Open",
            "period_start_date": "2026-07-03 09:00:00"
        }
    }
}
```

#### Error Responses

Missing mandatory fields (HTTP 400):
```json
{
    "success": false,
    "message": "POS Profile, User, Company and Balance Details (with at least one payment mode) are mandatory."
}
```

POS Profile doesn't exist (HTTP 404):
```json
{
    "success": false,
    "message": "POS Profile 'Bad Profile' does not exist."
}
```

User not assigned to the profile (HTTP 400):
```json
{
    "success": false,
    "message": "User 'other.user@example.com' is not assigned to POS Profile 'Main POS'."
}
```

Validation failure during creation, e.g. an already-open entry for the same user/profile per ERPNext's own validation (HTTP 409):
```json
{
    "success": false,
    "message": "<ERPNext validation message text>"
}
```

Unexpected failure (HTTP 500), rolled back and logged (`title="luxury_api.pos_opening.create_pos_opening_entry"`):
```json
{
    "success": false,
    "message": "Failed to create POS Opening Entry. Please try again."
}
```

#### Business Logic
1. Trim `pos_profile`, `user`, `company`; parse `balance_details` (accepts a JSON string or a native list; defaults to `[]`).
2. Validate all four are present and `balance_details` is non-empty — else 400.
3. Validate `pos_profile` exists — else 404.
4. Validate the `user` is assigned to that `pos_profile` via a `POS Profile User` row (`_is_user_assigned_to_profile`) — else 400.
5. `_create_opening_entry`: builds a `POS Opening Entry` document with `period_start_date` defaulting to `frappe.utils.now()` if not supplied, and the given `balance_details` as the child table; inserts, then **submits** it immediately (an Opening Entry is a submittable doctype — a draft has no effect, submission activates the shift).
6. On `frappe.ValidationError` (e.g. ERPNext's own business-rule checks, such as one active opening entry per user/profile), roll back and return 409.
7. On any other exception, roll back, log to Error Log, and return 500.

#### Database / DocTypes Used
- `POS Profile` (existence check)
- `POS Profile User` (assignment check)
- `POS Opening Entry` (created and submitted)

#### Input Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `pos_profile` | string | Yes | Existing POS Profile |
| `user` | string | Yes | Must be assigned to the profile |
| `company` | string | Yes | Company |
| `period_start_date` | string | No | Defaults to now |
| `balance_details` | array/JSON string | Yes | At least one payment-mode balance row |

#### Response Fields

| Field | Type | Description |
|---|---|---|
| `success` | boolean | Result flag |
| `message` | string | Human-readable status/error |
| `pos_opening_entry.name` | string | New POS Opening Entry ID |
| `pos_opening_entry.pos_profile` | string | POS Profile |
| `pos_opening_entry.user` | string | User |
| `pos_opening_entry.company` | string | Company |
| `pos_opening_entry.status` | string | Document status after submit (`Open`) |
| `pos_opening_entry.period_start_date` | string | Shift start timestamp |

#### Sequence Flow
1. Normalize and validate input presence.
2. Validate POS Profile exists.
3. Validate user-profile assignment.
4. Build, insert, and submit the POS Opening Entry.
5. Return 201 with the created entry summary, or the appropriate error/rollback response.

#### Functional Notes
- Used when a Sales Rep/cashier starts their POS shift — must succeed before `create_pos_closing_entry` or any POS sale can reference this shift.

#### Technical Notes
- **HTTP Method:** POST (`methods=["POST"]`)
- **Python Function:** `luxury_api.api.pos_opening.create_pos_opening_entry`
- **Document lifecycle:** Inserts *and submits* in the same call (submittable doctype) — not left as a draft.
- **Transaction handling:** `frappe.db.rollback()` on both `ValidationError` and generic exceptions; distinguishes business-rule failures (409) from unexpected errors (500).
- **Error logging:** Only unexpected exceptions are logged via `frappe.log_error`; `ValidationError` messages are surfaced directly to the caller instead.

---

## POS Closing APIs

### create_pos_closing_entry

#### Purpose
Closes an open POS shift: builds a POS Closing Entry from the referenced POS Opening Entry (via ERPNext's own `make_closing_entry_from_opening`), defaults every payment mode's closing amount to its system-expected amount (zero variance), and saves it as a draft.

#### Endpoint
```
POST {base_url}/api/method/luxury_api.api.pos_closing.create_pos_closing_entry
```

#### Authentication
Login session required (no `allow_guest` override; default `False`).

#### Request Headers
```http
Content-Type: application/json
Authorization: token <api_key>:<api_secret>
```

#### Request Payload

| Parameter | Type | Required | Description |
|---|---|---|---|
| `pos_opening_entry` | string | Yes | Name of an existing, `Open` status POS Opening Entry |

```json
{
  "pos_opening_entry": "POS-OPEN-0001"
}
```

#### Sample cURL
```bash
curl --location '{base_url}/api/method/luxury_api.api.pos_closing.create_pos_closing_entry' \
--header 'Authorization: token api_key:api_secret' \
--header 'Content-Type: application/json' \
--data '{
    "pos_opening_entry": "POS-OPEN-0001"
}'
```

#### Success Response (HTTP 201)
```json
{
    "message": {
        "success": true,
        "message": "POS Closing Entry created successfully.",
        "pos_closing_entry": {
            "name": "POS-CLOSING-0001",
            "pos_opening_entry": "POS-OPEN-0001",
            "pos_profile": "Main POS",
            "user": "sales.rep@example.com",
            "period_start_date": "2026-07-03 09:00:00",
            "period_end_date": "2026-07-03 18:00:00",
            "docstatus": 0,
            "payment_reconciliation": [
                {
                    "mode_of_payment": "Cash",
                    "opening_amount": 1000.0,
                    "expected_amount": 4500.0,
                    "closing_amount": 4500.0,
                    "difference": 0
                }
            ]
        }
    }
}
```
*(`pos_closing_entry` is the full `as_dict()` of the created document — exact field set depends on the installed ERPNext version's `POS Closing Entry` schema.)*

#### Error Responses

Missing `pos_opening_entry` (HTTP 400):
```json
{
    "success": false,
    "message": "POS Opening Entry is mandatory."
}
```

Opening Entry doesn't exist (HTTP 404):
```json
{
    "success": false,
    "message": "POS Opening Entry 'Bad Name' does not exist."
}
```

Already closed (HTTP 409):
```json
{
    "success": false,
    "message": "POS Opening Entry 'POS-OPEN-0001' is already closed."
}
```

Not in `Open` status, e.g. cancelled (HTTP 400):
```json
{
    "success": false,
    "message": "POS Opening Entry 'POS-OPEN-0001' must be Open to be closed."
}
```

Validation failure while building/inserting the closing entry (HTTP 400):
```json
{
    "success": false,
    "message": "<ERPNext validation message text>"
}
```

Unexpected failure (HTTP 500), rolled back and logged (`title="luxury_api.pos_closing.create_pos_closing_entry"`):
```json
{
    "success": false,
    "message": "Failed to create POS Closing Entry. Please try again."
}
```

#### Business Logic
1. Trim `pos_opening_entry`; require non-empty — else 400.
2. Verify it exists — else 404.
3. Read its `status`:
   - `"Closed"` → 409 (already closed).
   - Anything other than `"Open"` (e.g. `"Cancelled"`, draft) → 400.
4. Load the full `POS Opening Entry` document and call ERPNext's `make_closing_entry_from_opening(opening_entry)` to construct a `POS Closing Entry` pre-populated with expected amounts per payment mode (calculated by ERPNext from the shift's actual transactions).
5. `_apply_default_closing_amounts`: for every row in `payment_reconciliation`, sets `closing_amount = expected_amount` and `difference = 0` — i.e. assumes a perfect reconciliation with no cash variance unless the caller adjusts it afterward.
6. Inserts the closing entry as a **draft** (`docstatus=0`) — it is not submitted by this endpoint.
7. On `ValidationError`, roll back and return 400 with the message. On any other exception, roll back, log, and return 500.

#### Database / DocTypes Used
- `POS Opening Entry` (read)
- `POS Closing Entry` (created, via ERPNext's `make_closing_entry_from_opening`)

#### Input Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `pos_opening_entry` | string | Yes | Must exist and currently be `Open` |

#### Response Fields

| Field | Type | Description |
|---|---|---|
| `success` | boolean | Result flag |
| `message` | string | Human-readable status/error |
| `pos_closing_entry` | object | Full document dict of the newly created (draft) POS Closing Entry, including `payment_reconciliation` rows with `closing_amount` pre-filled to `expected_amount` and `difference=0` |

#### Sequence Flow
1. Validate input presence.
2. Validate the Opening Entry exists and its status.
3. Build the Closing Entry from the Opening Entry via ERPNext core logic.
4. Zero out variance by defaulting `closing_amount` to `expected_amount` on every payment row.
5. Insert as draft.
6. Return 201 with the full document, or the appropriate error/rollback response.

#### Functional Notes
- Used when a Sales Rep/cashier ends their POS shift. The returned draft is expected to be reviewed/adjusted (actual counted cash vs. expected) and submitted separately — this endpoint does not submit it.

#### Technical Notes
- **HTTP Method:** POST (`methods=["POST"]`)
- **Python Function:** `luxury_api.api.pos_closing.create_pos_closing_entry`
- **Delegation:** Reuses ERPNext's own `erpnext.accounts.doctype.pos_closing_entry.pos_closing_entry.make_closing_entry_from_opening` rather than re-implementing expected-amount calculation.
- **Document lifecycle:** Insert-only (draft, `docstatus=0`) — submission is a separate step not exposed here.
- **Transaction handling:** `frappe.db.rollback()` on both `ValidationError` (→ 400) and generic exceptions (→ 500, logged).

---

## Credit Sales

Credit sales are controlled by the **Channel** of the sale. Channel is an Accounting Dimension, so Sales Invoice and GL Entry carry a `channel` field.

### Setup

| Where | Setting | Value |
|---|---|---|
| Channel | Allow Credit Sales (`allow_credit`) | Check for non-POS channels (for example Wholesale). Keep unchecked for the POS counter. |
| POS Profile | Allow Partial Payment | Check on every POS Profile used for credit sales. |
| Customer | Credit Limit (per company) | Optional. ERPNext blocks the invoice on submit if the limit is exceeded. |

---

### Credit option on create_sales_invoice

#### Endpoint
```
POST {base_url}/api/method/luxury_api.api.sales_invoice_pos.create_sales_invoice
```

#### New Parameter

| Parameter | Type | Required | Description |
|---|---|---|---|
| `channel` | string | No | Existing Channel. Stored on the invoice (accounting dimension). |

#### Behavior

| Channel | Payments | Result |
|---|---|---|
| None, or `allow_credit = 0` | Must have at least one row with `amount > 0` | Unchanged: if the paid total is less than the grand total, the first payment row is raised to the grand total (paid in full). |
| `allow_credit = 1` | Optional. Rows may have `amount = 0` | The invoice is submitted with what was paid; the rest stays as `outstanding_amount`. If `payments` is empty, the POS Profile's default mode of payment is added with amount `0`. |

Credit validations (HTTP 400 unless noted):
- Channel does not exist → 404 (`DoesNotExistError`).
- Customer is the POS Profile's default (walk-in) customer.
- POS Profile does not have **Allow Partial Payment** enabled.
- Total payment is more than the invoice total.
- Customer credit limit exceeded (ERPNext validation on submit).

#### Sample cURL (full credit)
```bash
curl --location '{base_url}/api/method/luxury_api.api.sales_invoice_pos.create_sales_invoice' \
--header 'Authorization: token api_key:api_secret' \
--header 'Content-Type: application/json' \
--data '{
    "customer": "CUST-0001",
    "company": "Luxury Pvt Ltd",
    "pos_profile": "Branch 1 POS",
    "channel": "Wholesale",
    "items": [{"item_code": "ITEM-001", "qty": 1}],
    "payments": []
}'
```

#### Sample cURL (partial payment)
```bash
--data '{
    "customer": "CUST-0001",
    "company": "Luxury Pvt Ltd",
    "pos_profile": "Branch 1 POS",
    "channel": "Wholesale",
    "items": [{"item_code": "ITEM-001", "qty": 1}],
    "payments": [{"mode_of_payment": "Cash", "amount": 10000}]
}'
```

The response `data` is the full Sales Invoice; read `paid_amount` and `outstanding_amount` from it.

`list_sales_invoices` also accepts a `channel` filter and returns `channel` and `outstanding_amount` for each row. Use it to see unpaid invoices. Collect the remaining amount in ERPNext with a Payment Entry against the invoice.

---

## Sales Person Commission

Full POS integration guide: [`COMMISSION_API.md`](COMMISSION_API.md).

Commission is always a **fixed amount** sent by the POS for one **Sales Person**. It is stored in the standard ERPNext **Sales Team** table of the Sales Invoice (one row, 100% allocated):

- `sales_team[0].sales_person` = the `sales_person` sent by the POS.
- `sales_team[0].allocated_amount` = `amount_eligible_for_commission` = sum of `base_net_amount` of items whose Item has **Grant Commission** checked (ERPNext).
- `sales_team[0].incentives` = the `commission_amount` sent by the POS (set by a `validate` hook in this app, after ERPNext's own calculation).

The header fields `sales_partner` and `total_commission` are not used. ERPNext's **Sales Person Commission Summary** report shows the same amounts.

### Setup

| Where | Setting | Value |
|---|---|---|
| Sales Person | Create one record per sales person | Must be enabled and not a group. The commission rate on the master is not used. The POS always sends the amount. |
| Item | Grant Commission (`grant_commission`) | Checked by default. Uncheck for items that earn no commission. |
| POS Profile | Commission Expense Account (`commission_expense_account`) | Expense ledger debited when commission is paid on the spot. Must belong to the POS Profile company. |
| POS Profile | Auto Cancel Commission Payment (`auto_cancel_commission_payment`) | `Yes` (default): cancelling an invoice also cancels its commission payment. `No`: the POS must say what to do (see Cancel below). |
| POS Profile | Auto Recover Commission on Return (`auto_recover_commission_on_return`) | `Yes` (default): a return records the sales person giving back the returned share in cash. `No`: the POS must say what to do (see Returns below). |
| POS Profile | Payment methods | Must include a Mode of Payment of type **Cash** with a default account for the company. Commission is always paid from the first Cash mode in the list. |

Run `bench --site <site> migrate` once to create the custom fields on POS Profile and Sales Invoice.

---

### Commission option on create_sales_invoice

#### Endpoint
```
POST {base_url}/api/method/luxury_api.api.sales_invoice_pos.create_sales_invoice
```

#### New Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `sales_person` | string | No | Existing Sales Person name. Leave out (or send `""`) for no commission. |
| `commission_amount` | number | Yes, if `sales_person` is given | Fixed commission amount, in company currency. Must be more than 0 and not more than `amount_eligible_for_commission`. |
| `commission_paid` | 0/1 | No | Default `1`: the commission is paid to the sales person now and a Journal Entry is made. Send `0` to only record the commission. |

Validations:
- `commission_amount` given without `sales_person` → 417.
- `sales_person` does not exist → 404 (`DoesNotExistError`).
- `sales_person` disabled or a group → 417.
- `commission_amount` missing, not a number or `<= 0` → 417.
- Commission Expense Account or Cash mode setup missing on the POS Profile → 417.
- No item eligible for commission (Grant Commission off on all items) → 400.
- `commission_amount` more than `amount_eligible_for_commission` → 400.

#### Sample cURL
```bash
curl --location '{base_url}/api/method/luxury_api.api.sales_invoice_pos.create_sales_invoice' \
--header 'Authorization: token api_key:api_secret' \
--header 'Content-Type: application/json' \
--data '{
    "customer": "CUST-0001",
    "company": "Luxury Pvt Ltd",
    "pos_profile": "Branch 1 POS",
    "items": [{"item_code": "ITEM-001", "qty": 1}],
    "payments": [{"mode_of_payment": "Cash", "amount": 10000}],
    "sales_person": "Ahmed",
    "commission_amount": 500
}'
```

The response `data` is the full Sales Invoice. Read `sales_team[0].sales_person` and `sales_team[0].incentives` from it.

#### Commission payment (Journal Entry)

When `commission_paid = 1`, the API submits a Journal Entry in the same transaction as the invoice:

| Account | Debit | Credit |
|---|---|---|
| POS Profile `commission_expense_account` | `commission_amount` | |
| Default account of the POS Profile's Cash mode | | `commission_amount` |

- Commission is always paid in cash. Voucher type is `Cash Entry`. The cash mode used is saved in `commission_mode_of_payment`.
- Cost center is the POS Profile cost center. Accounting dimensions (for example `channel`) are copied from the invoice.
- The invoice stores `commission_paid`, `commission_mode_of_payment` and `commission_journal_entry`.
- If the JE fails, the invoice is not created either. Setup errors (no expense account, no Cash mode, Cash mode without account) are returned before anything is created.

#### Cancel

`cancel_sales_invoice` takes an optional `keep_commission_payment` (0/1).

| POS Profile "Auto Cancel Commission Payment" | `keep_commission_payment` | Result |
|---|---|---|
| Yes | not sent | Invoice and commission JE are cancelled. |
| Yes or No | `0` | Invoice and commission JE are cancelled (sales person returned the money). |
| Yes or No | `1` | Invoice is cancelled. The commission JE stays (sales person keeps the money). |
| No | not sent | **HTTP 409**, nothing is cancelled. Response has `"requires_commission_decision": true` and `data.commission_journal_entry`, `data.sales_person`, `data.commission_amount`. The POS asks the cashier and calls again with `0` or `1`. |

The success response `data` has `commission_journal_entry` and `commission_payment_cancelled`.

A cancel from Desk follows the POS Profile setting: `Yes` cancels the JE, `No` keeps it and shows a message. The JE cannot be cancelled alone while its invoice is submitted.

#### POS closing

`create_pos_closing_entry` lowers the expected amount of each mode of payment by the commission paid from it during the shift (submitted commission JEs of this POS Profile's invoices, including cancelled invoices whose commission was kept). The response has a new top-level `commission_paid` (total for the shift).

#### Returns

`create_sales_invoice_return` and `create_partial_sales_return` copy the Sales Team row to the return invoice. The return row gets negative `incentives` = the same share of the original commission as the share of the eligible value returned (example: 4,000 of 10,000 returned, 500 commission → −200). All returns together can never exceed the original commission. Earned commission goes down by that amount.

If commission was paid on the original invoice, both endpoints take an optional `recover_commission` (0/1):

| POS Profile "Auto Recover Commission on Return" | `recover_commission` | Result |
|---|---|---|
| Yes | not sent | Return is created and a recovery Cash Entry is submitted. |
| Yes or No | `1` | Return is created and a recovery Cash Entry is submitted (sales person gives the share back). |
| Yes or No | `0` | Return is created. No recovery (sales person keeps the share). |
| No | not sent | **HTTP 409**, nothing is created. Response has `"requires_commission_decision": true`. The POS asks the cashier and calls again with `0` or `1`. |

Recovery Cash Entry (example: 10,000 sale, 500 commission paid; 4,000 returned → 200):

| Account | Debit | Credit |
|---|---|---|
| Cash (same account as the original payment) | 200 | |
| Commission Expense (same account as the original payment) | | 200 |

- The JE is made in the same transaction as the return. If it fails, the return is not created either.
- The return invoice stores `commission_journal_entry` and `commission_mode_of_payment`. `create_partial_sales_return` also returns `sales_person`, `commission_amount` and `commission_journal_entry`.
- POS closing adds the recovered cash back to the expected amount of the shift in which the return is posted.
- `get_commission_summary`: `commission_paid` goes down by the recovered amount.
- Cancelling a return that has a recovery JE follows the "Auto Cancel Commission Payment" rules above.
- No commission paid on the original → nothing changes; `recover_commission` is ignored.

`list_sales_invoices` also accepts a `sales_person` filter and returns `sales_person`, `commission_amount`, `commission_paid` and `commission_journal_entry` for each row.

---

### list_sales_persons

#### Endpoint
```
GET {base_url}/api/method/luxury_api.api.sales_person.list_sales_persons
```

Returns enabled, non-group Sales Persons the user can read. Use it to fill the sales person list in the POS.

#### Success Response
```json
{
    "message": {
        "success": true,
        "count": 1,
        "data": [
            {"name": "Ahmed", "sales_person_name": "Ahmed", "employee": "HR-EMP-00001", "department": "Sales - LS"}
        ]
    }
}
```

---

### get_commission_summary

#### Endpoint
```
GET {base_url}/api/method/luxury_api.api.sales_person.get_commission_summary
```

Net commission per Sales Person from submitted POS Sales Invoices (`is_pos = 1`, `is_created_using_pos = 1`). Return invoices are included, so totals are net of returns.

#### Query Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `from_date` | string (YYYY-MM-DD) | No | Posting date from |
| `to_date` | string (YYYY-MM-DD) | No | Posting date to |
| `company` | string | No | Company |
| `sales_person` | string | No | One Sales Person |
| `pos_profile` | string | No | One POS Profile |
| `channel` | string | No | Channel |
| `branch` | string | No | Branch. Matches the POS Profiles with this `branch`. 404 if none. |

#### Sample cURL
```bash
curl --location '{base_url}/api/method/luxury_api.api.sales_person.get_commission_summary?from_date=2026-11-01&to_date=2026-11-30&branch=Branch%201' \
--header 'Authorization: token api_key:api_secret'
```

#### Success Response
```json
{
    "message": {
        "success": true,
        "filters": {"from_date": "2026-11-01", "to_date": "2026-11-30", "branch": "Branch 1"},
        "data": [
            {"sales_person": "Ahmed", "invoice_count": 3, "net_total": 25000.0, "amount_eligible_for_commission": 25000.0, "total_commission": 1250.0, "commission_paid": 1250.0}
        ],
        "totals": {"invoice_count": 3, "net_total": 25000.0, "amount_eligible_for_commission": 25000.0, "total_commission": 1250.0, "commission_paid": 1250.0}
    }
}
```

`invoice_count` includes return invoices.

- `total_commission`: commission earned (Sales Team `incentives`), net of returns (submitted invoices only).
- `commission_paid`: net cash paid to the sales person (payouts minus recoveries, submitted JEs only), including cancelled invoices whose commission was kept. It is higher than `total_commission` only when a return or cancel let the sales person keep the share.

#### Error Responses

| Scenario | HTTP Status |
|---|---|
| Invalid date format | 400 |
| No POS Profile for the branch | 404 |
| No read permission on Sales Invoice | 403 |
| Unexpected error (logged to Error Log) | 500 |

---

## Error Reference

| Scenario | HTTP Status | Response Shape |
|---|---|---|
| Invalid login credentials | 401 | `frappe.AuthenticationError` exception payload |
| Role does not exist (`get_users`) | 404 | `frappe.DoesNotExistError` exception payload |
| Item Group does not exist (`get_items`) | 404 | `frappe.DoesNotExistError` exception payload |
| Price List / Branch does not exist, or no price list for branch (`get_item_prices`) | 404 | `frappe.DoesNotExistError` exception payload |
| POS Profile not found / no profile for branch / none exist (`get_pos_profile`) | 404 | `frappe.DoesNotExistError` exception payload |
| Missing mandatory fields (`create_customer`, `create_pos_opening_entry`, `create_pos_closing_entry`) | 400 | `{"success": false, "message": "..."}` |
| Duplicate customer mobile number (`create_customer`) | 409 | `{"success": false, "message": "...", "customer": {...}}` |
| User not assigned to POS Profile (`create_pos_opening_entry`) | 400 | `{"success": false, "message": "..."}` |
| POS Opening Entry already closed (`create_pos_closing_entry`) | 409 | `{"success": false, "message": "..."}` |
| POS Opening Entry not Open (`create_pos_closing_entry`) | 400 | `{"success": false, "message": "..."}` |
| Business-rule validation failure (`create_pos_opening_entry`, `create_pos_closing_entry`) | 400/409 | `{"success": false, "message": "<ERPNext validation text>"}` |
| Unexpected server error (any `create_*` endpoint) | 500 | `{"success": false, "message": "Failed to ... Please try again."}` — logged to Error Log |

Frappe's default exception payload shape (for uncaught `frappe.throw`/core exceptions) looks like:
```json
{
    "exc_type": "DoesNotExistError",
    "_server_messages": "[\"<message>\"]"
}
```

---

## API Summary Table

| API | Method | Path | Auth | Creates/Modifies Data |
|---|---|---|---|---|
| `login` | POST | `luxury_api.api.auth.login` | Guest | Session only (no DocType writes) |
| `get_users` | GET | `luxury_api.api.user.get_users` | Session | No |
| `get_customers` | GET | `luxury_api.api.customer.get_customers` | Session | No |
| `create_customer` | POST | `luxury_api.api.customer.create_customer` | Session | Creates `Customer`, `Contact` |
| `get_items` | GET | `luxury_api.api.item.get_items` | Session | No |
| `get_item_prices` | GET | `luxury_api.api.item_price.get_item_prices` | Session | No |
| `get_pos_profile` | GET | `luxury_api.api.pos.get_pos_profile` | Session | No |
| `create_pos_opening_entry` | POST | `luxury_api.api.pos_opening.create_pos_opening_entry` | Session | Creates & submits `POS Opening Entry` |
| `create_pos_closing_entry` | POST | `luxury_api.api.pos_closing.create_pos_closing_entry` | Session | Creates draft `POS Closing Entry` |
| `list_sales_persons` | GET | `luxury_api.api.sales_person.list_sales_persons` | Session | No |
| `get_commission_summary` | GET | `luxury_api.api.sales_person.get_commission_summary` | Session | No |
