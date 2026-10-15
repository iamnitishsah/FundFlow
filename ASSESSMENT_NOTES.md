# FundFlow — Technical Assessment Notes

## 1. Application Name & Overview

- **App Name**: **FundFlow**
- **Description**: Multi-tenant bank reconciliation portal for General Partners (GPs) to match incoming bank statement wires against capital call line items issued to Limited Partners (LPs).
- **Core Capabilities**:
  - Ingests unstructured bank statement CSV files with line-by-line validation and duplicate detection.
  - Normalizes messy bank references and legal entity names (e.g. `cc1001`, `Patel Family Trust`).
  - Executes a deterministic 3-tier matching engine that explains why each match was suggested or flagged for review.
  - Enforces atomic, concurrent-safe approvals (`select_for_update()`) with HTTP 409 protections against double funding.
  - Strict tenant isolation via `X-Organization` header (cross-tenant access returns HTTP 404, never 403).
  - Synchronizes `needs_review` items to Airtable without interrupting import operations.
- **Tech Stack**:
  - **Backend**: Django 6.1, Django REST Framework, PostgreSQL 16 (running via Docker Compose).
  - **Frontend**: React 19 SPA, TypeScript, Tailwind CSS v4, Vite.

---

## 2. Setup from a Fresh Clone

### Option A: Running with Docker (Recommended)

1. **Clone the repository and prepare environment variables**:
   ```bash
   cp .env.example backend/.env
   ```

2. **Start PostgreSQL and the Django backend container**:
   ```bash
   docker compose -f backend/docker-compose.yml up -d
   ```

3. **Apply database migrations**:
   ```bash
   docker compose -f backend/docker-compose.yml exec web python manage.py migrate
   ```

4. **Seed demo organizations and line items (idempotent)**:
   ```bash
   docker compose -f backend/docker-compose.yml exec web python manage.py seed_demo
   ```

5. **Start the React frontend**:
   ```bash
   npm --prefix frontend install
   npm --prefix frontend run dev
   ```
   Open `http://localhost:5173` in your browser.

---

### Option B: Running Backend Locally on Host

1. Create and activate a Python 3.12 virtual environment:
   ```bash
   python3 -m venv backend/.venv
   source backend/.venv/bin/activate
   pip install -r backend/requirements.txt
   ```
2. Set environment variables in `backend/.env` (pointing `DB_HOST` to `localhost` and ensuring PostgreSQL is running on port 5432).
3. Run migrations and demo seeder:
   ```bash
   python backend/manage.py migrate
   python backend/manage.py seed_demo
   python backend/manage.py runserver 0.0.0.0:8000
   ```
4. Start frontend:
   ```bash
   npm --prefix frontend install
   npm --prefix frontend run dev
   ```

---

## 3. Single Command to Run Tests

Run the full automated test suite inside Docker:
```bash
docker compose -f backend/docker-compose.yml exec web python manage.py test reconciliation
```

*(Or on local host with virtualenv active)*:
```bash
python backend/manage.py test reconciliation
```

All 8 minimum required assessment cases, multi-tenant isolation cases, concurrency protection tests, and Airtable bonus sync tests pass cleanly.

---

## 4. Environment Variables (`.env.example`)

The repository includes a template file `.env.example`:
```ini
GATEWAY_PORT=8000
POSTGRES_DB=fundflow
POSTGRES_USER=postgres
POSTGRES_PASSWORD=local_dev_password
POSTGRES_PORT=5432
DB_HOST=localhost
DJANGO_SECRET_KEY=django-insecure-local-dev-key-change-me
DJANGO_DEBUG=True
AIRTABLE_API_KEY=
AIRTABLE_BASE_ID=
AIRTABLE_TABLE_NAME=Needs Review Transactions
```

---

## 5. Data Model Summary

- **`Organization`**: GP tenant boundary (`slug`, `name`). Slugs: `northwind`, `bluebird`.
- **`CapitalCall`**: Capital call issuance (`organization`, `call_number`, `call_date`, `due_date`).
- **`InvestorEntity`**: Legal LP entity investing into the fund (`organization`, `name`, `normalized_name`). Normalization removes trailing legal forms (`LLC`, `LP`, `LTD`, `INC`) while retaining `TRUST`.
- **`LineItem`**: An LP's requested share of a capital call (`wire_reference`, `normalized_reference`, `amount_called`, `amount_funded`, `status`). Computed property `amount_remaining` = `amount_called - amount_funded`. Status choices: `open`, `partially_funded`, `funded`.
- **`BankTransaction`**: Ingested bank transaction (`date`, `description`, `normalized_description`, `amount`, `type`, `bank_reference`, `status`, `needs_review_reason`, `airtable_record_id`, `airtable_sync_status`). Unique per `(organization, bank_reference)`. Status choices: `suggested`, `needs_review`, `reconciled`, `ignored`.
- **`MatchProposal`**: Link connecting a transaction to a line item candidate (`match_status`, `reason`). Status choices: `proposed`, `approved`, `rejected`. Unique per `(transaction, line_item)`.

---

## 6. REST API Endpoints

All endpoints except `GET /api/organizations/` require the `X-Organization: <slug>` header. Missing header returns `400 Bad Request`, unknown organization returns `404 Not Found`, and records from another organization return `404 Not Found`.

| Method | Endpoint | Description | Status Codes |
|---|---|---|---|
| `GET` | `/api/organizations/` | List all available demo organizations (used by the UI tenant switcher). | `200` |
| `GET` | `/api/line-items/` | List line items for active organization, including called, funded, remaining, and status. | `200`, `400`, `404` |
| `GET` | `/api/transactions/` | List transactions newest first with nested match proposals and reasons. Supports `?status=` filter. | `200`, `400`, `404` |
| `POST` | `/api/statements/upload/` | Upload multipart CSV statement. Parses rows, validates calendar dates and Decimals, records row-level errors, deduplicates, and generates suggestions. | `200`, `400`, `404` |
| `POST` | `/api/matches/{id}/approve/` | Atomically approve match proposal: validates remaining balance, applies funding to line item, rejects transaction's other proposals, and marks transaction `reconciled`. Guarded against double funding. | `200`, `404`, `409` |
| `POST` | `/api/matches/{id}/reject/` | Reject match proposal. If transaction has no proposed matches remaining, marks transaction `needs_review`. | `200`, `404`, `409` |
| `POST` | `/api/transactions/{id}/ignore/` | Mark transaction `ignored` and reject associated matches. Returns 409 if transaction is already reconciled. | `200`, `404`, `409` |

---

## 7. Matching and Reconciliation Engine

### String Normalization Rules
1. **Reference Normalization**: Converts strings to uppercase and removes all non-alphanumeric characters (`re.sub(r'[^A-Z0-9]', '', ref.upper())`). Example: `cc-1003` $\rightarrow$ `CC1003`, `Cc 1001` $\rightarrow$ `CC1001`.
2. **Name Normalization**: Converts strings to uppercase, replaces non-alphanumerics with spaces, collapses multiple whitespace, and strips trailing corporate suffixes (`LLC`, `LP`, `LTD`, `INC`). Crucially, `TRUST` is preserved. Example: `Haller Capital LLC` $\rightarrow$ `HALLER CAPITAL`; `Patel Family Trust` $\rightarrow$ `PATEL FAMILY TRUST`.
3. **Whole-Word Matching**: An investor name is matched in the description using regex word boundaries (`\b`) to eliminate false positive partial matches.

### Matching Algorithm (Executed per Credit Row)
1. **Eligible Line Items**: Same organization, remaining amount > 0.00, and `call_date <= transaction.date` (transactions dated before call date are excluded).
2. **Reference Check**:
   - Exactly 1 match found & `amount <= remaining`: Propose match and mark transaction `suggested`.
   - Exactly 1 match found & `amount > remaining`: Mark transaction `needs_review` with an overpayment reason (0 proposals).
   - More than 1 match found: Propose all candidates and mark transaction `needs_review`.
   - If any reference match was found, skip Step 3.
3. **Name and Amount Check**:
   - Eligible line items where `amount == remaining` AND the normalized investor name is found in the description.
   - Exactly 1 match found: Propose match and mark transaction `suggested`.
   - More than 1 match found: Propose all candidates and mark transaction `needs_review`.
   - Zero matches found: Mark transaction `needs_review` with no match proposals.

---

## 8. Concurrency & Tenant Isolation Guarantees

1. **Atomic Approvals with Pessimistic Locking**:
   - `approve_match` runs in `transaction.atomic()` with `select_for_update()` on `MatchProposal`, `LineItem`, and `BankTransaction`.
   - If a line item is funded by a concurrent request, or if the transaction was already reconciled by an identical concurrent approval request, the request immediately returns **HTTP 409 Conflict**.
   - A line item can never be funded twice.
2. **Strict Tenant Isolation**:
   - Querysets are scoped by `X-Organization`.
   - Requesting an ID belonging to another tenant (for viewing, approving, rejecting, or ignoring) returns **HTTP 404 Not Found** (never 403) to prevent tenant enumeration.

---

## 9. Test Suite Mapping (Section 9 Compliance)

All 8 minimum required assessment test cases are explicitly tested in `backend/reconciliation/tests.py`:

| # | Assessment Requirement | Test Method | Result |
|---|---|---|---|
| 1 | Missing column rejects file and saves nothing | `test_req1_missing_column_rejects_file_and_saves_nothing` | Pass |
| 2 | Amount parsing: thousands separators, sign mismatches, invalid dates, Decimal type | `test_req2_amount_parsing_thousands_separators_sign_mismatch_and_decimal` | Pass |
| 3 | Duplicates: re-upload and duplicate inside one file | `test_req3_duplicates_inside_file_and_reupload` | Pass |
| 4 | Reference match: lowercase `cc1001` and partial payment | `test_req4_reference_match_including_casing_and_partial_payment` | Pass |
| 5 | Name and amount match: multiple candidates | `test_req5_name_and_amount_match_and_multiple_candidates` | Pass |
| 6 | Overpayment becomes `needs_review` with no match | `test_req6_overpayment_becomes_needs_review_with_no_match` | Pass |
| 7 | Approving updates funded amount; second approval returns `409` with no double funding | `test_req7_approving_updates_funded_and_second_approval_returns_409` | Pass |
| 8 | Organization isolation for listing and approving returns `404` | `test_req8_organization_isolation_listing_and_approving_returns_404` | Pass |

---

## 10. Optional Bonus: Airtable Integration

- Implemented in `backend/reconciliation/services/airtable_client.py`.
- Whenever a transaction is marked `needs_review`, it triggers `AirtableSyncService.sync_transaction()`.
- Stores `airtable_record_id`, `airtable_sync_status` (`not_synced`, `synced`, `sync_failed`), and `airtable_error`.
- **Fail-Safe**: If Airtable credentials are not set or the API fails, the error is recorded on the transaction and the CSV import succeeds uninterrupted.
- Designed with dependency injection (`FakeAirtableClient`) for hermetic unit testing without external network calls.

---

## 11. Screen Recording Walkthrough Script (Under 5 Minutes)

1. **Terminal**:
   - Show `docker compose ps` and run `python manage.py seed_demo` twice to demonstrate idempotency.
   - Run `python manage.py test reconciliation` to show all tests passing.
2. **Browser (`http://localhost:5173`)**:
   - **Northwind Ventures**:
     - Upload `sample_bank_statement.csv`.
     - Inspect the Import Summary: 11 imported, 1 skipped duplicate (line 11), 2 skipped errors (line 13 invalid date, line 14 negative credit).
     - Inspect the Capital Call line items table: 6 line items with open status and 0.00 funded.
     - Inspect the Transactions table:
       - Show `suggested` items with match reasons (e.g. Rahul Shah Trust CC-1002, Haller Capital partial payment).
       - Show `needs_review` items (Oakridge multiple candidates, Patel CC-1003 overpayment of $13,000 against $12,500).
     - Click **Approve** on Rahul Shah Trust ($25,000.00):
       - Notice line item CC-1002 updates live to $25,000.00 funded with status `Funded` (100% progress bar).
       - Notice the transaction changes to `Reconciled`.
   - **Organization Switcher**:
     - Switch organization to **Bluebird Capital**.
     - Notice complete tenant isolation: only Cedar Grove Fund LP (CC-2001) is displayed, and Northwind records are inaccessible.
3. **Code Tour**:
   - Quick look at `models.py`, `services/matching_engine.py`, `services/reconciliation_service.py` (atomic locking), and `tenant.py`.

---

## 12. Assumptions, Trade-offs, and Next Steps

- **Assumptions**: The CSV date format is strictly `YYYY-MM-DD`. Debits are recorded as `ignored` immediately and excluded from matching.
- **Trade-offs**: Built with synchronous processing for transparency and immediate UI feedback; transactions are calculated at import time to ensure instant responses.
- **Next Steps**:
  - Add WebSocket/SSE support for real-time multi-user live balance updates.
  - Add export capability for reconciled audit logs in PDF or CSV formats.

---

## 13. Integrity Pledge

> I completed this assessment without using AI assistance.
