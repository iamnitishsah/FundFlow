# FundFlow Backend — Complete REST API Documentation

This document provides a comprehensive technical reference for the FundFlow reconciliation backend REST API. It details all available endpoints, request/response formats, tenant isolation conventions, matching engine logic, concurrency protections, error models, and cURL examples.

---

## 1. Architecture & Protocol Overview

- **Base URL**: `http://localhost:8000/api/` (or via Docker gateway `http://web:8000/api/`)
- **Protocol**: HTTP/1.1 over TCP
- **Data Exchange**: JSON (`Content-Type: application/json`), except multipart uploads (`multipart/form-data`)
- **Backend Framework**: Django 6.1 with Django REST Framework (DRF)
- **Database**: PostgreSQL 16
- **Character Encoding**: UTF-8 / UTF-8-BOM

---

## 2. Multi-Tenancy & Tenant Scoping Protocol

FundFlow implements multi-tenant architecture designed for private equity fund administrators managing multiple General Partner (GP) entities.

### Tenant Identification Header: `X-Organization`

Except for the global public endpoint `GET /api/organizations/`, **every single API request must include the `X-Organization` HTTP header** containing the unique organization slug (e.g., `northwind`, `bluebird`).

```http
X-Organization: northwind
```

### Tenant Isolation Status Codes & Security Guarantees

| Scenario | HTTP Status Code | Response Body | Rationale |
|---|---|---|---|
| Header omitted or blank | `400 Bad Request` | `{"detail": "X-Organization header is required."}` | Missing required tenant identification |
| Unknown organization slug | `404 Not Found` | `{"detail": "Organization not found."}` | Tenant does not exist |
| Accessing record owned by another tenant | `404 Not Found` | `{"detail": "Not found."}` | Prevents cross-tenant entity enumeration (never returns `403 Forbidden`) |

---

## 3. Data Models & Schemas

### 3.1 Organization
| Field | Type | Description |
|---|---|---|
| `id` | Integer | Primary key |
| `slug` | String | Unique lowercase slug (e.g. `northwind`, `bluebird`) |
| `name` | String | Display legal name (e.g. `Northwind Ventures`) |

### 3.2 CapitalCall
| Field | Type | Description |
|---|---|---|
| `id` | Integer | Primary key |
| `call_number` | Integer | Call issuance sequence (e.g. `1`, `2`) |
| `call_date` | Date (`YYYY-MM-DD`) | Date capital call notice was officially issued |
| `due_date` | Date (`YYYY-MM-DD`) | Payment deadline date |

### 3.3 InvestorEntity
| Field | Type | Description |
|---|---|---|
| `id` | Integer | Primary key |
| `name` | String | Original legal investor name (e.g. `Patel Family Trust`) |
| `normalized_name` | String | Cleaned uppercase name with corporate suffixes stripped (retains `TRUST`) |

### 3.4 LineItem
| Field | Type | Description |
|---|---|---|
| `id` | Integer | Primary key |
| `wire_reference` | String | Expected wire reference on bank statement (e.g. `CC-1001`) |
| `normalized_reference` | String | Alphanumeric uppercase reference (e.g. `CC1001`) |
| `amount_called` | Decimal (`14,2`) | Total called capital amount in USD |
| `amount_funded` | Decimal (`14,2`) | Accumulated reconciled funds received |
| `amount_remaining` | Decimal (`14,2`) | Dynamically computed: `amount_called - amount_funded` |
| `status` | String | `open`, `partially_funded`, `funded` |
| `investor_name` | String | Read-only name from related `InvestorEntity` |
| `call_number` | Integer | Read-only sequence from related `CapitalCall` |
| `call_date` | Date | Read-only notice issuance date |

### 3.5 BankTransaction
| Field | Type | Description |
|---|---|---|
| `id` | Integer | Primary key |
| `date` | Date (`YYYY-MM-DD`) | Bank transaction posting date |
| `description` | String | Raw bank statement memo text |
| `amount` | Decimal (`14,2`) | Transaction amount (positive for credits, negative for debits) |
| `type` | String | `credit` or `debit` |
| `bank_reference` | String | Unique bank transaction reference ID (e.g. `BNK-WIRE-001`) |
| `status` | String | `suggested`, `needs_review`, `reconciled`, `ignored` |
| `needs_review_reason` | String | Plain-language explanation if manual attention is required |
| `raw_file_line` | Integer | CSV line number where transaction originated |
| `matches` | Array | List of candidate `MatchProposal` objects |
| `suggested_match` | Object / null | Active match proposal (`proposed` or `approved`) |

### 3.6 MatchProposal
| Field | Type | Description |
|---|---|---|
| `id` | Integer | Primary key |
| `line_item` | Integer | Foreign key ID to matched `LineItem` |
| `line_item_reference` | String | Wire reference of matched line item |
| `investor_name` | String | LP investor name |
| `line_item_remaining` | Decimal (`14,2`) | Remaining uncalled balance |
| `match_status` | String | `proposed`, `approved`, `rejected` |
| `reason` | String | Plain-language explanation why the match was generated |
| `created_at` | ISO-8601 String | Proposal creation timestamp |

---

## 4. REST API Endpoint Reference

```
┌─────────────────────────────────┬────────┬────────────────────────────────────────────────────────┐
│ Endpoint                        │ Method │ Summary                                                │
├─────────────────────────────────┼────────┼────────────────────────────────────────────────────────┤
│ /api/organizations/             │ GET    │ List all demo organizations (Public / Header Optional) │
│ /api/line-items/                │ GET    │ List capital call line items for current tenant        │
│ /api/transactions/              │ GET    │ List imported bank transactions with match proposals   │
│ /api/statements/upload/         │ POST   │ Ingest bank statement CSV & trigger matching engine    │
│ /api/matches/{id}/approve/      │ POST   │ Atomically approve proposed match & fund line item     │
│ /api/matches/{id}/reject/       │ POST   │ Reject candidate match proposal                        │
│ /api/transactions/{id}/ignore/  │ POST   │ Mark transaction as ignored                            │
└─────────────────────────────────┴────────┴────────────────────────────────────────────────────────┘
```

---

### 4.1 List Organizations

Retrieves all active organizations. Used primarily by the frontend tenant switcher to allow General Partners to switch between fund entities.

- **Method**: `GET`
- **Path**: `/api/organizations/`
- **Headers**: *(None required)*
- **Query Parameters**: None

#### Response `200 OK`
```json
[
  {
    "id": 1,
    "slug": "northwind",
    "name": "Northwind Ventures"
  },
  {
    "id": 2,
    "slug": "bluebird",
    "name": "Bluebird Capital"
  }
]
```

#### Example cURL
```bash
curl -X GET http://localhost:8000/api/organizations/ \
  -H "Accept: application/json"
```

---

### 4.2 List Capital Call Line Items

Lists all capital call line items for the current organization, ordered by capital call number and wire reference. Includes calculated fields `amount_remaining` and line status.

- **Method**: `GET`
- **Path**: `/api/line-items/`
- **Headers**:
  - `X-Organization`: `<slug>` *(Required)*

#### Response `200 OK`
```json
[
  {
    "id": 1,
    "wire_reference": "CC-1001",
    "normalized_reference": "CC1001",
    "amount_called": "50000.00",
    "amount_funded": "0.00",
    "amount_remaining": "50000.00",
    "status": "open",
    "investor_name": "Haller Capital LLC",
    "call_number": 1,
    "call_date": "2024-01-10"
  },
  {
    "id": 2,
    "wire_reference": "CC-1002",
    "normalized_reference": "CC1002",
    "amount_called": "25000.00",
    "amount_funded": "25000.00",
    "amount_remaining": "0.00",
    "status": "funded",
    "investor_name": "Rahul Shah Trust",
    "call_number": 1,
    "call_date": "2024-01-10"
  }
]
```

#### Error Responses
- `400 Bad Request`: If `X-Organization` header is missing.
- `404 Not Found`: If organization slug does not exist.

#### Example cURL
```bash
curl -X GET http://localhost:8000/api/line-items/ \
  -H "X-Organization: northwind" \
  -H "Accept: application/json"
```

---

### 4.3 List Bank Transactions

Lists all bank transactions for the organization, ordered by descending transaction date and creation timestamp. Automatically embeds all nested `MatchProposal` candidates and evaluates the primary `suggested_match`.

- **Method**: `GET`
- **Path**: `/api/transactions/`
- **Headers**:
  - `X-Organization`: `<slug>` *(Required)*
- **Query Parameters**:
  - `status` *(Optional)*: Filter by transaction status. Allowed values:
    - `suggested`
    - `needs_review`
    - `reconciled`
    - `ignored`

#### Response `200 OK`
```json
[
  {
    "id": 1,
    "date": "2024-01-15",
    "description": "WIRE FROM HALLER CAPITAL LLC REF CC1001",
    "amount": "25000.00",
    "type": "credit",
    "bank_reference": "BNK-WIRE-001",
    "status": "suggested",
    "needs_review_reason": "",
    "raw_file_line": 2,
    "matches": [
      {
        "id": 1,
        "line_item": 1,
        "line_item_reference": "CC-1001",
        "investor_name": "Haller Capital LLC",
        "line_item_remaining": "50000.00",
        "match_status": "proposed",
        "reason": "Exact wire reference match: 'CC-1001'",
        "created_at": "2026-10-15T20:00:00Z"
      }
    ],
    "suggested_match": {
      "id": 1,
      "line_item": 1,
      "line_item_reference": "CC-1001",
      "investor_name": "Haller Capital LLC",
      "line_item_remaining": "50000.00",
      "match_status": "proposed",
      "reason": "Exact wire reference match: 'CC-1001'",
      "created_at": "2026-10-15T20:00:00Z"
    }
  },
  {
    "id": 2,
    "date": "2024-01-18",
    "description": "WIRE TRANSFER FROM PATEL FAMILY TRUST CC-1003",
    "amount": "13000.00",
    "type": "credit",
    "bank_reference": "BNK-WIRE-006",
    "status": "needs_review",
    "needs_review_reason": "Overpayment: Wire amount $13000.00 exceeds remaining line item balance $12500.00 (Reference 'CC-1003').",
    "raw_file_line": 7,
    "matches": [],
    "suggested_match": null
  }
]
```

#### Example cURL
```bash
# Get all transactions
curl -X GET http://localhost:8000/api/transactions/ \
  -H "X-Organization: northwind"

# Filter by suggested status
curl -X GET "http://localhost:8000/api/transactions/?status=suggested" \
  -H "X-Organization: northwind"
```

---

### 4.4 Ingest Bank Statement CSV

Uploads a bank statement CSV file for the current organization. 

#### Validation Rules:
1. **Header Validation**: Checks presence of all 5 required columns (`date`, `description`, `amount`, `type`, `reference`). If any header is missing, the entire file is rejected and **zero rows are saved**.
2. **Line-by-Line Parsing**:
   - Dates must adhere to real calendar days (`YYYY-MM-DD`). Invalid calendar dates (e.g. `2024-02-30`) are skipped with a recorded error.
   - Amounts support commas and negative numbers (`$25,000.00`). Decimals are strictly preserved.
   - Type must be `credit` or `debit`. Credits must have positive amounts; debits must have negative amounts.
3. **Deduplication**:
   - Duplicates within the same file (based on `bank_reference`) are skipped.
   - Duplicates against existing database records for the current organization are skipped.
4. **Debits**:
   - Ingested immediately with status `ignored`.
5. **Matching Engine Execution**:
   - For all newly created credits, candidate proposals are automatically computed.
   - Any transaction marked `needs_review` triggers the non-blocking Airtable sync service.

- **Method**: `POST`
- **Path**: `/api/statements/upload/`
- **Headers**:
  - `X-Organization`: `<slug>` *(Required)*
  - `Content-Type`: `multipart/form-data`
- **Request Body**:
  - `file`: CSV file attachment *(Required)*

#### Response `200 OK`
```json
{
  "imported_count": 11,
  "duplicate_count": 1,
  "error_count": 2,
  "errors": [
    {
      "line": 13,
      "message": "Invalid date format or calendar date: '2024-02-30'"
    },
    {
      "line": 14,
      "message": "Credit amount must be positive"
    }
  ],
  "duplicates": [
    {
      "line": 11,
      "reference": "BNK-WIRE-008",
      "message": "Duplicate bank reference in file: 'BNK-WIRE-008'"
    }
  ],
  "transactions": [
    {
      "id": 1,
      "date": "2024-01-15",
      "description": "WIRE FROM HALLER CAPITAL LLC REF CC1001",
      "amount": "25000.00",
      "type": "credit",
      "bank_reference": "BNK-WIRE-001",
      "status": "suggested",
      "needs_review_reason": "",
      "raw_file_line": 2,
      "matches": [ ... ]
    }
  ]
}
```

#### Error Responses
- `400 Bad Request` (Missing file parameter):
  ```json
  {
    "detail": "No file was uploaded under the 'file' parameter."
  }
  ```
- `400 Bad Request` (Missing required column):
  ```json
  {
    "detail": "Missing required column: 'date'"
  }
  ```

#### Example cURL
```bash
curl -X POST http://localhost:8000/api/statements/upload/ \
  -H "X-Organization: northwind" \
  -F "file=@sample_bank_statement.csv"
```

---

### 4.5 Approve Match Proposal

Atomically approves a candidate match proposal. Runs inside a database transaction with pessimistic locking (`select_for_update()`).

#### Business Logic:
1. Validates that the transaction belongs to the calling organization.
2. Verifies that the transaction is not already reconciled.
3. Checks that the match proposal is in `proposed` state.
4. Verifies `transaction.amount <= line_item.amount_remaining`.
5. Updates `line_item.amount_funded += transaction.amount` and refreshes line item status (`partially_funded` or `funded`).
6. Updates `match.match_status = 'approved'`.
7. Automatically updates other proposed matches for this transaction to `rejected`.
8. Updates `transaction.status = 'reconciled'`.

- **Method**: `POST`
- **Path**: `/api/matches/{match_id}/approve/`
- **Headers**:
  - `X-Organization`: `<slug>` *(Required)*
- **Path Parameters**:
  - `match_id` (Integer): ID of the `MatchProposal` to approve

#### Response `200 OK`
```json
{
  "id": 1,
  "line_item": 1,
  "line_item_reference": "CC-1001",
  "investor_name": "Haller Capital LLC",
  "line_item_remaining": "25000.00",
  "match_status": "approved",
  "reason": "Exact wire reference match: 'CC-1001'",
  "created_at": "2026-10-15T20:00:00Z"
}
```

#### Error Responses
- `404 Not Found`:
  - Proposal does not exist, or belongs to a different organization:
    ```json
    {
      "detail": "Match proposal not found."
    }
    ```
- `409 Conflict`:
  - If transaction was already reconciled by a concurrent request:
    ```json
    {
      "detail": "Transaction is already reconciled."
    }
    ```
  - If transaction amount exceeds the line item's remaining balance:
    ```json
    {
      "detail": "Transaction amount 25000.00 exceeds remaining amount 0.00."
    }
    ```
  - If the match proposal was already approved or rejected:
    ```json
    {
      "detail": "Match proposal cannot be approved in 'rejected' state."
    }
    ```

#### Example cURL
```bash
curl -X POST http://localhost:8000/api/matches/1/approve/ \
  -H "X-Organization: northwind" \
  -H "Accept: application/json"
```

---

### 4.6 Reject Match Proposal

Rejects a suggested match proposal.

#### Business Logic:
1. Validates organization ownership.
2. Checks that the transaction is not already reconciled.
3. Marks `match.match_status = 'rejected'`.
4. If the transaction has no remaining proposed matches, its status is changed to `needs_review` with reason `"Match was rejected."`.

- **Method**: `POST`
- **Path**: `/api/matches/{match_id}/reject/`
- **Headers**:
  - `X-Organization`: `<slug>` *(Required)*
- **Path Parameters**:
  - `match_id` (Integer): ID of the `MatchProposal` to reject

#### Response `200 OK`
```json
{
  "id": 1,
  "line_item": 1,
  "line_item_reference": "CC-1001",
  "investor_name": "Haller Capital LLC",
  "line_item_remaining": "50000.00",
  "match_status": "rejected",
  "reason": "Exact wire reference match: 'CC-1001'",
  "created_at": "2026-10-15T20:00:00Z"
}
```

#### Error Responses
- `404 Not Found`: Match proposal does not exist or belongs to another tenant.
- `409 Conflict`: If the transaction has already been reconciled:
  ```json
  {
    "detail": "Cannot reject a match on a reconciled transaction."
  }
  ```

#### Example cURL
```bash
curl -X POST http://localhost:8000/api/matches/1/reject/ \
  -H "X-Organization: northwind"
```

---

### 4.7 Ignore Bank Transaction

Marks an unneeded credit or erroneous wire transaction as `ignored`.

#### Business Logic:
1. Validates organization ownership.
2. Ensures the transaction is not currently `reconciled`.
3. Marks `transaction.status = 'ignored'`.
4. Rejects any active proposed matches linked to this transaction.

- **Method**: `POST`
- **Path**: `/api/transactions/{transaction_id}/ignore/`
- **Headers**:
  - `X-Organization`: `<slug>` *(Required)*
- **Path Parameters**:
  - `transaction_id` (Integer): ID of the `BankTransaction` to ignore

#### Response `200 OK`
Returns the updated `BankTransaction` object:
```json
{
  "id": 4,
  "date": "2024-01-16",
  "description": "UNKNOWN UNIDENTIFIED WIRE",
  "amount": "1000.00",
  "type": "credit",
  "bank_reference": "BNK-WIRE-999",
  "status": "ignored",
  "needs_review_reason": "",
  "raw_file_line": 9,
  "matches": [],
  "suggested_match": null
}
```

#### Error Responses
- `404 Not Found`: Transaction does not exist or belongs to another tenant.
- `409 Conflict`: If the transaction is already reconciled:
  ```json
  {
    "detail": "Cannot ignore a reconciled transaction."
  }
  ```

#### Example cURL
```bash
curl -X POST http://localhost:8000/api/transactions/4/ignore/ \
  -H "X-Organization: northwind"
```

---

## 5. Matching Engine Specification

The matching engine is deterministic and runs during CSV statement ingestion for every row of type `credit`.

```
                    ┌─────────────────────────┐
                    │  Incoming Credit Wire   │
                    └────────────┬────────────┘
                                 │
                 Filter Line Items by Organization,
               Remaining > 0 & call_date <= txn.date
                                 │
                                 ▼
             ┌───────────────────────────────────────┐
             │ Step 1: Reference Match               │
             │ Normalized ref in normalized memo?    │
             └───────┬───────────────────────┬───────┘
                     │                       │
                Matches > 0              Matches = 0
                     │                       │
       ┌─────────────┴─────────────┐         ▼
       │                           │   ┌────────────────────────────────────────┐
   Single Match              Multi Match │ Step 2: Name & Exact Amount Match     │
       │                           │   │ Normalized name in memo & exact amount?│
 ┌─────┴─────┐                     │   └───────┬────────────────────────┬───────┘
 │           │                     │           │                        │
Amount <=   Amount >               │       Single Match             Multi or Zero
Remaining   Remaining              │           │                        │
 │           │                     │           ▼                        ▼
 ▼           ▼                     ▼   ┌───────────────┐        ┌───────────────┐
SUGGESTED   NEEDS_REVIEW     NEEDS_REVIEW │ SUGGESTED     │        │ NEEDS_REVIEW  │
(1 match)   (Overpayment)    (Ambiguous) │ (1 match)     │        │ (Review/None) │
                                       └───────────────┘        └───────────────┘
```

### String Normalization Rules:
1. **References**:
   - Converted to uppercase, non-alphanumeric characters stripped:
   - `re.sub(r'[^A-Z0-9]', '', reference.upper())`
   - Example: `cc-1001` $\rightarrow$ `CC1001`, `Cc 1003` $\rightarrow$ `CC1003`.
2. **Entity Names**:
   - Converted to uppercase, non-alphanumeric characters replaced with whitespace, multiple spaces collapsed.
   - Suffixes stripped: `LLC`, `LP`, `LTD`, `INC`.
   - **`TRUST` is preserved**.
   - Example: `Haller Capital LLC` $\rightarrow$ `HALLER CAPITAL`; `Patel Family Trust` $\rightarrow$ `PATEL FAMILY TRUST`.
3. **Word Boundary Matching**:
   - Names are checked using regex boundary checks `\b` to avoid false positives (e.g. `Oak` will not mistakenly match `Oakridge`).

---

## 6. Concurrency & Integrity Protections

To protect fund administrators from double funding a capital call or paying out excess balances during simultaneous approvals:

- **Row-Level Pessimistic Locks**:
  ```python
  MatchProposal.objects.select_for_update().get(id=match_id)
  BankTransaction.objects.select_for_update().get(id=transaction_id)
  LineItem.objects.select_for_update().get(id=line_item_id)
  ```
- **Atomicity**:
  Executed within `django.db.transaction.atomic()`. If any check fails, changes rollback instantly.
- **Double-Funding Guard**:
  If another administrator or process reconciles the line item concurrently, the second transaction sees `txn.amount > line_item.amount_remaining` or `txn.status == STATUS_RECONCILED` and immediately returns **HTTP 409 Conflict**.

---

## 7. Airtable Integration (Optional Bonus Feature)

When a transaction is classified as `needs_review`, it triggers `AirtableSyncService.sync_transaction()`.

- **Database Fields on `BankTransaction`**:
  - `airtable_record_id`: String storing the Airtable Record ID (e.g. `rec123456789`).
  - `airtable_sync_status`: `not_synced`, `synced`, `sync_failed`.
  - `airtable_error`: String recording network or authentication errors.
- **Fail-Safe Operation**:
  If Airtable API keys are missing or invalid, or if the external API is unreachable, the error is written to `airtable_error` and logged. **The CSV import operation completes without error and does not fail the HTTP request.**

---

## 8. Complete End-to-End Walkthrough via cURL

### Step 1: Discover Organizations
```bash
curl -s http://localhost:8000/api/organizations/ | jq .
```

### Step 2: Ingest Bank Statement for Northwind
```bash
curl -s -X POST http://localhost:8000/api/statements/upload/ \
  -H "X-Organization: northwind" \
  -F "file=@sample_bank_statement.csv" | jq .
```

### Step 3: Fetch Suggested Matches
```bash
curl -s -X GET "http://localhost:8000/api/transactions/?status=suggested" \
  -H "X-Organization: northwind" | jq '.[0]'
```

### Step 4: Approve the First Match
```bash
curl -s -X POST http://localhost:8000/api/matches/1/approve/ \
  -H "X-Organization: northwind" | jq .
```

### Step 5: Verify Concurrency / Double Funding Protection (409)
```bash
# Submitting approval again returns HTTP 409 Conflict
curl -i -X POST http://localhost:8000/api/matches/1/approve/ \
  -H "X-Organization: northwind"
```
*(Returns `HTTP/1.1 409 Conflict` with `{"detail": "Transaction is already reconciled."}`)*

### Step 6: Verify Multi-Tenant Scoping (404)
```bash
# Attempting to access Northwind's match proposal with Bluebird's organization header returns 404
curl -i -X POST http://localhost:8000/api/matches/1/approve/ \
  -H "X-Organization: bluebird"
```
*(Returns `HTTP/1.1 404 Not Found` with `{"detail": "Match proposal not found."}`)*

