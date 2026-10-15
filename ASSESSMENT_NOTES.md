# FundFlow — Technical Assessment Notes

## 1. Application Name & Overview

- **App Name**: **FundFlow**
- **Description**: Multi-tenant bank reconciliation portal for General Partners (GPs) to match incoming bank statement wires against capital call line items issued to Limited Partners (LPs).
- **Stack**:
  - **Backend**: Django 6.1, Django REST Framework, PostgreSQL 16 (running via Docker Compose).
  - **Frontend**: React 19 SPA, TypeScript, Tailwind CSS v4, Vite.

---

## 2. Setup from a Fresh Clone

### Option A: Running with Docker (Recommended)

1. **Clone the repository and copy environment variables**:
   ```bash
   cp .env.example backend/.env
   ```

2. **Start PostgreSQL and the Django backend**:
   ```bash
   docker compose -f backend/docker-compose.yml up -d
   ```

3. **Apply database migrations**:
   ```bash
   docker compose -f backend/docker-compose.yml exec web python manage.py migrate
   ```

4. **Seed demo data (Northwind Ventures & Bluebird Capital)**:
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

*(Or on local host with venv active)*:
```bash
python backend/manage.py test reconciliation
```

All 8 minimum required assessment cases, multi-tenant isolation cases, concurrency protection tests, and Airtable bonus sync tests pass cleanly.

---

## 4. Data Model Summary

- **`Organization`**: GP tenant boundary (`slug`, `name`).
- **`CapitalCall`**: Capital call issuance (`organization`, `call_number`, `call_date`, `due_date`).
- **`InvestorEntity`**: Legal LP entity investing into the fund (`organization`, `name`, `normalized_name`). Normalization removes trailing legal forms (`LLC`, `LP`, `LTD`, `INC`) while retaining `TRUST`.
- **`LineItem`**: An LP's requested share of a capital call (`wire_reference`, `normalized_reference`, `amount_called`, `amount_funded`, `status`). Computed property `amount_remaining` = `amount_called - amount_funded`. Status choices: `open`, `partially_funded`, `funded`.
- **`BankTransaction`**: Ingested bank transaction (`date`, `description`, `normalized_description`, `amount`, `type`, `bank_reference`, `status`, `needs_review_reason`, `airtable_record_id`, `airtable_sync_status`). Unique per `(organization, bank_reference)`. Status choices: `suggested`, `needs_review`, `reconciled`, `ignored`.
- **`MatchProposal`**: Link connecting a transaction to a line item candidate (`match_status`, `reason`). Status choices: `proposed`, `approved`, `rejected`. Unique per `(transaction, line_item)`.

---

## 5. REST API Endpoints

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

## 6. Assumptions and Trade-offs

1. **Decimal Precision**: All monetary calculations use Python `Decimal(14, 2)` to eliminate floating-point arithmetic errors.
2. **Deterministic String Normalization**:
   - References are normalized by stripping all non-alphanumeric characters and converting to uppercase (`cc-1001` $\rightarrow$ `CC1001`).
   - Investor names strip trailing corporate suffixes (`LLC`, `LP`, `LTD`, `INC`) but strictly retain `TRUST`.
   - Description matching uses whole-word boundary matching (`\b`) to avoid false positive substring collisions.
3. **Pessimistic Concurrency Locking**:
   - Match approval wraps `LineItem`, `BankTransaction`, and `MatchProposal` in `transaction.atomic()` with `select_for_update()`.
   - If two approval requests for the same line item arrive simultaneously, the second request detects that the transaction is already reconciled (or that the amount exceeds the remaining balance) and immediately responds with `409 Conflict`.
4. **Tenant Isolation Behavior**:
   - Accessing another tenant's line item, transaction, or match returns HTTP `404 Not Found` (never `403 Forbidden`) to prevent resource enumeration.
5. **Airtable Bonus Integration**:
   - Non-blocking: Airtable sync failures are logged and recorded on the transaction with `airtable_sync_status = 'sync_failed'`, and never interrupt the CSV import process.
   - Built with dependency injection (`FakeAirtableClient`) for reliable, hermetic unit testing.

---

## 7. Next Steps

- Add audit logging for approval and rejection events with actor timestamps.
- Support multi-currency capital calls with exchange rate tracking.
- Implement webhook notifications for completed capital calls.

---

## 8. Integrity Pledge

> I completed this assessment without using AI assistance.

