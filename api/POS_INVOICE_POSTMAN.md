# POS Invoice API - Postman Examples

## Base URL
```
POST http://localhost:8000/api/method/luxury_api.api.pos_invoice.create_pos_invoice
GET  http://localhost:8000/api/method/luxury_api.api.pos_invoice.get_pos_invoice
GET  http://localhost:8000/api/method/luxury_api.api.pos_invoice.list_pos_invoices
POST http://localhost:8000/api/method/luxury_api.api.pos_invoice.cancel_pos_invoice
POST http://localhost:8000/api/method/luxury_api.api.pos_invoice.create_return_invoice
```

## Authentication
Include in headers or request (for authenticated endpoints):
```
Authorization: Bearer <token>
```

Or use Frappe session cookies if authenticating first with login endpoint.

---

## 1. Create POS Invoice (JSON)

**Endpoint:** POST `/api/method/luxury_api.api.pos_invoice.create_pos_invoice`

**Content-Type:** `application/json`

**Headers:**
```
Content-Type: application/json
```

**Request Body:**
```json
{
    "customer": "CUST-0001",
    "company": "ABC Company",
    "pos_profile": "Main POS",
    "warehouse": "WH-01",
    "remarks": "Sale from store counter",
    "items": [
        {
            "item_code": "ITEM-0001",
            "qty": 2,
            "rate": 120
        },
        {
            "item_code": "ITEM-0002",
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
}
```

**Response (201):**
```json
{
    "message": {
        "success": true,
        "message": "POS Invoice created successfully.",
        "data": {
            "name": "POS-INV-2024-00001",
            "customer": "CUST-0001",
            "company": "ABC Company",
            "grand_total": 320,
            "status": "Submitted",
            ...
        }
    }
}
```

---

## 2. Create POS Invoice (Form Data)

**Endpoint:** POST `/api/method/luxury_api.api.pos_invoice.create_pos_invoice`

**Content-Type:** `application/x-www-form-urlencoded`

**Form Data:**
```
customer=CUST-0001
company=ABC Company
pos_profile=Main POS
warehouse=WH-01
remarks=Sale from store counter
items=[{"item_code": "ITEM-0001", "qty": 2, "rate": 120}, {"item_code": "ITEM-0002", "qty": 1, "rate": 80}]
payments=[{"mode_of_payment": "Cash", "amount": 320}]
```

---

## 3. Get Single POS Invoice

**Endpoint:** GET `/api/method/luxury_api.api.pos_invoice.get_pos_invoice`

**Query Parameters:**
```
invoice=POS-INV-2024-00001
```

**Response (200):**
```json
{
    "message": {
        "success": true,
        "data": {
            "name": "POS-INV-2024-00001",
            "customer": "CUST-0001",
            "company": "ABC Company",
            "grand_total": 320,
            "status": "Submitted",
            "items": [
                {
                    "item_code": "ITEM-0001",
                    "qty": 2,
                    "rate": 120,
                    "amount": 240
                },
                {
                    "item_code": "ITEM-0002",
                    "qty": 1,
                    "rate": 80,
                    "amount": 80
                }
            ],
            ...
        }
    }
}
```

---

## 4. List POS Invoices

**Endpoint:** GET `/api/method/luxury_api.api.pos_invoice.list_pos_invoices`

**Query Parameters:**
```
company=ABC Company
customer=CUST-0001
from_date=2024-01-01
to_date=2024-12-31
status=Submitted
pos_profile=Main POS
page=1
page_length=20
order_by=posting_date
order=desc
```

**Response (200):**
```json
{
    "message": {
        "success": true,
        "count": 5,
        "filters": {
            "company": "ABC Company",
            "customer": "CUST-0001"
        },
        "data": [
            {
                "name": "POS-INV-2024-00005",
                "customer": "CUST-0001",
                "company": "ABC Company",
                "grand_total": 500,
                "status": "Submitted",
                "posting_date": "2024-12-20"
            },
            ...
        ]
    }
}
```

---

## 5. Cancel POS Invoice

**Endpoint:** POST `/api/method/luxury_api.api.pos_invoice.cancel_pos_invoice`

**Content-Type:** `application/json`

**Request Body:**
```json
{
    "invoice": "POS-INV-2024-00001"
}
```

**Response (200):**
```json
{
    "message": {
        "success": true,
        "message": "POS Invoice cancelled successfully.",
        "data": {
            "name": "POS-INV-2024-00001",
            "status": "Cancelled"
        }
    }
}
```

---

## 6. Create Return Invoice

**Endpoint:** POST `/api/method/luxury_api.api.pos_invoice.create_return_invoice`

**Content-Type:** `application/json`

**Request Body:**
```json
{
    "invoice": "POS-INV-2024-00001"
}
```

**Response (201):**
```json
{
    "message": {
        "success": true,
        "message": "Return POS Invoice created successfully.",
        "data": {
            "name": "POS-INV-2024-00001-1",
            "customer": "CUST-0001",
            "company": "ABC Company",
            "is_return": 1,
            "status": "Submitted",
            ...
        }
    }
}
```

---

## Error Responses

### 400 - Bad Request
```json
{
    "message": {
        "success": false,
        "message": "Customer is required."
    }
}
```

### 404 - Not Found
```json
{
    "message": {
        "success": false,
        "message": "POS Invoice 'POS-INV-INVALID' does not exist."
    }
}
```

### 409 - Conflict
```json
{
    "message": {
        "success": false,
        "message": "POS Invoice can only be cancelled if it is submitted."
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

## Curl Examples

### Create with JSON
```bash
curl -X POST http://localhost:8000/api/method/luxury_api.api.pos_invoice.create_pos_invoice \
  -H "Content-Type: application/json" \
  -d '{
    "customer": "CUST-0001",
    "company": "ABC Company",
    "pos_profile": "Main POS",
    "items": [{"item_code": "ITEM-0001", "qty": 2, "rate": 120}],
    "payments": [{"mode_of_payment": "Cash", "amount": 240}]
  }'
```

### Create with Form Data
```bash
curl -X POST http://localhost:8000/api/method/luxury_api.api.pos_invoice.create_pos_invoice \
  -d "customer=CUST-0001" \
  -d "company=ABC Company" \
  -d "pos_profile=Main POS" \
  -d 'items=[{"item_code": "ITEM-0001", "qty": 2, "rate": 120}]' \
  -d 'payments=[{"mode_of_payment": "Cash", "amount": 240}]'
```

### Get Invoice
```bash
curl -X GET "http://localhost:8000/api/method/luxury_api.api.pos_invoice.get_pos_invoice?invoice=POS-INV-2024-00001"
```

### List with Filters
```bash
curl -X GET "http://localhost:8000/api/method/luxury_api.api.pos_invoice.list_pos_invoices?company=ABC%20Company&status=Submitted&page=1&page_length=10"
```

### Cancel Invoice
```bash
curl -X POST http://localhost:8000/api/method/luxury_api.api.pos_invoice.cancel_pos_invoice \
  -H "Content-Type: application/json" \
  -d '{"invoice": "POS-INV-2024-00001"}'
```
