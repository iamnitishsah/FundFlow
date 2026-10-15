# Digital Alpha Full Stack Intern Technical Assessment

## Bank Reconciliation for Capital Calls

| | |
|---|---|
| **Timeline** | 24 hours from receipt (about 14 to 18 focused hours, including setup) |
| **Stack** | Backend: **Django and Django REST Framework only** (no FastAPI, Flask or Node). Frontend: a React SPA (Vite recommended). Database: **PostgreSQL**, with Django migrations. |
| **AI tools** | Strictly not allowed |
| **You receive** | This document and `sample_bank_statement.csv`. There is no starter repository; setting up the project yourself is part of the task. |

If anything is unclear, make a reasonable assumption, note it in `ASSESSMENT_NOTES.md` and keep going.

---

## 1. Context

You are building one feature of a fund administration portal for General Partners (GPs) and Limited Partners (LPs). **Choose a name for the app yourself** and use it in the UI.

When a fund needs money, the GP issues a **capital call** and each LP wires its share to the fund's bank account. Bank descriptions are messy, so the GP has to work out which payment came from which LP. Your app will:

1. Import a bank statement CSV.
2. Suggest which capital call line item each incoming payment belongs to, and explain why.
3. Let the GP approve, reject or ignore each suggestion.
4. Update how much each LP has paid when a match is approved.

---

## 2. Terms

| Term | Meaning |
|---|---|
| **Organization** | One GP firm (a *tenant*). Every record belongs to one organization, and an organization must never see or change another's data. |
| **Investor entity** | The legal entity an LP invests through, such as "Patel Family Trust". This is the name the bank shows. |
| **Capital call** | A request for money, with a **call date** (when it was sent) and a **due date**. |
| **Line item** | One LP's share of one capital call. Payments are matched to line items. |
| **Expected wire reference** | A code such as `CC-1003` that LPs are asked to include in their payment. They often forget it or write it differently (`cc1003`). |
| **Amount called / funded / remaining** | What the line item asks for, what has been approved so far (starting at 0.00), and the difference between the two. |
| **Line item status** | `open` (nothing funded), `partially_funded` or `funded` (nothing remaining). |
| **Partial payment / overpayment** | A payment smaller or larger than the remaining amount. A line item can be paid in several parts, but never funded beyond its amount called. |
| **Credit / debit** | Money in (positive amount) or money out (negative amount). Only credits can pay a capital call. |
| **Bank reference** | The bank's unique ID for a transaction, such as `FT20260403A`. |
| **Duplicate** | A row whose bank reference was already imported for the same organization. |
| **Match / match reason** | A link from one transaction to one line item, with a short sentence explaining why, for example "Reference CC-1003 found; amount equals remaining 12,500.00". |

---

## 3. Seed Data

Create this data **only with a Django management command**, `python manage.py seed_demo`. Do not use fixtures loaded by hand, SQL scripts, the admin or API calls. Running the command twice must not create duplicates.

**Organizations:** `northwind` (Northwind Ventures) and `bluebird` (Bluebird Capital).

| Org | Capital call (call date, due date) | Investor entity | Reference | Amount called |
|---|---|---|---|---|
| northwind | #1 (2026-03-25, 2026-04-10) | Haller Capital LLC | CC-1001 | 27,500.00 |
| northwind | #1 | Rahul Shah Trust | CC-1002 | 25,000.00 |
| northwind | #1 | Patel Family Trust | CC-1003 | 12,500.00 |
| northwind | #1 | Meridian Partners LP | CC-1004 | 15,000.00 |
| northwind | #1 | Oakridge Holdings LLC | CC-1005 | 15,000.00 |
| northwind | #2 (2026-04-01, 2026-04-20) | Oakridge Holdings LLC | CC-1006 | 15,000.00 |
| bluebird | #1 (2026-04-01, 2026-04-15) | Cedar Grove Fund LP | CC-2001 | 40,000.00 |

All line items start `open` with an amount funded of 0.00.

---

## 4. Organization Scoping

There is no login. Choose the organization with a header: `X-Organization: northwind`.

- A missing header returns `400`, and an unknown organization returns `404`.
- Every query is scoped to that organization.
- A record from another organization returns `404`, not `403`.

---

## 5. Part 1: Import

**Import is an action in the UI.** The GP chooses a CSV file on the React page and uploads it. There are no scripts and no management commands for importing. **In the live interview, we will upload our own CSV files through your UI** to check that your solution works on files it has never seen. Build it to follow the rules below for any file, not just the sample. Files may contain a few thousand rows.

The CSV has these columns: `date,description,amount,type,reference`.

- **`date`:** `YYYY-MM-DD`, and it must be a real calendar date.
- **All fields:** trim surrounding spaces before validating.
- **`description`:** required.
- **`amount`:** may include thousands separators (`"25,000.00"`). Store it as a `Decimal`, **never a float**. Zero is invalid.
- **`type`:** `credit` or `debit` in any letter case. Credits must be positive and debits negative.
- **`reference`:** required.

**Rules:**

- A missing column rejects the whole file with a `400` and saves nothing.
- Invalid rows are skipped and reported with their file line number (the header is line 1). Valid rows are still imported.
- Duplicates are skipped and reported, including duplicates inside the same file. Two organizations may have the same bank reference.
- Debits are stored as `ignored`. Credits go through matching.

**Import summary:** return the number of rows imported, the number of duplicates, and each error with its line number and message.

---

## 6. Part 2: Matching

**Transaction status:** `suggested` (one clear match), `needs_review` (no match, several matches or an overpayment), `reconciled` (approved; final) or `ignored`.
**Match status:** `proposed`, `approved` or `rejected`.

**Normalisation:**

- **Reference:** uppercase, with everything except letters and digits removed (`cc-1003` becomes `CC1003`).
- **Name:** uppercase, with everything except letters and digits replaced by a space and repeated spaces collapsed. Then drop a trailing `LLC`, `LP`, `LTD` or `INC`. `TRUST` is kept.
- A name is **found** if it appears as whole words in the normalised description.

**Matching rule.** Apply these steps to each new credit:

1. **Eligible line items:** same organization, a remaining amount above 0.00, and a call date on or before the transaction date.
2. **Reference check.** Look for eligible line items whose normalised reference appears in the normalised description or bank reference.
   - One found, and the amount is no more than its remaining amount: create a `proposed` match and mark the transaction `suggested` (full or partial payment).
   - One found, but the amount is more than its remaining amount: create no match and mark it `needs_review` (overpayment).
   - More than one found: propose all of them and mark it `needs_review`.
   - If any were found, skip step 3.
3. **Name and amount check.** Look for eligible line items where the amount **equals** the remaining amount **and** the investor name is found.
   - One found: `suggested`.
   - More than one found: propose all of them and mark it `needs_review`.
   - None found: `needs_review` with no matches.

Store a reason for every match and for every `needs_review` transaction. Suggestions are calculated once, at import; approval re-checks the amount.

**Examples:**

| Bank row | Result |
|---|---|
| `WIRE INCOMING RAHUL SHAH TRUST REF CC-1002`, 25,000.00 | `suggested` to CC-1002, because the reference is found |
| `WIRE INCOMING PATEL FAMILY TRUST`, 12,500.00 | `suggested` to CC-1003, because the name and amount match |
| `UNKNOWN INCOMING WIRE`, 9,999.99 | `needs_review`, with no matches |

**We will test your app with CSV files you have not seen**, so do not hard-code anything about the sample file.

---

## 7. Part 3: Actions

**Design the REST API yourself** (paths, methods, request and response shapes) and list your endpoints in `ASSESSMENT_NOTES.md`. Your API must let the GP:

- List transactions with their matches and reasons, newest first.
- List line items with amount called, funded, remaining and status.
- Approve or reject a specific proposed match, and ignore a transaction.

The actions must behave exactly as follows:

- **Approve** runs in **one database transaction**:
  - It re-checks the amount against the line item's remaining amount and returns `409` if it is now too large.
  - It adds the amount to the line item's funded amount, updates the line item's status, approves the chosen match, rejects the transaction's other matches and marks the transaction `reconciled`.
  - **A line item must never be funded twice**, even if the same approval arrives twice at the same moment. The second request returns `409`.
- **Reject** marks the match `rejected`. If the transaction has no proposed matches left, it becomes `needs_review`.
- **Ignore** works on `suggested` and `needs_review` credits: it marks the transaction `ignored` and rejects its matches. On a `reconciled` transaction it returns `409`.

---

## 8. Part 4: React Page

Build one page with:

- An organization switcher.
- A CSV upload that shows the import summary and each row error.
- A transaction table: date, description, amount, status, suggested investor and reference, match reason, and the actions available for that row.
- A line item panel showing amount called, funded, remaining and status.
- Loading, empty and error states. Refresh the data after each action, and disable a button while its request is running.

Keep it simple and clear, and format amounts as money.

---

## 9. Tests (Minimum)

1. A missing column rejects the file and saves nothing.
2. Amount parsing: thousands separators, sign/type mismatches and invalid dates. The stored amount is a `Decimal`.
3. Duplicates: a re-upload and a duplicate inside one file.
4. A reference match, including `cc1001` and a partial payment.
5. A name and amount match, including the case with more than one candidate.
6. An overpayment becomes `needs_review` with no match.
7. Approving updates the funded amount. A second approval returns `409` with no double funding.
8. Organization isolation for listing and approving (`404`).

---

## 10. Bonus and Out of Scope

**Optional bonus:** after everything else works, send `needs_review` transactions to an Airtable table (free account, Personal Access Token, configured through environment variables):

- Store the record ID and a sync status (`not_synced`, `synced` or `sync_failed`).
- An Airtable failure must never break the import.
- Make the client easy to fake in tests.
- Only create records.

**Out of scope:** OAuth, webhooks, background workers, real money movement, login or roles, fuzzy matching beyond Section 6, and AI-based matching.

---

## 11. AI Policy

**Strictly no AI.** Do not use ChatGPT, Claude, Gemini, Copilot, Cursor, Windsurf or any other AI assistant for code, writing, debugging or review. Turn off AI autocomplete in your editor. Documentation and normal web search are allowed.

**In the live interview, you will make code changes to your submission while we watch.** You must understand everything you build. If you cannot explain or change your own code, the submission will not be considered. Commit in small steps, because we review your commit history.

Include this line in your notes:

> I completed this assessment without using AI assistance.

---

## 12. Deliverables

1. A GitHub repository (or zip) with the backend, the frontend and the `seed_demo` command.
2. `ASSESSMENT_NOTES.md` covering:
   - setup from a fresh clone, and a single command to run the tests
   - a `.env.example` file (no real secrets)
   - your data model and API endpoints in brief, and the app name you chose
   - any assumptions, trade-offs and next steps
   - the integrity line
3. **A screen recording (up to 5 minutes)** showing:
   - the seed command and the CSV upload
   - the import summary, suggestions and `needs_review` items
   - an approval updating a line item
   - switching organization
   - a quick tour of the code
4. **Optional:** a deployed version, for example on Render and Vercel, with the URLs in your notes. Only do this if time allows; it never replaces correctness or tests.

---

## 13. Evaluation

| Area | Weight | What we look for |
|---|---|---|
| Matching and reconciliation correctness | 30% | Rules followed exactly, including on the unseen CSV |
| Data integrity and tenant safety | 20% | Decimals, duplicate protection, atomic approvals that are safe to repeat, isolation between organizations |
| Code quality and API design | 20% | Readable code, thin views with logic in services, a clean and consistent REST API, not over-engineered |
| Tests | 15% | The eight cases above, written so they catch real bugs |
| React page | 10% | Clear, with loading, empty and error states |
| Setup and notes | 5% | Runs from a fresh clone by following your notes alone |

A strong submission is small but complete: clear suggestions, an honest `needs_review` list, correct funding updates, and no way to fund a line item twice or see another organization's data.
