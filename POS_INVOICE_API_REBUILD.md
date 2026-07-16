# POS Invoice API - Complete Rebuild

## HTTP 415 Issue Fixed ✓

**Root Cause:**  
Original code used `frappe.request.get_json()` which requires strict `Content-Type: application/json`. Any other format (form-data, x-www-form-urlencoded) caused Frappe to throw HTTP 415 before the function was even called.

**Solution:**  
Replaced with `frappe.form_dict` which is Frappe's native handler for ALL request content types.

---

## Key Implementation Details

**File:** `luxury_api/api/pos_invoice.py`

### Changes Made

1. ✅ **Request Handling**: Uses `frappe.form_dict` instead of `frappe.request.get_json()`
2. ✅ **Content-Type Support**: JSON, form-data, x-www-form-urlencoded all work
3. ✅ **Rate Field**: Added validation for item rate (per requirements)
4. ✅ **Type Hints**: All parameters use proper `Optional[Union[...]]` syntax
5. ✅ **Validation**: Comprehensive error messages
6. ✅ **Standards**: Follows Frappe API best practices

### Function Signature

```python
@frappe.whitelist(methods=["POST"])
def create_pos_invoice(
    customer: Optional[str] = None,
    company: Optional[str] = None,
    pos_profile: Optional[str] = None,
    items: Optional[Union[str, list]] = None,
    payments: Optional[Union[str, list]] = None,
    warehouse: Optional[str] = None,
    posting_date: Optional[str] = None,
    remarks: Optional[str] = None,
):
```

---

## Request Examples

### 1. JSON Content-Type

```bash
curl -X POST http://127.0.0.1:8000/api/method/luxury_api.api.pos_invoice.create_pos_invoice \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "CUST-001",
    "company": "ABC Company",
    "pos_profile": "Main POS",
    "warehouse": "WH-01",
    "remarks": "POS Sale",
    "items": [
      {
        "item_code": "ITEM-001",
        "qty": 2,
        "rate": 120
      },
      {
        "item_code": "ITEM-002",
        "qty": 1,
        "rate": 80
      }
    ],
    "payments": [
      {
        "mode_of_payment": "Cash",
        "amount": 320
      }
    ]
  }'
```

### 2. Form Data Content-Type

```bash
curl -X POST http://127.0.0.1:8000/api/method/luxury_api.api.pos_invoice.create_pos_invoice \
  -d "customer=CUST-001" \
  -d "company=ABC Company" \
  -d "pos_profile=Main POS" \
  -d "warehouse=WH-01" \
  -d "remarks=POS Sale" \
  -d 'items=[{"item_code":"ITEM-001","qty":2,"rate":120}]' \
  -d 'payments=[{"mode_of_payment":"Cash","amount":320}]'
```

### 3. Form URL-Encoded

```bash
curl -X POST http://127.0.0.1:8000/api/method/luxury_api.api.pos_invoice.create_pos_invoice \
  --data-urlencode "customer=CUST-001" \
  --data-urlencode "company=ABC Company" \
  --data-urlencode "pos_profile=Main POS" \
  --data-urlencode 'items=[{"item_code":"ITEM-001","qty":2,"rate":120}]' \
  --data-urlencode 'payments=[{"mode_of_payment":"Cash","amount":320}]'
```

---

## Success Response

**Status:** 201 Created

```json
{
  "message": {
    "success": true,
    "message": "POS Invoice created successfully.",
    "data": {
      "name": "POS-INV-2024-00001",
      "customer": "CUST-001",
      "company": "ABC Company",
      "grand_total": 320,
      "status": "Submitted",
      "items": [
        {
          "item_code": "ITEM-001",
          "qty": 2,
          "rate": 120,
          "amount": 240
        },
        {
          "item_code": "ITEM-002",
          "qty": 1,
          "rate": 80,
          "amount": 80
        }
      ],
      "payments": [
        {
          "mode_of_payment": "Cash",
          "amount": 320
        }
      ]
    }
  }
}
```

---

## Error Responses

### 400 - Validation Error

```json
{
  "message": {
    "success": false,
    "message": "Customer is required."
  }
}
```

### 500 - Server Error

```json
{
  "message": {
    "success": false,
    "message": "Failed to create POS Invoice. Please try again."
  }
}
```

---

## Other Endpoints

The file also includes:

- `get_pos_invoice(invoice: str)` — GET single invoice
- `list_pos_invoices(...)` — GET list with filters, pagination, sorting
- `cancel_pos_invoice(invoice: str)` — POST to cancel
- `create_return_invoice(invoice: str)` — POST to create return

All follow the same standards and support the same request types.

---

## Postman Collection

See: `api/POS_INVOICE_POSTMAN.md` for complete Postman examples

---

## Notes

- ✅ No more HTTP 415 errors
- ✅ Supports all Frappe request formats
- ✅ ERPNext auto-populates item_name, description, uom, warehouse, accounts
- ✅ Stock ledger and accounting entries created automatically
- ✅ Standard Frappe error handling
