# Phase 15: CSV Documentation - Research

**Researched:** 2026-03-05
**Domain:** Documentation -- CSV format reference for non-technical office employees
**Confidence:** HIGH

## Summary

Phase 15 is a pure documentation task: creating a single `CSV_FORMAT.md` file that office employees can consult for any CSV-related question without asking IT. The "technology" here is the existing codebase -- the research goal is to extract every column name, rejection reason, address transformation rule, and validation constraint from the actual source code so the documentation is accurate and complete.

The codebase has two distinct CSV input paths: (1) raw CDCMS tab-separated exports auto-detected and preprocessed by `cdcms_preprocessor.py`, and (2) standard comma-separated CSVs consumed directly by `csv_importer.py`. Both paths feed into the same `CsvImporter` class. The documentation must cover both paths with exact column names matching what the employee sees.

**Primary recommendation:** Extract all documentation content directly from source code (not from memory or training data). The codebase is the single source of truth -- `cdcms_preprocessor.py`, `csv_importer.py`, `config.py`, and the upload endpoint in `main.py` contain every detail needed.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CSV-01 | CSV_FORMAT.md documents all accepted file formats (.csv, .xlsx, .xls) | `ALLOWED_EXTENSIONS` in main.py: `.csv`, `.xlsx`, `.xls`. `_read_file()` in csv_importer.py handles all three. `_read_cdcms_file()` handles tab-separated CSV and Excel for CDCMS. Max upload 10 MB. |
| CSV-02 | CSV_FORMAT.md documents CDCMS columns (required/optional, status filter) | CDCMS columns defined in `cdcms_preprocessor.py` constants: `CDCMS_COL_ORDER_NO`, `CDCMS_COL_ADDRESS` (required); `CDCMS_COL_ORDER_QTY`, `CDCMS_COL_AREA`, `CDCMS_COL_DELIVERY_MAN`, `CDCMS_COL_ORDER_STATUS` (optional). 19-column header from sample file. Status filter defaults to `Allocated-Printed`. |
| CSV-03 | CSV_FORMAT.md documents standard CSV columns with defaults and constraints | `ColumnMapping` class in csv_importer.py defines 12 columns. Required: `address` (or alternatives). Optional with defaults: `order_id` (auto ORD-0001), `customer_id` (auto CUST-0001), `weight_kg` (default 14.2), `quantity` (default 1), `priority` (default 2), `notes` (default empty), `latitude`/`longitude` (default none), `cylinder_type` (lookup), `delivery_window_start`/`delivery_window_end` (default none). |
| CSV-04 | CSV_FORMAT.md documents rejection reasons and what causes rows to fail | Two stages: validation (empty address, duplicate order_id, missing address column, unsupported file format, file too large, empty CDCMS file, no Allocated-Printed orders) and geocoding (ZERO_RESULTS, REQUEST_DENIED, OVER_QUERY_LIMIT, OVER_DAILY_LIMIT, INVALID_REQUEST, UNKNOWN_ERROR). |
| CSV-05 | CSV_FORMAT.md documents address cleaning pipeline with examples | 10-step pipeline in `clean_cdcms_address()`: phone removal, PH annotation stripping, backtick/quote cleanup, NR/PO/H expansion, digit-letter spacing, space collapse, dangling punctuation, title case, P.O./KSEB fixes, area suffix. Real before/after examples available from tests. |
| CSV-06 | CSV_FORMAT.md includes example rows for both CDCMS and standard CSV | Sample files exist at `data/sample_orders.csv` (30 rows, standard format) and `data/sample_cdcms_export.csv` (27+ rows, CDCMS format). Copy-pasteable rows from these verified samples. |
</phase_requirements>

## Standard Stack

This phase produces a Markdown documentation file. No libraries, packages, or build tools are needed.

### Core
| Tool | Purpose | Why |
|------|---------|-----|
| Markdown (.md) | Documentation format | Already used project-wide, no build step needed |
| Source code as truth | Content extraction | All facts come from `csv_importer.py`, `cdcms_preprocessor.py`, `config.py`, `main.py` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Markdown | MkDocs / Docusaurus site | Explicitly out of scope (see REQUIREMENTS.md) |
| Single file | Multiple files | Single file matches the goal: "one document without asking IT" |

## Architecture Patterns

### Recommended File Location
```
CSV_FORMAT.md     # Project root — same level as README.md and DEPLOY.md
```

Why project root? The audience (office employee) should find it alongside README.md and DEPLOY.md. DEPLOY.md already exists at root level. Phase 16 will cross-link from DEPLOY.md to CSV_FORMAT.md.

### Document Structure Pattern: Task-Oriented Reference

The document should be organized by what the employee is trying to do, not by code architecture. Recommended sections:

1. **Quick Start** -- "Which file do I upload?" (2-3 sentences)
2. **CDCMS Export Format** -- What comes out of CDCMS, which columns matter
3. **Standard CSV Format** -- For when they prepare CSVs manually
4. **Example Rows** -- Copy-pasteable valid examples for both formats
5. **What Can Go Wrong** -- Every rejection reason with fix instructions
6. **Address Cleaning** -- What the system does to addresses (before/after)

### Anti-Patterns to Avoid
- **Developer-oriented structure:** Don't organize by code modules (csv_importer, cdcms_preprocessor). Organize by employee tasks.
- **Python jargon:** Don't mention "ValueError", "DataFrame", "pandas". Use "the system shows an error".
- **Exhaustive technical detail:** Don't document internal architecture. Only document what the employee can observe or act on.
- **Stale examples:** Don't invent example data. Use real samples from `data/sample_orders.csv` and `data/sample_cdcms_export.csv`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Example rows | Invented data | `data/sample_orders.csv` and `data/sample_cdcms_export.csv` | Real samples already tested against the system |
| Column names | Memory | `ColumnMapping` class fields and `CDCMS_COL_*` constants | Source code is authoritative; column names must match exactly |
| Rejection messages | Guessing | Actual error strings from `csv_importer.py` and `GEOCODING_REASON_MAP` in `main.py` | Messages must match what the employee actually sees on screen |
| Address examples | Made-up addresses | Test assertions in `test_cdcms_preprocessor.py` | Tests have verified before/after pairs |

**Key insight:** Every fact in this document must come from source code, not from the document author's understanding. When the code changes, this document must be updated to match.

## Common Pitfalls

### Pitfall 1: Column Names Don't Match What Employee Sees
**What goes wrong:** Documentation says "OrderNumber" but CDCMS export has "OrderNo". Employee can't find the column.
**Why it happens:** Writer uses approximate names instead of checking source constants.
**How to avoid:** Use exact values from `CDCMS_COL_ORDER_NO = "OrderNo"`, `CDCMS_COL_ADDRESS = "ConsumerAddress"`, etc.
**Warning signs:** Any column name not copy-pasted from source code.

### Pitfall 2: Missing the Auto-Detection Logic
**What goes wrong:** Documentation implies employee must choose between CDCMS and standard format. They don't -- it's auto-detected.
**Why it happens:** Writer explains both formats as separate upload paths.
**How to avoid:** Clearly state: "The system automatically detects your file format. Just upload and it figures out the rest."
**Warning signs:** Any instruction that says "if you have a CDCMS file, use [different button/endpoint]."

### Pitfall 3: Incomplete Rejection Reasons
**What goes wrong:** Employee gets an error not listed in the docs, has to call IT anyway.
**Why it happens:** Writer documents some errors but misses edge cases.
**How to avoid:** Systematically extract EVERY error path from code. See comprehensive list below.
**Warning signs:** Any error message in source code not covered in the document.

### Pitfall 4: Address Cleaning Examples Missing Context
**What goes wrong:** Employee sees cleaned address that looks wrong, doesn't understand the transformation.
**Why it happens:** Examples show only the "after" without the "before" and "why."
**How to avoid:** Show before/after pairs with brief explanation of what changed.
**Warning signs:** Examples without corresponding input.

### Pitfall 5: Tab-Separated vs Comma-Separated Confusion
**What goes wrong:** Employee opens CDCMS export in Excel, resaves as comma-separated CSV, loses the auto-detection.
**Why it happens:** CDCMS exports are tab-separated. Re-saving as CSV changes the separator.
**How to avoid:** Document that CDCMS exports should be uploaded as-is, without opening in Excel first.
**Warning signs:** Not mentioning that CDCMS is tab-separated.

## Code Examples (Source Material for Documentation)

All content below is extracted directly from source code. The planner should use these as the basis for CSV_FORMAT.md content.

### CDCMS Column Reference (from `cdcms_preprocessor.py` and `test_cdcms_preprocessor.py`)

The full CDCMS header has 19 tab-separated columns:

```
OrderNo  OrderStatus  OrderDate  OrderSource  OrderType  CashMemoNo  CashMemoStatus  CashMemoDate  OrderQuantity  ConsumedSubsidyQty  AreaName  DeliveryMan  RefillPaymentStatus  IVRSBookingNumber  MobileNo  BookingDoneThroughRegistereMobile  ConsumerAddress  IsRefillPort  EkycStatus
```

**Required by system:** `OrderNo`, `ConsumerAddress`
**Used by system:** `OrderQuantity`, `AreaName`, `DeliveryMan`, `OrderStatus`
**Ignored by system:** All other 13 columns (CashMemoNo, CashMemoStatus, OrderDate, OrderSource, OrderType, CashMemoDate, ConsumedSubsidyQty, RefillPaymentStatus, IVRSBookingNumber, MobileNo, BookingDoneThroughRegistereMobile, IsRefillPort, EkycStatus)

**Status filter:** Only rows where `OrderStatus` = "Allocated-Printed" are imported. All other statuses (e.g., "Delivered", "Cancelled") are silently filtered out.

### Standard CSV Column Reference (from `csv_importer.py` ColumnMapping)

```
order_id,address,customer_id,cylinder_type,quantity,priority,notes,latitude,longitude,weight_kg,delivery_window_start,delivery_window_end
```

| Column | Required? | Default if missing | Constraints |
|--------|-----------|-------------------|-------------|
| `address` | YES (only required column) | -- | Must not be empty. Alternatives accepted: `delivery_address`, `addr`, `customer_address` |
| `order_id` | No | Auto-generated `ORD-0001`, `ORD-0002`, ... | Must be unique within file |
| `customer_id` | No | Auto-generated `CUST-0001`, `CUST-0002`, ... | -- |
| `weight_kg` | No | 14.2 (domestic cylinder) | Must be a number if provided |
| `cylinder_type` | No | -- | Recognized values: `domestic`, `14.2`, `14.2kg`, `commercial`, `19`, `19kg`, `5kg`, `5` |
| `quantity` | No | 1 | Must be a positive integer |
| `priority` | No | 2 (normal) | 1=high, 2=normal, 3=low |
| `notes` | No | empty | Free text, shown to driver |
| `latitude` | No | none (geocoded from address) | Decimal degrees, within India bounds (6.0-37.0) |
| `longitude` | No | none (geocoded from address) | Decimal degrees, within India bounds (68.0-97.5) |
| `delivery_window_start` | No | none (no time constraint) | HH:MM or HH:MM:SS format |
| `delivery_window_end` | No | none (no time constraint) | HH:MM or HH:MM:SS format. Windows < 30 min auto-widened. |

Column name normalization: the system strips whitespace, lowercases, and replaces spaces with underscores before matching.

### Complete Rejection Reason Inventory

#### File-Level Rejections (before any row processing)

| Error | Cause | What employee sees | Fix |
|-------|-------|--------------------|-----|
| Unsupported file type | Extension not .csv, .xlsx, or .xls | "Unsupported file type (.pdf). Accepted: .csv, .xls, .xlsx" | Save file as .csv or .xlsx |
| Unexpected content type | Browser sends wrong MIME type | "Unexpected content type (image/png). Upload a CSV or Excel file." | Re-download from CDCMS |
| File too large | File > 10 MB | "File too large (12.5 MB). Maximum: 10 MB." | Split into smaller batches |
| Missing address column | No column named `address` (or alternatives) | "Missing address column. Expected 'address' or one of ['address', 'delivery_address', 'addr', 'customer_address']. Found columns: [...]" | Rename address column |
| Missing CDCMS columns | CDCMS file lacks OrderNo or ConsumerAddress | "CDCMS export is missing required columns: {'OrderNo'}. Found columns: [...]. Make sure you're uploading the raw CDCMS export file." | Re-export from CDCMS |
| Empty address column | ConsumerAddress exists but all values blank | "The 'ConsumerAddress' column exists but all values are empty. Check the file format." | Re-export from CDCMS |
| No Allocated-Printed orders | CDCMS file has orders but none with status "Allocated-Printed" | "No 'Allocated-Printed' orders found in CDCMS export." | Check CDCMS order allocation |
| No valid orders | File parsed but zero valid rows after validation | "No valid orders found in file" | Fix row-level errors and re-upload |
| Unsupported file format (importer) | Extension not .csv, .xlsx, or .xls (reached CsvImporter) | "Unsupported file format: .txt. Use .csv, .xlsx, or .xls" | Save as correct format |

#### Row-Level Validation Rejections (per-row, row is skipped)

| Error | Cause | What employee sees | Fix |
|-------|-------|--------------------|-----|
| Empty address | Address cell is blank or whitespace-only | "Empty address -- add a delivery address" | Fill in the address for that row |
| Duplicate order_id | Same order_id appears twice in the file | "Duplicate order_id 'ORD-001' -- already imported from an earlier row" | Remove duplicate row or fix ID |

#### Row-Level Validation Warnings (per-row, row is imported with defaults)

| Warning | Cause | What employee sees | Impact |
|---------|-------|--------------------|--------|
| Invalid weight | weight_kg column has non-numeric value like "abc" | "Invalid weight 'abc' in weight_kg column -- using default 14.2 kg" | Order uses 14.2 kg default |

#### Geocoding-Stage Rejections (per-row, after validation passes)

| Error | Cause | What employee sees | Fix |
|-------|-------|--------------------|-----|
| ZERO_RESULTS | Google Maps can't find the address | "Address not recognized by Google Maps" | Check address spelling in CDCMS |
| REQUEST_DENIED | API key issue | "Geocoding service error (contact admin)" | Contact IT |
| OVER_QUERY_LIMIT | Monthly quota exceeded | "Geocoding quota exceeded (try again later)" | Wait or contact IT for quota |
| OVER_DAILY_LIMIT | Daily quota exceeded | "Geocoding quota exceeded (try again later)" | Wait until tomorrow |
| INVALID_REQUEST | Address too garbled for API | "Address could not be processed" | Rewrite address in CDCMS |
| UNKNOWN_ERROR | Google API temporary failure | "Geocoding service temporarily unavailable" | Retry upload |

### Address Cleaning Pipeline (from `clean_cdcms_address()`, 10 steps)

The system applies these transformations IN ORDER to CDCMS addresses only (standard CSV addresses are not cleaned):

| Step | What It Does | Before | After |
|------|-------------|--------|-------|
| 1. Remove phone numbers | Strips 10-digit numbers (preserving house nos like 4/146) | `VALIYAPARAMBATH (H) 9847862734KURUPAL` | `VALIYAPARAMBATH (H) KURUPAL` |
| 2. Remove PH annotations | Strips `/ PH: nnnnn` and `/ nnnnn` patterns | `SREYAS ... VALLIKKADU / PH: 2511259` | `SREYAS ... VALLIKKADU` |
| 3. Remove quote markers | Strips backticks (``) and double quotes | `` ``THANAL`` `` | `THANAL` |
| 4. Expand abbreviations | NR. / NR; / NR: -> Near, PO. -> P.O., (H) -> House | `NR. VALLIKKADU` | `Near Vallikkadu` |
| 5. Expand concatenated PO | `KUNIYILPO.` -> `KUNIYIL P.O.` | `09/210A KUNIYILPO.` | `09/210A KUNIYIL P.O.` |
| 6. Split digit-letter joins | Adds space between number and uppercase letter | `8/542SREESHYLAM` | `8/542 SREESHYLAM` |
| 7. Collapse spaces | Multiple spaces become one | `SOME   ADDRESS    WITH` | `SOME ADDRESS WITH` |
| 8. Strip dangling punctuation | Removes leading/trailing ; : - + | `NR: K.S.E.B +` | `NR: K.S.E.B` |
| 9. Title case | ALL CAPS -> Title Case | `KALAMASSERY HMT COLONY` | `Kalamassery Hmt Colony` |
| 10. Fix title-case artifacts | Preserves known abbreviations | `P.o.`, `Kseb` | `P.O.`, `KSEB` |

**Area suffix:** After all cleaning, the system appends `, Vatakara, Kozhikode, Kerala` to help Google Maps locate the address. This is configurable per deployment.

### Example Rows

**Standard CSV (minimal -- just address):**
```csv
address
"Kalamassery, HMT Colony, Near Bus Stop, Kochi"
"Edappally Junction, Opposite Lulu Mall, Kochi"
```

**Standard CSV (full columns):**
```csv
order_id,address,customer_id,cylinder_type,quantity,priority,notes,latitude,longitude
ORD-001,"Kalamassery, HMT Colony, Near Bus Stop, Kochi",CUST-001,domestic,2,2,Ring bell twice,10.0553,76.3221
ORD-002,"Edappally Junction, Opposite Lulu Mall, Kochi",CUST-002,domestic,1,2,,9.9816,76.2996
```

**CDCMS format (tab-separated -- from sample file):**
```
OrderNo	OrderStatus	OrderDate	OrderSource	OrderType	CashMemoNo	CashMemoStatus	CashMemoDate	OrderQuantity	ConsumedSubsidyQty	AreaName	DeliveryMan	RefillPaymentStatus	IVRSBookingNumber	MobileNo	BookingDoneThroughRegistereMobile	ConsumerAddress	IsRefillPort	EkycStatus
517827	Allocated-Printed	14-02-2026 9:41	IVRS	Refill	1234567	Printed	14-02-2026	1	1	VALLIKKADU	GIREESHAN ( C )		'1111111111	'1111111111	Y	4/146 AMINAS VALIYA PARAMBATH NR. VALLIKKADU SARAMBI PALLIVATAKARA	N	EKYC NOT DONE
```

### File Size and Row Limits

- **Maximum file size:** 10 MB (`MAX_UPLOAD_SIZE_BYTES`)
- **Maximum rows:** 1000 (`MAX_ROW_COUNT` -- defined but enforcement TBD in current code)
- **Typical batch:** 30-50 orders per day

## State of the Art

This is a documentation-only phase. No technology evolution is relevant.

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No CSV docs | CSV_FORMAT.md | Phase 15 | Employee self-service for CSV questions |

## Open Questions

1. **Where should CSV_FORMAT.md live?**
   - What we know: README.md and DEPLOY.md are at project root. Phase 16 will cross-link from DEPLOY.md.
   - What's unclear: Should it be at root or in a `docs/` directory?
   - Recommendation: Project root. Consistent with existing docs (README.md, DEPLOY.md). The REQUIREMENTS.md explicitly says "MkDocs / Docusaurus documentation site" is out of scope, implying simple flat files.

2. **Is MAX_ROW_COUNT enforced in the upload endpoint?**
   - What we know: `MAX_ROW_COUNT = 1000` is defined in main.py but no enforcement code was found in the upload flow.
   - What's unclear: Whether this limit should be documented if not currently enforced.
   - Recommendation: Document it with a note like "The system supports up to 1000 orders per upload." If it becomes enforced later, docs are already correct.

3. **Should the document include screenshots of CDCMS export workflow?**
   - What we know: The audience is non-technical office employees.
   - What's unclear: Whether the planner should plan for screenshot capture.
   - Recommendation: No screenshots -- this is a Markdown file. Text instructions with exact CDCMS menu paths would suffice. CDCMS UI may change, making screenshots stale.

## Sources

### Primary (HIGH confidence)
- `core/data_import/csv_importer.py` -- ColumnMapping class (12 fields), CsvImporter._validate_columns(), _row_to_order_with_warnings(), _resolve_weight_with_warning(), _read_file(), all RowError messages
- `core/data_import/cdcms_preprocessor.py` -- CDCMS_COL_* constants, clean_cdcms_address() (10-step pipeline), _validate_cdcms_columns(), preprocess_cdcms() status filter logic
- `apps/kerala_delivery/api/main.py` -- GEOCODING_REASON_MAP (6 entries), ALLOWED_EXTENSIONS, MAX_UPLOAD_SIZE_BYTES, _is_cdcms_format(), upload_and_optimize() error paths, ImportFailure model
- `apps/kerala_delivery/config.py` -- CYLINDER_WEIGHTS (8 key-value pairs), INDIA_COORDINATE_BOUNDS, CDCMS_AREA_SUFFIX, DEFAULT_CYLINDER_KG
- `data/sample_orders.csv` -- 30-row standard CSV sample
- `data/sample_cdcms_export.csv` -- Real CDCMS export sample (27+ rows)
- `tests/core/data_import/test_cdcms_preprocessor.py` -- SAMPLE_CDCMS_HEADER (19-column header), before/after address cleaning pairs
- `tests/core/data_import/test_csv_importer.py` -- Validation error scenarios, row number convention tests

### Secondary (MEDIUM confidence)
- None needed -- all content sourced from codebase

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- CDCMS format specification: HIGH -- extracted from source constants and sample file
- Standard CSV format specification: HIGH -- extracted from ColumnMapping class with all 12 fields
- Rejection reasons: HIGH -- complete inventory extracted from all error paths in csv_importer.py, cdcms_preprocessor.py, and main.py
- Address cleaning pipeline: HIGH -- all 10 steps from clean_cdcms_address() with test-verified examples
- Example rows: HIGH -- from actual sample files that pass validation

**Research date:** 2026-03-05
**Valid until:** Indefinitely (documentation of existing code -- only changes when code changes)
