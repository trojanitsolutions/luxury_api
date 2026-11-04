# Item Price API

Returns Item Price records for a branch or a specific Price List.

---

## Base URL

```
{base_url} = https://your-site.example.com
```

Replace `{base_url}` with your site URL. Do not hardcode a domain in client code.

All endpoints in this app use this format:

```
{METHOD} {base_url}/api/method/luxury_api.api.<module>.<function>
```

---

## Endpoint

```
GET {base_url}/api/method/luxury_api.api.item_price.get_item_prices
```

| Property | Value |
|---|---|
| HTTP method | `GET` only |
| Python function | `luxury_api.api.item_price.get_item_prices` |
| Guest access | No (`allow_guest=False`) |
| Parameters | Query string |

---

## Authentication

You must send one of these:

**Option 1 — API key and secret (recommended for integrations)**

```http
Authorization: token <api_key>:<api_secret>
```

**Option 2 — Session cookie**

Log in first. The response sets the `sid` cookie. Send that cookie with each request.

```bash
curl --location '{base_url}/api/method/luxury_api.api.auth.login' \
--header 'Content-Type: application/json' \
--cookie-jar cookies.txt \
--data '{"usr": "user@example.com", "pwd": "your-password"}'
```

---

## Query Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `branch` | string | No | — | Existing Branch name. Returns the branch price lists and the common price lists. |
| `price_list` | string | No | — | Existing Price List name. Returns only this list. Takes priority over `branch`. |
| `item_code` | string | No | — | Exact item code filter. |
| `search` | string | No | — | Partial match on item code or item name (`LIKE %search%`). |
| `page` | int | No | `1` | Page number. Sending `page` or `page_size` turns on pagination. |
| `page_size` | int | No | `20` | Rows per page. Minimum `1`, maximum `500`. |

### Rules

- If you send `price_list`, the API ignores `branch`.
- If you send neither `branch` nor `price_list`, the API uses only the common price lists.
- A common price list is an enabled selling Price List with an empty `branch` field. Its prices apply to all branches.
- If an item has a branch price and a common price for the same UOM, the API returns only the branch price.
- If you send neither `page` nor `page_size`, the API returns all matching rows and no `pagination` object.
- Rows are sorted by `item_code` ascending.

---

## Examples

### 1. All prices for a branch

```bash
curl --location '{base_url}/api/method/luxury_api.api.item_price.get_item_prices?branch=Branch%20-%201' \
--header 'Authorization: token api_key:api_secret'
```

### 2. Branch prices with pagination

```bash
curl --location '{base_url}/api/method/luxury_api.api.item_price.get_item_prices?branch=Branch%20-%201&page=1&page_size=50' \
--header 'Authorization: token api_key:api_secret'
```

### 3. One Price List only

```bash
curl --location '{base_url}/api/method/luxury_api.api.item_price.get_item_prices?price_list=Standard%20Selling' \
--header 'Authorization: token api_key:api_secret'
```

### 4. Price of one item in a branch

```bash
curl --location '{base_url}/api/method/luxury_api.api.item_price.get_item_prices?branch=Branch%20-%201&item_code=ITEM-001' \
--header 'Authorization: token api_key:api_secret'
```

### 5. Search by item code or name

```bash
curl --location '{base_url}/api/method/luxury_api.api.item_price.get_item_prices?branch=Branch%20-%201&search=watch' \
--header 'Authorization: token api_key:api_secret'
```

### 6. Common prices only

```bash
curl --location '{base_url}/api/method/luxury_api.api.item_price.get_item_prices' \
--header 'Authorization: token api_key:api_secret'
```

### 7. JavaScript (fetch)

```javascript
const BASE_URL = "https://your-site.example.com";

const params = new URLSearchParams({
	branch: "Branch - 1",
	search: "watch",
	page: 1,
	page_size: 50,
});

const res = await fetch(
	`${BASE_URL}/api/method/luxury_api.api.item_price.get_item_prices?${params}`,
	{ headers: { Authorization: "token api_key:api_secret" } }
);
const { message } = await res.json();
console.log(message.data);
```

### 8. Python (requests)

```python
import requests

BASE_URL = "https://your-site.example.com"

response = requests.get(
	f"{BASE_URL}/api/method/luxury_api.api.item_price.get_item_prices",
	params={"branch": "Branch - 1", "item_code": "ITEM-001"},
	headers={"Authorization": "token api_key:api_secret"},
)
prices = response.json()["message"]["data"]
```

---

## Success Response

HTTP `200`. Frappe wraps the return value in `message`.

### Without pagination

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
        "message": null
    }
}
```

### With pagination (`page=1&page_size=50`)

The response has the same fields, plus `pagination`:

```json
{
    "message": {
        "success": true,
        "branch_price_lists": ["Branch 1 Selling"],
        "common_price_lists": ["Common Selling"],
        "data": [ "..." ],
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

### With `price_list`

`branch_price_lists` holds the requested list. `common_price_lists` is empty. Every row has `is_branch_price: true`.

```json
{
    "message": {
        "success": true,
        "branch_price_lists": ["Standard Selling"],
        "common_price_lists": [],
        "data": [ "..." ],
        "message": null
    }
}
```

### No matching rows

```json
{
    "message": {
        "success": true,
        "branch_price_lists": ["Branch 1 Selling"],
        "common_price_lists": ["Common Selling"],
        "data": [],
        "message": "No item prices found."
    }
}
```

---

## Response Fields

| Field | Type | Description |
|---|---|---|
| `success` | bool | `true` on success. |
| `branch_price_lists` | array\<string\> | Branch price lists used, or the requested `price_list`. |
| `common_price_lists` | array\<string\> | Common (no branch) price lists used. |
| `data[].name` | string | Item Price ID. |
| `data[].item_code` | string | Item code. |
| `data[].item_name` | string | Item name. |
| `data[].item_description` | string | Item description. |
| `data[].uom` | string | Unit of measure. |
| `data[].price_list` | string | Price List that the rate comes from. |
| `data[].price_list_rate` | float | Rate. |
| `data[].currency` | string | Currency. |
| `data[].selling` | int (0/1) | Selling price flag. |
| `data[].buying` | int (0/1) | Buying price flag. |
| `data[].valid_from` | date \| null | Start of validity. |
| `data[].valid_upto` | date \| null | End of validity. |
| `data[].customer` | string \| null | Customer for a customer-specific price. |
| `data[].batch_no` | string \| null | Batch for a batch-specific price. |
| `data[].is_branch_price` | bool | `true` if the row comes from a branch price list (or the requested `price_list`). `false` if it comes from a common price list. |
| `message` | string \| null | `"No item prices found."` when `data` is empty. Otherwise `null`. |
| `pagination.page` | int | Current page. |
| `pagination.page_size` | int | Rows per page. |
| `pagination.total_records` | int | Total matching rows. |
| `pagination.total_pages` | int | Total pages. |
| `pagination.has_next` | bool | `true` if a next page exists. |
| `pagination.has_previous` | bool | `true` if a previous page exists. |

`pagination` is present only when you send `page` or `page_size`.

---

## Error Responses

All errors below return HTTP `404` with `exc_type: DoesNotExistError`.

| Cause | Message |
|---|---|
| `price_list` does not exist | `Price List '<name>' does not exist.` |
| `branch` does not exist | `Branch '<name>' does not exist.` |
| Branch has no price list and no common price list exists | `No Price List found for Branch '<name>'.` |

Example:

```json
{
    "exc_type": "DoesNotExistError",
    "_server_messages": "[\"Branch 'Nonexistent' does not exist.\"]"
}
```

Other errors:

| HTTP | Cause |
|---|---|
| `401` / `403` | No session or invalid API key/secret. |
| `405` | Request sent with a method other than `GET`. |

---

## How It Works

1. **Resolve price lists**
   - If `price_list` is sent, validate it and use only it.
   - Otherwise, get the common price lists: enabled, `selling = 1`, `branch` not set.
   - If `branch` is sent, validate it and get its price lists: enabled, `selling = 1`, `branch = <branch>`.
2. **Fetch Item Prices** for all resolved price lists. Apply the `item_code` and `search` filters.
3. **Prefer branch prices.** For each `(item_code, uom)` with a branch price, remove the common price row. Set `is_branch_price` on each row.
4. **Paginate** if `page` or `page_size` is sent.

### Example of branch override

| Item | UOM | Branch 1 Selling | Common Selling | Returned for `branch=Branch - 1` |
|---|---|---|---|---|
| ITEM-001 | Nos | 48000 | 50000 | 48000 (`is_branch_price: true`) |
| ITEM-002 | Nos | — | 5000 | 5000 (`is_branch_price: false`) |
| ITEM-001 | Box | — | 240000 | 240000 (`is_branch_price: false`) |

---

## DocTypes Used

- `Price List` (custom field `branch`)
- `Branch`
- `Item Price`

## Notes

- To make a price list apply to all branches, leave its `branch` field empty.
- The API fetches all matching rows before it removes overridden common prices. Pagination is applied after that, so `total_records` counts rows after the override.

---

# Price List API

Returns the Price List records for a branch. It does not return item rates. To get rates, use `get_item_prices`.

## Endpoint

```
GET /api/method/luxury_api.api.item_price.get_price_lists
```

Authentication is the same as `get_item_prices`.

## Query Parameters

| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `branch` | string | No | — | Existing Branch name. Returns the price lists for this branch. |
| `include_common` | int (0/1) | No | `1` | Set to `0` to return only the branch price lists. |

### Rules

- The API returns only enabled selling Price Lists.
- If you do not send `branch`, the API returns only the common price lists (with an empty `branch` field).
- Branch price lists come first, then common price lists. Each group is sorted by name.

## Examples

```bash
# Branch and common price lists
curl --location '{base_url}/api/method/luxury_api.api.item_price.get_price_lists?branch=Branch%20-%201' \
--header 'Authorization: token api_key:api_secret'

# Branch price lists only
curl --location '{base_url}/api/method/luxury_api.api.item_price.get_price_lists?branch=Branch%20-%201&include_common=0' \
--header 'Authorization: token api_key:api_secret'
```

## Success Response

```json
{
    "message": {
        "success": true,
        "branch": "Branch - 1",
        "data": [
            {
                "name": "Branch 1 Selling",
                "price_list_name": "Branch 1 Selling",
                "currency": "INR",
                "branch": "Branch - 1",
                "selling": 1,
                "buying": 0,
                "enabled": 1,
                "is_common": false
            },
            {
                "name": "Standard Selling",
                "price_list_name": "Standard Selling",
                "currency": "INR",
                "branch": null,
                "selling": 1,
                "buying": 0,
                "enabled": 1,
                "is_common": true
            }
        ],
        "message": null
    }
}
```

If there are no matching price lists, `data` is `[]` and `message` is `"No price lists found."`.

## Error Responses

| Case | Exception | HTTP |
|---|---|---|
| `branch` does not exist | `DoesNotExistError` — `Branch '<name>' does not exist.` | 404 |
| Not logged in | `PermissionError` | 403 |
