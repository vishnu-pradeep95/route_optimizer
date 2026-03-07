# Phase 20: Sync Error Message Documentation - Research

**Researched:** 2026-03-07
**Domain:** Documentation sync -- error message fidelity between code and user-facing docs
**Confidence:** HIGH

## Summary

Phase 20 is a pure documentation sync phase. Phase 17 humanized all user-facing error messages in the code to follow a "problem -- fix action" pattern with double-dash separators. The documentation files (CSV_FORMAT.md and DEPLOY.md) were written during Phase 15/16, before Phase 17's changes, so 8 documented messages are now stale.

This research identifies every discrepancy between the actual code output and the current documentation, maps each code error path to its documentation entry, and catalogs the exact changes needed. No code changes are required -- only documentation updates.

**Primary recommendation:** Perform a line-by-line comparison of each documented error message against its code source, update all stale entries to verbatim code strings, and create a traceability artifact mapping every documented message to its code location.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- CSV_FORMAT.md "What You See" column must show **exact code strings verbatim** -- employee matches screen output to doc
- Keep existing 3-column table structure (What You See | Why It Happened | How to Fix It) across all error sections
- Include the geocoding fallback message ("Could not find this address -- try checking the spelling") as a 7th geocoding row
- Keep and verify the "Geocoding service not configured (missing API key)" entry -- check actual code message and update to match
- Document all 5 _humanize_row_error() patterns plus the catch-all fallback (6 total rows in "During Processing" table)
- Keep row-level errors in the existing "During Processing" table -- no subsections
- Use concrete examples for dynamic messages (e.g., "Missing required field 'order_id'" not "Missing required field '{column_name}'")
- Create a separate error mapping file in `.planning/phases/20-sync-error-message-documentation/` as a verification artifact
- 3-column format: Message | Code Location | Status (verified/stale)
- CSV_FORMAT.md stays clean for office staff -- no code references in user-facing doc
- Update all 5 troubleshooting sections to use humanized messages (not just the set notation one)
- Keep code blocks for error display -- visually distinct from instructions
- Remove the "File not found" (FileNotFoundError) section -- stale, dashboard uses drag-and-drop upload
- Add cross-link to CSV_FORMAT.md: "For a complete list of error messages, see CSV_FORMAT.md > What Can Go Wrong"

### Claude's Discretion
- Exact wording of "Why It Happened" and "How to Fix It" columns (as long as "What You See" is verbatim)
- Error mapping file name and internal structure
- Whether to reorder troubleshooting sections in DEPLOY.md for better flow after removing "File not found"

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CSV-04 | CSV_FORMAT.md documents rejection reasons and what causes rows to fail | Complete error message audit below identifies all 8 stale messages; replacement strings verified against code |
| ERR-01 | Upload errors use plain English instead of Python set notation | DEPLOY.md line 212 uses `{'OrderNo'}` set notation; code now produces `OrderNo, ConsumerAddress` (comma-separated sorted list) |
| ERR-02 | Geocoding errors translated to office-friendly descriptions | All 6 GEOCODING_REASON_MAP entries verified; CSV_FORMAT.md geocoding table has 6 stale messages that don't match code strings |

</phase_requirements>

## Complete Error Message Audit

### Confidence: HIGH -- all messages verified by reading actual source code

Every error message below was verified by reading the source file directly. No training-data assumptions.

### CSV_FORMAT.md "Before Processing" Table (File-Level Errors)

These are the current documentation entries compared against actual code strings.

| # | Current Doc (line) | Actual Code String | Source File:Line | Match? |
|---|--------------------|--------------------|------------------|--------|
| 1 | `"Unsupported file type (.pdf). Accepted: .csv, .xls, .xlsx"` | `f"Unsupported file type ({ext or 'none'}). Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}"` | main.py:722 | MATCH (dynamic but format correct) |
| 2 | `"Unexpected content type (application/pdf). Upload a CSV or Excel file."` | `f"Unexpected content type ({content_type}). Upload a CSV or Excel file."` | main.py:730 | MATCH |
| 3 | `"File too large (15.2 MB). Maximum: 10 MB."` | `f"File too large ({size_mb:.1f} MB). Maximum: {max_mb:.0f} MB."` | main.py:746 | MATCH |
| 4 | `"No 'Allocated-Printed' orders found..."` | `"No 'Allocated-Printed' orders found in CDCMS export. Check that the file has orders with status 'Allocated-Printed'."` | main.py:771-772 | MATCH |
| 5 | `"No valid orders found in file"` | `"No valid orders found in file"` | main.py:851 | MATCH |
| 6 | `"Missing address column. Expected 'address' or one of [...]..."` | `f"Missing address column '{address_col}' -- make sure you're uploading the correct file format"` | csv_importer.py:301-302 | **STALE** |
| 7 | `"CDCMS export is missing required columns: {'OrderNo', 'ConsumerAddress'}..."` | `f"Required columns missing: {', '.join(sorted(missing_required))} -- make sure you're uploading the raw CDCMS export"` | cdcms_preprocessor.py:352-354 | **STALE** |
| 8 | `"The 'ConsumerAddress' column exists but all values are empty. Check the file format."` | `f"The '{CDCMS_COL_ADDRESS}' column exists but all values are empty. Check the file format."` | cdcms_preprocessor.py:370-372 | MATCH |
| 9 | `"Unsupported file format: .txt. Use .csv, .xlsx, or .xls"` | `f"Unsupported file format: {suffix}. Use .csv, .xlsx, or .xls"` | csv_importer.py:279 | MATCH |

**Stale entries (2):**

1. **Line 163 (Missing address column):** Doc says `"Missing address column. Expected 'address' or one of ['address', 'delivery_address', 'addr', 'customer_address']. Found columns: [...]"` but code says `"Missing address column 'address' -- make sure you're uploading the correct file format"`. The doc version has extra detail not in the code, and is missing the `--` separator from Phase 17.

2. **Line 164 (CDCMS required columns):** Doc says `"CDCMS export is missing required columns: {'OrderNo', 'ConsumerAddress'}. ... Make sure you're uploading the raw CDCMS export file."` but code says `"Required columns missing: OrderNo, ConsumerAddress -- make sure you're uploading the raw CDCMS export"`. The doc uses Python set notation `{...}`, the old error message format, and a different sentence structure. Phase 17 changed this to comma-separated sorted list with `--` separator.

### CSV_FORMAT.md "During Processing" Table (Row-Level Errors)

| # | Current Doc (line) | Actual Code String | Source File:Line | Match? |
|---|--------------------|--------------------|------------------|--------|
| 1 | `"Empty address -- add a delivery address"` | `f"Empty {self.mapping.address} -- add a delivery address"` | csv_importer.py:221 | MATCH (renders as "Empty address -- add a delivery address") |
| 2 | `"Duplicate order_id 'ORD-001' -- already imported from an earlier row"` | `f"Duplicate {self.mapping.order_id} '{order_id}' -- already imported from an earlier row"` | csv_importer.py:236-237 | MATCH |
| 3 | `"Invalid weight '20kg' in weight_kg column -- using default 14.2 kg"` | `f"Invalid weight '{weight_str}' in {self.mapping.weight_kg} column -- using default {self.default_weight} kg"` | csv_importer.py:395-396 | MATCH |

**Missing entries (4):** The current "During Processing" table has only 3 rows. The CONTEXT.md requires documenting all 5 `_humanize_row_error()` patterns plus the catch-all (6 total). Currently missing:

| # | Code String | Source File:Line | Type |
|---|-------------|------------------|------|
| 4 | `"Invalid number value -- check for letters or symbols in numeric fields"` | csv_importer.py:115 | ValueError with "could not convert" + "float" |
| 5 | `"Unexpected value format -- check the cell contents"` | csv_importer.py:117 | ValueError with "could not convert" (non-float) |
| 6 | `"Invalid value -- {msg}"` (if msg < 60 chars) or `"Invalid value in this row"` (if msg >= 60 chars) | csv_importer.py:118 | Generic ValueError |
| 7 | `"Missing required field '{col}' -- check your CSV has all required columns"` | csv_importer.py:121 | KeyError |
| 8 | `"Empty or invalid cell -- fill in required fields"` | csv_importer.py:123 | TypeError |
| 9 | `"Could not process this row -- check the data format"` | csv_importer.py:124 | Catch-all fallback |

Note: Rows 1-3 above (empty address, duplicate, invalid weight) are pre-validation checks, not from `_humanize_row_error()`. The 6 `_humanize_row_error()` patterns are rows 4-9. Total row-level entries should be 3 (pre-validation) + 6 (_humanize_row_error) = 9. But CONTEXT.md says "6 total rows in 'During Processing' table" -- this means the 5 `_humanize_row_error()` patterns + 1 catch-all = 6 entries, plus the existing 3 pre-validation entries stay = 9 total.

Actually, re-reading CONTEXT.md more carefully: "Document all 5 _humanize_row_error() patterns plus the catch-all fallback (6 total rows in 'During Processing' table)" -- this says 6 total rows, which is the `_humanize_row_error` set alone. The existing 3 pre-validation entries (empty address, duplicate, invalid weight) are already in the table, so the final table should have 3 + 6 = 9 rows. But the "6 total rows" phrase may mean the user wants 6 total rows replacing the current 3. Let the planner decide -- present both interpretations.

**Clarification needed for planner:** CONTEXT.md says "6 total rows in 'During Processing' table." This could mean:
- (A) 6 _humanize_row_error entries added, making 9 total rows (3 existing + 6 new)
- (B) 6 total rows in the table (replacing current 3 with 6)

Given the directive "Document all 5 _humanize_row_error() patterns plus the catch-all fallback" and "Keep row-level errors in the existing 'During Processing' table", interpretation (A) is more likely -- add the 6 missing patterns to the existing table, keeping the 3 current entries. The "(6 total rows)" is describing what's being added, not the final count.

### CSV_FORMAT.md "During Map Lookup" Table (Geocoding Errors)

| # | Current Doc (line) | Actual Code String | Source File:Line | Match? |
|---|--------------------|--------------------|------------------|--------|
| 1 | `"Address not recognized by Google Maps"` | `"Address not found -- check spelling in CDCMS"` | main.py:83 (ZERO_RESULTS) | **STALE** |
| 2 | `"Geocoding service error (contact admin)"` | `"Geocoding service blocked -- contact IT"` | main.py:84 (REQUEST_DENIED) | **STALE** |
| 3 | `"Geocoding quota exceeded (try again later)"` | `"Google Maps quota exceeded -- contact IT"` | main.py:85-86 (OVER_QUERY_LIMIT / OVER_DAILY_LIMIT) | **STALE** |
| 4 | `"Address could not be processed"` | `"Address could not be processed -- check for unusual characters"` | main.py:87 (INVALID_REQUEST) | **STALE** |
| 5 | `"Geocoding service temporarily unavailable"` | `"Google Maps is temporarily unavailable -- try again in a few minutes"` | main.py:88 (UNKNOWN_ERROR) | **STALE** |
| 6 | `"Geocoding service not configured (missing API key)"` | `"Geocoding service not configured (missing API key)"` | main.py:959 | MATCH |
| 7 | (missing) | `"Could not find this address -- try checking the spelling"` | main.py:934 (fallback) | **MISSING** |

**Stale entries (5):** Rows 1-5 all use the pre-Phase-17 wording. Phase 17 changed GEOCODING_REASON_MAP to use the "problem -- fix action" pattern with `--` separator.

**Missing entry (1):** The fallback message for unmapped geocoding statuses is not documented. CONTEXT.md requires it as the 7th geocoding row.

### DEPLOY.md Troubleshooting Section

| # | Section | Current Doc Message | Actual Behavior | Status |
|---|---------|--------------------|--------------------|--------|
| 1 | "Cannot connect to Docker" | `Cannot connect to the Docker daemon` | System/Docker message, not app code | OK (infrastructure, not Phase 17 scope) |
| 2 | "File not found" | `FileNotFoundError: CDCMS export file not found` | This code path does not exist -- dashboard uses drag-and-drop upload via HTTP POST | **REMOVE** (per CONTEXT.md decision) |
| 3 | "Missing required columns" | `ValueError: CDCMS export is missing required columns: {'OrderNo'}` | Code produces: `Required columns missing: OrderNo -- make sure you're uploading the raw CDCMS export` | **STALE** (set notation + wrong message format) |
| 4 | "No orders remain after filtering" | `WARNING: No orders remain after filtering` | This is a logger.warning in cdcms_preprocessor.py:161, surfaces to user as "No 'Allocated-Printed' orders found in CDCMS export." | **STALE** (user sees the HTTPException, not the log warning) |
| 5 | "Google Maps API key error" | `ERROR: GOOGLE_MAPS_API_KEY not set` | In the API (main.py), this surfaces as `"Geocoding service not configured (missing API key)"` per-address. The `GOOGLE_MAPS_API_KEY not set` message only appears in CLI scripts (import_orders.py:111, geocode_batch.py:167), not in the dashboard workflow. | **STALE** (wrong message source for dashboard users) |

## Architecture Patterns

### Documentation Structure (Do Not Change)

**CSV_FORMAT.md** has a clear information architecture:
1. Accepted File Formats (table)
2. CDCMS Export Format (columns, status filter, header)
3. Standard CSV Format (columns, types, bounds)
4. Example Rows (3 examples)
5. **What Can Go Wrong** (3 tables: file-level, row-level, geocoding)
6. Address Cleaning (pipeline + examples)

The error section uses 3 tables with the same 3-column format: `What You See | Why It Happened | How to Fix It`. This structure is locked.

**DEPLOY.md** troubleshooting uses `### heading` + code block + `**Fix:**` paragraph pattern. This structure is locked except for removing "File not found" and optionally reordering.

### Error Flow Architecture

```
User uploads file
    |
    v
[File validation: main.py:718-747]
    | Extension check → HTTPException 400
    | Content-type check → HTTPException 400
    | Size check → HTTPException 413
    v
[CDCMS detection: main.py:760]
    |-- CDCMS → [Preprocess: cdcms_preprocessor.py]
    |            | Column validation → ValueError
    |            | Empty address check → ValueError
    |            | Status filter → empty DataFrame → HTTPException 400
    |
    |-- Standard CSV → [Import: csv_importer.py]
                        | Column validation → ValueError
                        | Row parsing → RowError (per-row)
                        | Weight parsing → RowError warning
    v
[Geocoding: main.py:880-961]
    | GEOCODING_REASON_MAP statuses → ImportFailure
    | Fallback message → ImportFailure
    | No API key → ImportFailure
    v
[Response: OptimizationSummary with failures list]
```

Key insight: All errors surface to the user through the dashboard UI, not through terminal/console output. DEPLOY.md troubleshooting should reference what the employee sees in the browser, not Python exception types.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Message extraction from code | Manually copying strings from source | Direct reading of source files with line numbers | Phase 17 changed messages; manual copying from memory will reproduce stale versions |
| Dynamic message examples | Inventing plausible examples | Use concrete examples from the code's default values (address_col='address', default_weight=14.2) | Ensures examples match what a user would actually see |

## Common Pitfalls

### Pitfall 1: Dynamic Message Templates
**What goes wrong:** Some error messages contain dynamic values (file extension, column name, weight). Documentation must use concrete realistic examples, not template syntax.
**Why it happens:** Code uses f-strings like `f"Missing address column '{address_col}'"`. The variable value depends on the CSV column mapping.
**How to avoid:** Use the default column mapping values: `address_col='address'`, `order_id='order_id'`, `weight_kg='weight_kg'`. These are what standard CSV users would see. CDCMS users see different column names after preprocessing.
**Warning signs:** Documentation shows `{variable}` syntax or uses column names from CDCMS raw format in standard CSV error messages.

### Pitfall 2: OVER_QUERY_LIMIT and OVER_DAILY_LIMIT Have Identical Messages
**What goes wrong:** Two different Google API status codes map to the same user-facing message.
**Why it happens:** `GEOCODING_REASON_MAP` maps both `OVER_QUERY_LIMIT` and `OVER_DAILY_LIMIT` to `"Google Maps quota exceeded -- contact IT"`.
**How to avoid:** Document this as a single row in the geocoding table (one message covers both statuses). The user sees only one message regardless of which limit was hit.

### Pitfall 3: Pre-Validation vs. _humanize_row_error Distinction
**What goes wrong:** Mixing up the 3 pre-validation row errors (empty address, duplicate order_id, invalid weight warning) with the 6 _humanize_row_error patterns.
**Why it happens:** Both appear in the same "During Processing" table but come from different code paths.
**How to avoid:** Pre-validation errors are checked before `_row_to_order_with_warnings()`. The _humanize_row_error patterns are caught in the `except` block after it. Both go in the same table per CONTEXT.md decision, but the planner should organize them logically (pre-validation first, then parsing errors).

### Pitfall 4: DEPLOY.md "No orders remain" vs. User-Facing Message
**What goes wrong:** Documenting the logger.warning message instead of what the user actually sees.
**Why it happens:** `cdcms_preprocessor.py:161` logs "No orders remain after filtering" but returns an empty DataFrame. The empty DataFrame then triggers `main.py:768-773` which returns `"No 'Allocated-Printed' orders found in CDCMS export"` as an HTTPException.
**How to avoid:** Always trace the error path to the HTTP response that reaches the browser. Logger messages are for IT debugging, not user docs.

### Pitfall 5: ValueError Prefix in DEPLOY.md
**What goes wrong:** DEPLOY.md shows `ValueError: CDCMS export is missing required columns...` with the Python exception type prefix.
**Why it happens:** The ValueError is caught by the API and its message is extracted for the HTTP response. The user never sees `ValueError:` in the browser.
**How to avoid:** Strip exception type prefixes from DEPLOY.md code blocks. Show only the message text that appears in the dashboard.

## Exact Replacement Strings

### CSV_FORMAT.md Geocoding Table (6 stale + 1 missing = 7 entries needed)

| # | Code Message (VERBATIM) | Status Code | Source |
|---|------------------------|-------------|--------|
| 1 | `Address not found -- check spelling in CDCMS` | ZERO_RESULTS | main.py:83 |
| 2 | `Geocoding service blocked -- contact IT` | REQUEST_DENIED | main.py:84 |
| 3 | `Google Maps quota exceeded -- contact IT` | OVER_QUERY_LIMIT + OVER_DAILY_LIMIT | main.py:85-86 |
| 4 | `Address could not be processed -- check for unusual characters` | INVALID_REQUEST | main.py:87 |
| 5 | `Google Maps is temporarily unavailable -- try again in a few minutes` | UNKNOWN_ERROR | main.py:88 |
| 6 | `Geocoding service not configured (missing API key)` | (no geocoder) | main.py:959 |
| 7 | `Could not find this address -- try checking the spelling` | (unmapped/fallback) | main.py:934 |

### CSV_FORMAT.md Row-Level Table (3 existing OK + 6 new = 9 entries)

Existing (already match code -- keep as-is):

| # | Message Pattern | Source |
|---|----------------|--------|
| 1 | `Empty address -- add a delivery address` | csv_importer.py:221 |
| 2 | `Duplicate order_id 'ORD-001' -- already imported from an earlier row` | csv_importer.py:236-237 |
| 3 | `Invalid weight '20kg' in weight_kg column -- using default 14.2 kg` (warning) | csv_importer.py:395-396 |

New (from _humanize_row_error):

| # | Message Pattern | Trigger | Source |
|---|----------------|---------|--------|
| 4 | `Invalid number value -- check for letters or symbols in numeric fields` | ValueError with "could not convert" + "float" | csv_importer.py:115 |
| 5 | `Unexpected value format -- check the cell contents` | ValueError with "could not convert" (non-float) | csv_importer.py:117 |
| 6 | `Invalid value -- {short description}` or `Invalid value in this row` | Other ValueError | csv_importer.py:118 |
| 7 | `Missing required field 'order_id' -- check your CSV has all required columns` | KeyError | csv_importer.py:121 |
| 8 | `Empty or invalid cell -- fill in required fields` | TypeError | csv_importer.py:123 |
| 9 | `Could not process this row -- check the data format` | Catch-all | csv_importer.py:124 |

For entry #6, use concrete example: `"Invalid value in this row"` (the short-message variant is rare and context-dependent; use the generic form as the documented example).

### CSV_FORMAT.md File-Level Table (2 stale entries)

**Entry 6 (Missing address column) -- replace with:**
`"Missing address column 'address' -- make sure you're uploading the correct file format"`

**Entry 7 (CDCMS required columns) -- replace with:**
`"Required columns missing: ConsumerAddress, OrderNo -- make sure you're uploading the raw CDCMS export"`

### DEPLOY.md Troubleshooting (5 sections -> 4 sections after removing "File not found")

| # | Keep/Remove/Update | Current Heading | New Content |
|---|-------------------|-----------------|-------------|
| 1 | KEEP as-is | "Cannot connect to Docker" | No change needed -- infrastructure message |
| 2 | **REMOVE** | "File not found" | Delete entire section per CONTEXT.md |
| 3 | **UPDATE** | "Missing required columns" | Code block: `Required columns missing: OrderNo -- make sure you're uploading the raw CDCMS export` (no `ValueError:` prefix, no set notation) |
| 4 | **UPDATE** | "No orders remain after filtering" | Code block should show the user-facing message: `No 'Allocated-Printed' orders found in CDCMS export. Check that the file has orders with status 'Allocated-Printed'.` |
| 5 | **UPDATE** | "Google Maps API key error" | Code block should show: `Geocoding service not configured (missing API key)` (the dashboard message, not the CLI script message) |
| + | **ADD** | Cross-link to CSV_FORMAT.md | Add note: "For a complete list of error messages, see CSV_FORMAT.md > What Can Go Wrong" |

## Error Mapping Artifact

Per CONTEXT.md, create a separate error mapping file. Recommended name: `ERROR-MAP.md` in the phase directory.

Structure:

```markdown
# Error Message Mapping

| Message | Code Location | Status |
|---------|--------------|--------|
| "Unsupported file type ({ext}). Accepted: ..." | main.py:722 | verified |
| ... | ... | ... |
```

This artifact covers every user-facing error message (file-level, row-level, geocoding) with its exact code location and verification status. Total entries: ~22 (9 file-level + 9 row-level + 7 geocoding - 3 duplicates where OVER_QUERY_LIMIT and OVER_DAILY_LIMIT share a message).

## State of the Art

| Old Approach (Phase 15) | Current Approach (Phase 17+) | When Changed | Impact on Docs |
|--------------------------|------------------------------|--------------|----------------|
| `"Address not recognized by Google Maps"` | `"Address not found -- check spelling in CDCMS"` | Phase 17 | 5 geocoding messages stale |
| `{'OrderNo', 'ConsumerAddress'}` (set notation) | `ConsumerAddress, OrderNo` (sorted comma list) | Phase 17 | 1 CDCMS column error stale |
| `"Missing address column. Expected 'address' or one of [...]"` | `"Missing address column 'address' -- make sure you're uploading the correct file format"` | Phase 17 | 1 address error stale |
| Only 3 row-level errors documented | 9 row-level error patterns exist | Phase 17 added _humanize_row_error | 6 entries need adding |
| `FileNotFoundError` in troubleshooting | Dashboard uses drag-and-drop (no file paths) | Has been this way since Phase 4+ | 1 DEPLOY.md section to remove |

## Open Questions

1. **Row-level table total count ambiguity**
   - What we know: CONTEXT.md says "6 total rows in 'During Processing' table"
   - What's unclear: Whether "6 total" means 6 new rows (making 9 total) or 6 replacing the current 3
   - Recommendation: Add 6 new `_humanize_row_error` patterns to the existing 3 pre-validation entries, making 9 total rows. The "(6 total rows)" is describing the set of patterns to add, not the final table size.

2. **Generic ValueError message example**
   - What we know: `_humanize_row_error` has a branch that produces `f"Invalid value -- {msg}"` when the exception message is short, or `"Invalid value in this row"` when it's long
   - What's unclear: Which variant to document as the example
   - Recommendation: Document both: `"Invalid value in this row"` as the primary example (most likely to be seen), with a note that short error details may appear.

## Validation Architecture

> `workflow.nyquist_validation` is not set in config.json -- treating as enabled.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Manual verification (documentation phase -- no automated tests) |
| Config file | N/A |
| Quick run command | `diff` comparison of documented messages vs code strings |
| Full suite command | Line-by-line audit of all error message entries |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CSV-04 | Every documented rejection matches actual code string | manual | `grep` comparison of CSV_FORMAT.md strings vs source code | N/A (doc audit) |
| ERR-01 | No Python set notation in documentation | manual | `grep -n "{'\\|'}" CSV_FORMAT.md DEPLOY.md` | N/A |
| ERR-02 | Geocoding messages use office-friendly language | manual | Compare GEOCODING_REASON_MAP values against CSV_FORMAT.md geocoding table | N/A |

### Sampling Rate
- **Per task commit:** Verify changed lines against source code
- **Per wave merge:** Full audit of all 22 error message entries
- **Phase gate:** Every documented message traceable to code path via ERROR-MAP.md

### Wave 0 Gaps
None -- this is a documentation-only phase. No test infrastructure needed.

## Sources

### Primary (HIGH confidence)
- `apps/kerala_delivery/api/main.py:82-89` -- GEOCODING_REASON_MAP (6 entries, read directly)
- `apps/kerala_delivery/api/main.py:718-851` -- File validation and HTTPExceptions (read directly)
- `apps/kerala_delivery/api/main.py:920-961` -- Geocoding error handling (read directly)
- `core/data_import/csv_importer.py:102-124` -- _humanize_row_error (5 patterns + fallback, read directly)
- `core/data_import/csv_importer.py:214-265` -- Pre-validation errors (empty address, duplicate, read directly)
- `core/data_import/csv_importer.py:388-397` -- Weight warning (read directly)
- `core/data_import/csv_importer.py:278-279` -- Unsupported file format (read directly)
- `core/data_import/csv_importer.py:300-302` -- Missing address column (read directly)
- `core/data_import/cdcms_preprocessor.py:352-354` -- CDCMS required columns (read directly)
- `core/data_import/cdcms_preprocessor.py:370-372` -- Empty ConsumerAddress (read directly)
- `CSV_FORMAT.md:150-189` -- Current "What Can Go Wrong" section (read directly)
- `DEPLOY.md:186-243` -- Current troubleshooting section (read directly)

### Secondary (MEDIUM confidence)
- `.planning/phases/20-sync-error-message-documentation/20-CONTEXT.md` -- User decisions
- `.planning/phases/15-csv-documentation/15-VERIFICATION.md` -- Prior verification confirms Phase 15 matched at that time

## Metadata

**Confidence breakdown:**
- Error message audit: HIGH -- every message verified by direct source code reading
- Stale message identification: HIGH -- side-by-side comparison of code vs docs
- Replacement strings: HIGH -- copied verbatim from source code
- Row-level table count interpretation: MEDIUM -- CONTEXT.md phrasing is slightly ambiguous

**Research date:** 2026-03-07
**Valid until:** Stable -- documentation sync is a point-in-time operation. Valid as long as no further code changes to error messages.
