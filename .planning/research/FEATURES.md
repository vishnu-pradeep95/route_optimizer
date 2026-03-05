# Feature Research

**Domain:** Office-ready deployment — one-command install, daily startup UX, CSV format documentation, non-technical user error messages
**Researched:** 2026-03-04
**Confidence:** HIGH (codebase thoroughly analyzed; existing scripts audited; target user pattern well-understood from DEPLOY.md and PROJECT.md)

---

## Context: What Already Exists (v1.2 Complete)

This is the v1.3 milestone on a working, deployed system. These deployment artifacts are ALREADY SHIPPED and must NOT be rebuilt:

- `scripts/install.sh` — interactive env setup, docker compose build, OSRM data, health check with 5-minute timeout
- `scripts/deploy.sh` — production deployment with backup, migrations, health check
- `DEPLOY.md` — office employee guide with daily workflow, CDCMS export instructions, troubleshooting section
- `README.md` — developer reference with architecture overview, API table, CSV format docs
- `SETUP.md` — developer setup (WSL, Docker, Python venv, migrations)
- CDCMS auto-detection in API upload endpoint (`cdcms_preprocessor.py`)
- Standard CSV/Excel upload with flexible column mapping (`csv_importer.py`)
- Geocoding failure reporting with per-row reasons, duplicate detection, cost tracking

**The gap for v1.3:** The daily startup still requires 3 manual bash commands (`sudo service docker start`, `docker compose up -d`, `source .venv/bin/activate`). README has stale container names (`routing-db` vs actual `lpg-db`, `routeopt` vs actual `routing`). The `<REPO_URL>` placeholder in README and DEPLOY.md is never filled in. CSV format documentation is scattered across README, DEPLOY.md, and source code — an office employee cannot find all constraints in one place. Error messages from the API are developer-facing (stack traces, Python exceptions) rather than office-staff-facing ("Your CDCMS file is missing the OrderNo column").

---

## Feature Landscape

### Domain 1: One-Command Daily Startup

#### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Single script for daily startup** | Office staff follow printed checklists. 3 separate bash commands with `sudo` prompts is not a checklist — it's a debugging session waiting to fail. Any tool targeting non-technical users (VPN clients, database GUIs, WAMP/XAMPP) provides a single "Start" button or script. | LOW | New `scripts/start.sh`: `sudo service docker start`, `docker compose up -d`, health check poll, print URLs on success. Idempotent — safe to run if already running. Exits with clear message if already healthy. |
| **Success output with actionable URLs** | `install.sh` already does this well at the end of installation — shows dashboard URL, driver URL, daily workflow in a box. Daily `start.sh` should do the same. Without this, staff open Chrome and type the URL from memory (error-prone). | LOW | Print the same "what to open next" block that `install.sh` shows: Dashboard URL, Driver App URL, "Upload your CDCMS file" next step. |
| **Non-zero exit code with human-readable reason on failure** | If Docker is not installed or the compose file is missing, the script must fail with a plain-English message and a recovery action. `docker: command not found` is not actionable for a non-technical user. | LOW | Existing `install.sh` already has `require_cmd()` with install hints. Copy that pattern to `start.sh`. |
| **Idempotent re-run behavior** | Staff may run the start script twice. On the second run, Docker is already started and containers are already up. The script must handle this gracefully (not fail with "port already in use" or "already running"). | LOW | `docker compose up -d` is already idempotent. For `sudo service docker start`: check `docker info` first; skip if daemon responds. |

#### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Docker auto-start without password prompt** | `sudo service docker start` requires the WSL user's password every time. This is a friction point for non-technical staff. Auto-starting Docker on WSL login (via `.bashrc`) removes a required manual step. | LOW | Add `sudo service docker start 2>/dev/null` to `~/.bashrc` inside the installer if the user opts in. Already mentioned in SETUP.md as a tip. Promote it to install.sh — ask the user during setup: "Start Docker automatically when Ubuntu opens? [Y/n]". |
| **Status command showing all services** | Staff sometimes wonder if the system is running without trying to open the dashboard. A quick `scripts/status.sh` that runs `docker compose ps` and hits `/health` gives them confidence. | LOW | A 15-line wrapper around `docker compose ps` + `curl /health`. Prints "System is running" or lists which containers are down. |
| **Graceful timeout feedback during startup** | `docker compose up -d` returns immediately but OSRM takes time to load maps. `install.sh` has a 5-minute health poll with a spinner. `start.sh` should have the same (but with a 60-second timeout, not 5 minutes — on subsequent starts OSRM is already preprocessed and boots in ~15 seconds). | LOW | Reuse the spinner loop from `install.sh`. Poll `http://localhost:8000/health` for 60 seconds. On timeout, print "Still starting — check logs with: docker compose logs -f api". |

#### Anti-Features (Do NOT Build)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **GUI launcher (Electron/Tauri app)** | "Make it feel like a real application" | Building a native app to launch a bash script is massive scope creep. Adds a separate build system, packaging pipeline, and update mechanism to a project that is already a Docker stack. | Shell script + desktop shortcut. On Windows, a `.bat` file or WSL shortcut can launch Ubuntu + run the script. The "app" is Chrome opening `localhost:8000`. |
| **Windows batch file or PowerShell wrapper** | "Staff shouldn't have to open Ubuntu" | WSL2 integration complexity. WSL has its own network, file system, and process space. Cross-WSL script invocation is fragile (different path conventions, credential prompts). | DEPLOY.md instructs: "Open Ubuntu from Start menu". This is the established and working pattern. Add a desktop shortcut to Ubuntu as a differentiator, not a batch file. |
| **Automatic Docker restart on WSL launch** | "I don't want to run any command at all" | systemd in WSL2 is supported only on Ubuntu 22.04+ with WSL version 0.67.6+. Many office laptops may be on older WSL. Auto-start via systemd would silently fail on older systems. | Offer `~/.bashrc` auto-start (explicit opt-in during install). Document it clearly. Do not depend on systemd. |

---

### Domain 2: CSV Format Documentation

#### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Single-page CSV format reference** | Currently CSV documentation is split across: README.md (developer tables), DEPLOY.md (office narrative), `csv_importer.py` docstring (code comments), and `cdcms_preprocessor.py` (inline). An office employee who gets a "missing column" error cannot find all constraints in one place. Every SaaS product (Airtable, Mailchimp, Stripe) has a single CSV import specification page. | LOW | New `CSV_FORMAT.md` at project root. Covers both formats: CDCMS (tab-separated, 19 columns, 6 used) and generic CSV (11 possible columns, 1 required). Self-contained — someone can print it and use it without looking at other docs. |
| **"What happens if I..." rejection reason table** | The API already generates per-row validation errors with human-readable messages. But there is no doc that tells an office employee in advance: "If OrderStatus is not 'Allocated-Printed', the row is skipped — this is normal." Pre-explaining expected rejections prevents support calls. | LOW | Section in `CSV_FORMAT.md`: "Common Rejection Reasons and What They Mean". Table: error message → plain-English explanation → what to do. Cover: missing required column, empty address, wrong status, duplicate order ID, non-numeric quantity. |
| **Sample CDCMS row with before/after address cleaning** | DEPLOY.md has a brief table showing address cleaning steps. But office staff need to understand WHY rows are rejected vs. just cleaned. A worked example with the actual sample data (already in `data/sample_cdcms_export.csv`) makes this concrete. | LOW | Already partially done in DEPLOY.md Section 5. Consolidate in `CSV_FORMAT.md` with a side-by-side table for at least 3 real examples from `data/sample_cdcms_export.csv`. |
| **Column constraint specification** | `csv_importer.py` ColumnMapping documents column names. But constraints (valid values for `cylinder_type`, max value for `priority`, expected format for `delivery_window_start`) are only in code. Office staff uploading a manually-crafted CSV need to know these. | LOW | Column reference table in `CSV_FORMAT.md`: name, type, required/optional, valid values, example. For CDCMS format: which 6 of 19 columns are used, what each does. |
| **Excel file support documented** | The API accepts `.xlsx` and `.xls` files (handled in `_read_cdcms_file()` and `CsvImporter._read_file()`). This is not documented anywhere in user-facing docs. Office staff who save CDCMS export as Excel and get an error will assume Excel is unsupported. | LOW | Add explicit note in `CSV_FORMAT.md` and relevant DEPLOY.md sections: "Excel files (.xlsx) are supported — you do not need to convert to CSV." |
| **Tab-separated vs comma-separated behavior documented** | The CDCMS preprocessor tries tab-separated first, falls back to comma-separated. This auto-detection is silently correct in normal use, but if an office employee manually edits the file in Excel (which re-saves as comma-separated), the system still works — they don't know why. | LOW | One sentence in `CSV_FORMAT.md`: "CDCMS exports are tab-separated. If you open and save the file in Excel, it may become comma-separated — that's fine, the system handles both." |

#### Differentiators (Competitive Advantage)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Printable one-page CSV cheat sheet** | Office staff often print reference cards and tape them near the printer or computer. A condensed reference: "CDCMS columns used: OrderNo, OrderStatus, ConsumerAddress, OrderQuantity, AreaName, DeliveryMan. Status must be: Allocated-Printed." Fits on half an A4 sheet. | LOW | Last section of `CSV_FORMAT.md` with `@media print` friendly layout. Or a separate "quick reference" block (the format DEPLOY.md uses at the end). |
| **Error message glossary** | The upload endpoint returns structured JSON errors. The dashboard shows them. But terms like "geocoding failure", "row rejected", "cache miss" are technical. A glossary with plain-English definitions builds trust with non-technical users. | LOW | Section in `CSV_FORMAT.md` or `DEPLOY.md`: "What do these messages mean?" Map technical terms to English. Example: "geocoding failure" → "We couldn't find this address on Google Maps. Check the ConsumerAddress field in CDCMS for typos." |
| **Address cleaning worked examples beyond what's in DEPLOY.md** | DEPLOY.md shows 8 address cleaning examples. The actual preprocessor has 10 cleaning steps covering cases like PO. concatenation (`KUNIYILPO.` → `Kuniyil P.O.`) and CDCMS backtick markers (`` ``THANAL`` `` → `Thanal`). Documenting all 10 with real examples shows office staff why some addresses auto-fix and others don't. | LOW | Extend the address cleaning table with the 2 missing cases. Pull directly from `cdcms_preprocessor.py` comments which already document every step with before/after examples. |

#### Anti-Features (Do NOT Build)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Interactive CSV validator web page** | "Let staff validate the file before uploading" | The API upload endpoint already validates on upload and returns row-level errors. A separate validator duplicates this logic and creates a two-step workflow (validate, then upload). | The dashboard upload UI already shows validation errors inline. Improve the error display (plain-English messages), not the validation location. |
| **Column mapping UI (drag columns to fields)** | "What if CDCMS changes column names?" | CDCMS is an HPCL system with fixed column names. If they change, it's a code update, not a user configuration. Column mapping UI is the right solution for generic import tools (like Airtable or Mailchimp), not for a single-customer system with one known data format. | Update `cdcms_preprocessor.py` constants when CDCMS changes column names. Document in `CSV_FORMAT.md` that column names are fixed and known. |
| **Auto-detect delimiter (beyond what already exists)** | "The file might use semicolons" | CDCMS exports are exclusively tab-separated. The current tab→comma fallback already covers the edge case of Excel re-saves. Adding semicolon detection or full RFC 4180 sniffing adds complexity for zero real-world value. | Document the tab/comma fallback in `CSV_FORMAT.md`. Current behavior is correct for all known inputs. |

---

### Domain 3: README Accuracy

#### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Correct container names in README** | README.md (line 404) documents container name `routing-db` and health check user `routeopt`. Actual docker-compose.yml has `container_name: lpg-db` and the DB user in `.env.example` is `routing`. Developers hitting "container not found" errors because of stale docs are a support burden. | LOW | Find/replace stale names. Run `grep -n "routing-db\|routeopt" README.md` and fix. Also fix `POSTGRES_USER` discrepancy ("Defaults to `routing`" is correct in env var table but `routeopt` appears in health check example). |
| **Filled-in REPO_URL placeholder** | README.md line 15 and DEPLOY.md Step 2.3 both have `git clone <REPO_URL>`. This placeholder is never substituted. A non-technical user copy-pasting this command gets a git error. | LOW | Replace `<REPO_URL>` with the actual repository URL. If the repo is private, replace with a generic instruction: "Ask your technical contact for the repository URL." |
| **Remove manual steps now automated by install.sh** | README Quick Start (lines 14-50) still shows `python3 -m venv .venv`, `pip install -r requirements.txt`, `alembic upgrade head` as manual steps. These are now handled by `install.sh`. Developer-facing README can keep these for development context, but the Quick Start section should lead with `./scripts/install.sh`. | LOW | Rewrite Quick Start to lead with `./scripts/install.sh` for office users. Retain manual steps in a collapsible "For developers" section below. |
| **Accurate Docker service table** | README documents 4 services: `routing-db`, `osrm-kerala`, `vroom-solver`, `lpg-api`. Actual container names from docker-compose.yml: `lpg-db`, `osrm-kerala` (correct), `vroom-solver` (correct), `lpg-api` (correct). Only `routing-db` is wrong. | LOW | Fix the one wrong container name. Also verify the health check commands in the table match actual working commands. |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Link to CSV_FORMAT.md from README and DEPLOY.md** | When CSV_FORMAT.md is written, README and DEPLOY.md should cross-reference it. Right now CSV format docs are inline in README. After the refactor, the inline docs can be abbreviated with "See CSV_FORMAT.md for full column reference." | LOW | Update README line ~218: "See [CSV_FORMAT.md](CSV_FORMAT.md) for the complete column reference and address cleaning documentation." |
| **Version badge and last-updated date** | README has no version indicator. Developers and staff cannot tell if they have current documentation. A simple `**Version: v1.3**` at the top and "Last updated: 2026-03-04" gives document confidence. | LOW | Add to README preamble. Update it as part of the milestone completion checklist. |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Auto-generate README from code** | "Keep docs in sync with code automatically" | Auto-generated README lacks the narrative context (Kerala business rules, architecture decisions, safety constraints) that makes this README useful. Auto-generated API docs already exist at `/docs` (FastAPI/Swagger). | Keep README hand-maintained. Add to contributing guidelines: "Update README when adding new endpoints or changing container names." |
| **Separate README per audience (developer vs office)** | "Developers and office staff need different docs" | Already solved: README.md → developer, DEPLOY.md → office staff. Adding a third README file fragments documentation and creates 3 sources of truth to maintain. | Improve README Quick Start to route readers immediately ("Employee? See DEPLOY.md"). Already done (line 7 of README). Just ensure the cross-link is prominent and accurate. |

---

### Domain 4: Non-Technical Error Messages

#### Table Stakes (Users Expect These)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Upload error messages in plain English** | The API returns structured JSON errors with message fields. Currently those messages are developer-facing: `"CDCMS export is missing required columns: {'OrderNo'}. Found columns: [...]"`. A non-technical user reading "Found columns: [...]" doesn't know what to do. Every consumer-facing SaaS (Mailchimp, Airtable) translates import errors into "Column 'Name' is missing — check that your file has a header row." | MEDIUM | The message text is already parameterized in `cdcms_preprocessor.py` `_validate_cdcms_columns()` and `csv_importer.py` `_validate_columns()`. Update the message strings to plain English. No architecture change needed — the message field is already surfaced in the dashboard UI's ImportSummary component. |
| **Geocoding failure message explains next step** | Current geocoding failure message: `"Geocoding failed for row 7: REQUEST_DENIED"`. A non-technical user doesn't know what `REQUEST_DENIED` means. The expected message: `"Could not find GPS coordinates for address in row 7. Check the ConsumerAddress in CDCMS for typos. If the address looks correct, the Google Maps API key may need renewal."` | MEDIUM | Wrap Google Maps API error codes (`REQUEST_DENIED`, `ZERO_RESULTS`, `OVER_DAILY_LIMIT`) into plain-English messages in `core/geocoding/google_adapter.py`. The message field already flows to the dashboard — this is a string change, not an API change. |
| **Empty file error message** | If staff upload a 0-byte file or an empty CSV (headers only, no data rows), the current error is a Python stack trace or generic "no orders". Expected: `"The uploaded file appears empty. Export a new file from CDCMS and try again."` | LOW | Already partially handled in `_validate_cdcms_columns()` (checks for empty address column). Add explicit empty-file check at the start of the upload pipeline. |
| **Wrong file type message** | If staff accidentally upload a PDF or image (it happens), the API returns HTTP 422 Unprocessable Entity with a cryptic Pydantic error. Expected: `"This file type is not supported. Upload a CSV file (.csv) or Excel file (.xlsx) exported from CDCMS."` | LOW | Add file extension check at the start of the upload endpoint before passing to the preprocessor. Return HTTP 400 with a plain-English message. |

#### Differentiators

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **"Did you mean...?" suggestions for column name mismatches** | If the file has `Order_No` instead of `OrderNo`, instead of "missing required column OrderNo", show: `"Column 'OrderNo' not found. Your file has 'Order_No' — this looks like it might be a renamed CDCMS column. Try re-exporting from CDCMS without renaming columns."` | LOW | Fuzzy column matching for error messages ONLY (not for silent auto-fixing — that's an anti-feature). Compute Levenshtein distance between "OrderNo" and each found column. If distance ≤ 2, include the suggestion in the error message. |
| **Structured error response with remediation steps** | Current API returns `{"detail": "error message"}`. A richer format: `{"error": "missing_column", "column": "OrderNo", "message": "...", "docs": "See CSV_FORMAT.md#required-columns"}` gives the dashboard enough structure to show a "How to fix this" button. | MEDIUM | New `UploadError` Pydantic model with `error_code`, `message`, `remediation` fields. Return from upload endpoint instead of bare `HTTPException`. Dashboard shows the remediation step next to the error. Requires dashboard UI change to use the new field. |

#### Anti-Features

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **Auto-correct column names** | "If OrderNo is renamed, map it automatically" | Auto-correction creates ambiguity: if the user uploaded the wrong file entirely (not a CDCMS export), auto-mapping would silently produce wrong results. Data integrity matters more than convenience for a delivery routing system. | Report mismatches with a "Did you mean...?" suggestion in the error message. Let the user re-export correctly from CDCMS. |
| **Inline address editor in dashboard** | "Let staff fix addresses without going back to CDCMS" | Editing addresses in the dashboard creates a divergence between CDCMS (the source of truth) and the route optimizer. When staff re-upload tomorrow, the manually-fixed addresses are gone. | Fix addresses in CDCMS. Document in `CSV_FORMAT.md` and `DEPLOY.md` that address corrections should be made in CDCMS. |

---

## Feature Dependencies

```
[scripts/start.sh]
    +-- requires --> [scripts/install.sh health check pattern (reuse)]
    +-- enables --> [Docker auto-start in ~/.bashrc (opt-in from install.sh)]
    +-- enables --> [scripts/status.sh (simple wrapper)]

[CSV_FORMAT.md]
    +-- requires --> [Address cleaning examples (from cdcms_preprocessor.py docstrings)]
    +-- requires --> [Column constraints (from csv_importer.py ColumnMapping)]
    +-- enables --> [README cross-link update]
    +-- enables --> [DEPLOY.md cross-link update]
    +-- enables --> [Error message glossary (reuse content)]

[README accuracy fixes]
    +-- requires --> [docker-compose.yml audit (container names)]
    +-- requires --> [.env.example audit (POSTGRES_USER, POSTGRES_DB defaults)]
    +-- independent-of --> [CSV_FORMAT.md (can be done in any order)]

[Plain-English error messages]
    +-- requires --> [CSV_FORMAT.md (for remediation links in error text)]
    +-- requires --> [Audit of all error message strings in upload pipeline]
    +-- independent-of --> [start.sh]

[Structured error response (UploadError model)]
    +-- requires --> [Plain-English error messages (content prerequisite)]
    +-- requires --> [Dashboard UI update to use new error_code + remediation fields]
```

### Dependency Notes

- **`start.sh` is fully independent.** It can be written before any doc work. It has no dependencies on CSV_FORMAT.md or error message changes.
- **`CSV_FORMAT.md` should be written before README updates.** README can then just link to it rather than embedding the full table inline.
- **Plain-English error messages are independent of the structured UploadError model.** Improving the message strings is a LOW complexity change that can ship first. The structured model (with `error_code` and `remediation` fields) is a MEDIUM complexity change that requires both API and dashboard changes.
- **README accuracy is fully independent of all other features.** Fix container names and REPO_URL placeholder in any order.

---

## MVP Definition

### Must Ship in v1.3 (P1)

These directly address the milestone goals stated in PROJECT.md:

- [ ] **`scripts/start.sh`** — single command for daily startup: start Docker, start containers, health check, print URLs. This is the core UX improvement for office staff.
- [ ] **`CSV_FORMAT.md`** — consolidated single-page reference for both CDCMS and generic CSV formats, column constraints, rejection reasons, address cleaning examples.
- [ ] **README container name fixes** — `routing-db` → `lpg-db`, `routeopt` → `routing` in health check examples. Stale docs cause support overhead.
- [ ] **`<REPO_URL>` placeholder filled** — both README.md and DEPLOY.md. Non-technical users cannot follow setup without a real URL.
- [ ] **Plain-English error messages in upload pipeline** — at minimum: missing column, empty file, wrong file type. These are the three most common error cases for office staff.

### Should Have (P2 — add during v1.3 if time permits)

- [ ] **`scripts/status.sh`** — `docker compose ps` wrapper with health check. Gives staff a "is it running?" command without asking a developer.
- [ ] **Docker auto-start opt-in in `install.sh`** — eliminates `sudo service docker start` from daily routine.
- [ ] **Geocoding error messages plain-English** — translate `REQUEST_DENIED`, `ZERO_RESULTS` to staff-facing language.
- [ ] **`CSV_FORMAT.md` linked from README and DEPLOY.md** — cross-links to avoid duplication.
- [ ] **"Did you mean...?" column name suggestion** — fuzzy match in error messages for slightly-wrong column names.
- [ ] **Address cleaning examples expanded to all 10 steps** — currently 8 of 10 steps are documented in DEPLOY.md.

### Future Consideration (v1.4+)

- [ ] **Structured UploadError model** — `error_code` + `remediation` fields — requires coordinated API + dashboard change.
- [ ] **Desktop shortcut for Ubuntu** — `.desktop` file or Windows shortcut for "Start Route Optimizer".
- [ ] **`scripts/status.sh` with per-service breakdown** — shows which containers are healthy vs. not, with suggested fixes.
- [ ] **Error message glossary page** — if office staff report confusion with specific terms.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| `scripts/start.sh` | HIGH | LOW | P1 |
| `CSV_FORMAT.md` | HIGH | LOW | P1 |
| README container name fixes | MEDIUM | LOW | P1 |
| `<REPO_URL>` placeholder filled | HIGH | LOW | P1 |
| Plain-English error messages (upload) | HIGH | LOW | P1 |
| `scripts/status.sh` | MEDIUM | LOW | P2 |
| Docker auto-start opt-in | MEDIUM | LOW | P2 |
| Geocoding error plain-English | MEDIUM | LOW | P2 |
| CSV_FORMAT.md cross-links | LOW | LOW | P2 |
| "Did you mean...?" column suggestions | MEDIUM | LOW | P2 |
| Address cleaning examples (2 remaining) | LOW | LOW | P2 |
| Structured UploadError model | MEDIUM | MEDIUM | P3 |
| Desktop shortcut | LOW | LOW | P3 |

**Priority key:**
- P1: Must have for v1.3 milestone completion — makes the system office-ready
- P2: Should have, add during v1.3 if time permits
- P3: Nice to have, defer to v1.4+

---

## Reference: What Good Looks Like in Each Area

### One-Command Startup (Industry Standard)

XAMPP, WAMP, and Laragon set the bar for local development tool startup UX for non-technical users:
- Single launcher: double-click or one command
- Green/red status indicators per service
- Direct links to dashboard in the output
- Graceful handling of "already running" without errors

`scripts/start.sh` should reach this level within the constraints of WSL2 bash.

### CSV Documentation (Industry Standard)

Mailchimp CSV import docs are the gold standard:
- Column name + type + required/optional in a table
- Valid values enumerated (not "see the code")
- Sample rows with correct formatting
- Common errors listed with "what to do"
- All on one page, no clicking around

`CSV_FORMAT.md` should reach this level for both the CDCMS and generic CSV formats.

### Error Messages (Industry Standard)

Stripe's API error messages are the gold standard for technical→non-technical translation:
- Error code (for developers to look up)
- Human-readable message (for displaying to users)
- Suggested next action (not just what went wrong, but what to do)

The upload endpoint error messages should have all three, even if the dashboard only displays the human-readable message today.

---

## Sources

- Codebase analysis: `scripts/install.sh` (health check pattern, spinner, color output), `DEPLOY.md` (daily workflow steps, quick reference card), `core/data_import/cdcms_preprocessor.py` (cleaning steps, validation messages), `core/data_import/csv_importer.py` (ColumnMapping, error types), `docker-compose.yml` (actual container names)
- DEPLOY.md audit: daily startup requires 3 commands (lines 154-157), `<REPO_URL>` placeholder unfilled (line 119), CDCMS format reference scattered (Sections 4-5)
- README.md audit: stale container name `routing-db` (line 404), stale health check user `routeopt` (line 404), `<REPO_URL>` placeholder (line 15), Quick Start still shows manual venv/pip/alembic steps (lines 14-50)
- PROJECT.md v1.3 goal: "Make the system installable and usable by a non-technical office employee — one-command install from WSL, one-command daily startup, comprehensive documentation of CSV formats and workflow."

---
*Feature research for: Kerala LPG Delivery Route Optimizer v1.3 — Office-Ready Deployment*
*Researched: 2026-03-04*
