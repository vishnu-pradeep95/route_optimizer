# Phase 3: Data Integrity - Context

**Gathered:** 2026-03-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Make every geocoding failure visible to the office user with a per-row reason — no order silently disappears from the map. Fix the silent drop bug where orders that fail geocoding are excluded from optimization without any indication. Add CSV row-level pre-validation before geocoding. Surface structured import summaries in the dashboard.

</domain>

<decisions>
## Implementation Decisions

### Failure Response Structure
- Enrich the existing `OptimizationSummary` response with a `failures` array — no separate endpoint
- Each failure entry includes: row number, address snippet, reason string, and stage (validation or geocoding)
- Two distinct stages: `validation` (bad CSV fields caught before geocoding) and `geocoding` (valid row but address not found by Google)
- Include summary counts in the response: `total_rows`, `geocoded`, `failed_geocoding`, `failed_validation` — dashboard doesn't need to calculate from array

### Import Summary Display
- New summary section placed BETWEEN the upload area and the route cards — staff sees it before looking at routes
- Summary counts (succeeded/failed) always visible; failure detail table is expandable (collapsed by default)
- Amber/yellow background when failures exist; green background when all rows succeed
- Zero-failure state: compact green confirmation bar ("All 50 orders geocoded successfully") — reassures staff nothing was lost

### Partial Success Behavior
- Auto-continue optimizing whatever succeeded — no blocking confirmation dialog. Office staff upload once daily and need routes fast; they can fix failed addresses in the next batch
- Three distinct categories in the summary: **routed** (geocoded + assigned to vehicle), **unassigned** (geocoded but optimizer couldn't fit), **failed** (validation or geocoding error)
- Zero-success case: show the import summary with all failures listed, no route cards, clear message "No orders could be geocoded — check addresses below" (replaces current generic 400 error)

### Pre-validation Scope
- Validate per-row before geocoding: empty/missing address → reject row, invalid weight (negative/non-numeric) → use default 14.2kg and warn, missing order_id → auto-generate (existing behavior)
- Duplicate order IDs in the same CSV → flag the second occurrence as a validation error (CDCMS re-exports sometimes duplicate)
- Strict for critical fields (address, duplicate ID) → row rejected. Lenient for optional fields (weight, quantity) → use defaults and include warning in response
- Error messages reference original CSV column names (via ColumnMapping), not internal field names — staff sees exactly which spreadsheet column to fix

### Claude's Discretion
- Exact Pydantic model structure for the enriched response (field names, nesting)
- How to collect validation errors through CsvImporter (new return type or exception accumulator)
- DaisyUI component choices for the summary section (alert, card, collapse, etc.)
- Whether warnings (lenient defaults used) appear in the same `failures` array or a separate `warnings` array
- Geocoding error reason extraction from Google API response codes

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `OptimizationSummary` Pydantic model (main.py) — extend with failure/count fields
- `CsvImporter._row_to_order()` (csv_importer.py:143) — already catches ValueError/KeyError/TypeError per row with TODO "collect these into a validation report"
- `UploadRoutes.tsx` workflow states — "success" state already has summary stats bar that can be enriched
- `ColumnMapping` (csv_importer.py:41) — maps CSV column names to internal fields, use for error messages
- DaisyUI 5 + Tailwind 4 installed in Phase 1 — `tw-` prefix, available for summary section components

### Established Patterns
- API responses use Pydantic `BaseModel` with `Field()` descriptors — extend OptimizationSummary the same way
- Error handling: `HTTPException(status_code, detail)` for user-facing errors — zero-success case should return structured response instead of 400
- Dashboard fetches via `uploadAndOptimize()` in `lib/api.ts` — returns parsed JSON, dashboard uses typed response
- CSS in `UploadRoutes.css` with vanilla class names — Phase 4 migrates to Tailwind, so new CSS should follow existing pattern for now

### Integration Points
- `upload_and_optimize()` endpoint (main.py:614) — modify to collect failures during parsing and geocoding loops
- `CsvImporter.import_orders()` (csv_importer.py:111) — change return type or add error collection to surface row-level failures
- `UploadRoutes.tsx` success state (line 315) — insert import summary section before route cards
- `types.ts` — add TypeScript types matching the enriched response model
- `lib/api.ts` `uploadAndOptimize()` — update response type

</code_context>

<specifics>
## Specific Ideas

- Error messages should be actionable for non-technical office staff: "Row 12: Empty ConsumerAddress — add a delivery address" not "Row 12: ValueError: address_raw is None"
- The geocoding failure reason should surface Google's status code meaningfully: ADDRESS_NOT_FOUND → "Address not recognized", ZERO_RESULTS → "No location found for this address", REQUEST_DENIED → "Geocoding service error"
- The import summary should feel like a "receipt" for the upload — staff can glance at it, see everything's fine, and move on to routes

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-data-integrity*
*Context gathered: 2026-03-01*
