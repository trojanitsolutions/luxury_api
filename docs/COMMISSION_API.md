# Commission API

A Sales Person gets a fixed commission on a POS sale. The commission is paid in cash at the counter.

Base path: `{base_url}/api/method/`
Auth header: `Authorization: token api_key:api_secret`

---

## Setup (once)

1. Run `bench --site <site> migrate`.
2. Create the **Sales Person** (enabled, not a group).
3. On the **POS Profile**:
   - Set **Commission Expense Account**.
   - Add a **Cash** mode in Payment Methods. The Cash mode needs a default account.
4. On the **Item**, keep **Grant Commission** ticked (default).

---

## 1. Create a sale with commission

`POST luxury_api.api.sales_invoice_pos.create_sales_invoice`

Add these fields to the normal sale request:

| Field | Required | Description |
|---|---|---|
| `sales_person` | Yes | Sales Person name |
| `commission_amount` | Yes | Commission amount, for example `500` |
| `commission_paid` | No | `1` (default) = paid in cash now. `0` = record only |

```json
{
    "customer": "CUST-0001",
    "company": "Luxury Pvt Ltd",
    "pos_profile": "Branch 1 POS",
    "items": [{"item_code": "ITEM-001", "qty": 1}],
    "payments": [{"mode_of_payment": "Cash", "amount": 10000}],
    "sales_person": "Ahmed",
    "commission_amount": 500
}
```

Result:
- The invoice's Sales Team table has one row: `sales_person: Ahmed`, `incentives: 500`.
- A Cash Entry is made: **Dr Commission Expense 500 / Cr Cash 500**. Its name is in `commission_journal_entry`.

---

## 2. Return

`POST luxury_api.api.sales_invoice_pos.create_sales_invoice_return` (full)
`POST luxury_api.api.sales_invoice_pos.create_partial_sales_return` (partial)

The commission goes down by the same share as the sale.
Example: 4,000 of 10,000 returned → commission −200.

Optional field `recover_commission`:
- `1` = the sales person gives back the 200. A Cash Entry is made: **Dr Cash 200 / Cr Commission Expense 200**.
- `0` = the sales person keeps it.

If you don't send it, the POS Profile setting **Auto Recover Commission on Return** decides (Yes = recover).

---

## 3. Cancel

`POST luxury_api.api.sales_invoice_pos.cancel_sales_invoice`

Optional field `keep_commission_payment`:
- `0` = cancel the commission Cash Entry too.
- `1` = keep it (the sales person keeps the money).

If you don't send it, the POS Profile setting **Auto Cancel Commission Payment** decides (Yes = cancel).

---

## When the API asks (HTTP 409)

If the POS Profile setting is **No** and you did not send the field, nothing is saved and you get:

```json
{"success": false, "requires_commission_decision": true, "message": "..."}
```

Ask the cashier: *"Does the sales person give back the commission?"* Then call again with the field.

| Action | Gives back | Keeps |
|---|---|---|
| Return | `recover_commission: 1` | `recover_commission: 0` |
| Cancel | `keep_commission_payment: 0` | `keep_commission_payment: 1` |

---

## 4. POS closing

`POST luxury_api.api.pos_closing.create_pos_closing_entry`

There are no new fields. The expected cash is lowered by the commission paid in the shift. The response also has `commission_paid` (the total for the shift).

---

## 5. List Sales Persons

`GET luxury_api.api.sales_person.list_sales_persons`

Use it to fill the sales person dropdown. Send `name` as `sales_person`.

---

## 6. Commission summary

`GET luxury_api.api.sales_person.get_commission_summary`

Optional filters: `from_date`, `to_date` (YYYY-MM-DD), `company`, `sales_person`, `pos_profile`, `channel`, `branch`.

Returns a row for each sales person:
- `total_commission` = commission earned (after returns)
- `commission_paid` = cash paid (after recoveries)

---

## Errors

| Message | Fix |
|---|---|
| Set 'Commission Expense Account' on POS Profile | Setup step 3 |
| POS Profile has no Cash mode of payment | Setup step 3 |
| Please set default Cash or Bank account in Mode of Payment | Add an account to the Cash mode |
| Sales Person does not exist | Use a name from `list_sales_persons` |
| Sales Person is disabled / is a group | Enable it, or pick an individual person |
| No item is eligible for commission | Tick Grant Commission on the item |
| Commission amount cannot be more than the eligible amount | Lower `commission_amount` |
