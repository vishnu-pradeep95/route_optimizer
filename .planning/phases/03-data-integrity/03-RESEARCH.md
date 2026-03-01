# Phase 3: Data Integrity - Research

**Researched:** 2026-03-01
**Domain:** CSV import validation, geocoding error surfacing, partial-success workflow, FastAPI/React response enrichment
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Failure Response Structure
- Enrich the existing `OptimizationSummary` response with a `failures` array -- no separate endpoint
- Each failure entry includes: row number, address snippet, reason string, and stage (validation or geocoding)
- Two distinct stages: `validation` (bad CSV fields caught before geocoding) and `geocoding` (valid row but address not found by Google)
- Include summary counts in the response: `total_rows`, `geocoded`, `failed_geocoding`, `failed_validation` -- dashboard doesn't need to calculate from array

#### Import Summary Display
- New summary section placed BETWEEN the upload area and the route cards -- staff sees it before looking at routes
- Summary counts (succeeded/failed) always visible; failure detail table is expandable (collapsed by default)
- Amber/yellow background when failures exist; green background when all rows succeed
- Zero-failure state: compact green confirmation bar ("All 50 orders geocoded successfully") -- reassures staff nothing was lost

#### Partial Success Behavior
- Auto-continue optimizing whatever succeeded -- no blocking confirmation dialog. Office staff upload once daily and need routes fast; they can fix failed addresses in the next batch
- Three distinct categories in the summary: **routed** (geocoded + assigned to vehicle), **unassigned** (geocoded but optimizer couldn't fit), **failed** (validation or geocoding error)
- Zero-success case: show the import summary with all failures listed, no route cards, clear message "No orders could be geocoded -- check addresses below" (replaces current generic 400 error)

#### Pre-validation Scope
- Validate per-row before geocoding: empty/missing address -> reject row, invalid weight (negative/non-numeric) -> use default 14.2kg and warn, missing order_id -> auto-generate (existing behavior)
- Duplicate order IDs in the same CSV -> flag the second occurrence as a validation error (CDCMS re-exports sometimes duplicate)
- Strict for critical fields (address, duplicate ID) -> row rejected. Lenient for optional fields (weight, quantity) -> use defaults and include warning in response
- Error messages reference original CSV column names (via ColumnMapping), not internal field names -- staff sees exactly which spreadsheet column to fix

### Claude's Discretion
- Exact Pydantic model structure for the enriched response (field names, nesting)
- How to collect validation errors through CsvImporter (new return type or exception accumulator)
- DaisyUI component choices for the summary section (alert, card, collapse, etc.)
- Whether warnings (lenient defaults used) appear in the same `failures` array or a separate `warnings` array
- Geocoding error reason extraction from Google API response codes

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DATA-01 | User sees which orders failed geocoding, with reason per row (not silently dropped) | Geocoding loop in main.py:760-795 already has status/error_msg -- collect into failures array instead of just logging. GeocodingResult.raw_response provides Google API status. See Architecture Pattern 1 (error collection) and Code Examples (geocoding failure capture). |
| DATA-02 | Upload response includes import summary: N succeeded, M failed, with downloadable failure report | Extend OptimizationSummary (main.py:562) with ImportFailure list and counts. Current model has 8 fields -- add 5 count fields and failures array. See Standard Stack (Pydantic response model). |
| DATA-03 | Partially-geocoded batches still optimize the successful orders (not all-or-nothing) | Current code at main.py:798-824 already filters to geocoded orders but raises HTTPException when none succeed. Change zero-success case to return structured response instead of 400. Partial success already works for N>0 geocoded orders. |
| DATA-04 | Depot coordinates from config.py (Vatakara 11.52N) flow correctly through entire pipeline -- audit and fix any leaks | config.py:23 has DEPOT_LOCATION at 11.624N, 75.580E. main.py:592 and :1097 use config.DEPOT_LOCATION. Integration tests still use `kochi_depot` fixture names but coordinates are Vatakara-area per Phase 1 fix. Audit all coordinate literals and fixture references. |
| DATA-05 | CSV import validation shows row-level errors (missing fields, bad formats) before geocoding starts | CsvImporter._row_to_order() (csv_importer.py:143-155) already catches ValueError/KeyError/TypeError per row with TODO "collect these into a validation report". Change return type from `list[Order]` to `ImportResult` with orders + errors. |
</phase_requirements>

## Summary

This phase addresses a critical data integrity bug: orders that fail geocoding are silently dropped from the optimization, giving office staff no indication that deliveries were lost. The fix involves three layers: (1) pre-geocoding CSV row validation in `CsvImporter`, (2) geocoding error collection in the `upload_and_optimize` endpoint, and (3) a structured import summary in the dashboard UI.

The codebase is well-prepared for this change. `CsvImporter._row_to_order()` already catches row-level exceptions with an explicit TODO to "collect these into a validation report." The geocoding loop already extracts Google API status codes and error messages but only logs them. `OptimizationSummary` is a simple Pydantic model that can be extended with failure data. The dashboard already renders summary stats in the success state.

The primary technical challenge is threading error information through three layers (CsvImporter -> main.py endpoint -> React dashboard) while maintaining the existing partial-success behavior (geocoded orders still get optimized even when some fail). The zero-success case requires special handling: instead of raising an HTTPException(400), return a structured response with all failures listed.

**Primary recommendation:** Introduce an `ImportResult` dataclass as the return type of `CsvImporter.import_orders()` containing both valid orders and row-level errors, then enrich `OptimizationSummary` with failure arrays and counts. Use DaisyUI alert + collapse components for the import summary section.

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Pydantic | v2 (already installed) | Response models for enriched OptimizationSummary | Already used throughout -- BaseModel with Field() descriptors |
| FastAPI | 0.115+ (already installed) | Endpoint modification, response model | Already the API framework |
| React | 19.x (already installed) | Dashboard UI for import summary | Already the frontend framework |
| DaisyUI | 5.x with tw- prefix (Phase 1) | Summary section UI components | Already installed, theme configured |
| Tailwind CSS | 4.x with prefix(tw) (Phase 1) | Utility classes for summary styling | Already installed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pandas | 2.x (already installed) | CSV row iteration in CsvImporter | Already used for file reading |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pydantic `ImportResult` | Plain dataclass | Pydantic gives automatic JSON serialization and validation; already the project pattern |
| DaisyUI alert+collapse | Custom HTML/CSS | DaisyUI is installed; using it avoids hand-rolling expandable sections |

**Installation:**
```bash
# No new dependencies required -- all libraries already installed
```

## Architecture Patterns

### Recommended Changes to Existing Structure
```
core/data_import/
  csv_importer.py            # Modify: import_orders() returns ImportResult
                             # Add: ImportResult, RowError models

apps/kerala_delivery/api/
  main.py                    # Modify: OptimizationSummary + ImportFailure models
                             # Modify: upload_and_optimize() collects errors
                             # Modify: zero-success returns response, not 400

apps/kerala_delivery/dashboard/src/
  types.ts                   # Add: ImportFailure, enriched UploadResponse types
  lib/api.ts                 # Modify: UploadResponse type with new fields
  pages/UploadRoutes.tsx     # Add: ImportSummary section between upload and routes
  pages/UploadRoutes.css     # Add: styles for import summary (or use DaisyUI classes)
```

### Pattern 1: Error Collection Through Import Pipeline
**What:** Instead of swallowing exceptions in a try/except loop, collect them into a typed list and return alongside valid data.
**When to use:** Any batch processing where partial success is expected and per-item errors must be surfaced.

Current code (csv_importer.py:143-155):
```python
# CURRENT: silently drops bad rows
for idx, row in df.iterrows():
    try:
        order = self._row_to_order(row, idx)
        orders.append(order)
    except (ValueError, KeyError, TypeError) as e:
        logger.warning("Skipping row %s: %s", idx, e)
```

Recommended change:
```python
# NEW: collects errors alongside valid orders
class RowError(BaseModel):
    """A single row-level validation error."""
    row_number: int = Field(..., description="1-based CSV row number (header=0)")
    column: str = Field(default="", description="CSV column name that caused the error")
    message: str = Field(..., description="Human-readable error message")
    stage: Literal["validation"] = "validation"

class ImportResult(BaseModel):
    """Result of CSV import: valid orders + row-level errors."""
    orders: list[Order] = Field(default_factory=list)
    errors: list[RowError] = Field(default_factory=list)
    warnings: list[RowError] = Field(default_factory=list)

def import_orders(self, source: str) -> ImportResult:
    # ... read file, validate columns ...
    result = ImportResult()
    seen_order_ids: set[str] = set()

    for idx, row in df.iterrows():
        row_num = idx + 2  # 1-based, accounting for header row
        try:
            # Pre-validation checks
            address_raw = self._get_field(row, self.mapping.address, default="")
            if not address_raw:
                col_display = self.mapping.address
                result.errors.append(RowError(
                    row_number=row_num,
                    column=col_display,
                    message=f"Empty {col_display} -- add a delivery address"
                ))
                continue

            order = self._row_to_order(row, idx)

            # Duplicate check
            if order.order_id in seen_order_ids:
                result.errors.append(RowError(
                    row_number=row_num,
                    column=self.mapping.order_id,
                    message=f"Duplicate {self.mapping.order_id} '{order.order_id}' -- already in row above"
                ))
                continue
            seen_order_ids.add(order.order_id)

            result.orders.append(order)
        except (ValueError, KeyError, TypeError) as e:
            result.errors.append(RowError(
                row_number=row_num,
                column="",
                message=str(e)
            ))

    return result
```

### Pattern 2: Enriched Response Model with Failure Arrays
**What:** Extend the existing Pydantic response to carry structured failure data alongside success data.
**When to use:** When the API consumer needs both results and per-item error detail.

```python
class ImportFailure(BaseModel):
    """A single import failure (validation or geocoding)."""
    row_number: int = Field(..., description="1-based CSV row number")
    address_snippet: str = Field(default="", description="First 80 chars of the address (or empty if no address)")
    reason: str = Field(..., description="Human-readable failure reason")
    stage: Literal["validation", "geocoding"] = Field(..., description="When the failure occurred")

class OptimizationSummary(BaseModel):
    """Summary of the optimization run including import diagnostics."""
    # Existing fields (unchanged)
    run_id: str
    assignment_id: str
    total_orders: int
    orders_assigned: int
    orders_unassigned: int
    vehicles_used: int
    optimization_time_ms: float
    created_at: datetime

    # NEW: import diagnostics
    total_rows: int = Field(default=0, description="Total rows in uploaded CSV")
    geocoded: int = Field(default=0, description="Orders successfully geocoded")
    failed_geocoding: int = Field(default=0, description="Orders that failed geocoding")
    failed_validation: int = Field(default=0, description="Rows rejected during pre-validation")
    failures: list[ImportFailure] = Field(default_factory=list, description="Per-row failure details")
    warnings: list[ImportFailure] = Field(default_factory=list, description="Per-row warnings (defaults applied)")
```

### Pattern 3: Zero-Success Structured Response
**What:** Replace HTTPException(400) for zero-geocoded-orders with a valid response containing only failures.
**When to use:** When the caller needs to display detailed error information, not just an error string.

```python
# CURRENT (main.py:816-824): raises HTTPException -- dashboard shows generic error
if not geocoded:
    raise HTTPException(status_code=400, detail="No orders could be geocoded...")

# NEW: return structured response with sentinel values
if not geocoded:
    return OptimizationSummary(
        run_id="",
        assignment_id="",
        total_orders=len(orders),
        orders_assigned=0,
        orders_unassigned=0,
        vehicles_used=0,
        optimization_time_ms=0,
        created_at=datetime.now(timezone.utc),
        total_rows=total_row_count,
        geocoded=0,
        failed_geocoding=geocoding_failure_count,
        failed_validation=validation_failure_count,
        failures=all_failures,
        warnings=all_warnings,
    )
```

### Anti-Patterns to Avoid
- **Raising HTTPException for expected partial failures:** Geocoding failures are expected operational outcomes, not server errors. Return structured data, not error responses.
- **Computing counts from array length on the client:** The CONTEXT.md explicitly requires server-side counts. Don't make the dashboard calculate `failures.filter(f => f.stage === 'geocoding').length`.
- **Using internal field names in error messages:** Error messages MUST use the original CSV column names from `ColumnMapping` (e.g., "ConsumerAddress" not "address_raw"). Staff sees the spreadsheet column name they need to fix.
- **Breaking backward compatibility:** The enriched response adds new fields but keeps all existing fields. The dashboard should handle responses both with and without the new fields during transition.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Expandable/collapsible failure detail table | Custom JS show/hide toggle | DaisyUI `collapse` or `details` component with `tw-` prefix | Already installed, accessible, keyboard-navigable |
| Status-colored summary banners | Custom CSS class switching | DaisyUI `alert` component variants (alert-success, alert-warning) | Semantic color mapping already in logistics theme |
| CSV row number tracking | Manual counter in loop | pandas `df.iterrows()` already provides `idx`; add +2 for 1-based header offset | Correct row numbers matter for user trust |
| Google API status code mapping | Giant if/else chain | Simple dict lookup `STATUS_MESSAGES = {"ZERO_RESULTS": "No location found...", ...}` | Maintainable, testable, extensible |

**Key insight:** This phase is about data plumbing (threading errors through layers) not about building new infrastructure. Every piece already exists -- the challenge is connecting them without breaking the existing success path.

## Common Pitfalls

### Pitfall 1: Off-by-One Row Numbers
**What goes wrong:** Error messages say "Row 0" or "Row 1" when the user sees "Row 2" in their spreadsheet (because pandas uses 0-based indexing and CSVs have a header row).
**Why it happens:** `df.iterrows()` yields 0-based integer indices. The CSV header is row 1 in the spreadsheet, so data row 0 is actually spreadsheet row 2.
**How to avoid:** Always compute `row_number = pandas_idx + 2` (1 for 1-based, 1 for header). Document this formula in a comment.
**Warning signs:** Test CSV with 3 rows reports errors on "Row 0, 1, 2" instead of "Row 2, 3, 4".

### Pitfall 2: Zero-Success Response Breaking Dashboard
**What goes wrong:** Changing from HTTPException(400) to a 200 response for zero-geocoded-orders breaks the dashboard's error handling path.
**Why it happens:** The dashboard currently catches `response.ok === false` to show errors. A 200 with empty routes bypasses the error display.
**How to avoid:** The dashboard must check `uploadResult.geocoded === 0` (or `uploadResult.orders_assigned === 0 && uploadResult.failures.length > 0`) and show the import summary with "No orders could be geocoded" message -- a distinct workflow state between "success" and "error".
**Warning signs:** Upload a CSV with all bad addresses and see a blank results page instead of the failure summary.

### Pitfall 3: Google API Status vs. User-Facing Reason
**What goes wrong:** Exposing raw Google API status codes ("ZERO_RESULTS", "REQUEST_DENIED") to non-technical office staff who have no idea what they mean.
**Why it happens:** Developer convenience -- just pass through the API response.
**How to avoid:** Map Google status codes to actionable messages:
```python
GEOCODING_REASON_MAP = {
    "ZERO_RESULTS": "Address not recognized by Google Maps",
    "REQUEST_DENIED": "Geocoding service error (contact admin)",
    "OVER_QUERY_LIMIT": "Geocoding quota exceeded (try again later)",
    "OVER_DAILY_LIMIT": "Geocoding quota exceeded (try again later)",
    "INVALID_REQUEST": "Address could not be processed",
    "UNKNOWN_ERROR": "Geocoding service temporarily unavailable",
}
```
**Warning signs:** Staff sees "ZERO_RESULTS" in the error table and has no idea what to do.

### Pitfall 4: Forgetting the Warning Path for Lenient Defaults
**What goes wrong:** Weight defaults are applied silently -- staff doesn't know their weight column was ignored.
**Why it happens:** The current code silently falls back to 14.2kg in `_resolve_weight()` without any indication.
**How to avoid:** Return warnings (separate from errors) when lenient defaults are used. The response should include: "Row 5: Invalid weight 'abc' in WeightKG column -- using default 14.2 kg". Use a `warnings` array separate from `failures` so warnings don't clutter the error view.
**Warning signs:** Staff uploads a CSV with all weight values in "pounds" format, gets routes with wrong weights, has no indication anything was adjusted.

### Pitfall 5: Address Snippet Leaking PII
**What goes wrong:** The `address_snippet` field in the failure response may contain customer-identifying information (e.g., "Near Raju's house, Vatakara").
**Why it happens:** Indian addresses often include personal names as landmarks.
**How to avoid:** This is acceptable for the office dashboard (staff already has the full CSV). Just truncate to first 80 chars. Do NOT log full addresses to external services.
**Warning signs:** None -- this is an acceptable tradeoff per project design (staff sees their own data).

### Pitfall 6: Kozhikode Coordinates Leaking Through Geocoding
**What goes wrong:** Google Geocoding API returns Kozhikode city center coordinates (11.25N, 75.77E) when an address in the Vatakara area is ambiguous.
**Why it happens:** "Vatakara" is a taluk in Kozhikode district. Ambiguous addresses like "Near temple, Kerala" may geocode to Kozhikode city (30km south of Vatakara depot at 11.62N).
**How to avoid:** DATA-04 audit: check geocoded coordinates are within a reasonable radius of the depot. The `config.INDIA_COORDINATE_BOUNDS` is too broad (all of India). Consider adding a local bounds check (e.g., within 30km of depot) as a warning, not a rejection.
**Warning signs:** Geocoded delivery points appear 30+ km from the depot on the map.

## Code Examples

Verified patterns from the existing codebase:

### Extending OptimizationSummary (Pydantic v2 pattern)
```python
# Source: existing pattern in main.py:562-571
# All existing fields use Field(...) with descriptions
# New fields MUST use Field() with default values for backward compatibility
class ImportFailure(BaseModel):
    row_number: int = Field(..., description="1-based row in original CSV")
    address_snippet: str = Field(default="", description="First 80 chars of address")
    reason: str = Field(..., description="Human-readable error reason")
    stage: Literal["validation", "geocoding"] = Field(
        ..., description="When the failure occurred"
    )

class OptimizationSummary(BaseModel):
    # ... existing fields unchanged ...
    total_rows: int = Field(default=0)
    geocoded: int = Field(default=0)
    failed_geocoding: int = Field(default=0)
    failed_validation: int = Field(default=0)
    failures: list[ImportFailure] = Field(default_factory=list)
    warnings: list[ImportFailure] = Field(default_factory=list)
```

### Collecting Geocoding Failures (from existing loop at main.py:760-795)
```python
# Source: main.py:760-795 geocoding loop
# Current code logs failures -- collect them instead
geocoding_failures: list[ImportFailure] = []

for order in orders:
    if not order.is_geocoded:
        cached = await repo.get_cached_geocode(session, order.address_raw)
        if cached:
            order.location = cached
        elif geocoder:
            result = geocoder.geocode(order.address_raw)
            if result.success and result.location:
                order.location = result.location
                await repo.save_geocode_cache(...)
            else:
                # COLLECT instead of just logging
                raw = getattr(result, "raw_response", {})
                status = raw.get("status", "UNKNOWN")
                reason = GEOCODING_REASON_MAP.get(
                    status,
                    f"Geocoding failed ({status})"
                )
                geocoding_failures.append(ImportFailure(
                    row_number=order_row_numbers.get(order.order_id, 0),
                    address_snippet=order.address_raw[:80],
                    reason=reason,
                    stage="geocoding",
                ))
```

### DaisyUI Import Summary Component (tw- prefix)
```tsx
// Source: DaisyUI 5 docs + project's tw- prefix convention from Phase 1
// Placed BETWEEN upload area and route cards per user decision

interface ImportSummaryProps {
  totalRows: number;
  geocoded: number;
  failedGeocoding: number;
  failedValidation: number;
  ordersAssigned: number;
  ordersUnassigned: number;
  failures: ImportFailure[];
  warnings: ImportFailure[];
}

function ImportSummary({ totalRows, geocoded, failedGeocoding, failedValidation,
                         ordersAssigned, ordersUnassigned, failures, warnings }: ImportSummaryProps) {
  const hasFailures = failures.length > 0;
  const alertClass = hasFailures
    ? "tw-alert tw-alert-warning"    // Amber background when failures exist
    : "tw-alert tw-alert-success";   // Green when all rows succeed

  return (
    <div className="import-summary">
      {/* Always-visible summary counts */}
      <div className={alertClass}>
        {!hasFailures ? (
          <span>All {totalRows} orders geocoded successfully</span>
        ) : (
          <div className="summary-counts">
            <span>{ordersAssigned} routed</span>
            <span>{ordersUnassigned} unassigned</span>
            <span>{failedGeocoding + failedValidation} failed</span>
          </div>
        )}
      </div>

      {/* Expandable failure detail table -- collapsed by default */}
      {hasFailures && (
        <div className="tw-collapse tw-collapse-arrow tw-bg-base-200">
          <input type="checkbox" />
          <div className="tw-collapse-title tw-font-medium">
            {failures.length} failed row{failures.length !== 1 ? 's' : ''} -- click to expand
          </div>
          <div className="tw-collapse-content">
            <table className="tw-table tw-table-sm">
              <thead>
                <tr>
                  <th>Row</th>
                  <th>Address</th>
                  <th>Reason</th>
                  <th>Stage</th>
                </tr>
              </thead>
              <tbody>
                {failures.map((f, i) => (
                  <tr key={i}>
                    <td>{f.row_number}</td>
                    <td>{f.address_snippet || '--'}</td>
                    <td>{f.reason}</td>
                    <td>{f.stage}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
```

### TypeScript Type for Enriched Response
```typescript
// Source: pattern from existing types.ts and api.ts UploadResponse
export interface ImportFailure {
  row_number: number;
  address_snippet: string;
  reason: string;
  stage: "validation" | "geocoding";
}

export interface UploadResponse {
  // Existing fields
  run_id: string;
  assignment_id: string;
  total_orders: number;
  orders_assigned: number;
  orders_unassigned: number;
  vehicles_used: number;
  optimization_time_ms: number;
  created_at: string;

  // NEW: import diagnostics
  total_rows: number;
  geocoded: number;
  failed_geocoding: number;
  failed_validation: number;
  failures: ImportFailure[];
  warnings: ImportFailure[];
}
```

### Row Number Tracking Through Geocoding
```python
# Problem: CsvImporter knows row numbers, but the geocoding loop in main.py
# only has Order objects (no row number).
# Solution: ImportResult carries row numbers; main.py builds a lookup map.

# In main.py after import:
import_result = importer.import_orders(file_path)
orders = import_result.orders
validation_failures = [
    ImportFailure(
        row_number=e.row_number,
        address_snippet="",
        reason=e.message,
        stage="validation"
    )
    for e in import_result.errors
]

# Build order_id -> row_number map for geocoding failure tracking
# Row numbers come from the RowError entries in ImportResult
order_row_map: dict[str, int] = {}
for idx, row in enumerate(df_rows):  # or track during import
    # ...
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Raise HTTP 400 for all geocoding failures | Return structured response with per-row failures | This phase | Dashboard can show exactly what failed and why |
| Silent row drops in CsvImporter | Collect errors into ImportResult | This phase | Every dropped row is visible with reason |
| Generic "No valid orders" error message | Zero-success structured response with failure details | This phase | Staff sees which addresses to fix |
| Log-only geocoding failures | Structured failure array in API response | This phase | Frontend can display per-row geocoding errors |

**Deprecated/outdated:**
- The current `HTTPException(400)` for zero-geocoded-orders will be replaced with a structured 200 response containing failures. The dashboard must be updated simultaneously.

## Open Questions

1. **Row number tracking through the geocoding stage**
   - What we know: CsvImporter can track row numbers (pandas idx + 2). But the geocoding loop in main.py only has Order objects.
   - What's unclear: Best way to carry row numbers from CsvImporter through to the geocoding loop. Options: (a) add `_source_row` field to Order model, (b) return a dict mapping order_id to row_number from ImportResult, (c) use the order index in the list.
   - Recommendation: Option (b) -- add a `row_numbers: dict[str, int]` field to `ImportResult` mapping `order_id -> row_number`. This avoids polluting the Order model with import-specific metadata.

2. **DaisyUI CSS class prefix behavior with dynamic classes**
   - What we know: DaisyUI 5 classes use `tw-` prefix (e.g., `tw-alert`, `tw-collapse`). This is configured in Phase 1.
   - What's unclear: Whether conditional class names like `tw-alert-success` vs `tw-alert-warning` work correctly with the prefix.
   - Recommendation: Test during implementation. If prefix causes issues with variant classes, fall back to the existing CSS custom properties pattern (using `--color-success-bg` etc.).

3. **Should zero-success return HTTP 200 or a different status?**
   - What we know: Current behavior is HTTP 400 with error detail string. User decision says "show import summary with all failures listed, no route cards."
   - What's unclear: Whether returning HTTP 200 for a "nothing geocoded" response is semantically correct.
   - Recommendation: Return HTTP 200 with `run_id: ""` and `orders_assigned: 0`. The response is valid (the import was processed successfully; it just found no geocodable addresses). The dashboard checks `geocoded === 0` for the zero-success UI state.

## Google Geocoding API Status Codes Reference

Official status codes from Google Maps Geocoding API (verified via [official documentation](https://developers.google.com/maps/documentation/geocoding/requests-geocoding)):

| API Status | User-Facing Message | Action for Staff |
|------------|---------------------|------------------|
| `OK` | (success) | -- |
| `ZERO_RESULTS` | "Address not recognized by Google Maps" | Check spelling, add landmarks |
| `REQUEST_DENIED` | "Geocoding service error (contact admin)" | Admin checks API key/billing |
| `OVER_QUERY_LIMIT` | "Geocoding quota exceeded (try again later)" | Wait or contact admin |
| `OVER_DAILY_LIMIT` | "Geocoding quota exceeded (try again later)" | Wait or contact admin |
| `INVALID_REQUEST` | "Address could not be processed" | Fix address format |
| `UNKNOWN_ERROR` | "Geocoding service temporarily unavailable" | Retry upload |

**Important:** Google does NOT return an `ADDRESS_NOT_FOUND` status code. The CONTEXT.md example "Row 12: ADDRESS_NOT_FOUND" should use `ZERO_RESULTS` internally but display as "Address not recognized" to users.

## Depot Coordinate Audit Guidance (DATA-04)

Current depot location in `config.py`:
- Latitude: **11.624443730714066** (Vatakara, ~11.62N)
- Longitude: **75.57964507762223**

Places to audit for Kozhikode coordinates (11.25N, 75.77E) or outdated Kochi coordinates (9.97N):

| Location | Current Status | Action Needed |
|----------|---------------|---------------|
| `config.py:23` DEPOT_LOCATION | Correct (11.624N) | None |
| `main.py:592` `_build_fleet()` depot= | Uses config.DEPOT_LOCATION | Verify |
| `main.py:1097` route endpoint | Uses config.DEPOT_LOCATION | Verify |
| `tests/conftest.py` vatakara_depot | Correct per Phase 1 | Verify exact match |
| `tests/integration/test_osrm_vroom_pipeline.py` | Uses `kochi_depot` fixture name | Rename fixture; verify coords |
| Geocoded results | Google may return Kozhikode city center | Add distance-from-depot warning |

## Sources

### Primary (HIGH confidence)
- Existing codebase: `csv_importer.py`, `main.py`, `google_adapter.py`, `types.ts`, `api.ts`, `UploadRoutes.tsx` -- direct source code analysis
- [Google Geocoding API Documentation](https://developers.google.com/maps/documentation/geocoding/requests-geocoding) -- status codes verified
- `config.py` -- depot coordinates verified

### Secondary (MEDIUM confidence)
- DaisyUI 5 component library -- alert, collapse, table components. Verified installed in Phase 1 with tw- prefix.

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new libraries needed, all existing
- Architecture: HIGH -- clear code paths identified, TODO comment in source confirms intent
- Pitfalls: HIGH -- based on direct codebase analysis and Google API documentation
- Depot audit: HIGH -- all coordinate sources identified through grep

**Research date:** 2026-03-01
**Valid until:** 2026-03-31 (stable domain -- no external API changes expected)
