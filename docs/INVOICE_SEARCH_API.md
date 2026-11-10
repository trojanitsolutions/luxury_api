# Invoice Search API

Search POS Sales Invoices by customer ID, customer name, item or date.

Base path: `{base_url}/api/method/`
Auth header: `Authorization: token api_key:api_secret`

---

## Endpoint

`GET luxury_api.api.sales_invoice_find.search_sales_invoices`

Send all parameters in the query string. Only `GET` is allowed.

Only invoices with a POS Profile are returned. Draft, submitted, cancelled and return invoices are all included. Results are limited to the Sales Invoices the user can read.

---

## Parameters

| Param | Type | Required | Description |
|---|---|---|---|
| `customer_id` | string | * | Exact customer ID, for example `CUST-0001` |
| `customer_name` | string | * | Partial match on `customer_name` or `customer` |
| `item_code` | string | * | Exact match. Returns invoices that have this item on any line |
| `posting_date` | `YYYY-MM-DD` | * | Invoices on this date |
| `from_date` | `YYYY-MM-DD` | * | Invoices on or after this date |
| `to_date` | `YYYY-MM-DD` | * | Invoices on or before this date |
| `page` | int | No | Default `1` |
| `page_length` | int | No | Default `20` |
| `order_by` | string | No | `posting_date` (default), `grand_total`, `customer`, `status`, `modified` |
| `order` | string | No | `desc` (default) or `asc` |

\* Send at least one of these six.

If you send more than one filter, an invoice must match all of them.

---

## Examples

By customer ID:

```
GET luxury_api.api.sales_invoice_find.search_sales_invoices?customer_id=CUST-0001
```

By customer name:

```
GET luxury_api.api.sales_invoice_find.search_sales_invoices?customer_name=john
```

By item code:

```
GET luxury_api.api.sales_invoice_find.search_sales_invoices?item_code=ITEM-001
```

Customer name and item code:

```
GET luxury_api.api.sales_invoice_find.search_sales_invoices?customer_name=john&item_code=ITEM-001
```

On one date:

```
GET luxury_api.api.sales_invoice_find.search_sales_invoices?posting_date=2026-11-10
```

Date range:

```
GET luxury_api.api.sales_invoice_find.search_sales_invoices?from_date=2026-11-01&to_date=2026-11-10
```

All filters with paging and sorting:

```
GET luxury_api.api.sales_invoice_find.search_sales_invoices?customer_id=CUST-0001&customer_name=john&item_code=ITEM-001&from_date=2026-11-01&to_date=2026-11-10&page=1&page_length=20&order_by=grand_total&order=asc
```

curl:

```bash
curl -G '{base_url}/api/method/luxury_api.api.sales_invoice_find.search_sales_invoices' \
  -H 'Authorization: token api_key:api_secret' \
  --data-urlencode 'customer_name=john' \
  --data-urlencode 'item_code=ITEM-001'
```

---

## Response

```json
{
    "message": {
        "success": true,
        "count": 1,
        "filters": {"customer_name": "john", "item_code": "ITEM-001"},
        "data": [
            {
                "name": "ACC-SINV-2026-00012",
                "customer": "CUST-0001",
                "customer_name": "John Doe",
                "company": "Luxury Pvt Ltd",
                "pos_profile": "Branch 1 POS",
                "channel": "Retail",
                "posting_date": "2026-11-05",
                "grand_total": 10000.0,
                "outstanding_amount": 0.0,
                "status": "Paid",
                "docstatus": 1,
                "is_return": 0,
                "sales_person": "Ahmed",
                "commission_amount": 500.0,
                "items": [
                    {"item_code": "ITEM-001", "item_name": "Watch", "qty": 1, "rate": 10000.0, "amount": 10000.0}
                ]
            }
        ]
    }
}
```

- `count` is the number of rows on this page, not the total number of matches.
- `filters` lists the filters that were applied.
- `items` lists all lines on the invoice, not only the matching item.
- `sales_person` and `commission_amount` come from the invoice's Sales Team table. If there is no Sales Team row, they are `null` and `0`.

---

## Errors

```json
{"message": {"success": false, "message": "..."}}
```

| HTTP | When |
|---|---|
| 400 | None of `customer_id`, `customer_name`, `item_code`, `posting_date`, `from_date`, `to_date` is sent |
| 400 | A date is not `YYYY-MM-DD` |
| 400 | `from_date` is after `to_date` |
| 400 | `order_by` or `order` is not an allowed value |
| 400 | `page` or `page_length` is not a positive integer |
| 500 | Server error. Logged in the Error Log |
