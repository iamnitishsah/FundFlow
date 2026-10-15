# FundFlow

> **Intelligent Capital Call Bank Reconciliation for Private Equity & Venture Capital**

FundFlow is a modern, audit-ready reconciliation platform built for General Partners (GPs) and fund accounting teams. It automates the intake of unstructured bank statements, resolves messy wire memos to investor capital calls using deterministic multi-tier matching, and guarantees zero double-funding through pessimistic concurrency controls.

---

## The Problem: Chaos in Fund Operations

When private equity or venture capital funds issue a capital call notice to their Limited Partners (LPs), dozens or hundreds of wire transfers flood into fund bank accounts over a 10–14 day period.

In theory, LPs include a unique wire reference code. In reality:
- Banking networks truncate memos (`WIRE FRM PATEL FAM TRST CC1003`).
- Investors pay from different entity names than their registered LP entity (`Haller Capital LLC` vs. personal holding vehicles).
- Intermediary banks strip punctuation, alter casing (`cc-1001` vs `CC1001`), or insert arbitrary wire routing numbers.
- LPs send partial payments or accidental overpayments.
- Duplicate wires and debits clutter statements.

Historically, fund operations teams rely on manual spreadsheet reconciliation, creating high operational risk, delayed funding confirmations, and potential double-crediting of capital calls.

---

## The FundFlow Solution

FundFlow replaces error-prone spreadsheets with an automated, transparent reconciliation engine:

```
  ┌─────────────────────────┐
  │   Bank Statement CSV    │
  │   (Messy Wire Memos)    │
  └────────────┬────────────┘
               │
               ▼
  ┌─────────────────────────┐      ┌─────────────────────────┐
  │  Multi-Tenant Scoping   │ ───► │ Quality Control Engine  │
  │   (Strict Isolation)    │      │ (Validates, Deduplicates│
  │                         │      │  & Routes Debits)       │
  └─────────────────────────┘      └────────────┬────────────┘
                                                │
                                                ▼
  ┌──────────────────────────────────────────────────────────┐
  │            Deterministic 3-Tier Matching Engine          │
  │                                                          │
  │   1. Normalized Reference Match (e.g. 'cc1001' ➜ CC-1001)│
  │   2. Normalized Name + Exact Amount Match                │
  │   3. Overpayment & Multi-Candidate Detection             │
  └─────────────────────────────┬────────────────────────────┘
                                │
                 ┌──────────────┴──────────────┐
                 ▼                             ▼
     ┌───────────────────────┐     ┌───────────────────────┐
     │   Suggested Matches   │     │     Needs Review      │
     │  (Clear Explanations) │     │ (Overpayments/Unknown)│
     └───────────┬───────────┘     └───────────┬───────────┘
                 │                             │
                 ▼                             ▼
     ┌───────────────────────┐     ┌───────────────────────┐
     │  One-Click Approval   │     │ Fail-Safe Airtable    │
     │ (Pessimistic Locking  │     │ Exception Sync        │
     │  & Anti-Double-Fund)  │     │                       │
     └───────────────────────┘     └───────────────────────┘
```

---

## Core Features & Business Capabilities

### 1. Multi-Tenant Fund Boundary
- **Isolated GP Environments**: Supports multiple distinct fund organizations (e.g. *Northwind Ventures* and *Bluebird Capital*) from a single deployment.
- **Tenant Privacy Guarantee**: Every record is scoped by tenant. Cross-tenant queries return `404 Not Found` (never `403 Forbidden`) to eliminate resource enumeration risks.

### 2. Resilient Statement Ingestion
- **Header & Schema Defense**: Rejects files missing mandatory columns and protects against partial database writes.
- **Calendar & Type Validation**: Detects leap-year anomalies, impossible dates (e.g., `2024-02-30`), and malformed decimals.
- **Smart Deduplication**: Flags duplicates occurring within the same CSV as well as duplicates previously imported into the database.
- **Debit Classification**: Automatically tags outgoing debit items (e.g. bank wire fees) as `ignored` to keep reconciliation feeds focused on capital inflows.

### 3. Explainable 3-Tier Matching Engine
FundFlow eliminates guesswork by explaining *why* every single match was suggested:
- **Reference Normalization**: Strips hyphens, whitespace, and punctuation, comparing normalized strings in uppercase (`cc-1001` matches `CC1001`).
- **Entity Name Sanitization**: Cleans corporate prefixes/suffixes (`LLC`, `LP`, `LTD`, `INC`) while carefully preserving family trusts (`TRUST`).
- **Word-Boundary Matching**: Uses word boundary regex (`\b`) to ensure short entity names (e.g., `Oak`) do not generate false positive substring matches against unrelated entities (e.g., `Oakridge`).
- **Notice Date Verification**: Excludes historical transactions that cleared before the capital call notice date.
- **Overpayment Guard**: If an investor wires an amount exceeding their outstanding balance (e.g., $13,000 for a $12,500 call), FundFlow flags it as `Needs Review` rather than auto-applying an invalid balance.

### 4. Pessimistic Concurrency & Double-Funding Defense
Fund operations often involve multiple team members reconciling simultaneous statement uploads:
- **Database Row Locks (`select_for_update`)**: Match approvals acquire exclusive pessimistic locks across `MatchProposal`, `LineItem`, and `BankTransaction` within an atomic transaction.
- **409 Conflict Protection**: If two operators click approve simultaneously, or if a line item's remaining balance is depleted by a concurrent transaction, the system returns an immediate `409 Conflict`, guaranteeing that a capital call line item can never be funded twice.

### 5. Portfolio Status Dashboard
- **Real-Time Capital Tracking**: Visual progress bars and metric badges display Called, Funded, and Remaining balances across all issued line items.
- **Categorized Feed**: Filter bank transactions instantly across `Suggested`, `Needs Review`, `Reconciled`, and `Ignored`.
- **Audit Traceability**: View raw statement line numbers, full original memo text, and proposal generation timestamps.

### 6. Airtable Exception Sync (Bonus Integration)
- Whenever a transaction is flagged as `Needs Review` (due to an overpayment, ambiguous name match, or missing reference), FundFlow automatically syncs the exception to an external Airtable base.
- **Non-blocking Resiliency**: If Airtable credentials are unavailable or the third-party API is temporarily unreachable, the incident is recorded on the transaction without interrupting the core CSV import.

---

## User Workflow & Experience Showcase

### Step 1: Fund Selection & Overview
Upon loading the dashboard, fund accountants select their active fund organization (*Northwind Ventures* or *Bluebird Capital*). The Capital Calls panel immediately surfaces all issued line items, investor entities, called amounts, and real-time funding statuses.

### Step 2: Upload Bank Statement
Upload any raw CSV bank statement. FundFlow validates the file structure and displays an import summary modal detailing:
- Number of successfully ingested credits.
- Skipped duplicate wire references (in-file and cross-batch).
- Skipped malformed rows (with line numbers and specific failure reasons).

### Step 3: Review Match Suggestions
Transactions appear in the reconciliation table with visual state badges:
- **Suggested**: Displays high-confidence matches with plain-language explanations (e.g. *"Exact wire reference match: 'CC-1001'"* or *"Matched investor name 'Haller Capital' and remaining amount $25,000.00"*).
- **Needs Review**: Highlights transactions requiring human decisions (e.g. *"Overpayment: Wire amount $13,000.00 exceeds remaining line item balance $12,500.00"* or *"Multiple potential line items match this transaction"*).
- **Ignored**: Shows outgoing debit transfers and manually dismissed items.

### Step 4: One-Click Reconcile
Clicking **Approve** on a suggested match:
1. Atomically deposits the transaction amount into the line item's funded balance.
2. Updates line item status (`open` $\rightarrow$ `partially_funded` $\rightarrow$ `funded`).
3. Closes out the bank transaction as `reconciled`.
4. Automatically dismisses any competing candidate proposals.

---

## Matching Logic Rules Summary

| Case | Scenario | Engine Action | Resulting Status |
|---|---|---|---|
| **A** | Exactly 1 reference match & Amount $\le$ Remaining | Suggests match with reference explanation | `suggested` |
| **B** | Exactly 1 reference match & Amount $>$ Remaining | Flags overpayment; suppresses proposal | `needs_review` |
| **C** | Multiple reference matches found | Proposes all candidates for human selection | `needs_review` |
| **D** | Name match + Exact remaining amount & 1 candidate | Suggests match with name and amount explanation | `suggested` |
| **E** | Name match + Exact remaining amount & multiple candidates | Proposes all candidates for human selection | `needs_review` |
| **F** | No reference and no name matches | Flags unknown wire for manual investigation | `needs_review` |
| **G** | Debit transaction (negative amount) | Flags as debit fee/outgoing wire | `ignored` |

---

## Technology Stack

- **Backend**:
  - **Django 6.1 & Django REST Framework**: Robust API architecture, ORM, and serializers.
  - **PostgreSQL 16**: Relational ACID database with row-level locking (`select_for_update`).
  - **Docker Compose**: Containerized database and backend services.
- **Frontend**:
  - **React 19**: Modern component architecture with optimistic client state updates.
  - **TypeScript**: Strict type safety with `verbatimModuleSyntax` compliance.
  - **Tailwind CSS v4**: Utility-first styling with high-density financial data layouts.
  - **Vite**: Ultra-fast build pipeline and development server with reverse API proxy.
  - **Lucide Icons**: Clean iconography for financial data states.

---

## Quickstart Showcase

### 1. Launch Services (Docker)
```bash
cp .env.example backend/.env
docker compose -f backend/docker-compose.yml up -d
docker compose -f backend/docker-compose.yml exec web python manage.py migrate
docker compose -f backend/docker-compose.yml exec web python manage.py seed_demo
```

### 2. Launch Frontend
```bash
npm --prefix frontend install
npm --prefix frontend run dev
```
Open **`http://localhost:5173`** to access the FundFlow dashboard.

### 3. Run Automated Verification
Execute the test suite covering multi-tenant isolation, matching heuristics, and concurrency locking:
```bash
docker compose -f backend/docker-compose.yml exec web python manage.py test reconciliation
```

---

## Project Documentation Directory

- **Technical Assessment & Verification**: [`ASSESSMENT_NOTES.md`](file:///Users/iamnitishsah/Documents/Projects/FundFlow/ASSESSMENT_NOTES.md)
- **Detailed Backend REST API Reference**: [`backend/API_DOCUMENTATION.md`](file:///Users/iamnitishsah/Documents/Projects/FundFlow/backend/API_DOCUMENTATION.md)
- **Sample Bank Statement for Demo**: [`sample_bank_statement.csv`](file:///Users/iamnitishsah/Documents/Projects/FundFlow/sample_bank_statement.csv)
