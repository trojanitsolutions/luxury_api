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
6. [POS APIs](#pos-apis)
   - [get_pos_profile](#get_pos_profile)
7. [POS Opening APIs](#pos-opening-apis)
   - [create_pos_opening_entry](#create_pos_opening_entry)
8. [POS Closing APIs](#pos-closing-apis)
   - [create_pos_closing_entry](#create_pos_closing_entry)
9. [Error Reference](#error-reference)
10. [API Summary Table](#api-summary-table)

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

### POS APIs (`api/pos.py`)
Read-only lookup of one or more POS Profiles (by name or branch) with resolved company address, configured payment modes (with default GL account), and the list of users the profile applies to.

### POS Opening APIs (`api/pos_opening.py`)
Creates and submits a POS Opening Entry (opening cash/payment-mode balances) for a user against a POS Profile.

### POS Closing APIs (`api/pos_closing.py`)
Creates a POS Closing Entry from an open POS Opening Entry, defaulting each payment mode's closing amount to its system-expected amount (zero difference).

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

## Error Reference

| Scenario | HTTP Status | Response Shape |
|---|---|---|
| Invalid login credentials | 401 | `frappe.AuthenticationError` exception payload |
| Role does not exist (`get_users`) | 404 | `frappe.DoesNotExistError` exception payload |
| Item Group does not exist (`get_items`) | 404 | `frappe.DoesNotExistError` exception payload |
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
| `get_pos_profile` | GET | `luxury_api.api.pos.get_pos_profile` | Session | No |
| `create_pos_opening_entry` | POST | `luxury_api.api.pos_opening.create_pos_opening_entry` | Session | Creates & submits `POS Opening Entry` |
| `create_pos_closing_entry` | POST | `luxury_api.api.pos_closing.create_pos_closing_entry` | Session | Creates draft `POS Closing Entry` |
