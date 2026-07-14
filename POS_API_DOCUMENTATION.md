# POS Opening & Closing Entry APIs

Complete API documentation for POS Opening Entry and POS Closing Entry endpoints in the luxury_api application.

---

## Table of Contents
1. [POS Opening Entry APIs](#pos-opening-entry-apis)
2. [POS Closing Entry APIs](#pos-closing-entry-apis)
3. [Response Formats](#response-formats)
4. [Error Handling](#error-handling)

---

## POS Opening Entry APIs

### 1. GET - Retrieve POS Opening Entries

Fetch a list of POS Opening Entries with optional filters.

**Endpoint:**
```
GET /api/method/luxury_api.api.pos_opening.get_pos_opening_entries
```

**Authentication:** Required (non-guest)

**Query Parameters:**

| Parameter | Type | Description | Format |
|-----------|------|-------------|--------|
| `posting_date` | string | Filter by posting date | YYYY-MM-DD (optional) |
| `status` | string | Filter by status | Draft, Open, Closed (optional) |
| `pos_profile` | string | Filter by POS profile name | (optional) |

**Examples:**

#### Get All POS Opening Entries
```bash
curl -X GET "http://localhost:8000/api/method/luxury_api.api.pos_opening.get_pos_opening_entries" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json"
```

#### Filter by Posting Date
```bash
curl -X GET "http://localhost:8000/api/method/luxury_api.api.pos_opening.get_pos_opening_entries?posting_date=2026-07-14" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Filter by Status
```bash
curl -X GET "http://localhost:8000/api/method/luxury_api.api.pos_opening.get_pos_opening_entries?status=Open" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Filter by POS Profile
```bash
curl -X GET "http://localhost:8000/api/method/luxury_api.api.pos_opening.get_pos_opening_entries?pos_profile=LUX" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Multiple Filters
```bash
curl -X GET "http://localhost:8000/api/method/luxury_api.api.pos_opening.get_pos_opening_entries?pos_profile=LUX&status=Open&posting_date=2026-07-14" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Successful Response (200 OK):**
```json
{
  "success": true,
  "count": 2,
  "filters": {
    "pos_profile": "LUX",
    "status": "Open"
  },
  "data": [
    {
      "name": "POS-OPE-2026-00005",
      "company": "Luxury Stationery",
      "pos_profile": "LUX",
      "user": "anas@lux.com",
      "posting_date": "2026-07-14",
      "period_start_date": "2026-07-13 16:29:04",
      "status": "Open",
      "balance_details": [
        {
          "mode_of_payment": "Cash",
          "opening_amount": 1000.0
        }
      ]
    },
    {
      "name": "POS-OPE-2026-00004",
      "company": "Luxury Stationery",
      "pos_profile": "LUX",
      "user": "anas@lux.com",
      "posting_date": "2026-07-13",
      "period_start_date": "2026-07-12 16:29:04",
      "status": "Open",
      "balance_details": [
        {
          "mode_of_payment": "Card",
          "opening_amount": 5000.0
        }
      ]
    }
  ]
}
```

**Error Response (400 Bad Request) - Invalid Date Format:**
```json
{
  "success": false,
  "message": "Invalid posting_date format. Use YYYY-MM-DD."
}
```

**Error Response (500 Internal Server Error):**
```json
{
  "success": false,
  "message": "Database connection error"
}
```

---

### 2. POST - Create POS Opening Entry

Create a new POS Opening Entry with balance details.

**Endpoint:**
```
POST /api/method/luxury_api.api.pos_opening.create_pos_opening_entry
```

**Authentication:** Required (non-guest)

**Request Body Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `pos_profile` | string | Yes | Name of the POS Profile |
| `user` | string | Yes | Cashier/User email |
| `company` | string | Yes | Company name |
| `period_start_date` | string | Yes | Start date (ISO format) |
| `balance_details` | array | Yes | Array of payment mode details |

**balance_details Array Structure:**
```json
[
  {
    "mode_of_payment": "Cash",
    "opening_amount": 1000.0
  },
  {
    "mode_of_payment": "Card",
    "opening_amount": 5000.0
  }
]
```

**Examples:**

#### Basic Create Request
```bash
curl -X POST "http://localhost:8000/api/method/luxury_api.api.pos_opening.create_pos_opening_entry" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "pos_profile": "LUX",
    "user": "anas@lux.com",
    "company": "Luxury Stationery",
    "period_start_date": "2026-07-14 08:00:00",
    "balance_details": [
      {
        "mode_of_payment": "Cash",
        "opening_amount": 1000.0
      },
      {
        "mode_of_payment": "Card",
        "opening_amount": 5000.0
      }
    ]
  }'
```

#### Using JavaScript/Fetch
```javascript
const response = await fetch('/api/method/luxury_api.api.pos_opening.create_pos_opening_entry', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer YOUR_TOKEN'
  },
  body: JSON.stringify({
    pos_profile: 'LUX',
    user: 'anas@lux.com',
    company: 'Luxury Stationery',
    period_start_date: '2026-07-14 08:00:00',
    balance_details: [
      {
        mode_of_payment: 'Cash',
        opening_amount: 1000.0
      }
    ]
  })
});

const data = await response.json();
console.log(data);
```

#### Using Python/Requests
```python
import requests
import json

url = 'http://localhost:8000/api/method/luxury_api.api.pos_opening.create_pos_opening_entry'
headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer YOUR_TOKEN'
}
payload = {
    'pos_profile': 'LUX',
    'user': 'anas@lux.com',
    'company': 'Luxury Stationery',
    'period_start_date': '2026-07-14 08:00:00',
    'balance_details': [
        {
            'mode_of_payment': 'Cash',
            'opening_amount': 1000.0
        }
    ]
}

response = requests.post(url, json=payload, headers=headers)
print(response.json())
```

**Successful Response (201 Created):**
```json
{
  "success": true,
  "message": "POS Opening Entry created successfully.",
  "name": "POS-OPE-2026-00006"
}
```

**Error Response (400 Bad Request) - Validation Error:**
```json
{
  "success": false,
  "message": "POS Profile 'INVALID' is not configured for the company."
}
```

**Error Response (500 Internal Server Error):**
```json
{
  "success": false,
  "message": "Error creating POS Opening Entry"
}
```

---

## POS Closing Entry APIs

### 1. GET - Retrieve POS Closing Entries

Fetch a list of POS Closing Entries with optional filters.

**Endpoint:**
```
GET /api/method/luxury_api.api.pos_closing.get_pos_closing_entries
```

**Authentication:** Required (non-guest)

**Query Parameters:**

| Parameter | Type | Description | Format |
|-----------|------|-------------|--------|
| `pos_profile` | string | Filter by POS profile name | (optional) |
| `company` | string | Filter by company name | (optional) |
| `posting_date` | string | Filter by posting date | YYYY-MM-DD (optional) |
| `status` | string | Filter by status | Draft, Submitted, Queued, Failed, Cancelled (optional) |
| `pos_opening_entry` | string | Filter by linked POS Opening Entry | (optional) |

**Examples:**

#### Get All POS Closing Entries
```bash
curl -X GET "http://localhost:8000/api/method/luxury_api.api.pos_closing.get_pos_closing_entries" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Filter by Status
```bash
curl -X GET "http://localhost:8000/api/method/luxury_api.api.pos_closing.get_pos_closing_entries?status=Submitted" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Filter by Company
```bash
curl -X GET "http://localhost:8000/api/method/luxury_api.api.pos_closing.get_pos_closing_entries?company=Luxury%20Stationery" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Filter by POS Profile
```bash
curl -X GET "http://localhost:8000/api/method/luxury_api.api.pos_closing.get_pos_closing_entries?pos_profile=LUX" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Filter by Date
```bash
curl -X GET "http://localhost:8000/api/method/luxury_api.api.pos_closing.get_pos_closing_entries?posting_date=2026-07-14" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Filter by POS Opening Entry
```bash
curl -X GET "http://localhost:8000/api/method/luxury_api.api.pos_closing.get_pos_closing_entries?pos_opening_entry=POS-OPE-2026-00004" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

#### Multiple Filters Combined
```bash
curl -X GET "http://localhost:8000/api/method/luxury_api.api.pos_closing.get_pos_closing_entries?company=Luxury%20Stationery&pos_profile=LUX&status=Submitted&posting_date=2026-07-14" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Successful Response (200 OK):**
```json
{
  "success": true,
  "count": 3,
  "filters": {
    "pos_profile": "LUX",
    "status": "Submitted"
  },
  "data": [
    {
      "name": "POS-CLO-2026-00006",
      "company": "Luxury Stationery",
      "pos_profile": "LUX",
      "user": "anas@lux.com",
      "pos_opening_entry": "POS-OPE-2026-00005",
      "posting_date": "2026-07-14",
      "period_start_date": "2026-07-13 16:29:04",
      "period_end_date": "2026-07-14 12:02:41",
      "status": "Submitted",
      "grand_total": 1500.0,
      "net_total": 1500.0,
      "total_quantity": 2.0,
      "payment_reconciliation": [
        {
          "mode_of_payment": "Cash",
          "opening_amount": 1000.0,
          "expected_amount": 2500.0,
          "closing_amount": 3000.0,
          "difference": 500.0
        }
      ]
    },
    {
      "name": "POS-CLO-2026-00005",
      "company": "Luxury Stationery",
      "pos_profile": "LUX",
      "user": "anas@lux.com",
      "pos_opening_entry": "POS-OPE-2026-00004",
      "posting_date": "2026-07-14",
      "period_start_date": "2026-07-13 16:29:04",
      "period_end_date": "2026-07-14 11:57:24",
      "status": "Submitted",
      "grand_total": 2000.0,
      "net_total": 2000.0,
      "total_quantity": 5.0,
      "payment_reconciliation": [
        {
          "mode_of_payment": "Cash",
          "opening_amount": 1000.0,
          "expected_amount": 3000.0,
          "closing_amount": 1000.0,
          "difference": -2000.0
        }
      ]
    }
  ]
}
```

**Error Response (400 Bad Request) - Invalid Date Format:**
```json
{
  "success": false,
  "message": "Invalid posting_date format. Use YYYY-MM-DD."
}
```

**Error Response (500 Internal Server Error):**
```json
{
  "success": false,
  "message": "Database error occurred"
}
```

---

### 2. POST - Create POS Closing Entry

Create a new POS Closing Entry from an existing POS Opening Entry.

**Endpoint:**
```
POST /api/method/luxury_api.api.pos_closing.create_pos_closing_entry
```

**Authentication:** Required (non-guest)

**Request Body Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `pos_opening_entry` | string | Yes | Name of the POS Opening Entry to close |
| `payment_reconciliation` | array | No | Array of payment reconciliation details with closing amounts |
| `submit` | integer | No | 1 to auto-submit, 0 to keep as draft (default: 0) |

**payment_reconciliation Array Structure:**
```json
[
  {
    "mode_of_payment": "Cash",
    "closing_amount": 2000.0
  },
  {
    "mode_of_payment": "Card",
    "closing_amount": 5500.0
  }
]
```

**Examples:**

#### Basic Create Request (Draft)
```bash
curl -X POST "http://localhost:8000/api/method/luxury_api.api.pos_closing.create_pos_closing_entry" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "pos_opening_entry": "POS-OPE-2026-00004"
  }'
```

#### Create and Submit with Payment Reconciliation
```bash
curl -X POST "http://localhost:8000/api/method/luxury_api.api.pos_closing.create_pos_closing_entry" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "pos_opening_entry": "POS-OPE-2026-00004",
    "payment_reconciliation": [
      {
        "mode_of_payment": "Cash",
        "closing_amount": 2000.0
      },
      {
        "mode_of_payment": "Card",
        "closing_amount": 5500.0
      }
    ],
    "submit": 1
  }'
```

#### Using JavaScript/Fetch
```javascript
const response = await fetch('/api/method/luxury_api.api.pos_closing.create_pos_closing_entry', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer YOUR_TOKEN'
  },
  body: JSON.stringify({
    pos_opening_entry: 'POS-OPE-2026-00004',
    payment_reconciliation: [
      {
        mode_of_payment: 'Cash',
        closing_amount: 2000.0
      }
    ],
    submit: 1
  })
});

const data = await response.json();
console.log(data);
```

#### Using Python/Requests
```python
import requests

url = 'http://localhost:8000/api/method/luxury_api.api.pos_closing.create_pos_closing_entry'
headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer YOUR_TOKEN'
}
payload = {
    'pos_opening_entry': 'POS-OPE-2026-00004',
    'payment_reconciliation': [
        {
            'mode_of_payment': 'Cash',
            'closing_amount': 2000.0
        }
    ],
    'submit': 1
}

response = requests.post(url, json=payload, headers=headers)
print(response.json())
```

**Successful Response (201 Created):**
```json
{
  "success": true,
  "message": "POS Closing Entry created successfully.",
  "pos_closing_entry": {
    "name": "POS-CLO-2026-00007",
    "doctype": "POS Closing Entry",
    "owner": "anas@lux.com",
    "company": "Luxury Stationery",
    "pos_profile": "LUX",
    "user": "anas@lux.com",
    "pos_opening_entry": "POS-OPE-2026-00004",
    "posting_date": "2026-07-14",
    "period_start_date": "2026-07-13 16:29:04",
    "period_end_date": "2026-07-14 13:45:00",
    "status": "Submitted",
    "grand_total": 2000.0,
    "net_total": 2000.0,
    "total_quantity": 10.0,
    "payment_reconciliation": [
      {
        "mode_of_payment": "Cash",
        "opening_amount": 1000.0,
        "expected_amount": 2500.0,
        "closing_amount": 2000.0,
        "difference": -500.0
      }
    ]
  }
}
```

**Error Response (400 Bad Request) - Missing Required Field:**
```json
{
  "success": false,
  "message": "POS Opening Entry is mandatory."
}
```

**Error Response (404 Not Found) - POS Opening Entry Not Found:**
```json
{
  "success": false,
  "message": "POS Opening Entry 'POS-OPE-2026-99999' does not exist."
}
```

**Error Response (409 Conflict) - Already Closed:**
```json
{
  "success": false,
  "message": "POS Opening Entry 'POS-OPE-2026-00001' is already closed."
}
```

**Error Response (400 Bad Request) - Validation Error:**
```json
{
  "success": false,
  "message": "closing_amount is required for mode_of_payment 'Cash'."
}
```

**Error Response (500 Internal Server Error):**
```json
{
  "success": false,
  "message": "Failed to create POS Closing Entry. Please try again."
}
```

---

## Response Formats

### Success Response Format
All successful responses follow this structure:

**GET Request:**
```json
{
  "success": true,
  "count": <number>,
  "filters": {
    "filter_name": "filter_value"
  },
  "data": [...]
}
```

**POST Request:**
```json
{
  "success": true,
  "message": "Operation completed successfully.",
  "name": "DOC-NAME-001"
}
```

### HTTP Status Codes

| Code | Meaning | Usage |
|------|---------|-------|
| 200 | OK | Successful GET request |
| 201 | Created | Successful POST request (document created) |
| 400 | Bad Request | Invalid input, validation error, missing required fields |
| 404 | Not Found | Referenced document does not exist |
| 409 | Conflict | Operation conflicts with current state |
| 500 | Internal Server Error | Server-side error |

---

## Error Handling

### Common Error Scenarios

**Missing Authentication:**
```
HTTP/1.1 403 Forbidden
{
  "message": "You do not have permission to access this endpoint"
}
```

**Invalid JSON:**
```
HTTP/1.1 400 Bad Request
{
  "success": false,
  "message": "Invalid JSON in request body"
}
```

**Server Error with Logging:**
When a 500 error occurs, check the server error log:
```bash
# From the Frappe bench
bench --site local.com logs
```

---

## Best Practices

1. **Always include the full date format** (YYYY-MM-DD) for date filters
2. **URL encode query parameters** when they contain spaces: `company=Luxury%20Stationery`
3. **Validate balance_details array** before creating POS Opening Entry
4. **Check opening entry status** before creating closing entry (must be "Open")
5. **Handle payment reconciliation carefully** - ensure all modes of payment have closing amounts when provided
6. **Test with invalid data** to understand error responses before integrating

---

## Quick Reference

### POS Opening Entry Endpoints
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/method/luxury_api.api.pos_opening.get_pos_opening_entries` | List POS Opening Entries |
| POST | `/api/method/luxury_api.api.pos_opening.create_pos_opening_entry` | Create POS Opening Entry |

### POS Closing Entry Endpoints
| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/method/luxury_api.api.pos_closing.get_pos_closing_entries` | List POS Closing Entries |
| POST | `/api/method/luxury_api.api.pos_closing.create_pos_closing_entry` | Create POS Closing Entry |

---

## Support & Debugging

For issues or questions:
1. Check the error message returned in the response
2. Review server logs: `bench --site local.com logs`
3. Verify the document exists: `bench --site local.com console`
4. Check permissions for the authenticated user
