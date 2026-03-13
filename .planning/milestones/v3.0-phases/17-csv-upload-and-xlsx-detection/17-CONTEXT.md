# Phase 17: CSV Upload and XLSX Detection - Context

**Gathered:** 2026-03-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can upload both .csv and .xlsx CDCMS files, see which drivers are in the file with order counts and status, select which drivers to process, then optimization runs for selected drivers only. The .xlsx CDCMS format detection bug is fixed so Excel files are correctly identified and preprocessed.

</domain>

<decisions>
## Implementation Decisions

### Driver Preview Layout
- Checkbox table with columns: checkbox, driver name, order count, status badge
- Fuzzy match details shown as inline sub-rows (indented, always visible): "ANIL PK" → Anil P (92%)
- Semantic color badges: Green = Existing, Blue = New, Amber = Matched, Purple = Reactivated
- Stats bar above the table: "4 drivers · 41 orders · 2 new · 1 matched · 1 reactivated"
- "Select All (N)" / "Deselect All" toggle above the table with selected count

### Driver Selection Behavior
- All drivers selected by default — user unchecks the ones they don't want
- Deselected drivers' orders are imported and geocoded but NOT optimized (no route generated)
- All drivers from CSV are auto-created in DB regardless of selection — selection only controls route generation
- Drivers grow organically from every CSV upload as Phase 16 intended

### Fuzzy Match Handling
- Informational only — auto-merge as Phase 16 decided, no confirm/reject per match
- Match score (e.g., 92%) is visible to the user for transparency
- Reactivated drivers shown with Purple status badge + sub-row note, no special warning banner
- Wrong matches are fixed on the Driver Management page after processing

### Upload Flow Structure
- In-page steps (no separate pages or modals): Upload → Driver Preview → Results
- Step 1 (Upload): Drop zone + file picker, "Upload" button parses file only (no geocoding/optimization)
- Between steps: inline progress text spinner ("Parsing file...") on the upload button
- Step 2 (Driver Preview): Shows filename, stats bar, checkbox table, "← Back" and "Process Selected →" buttons
- Step 3 (Results): Existing import summary + route cards + QR codes (unchanged from current)
- "Back" button returns to empty file picker (clean reset, discards parse)
- Always show preview — even for single-driver files, no auto-skip
- Processing state between Step 2 and Step 3: existing upload progress pattern (geocoding → optimizing → saving)

### XLSX Detection Fix
- Fix `_is_cdcms_format()` to handle .xlsx binary files (currently reads raw text, fails on ZIP-based Excel format)
- "Allocated-Printed" OrderStatus filter applied by default (CSV-04)
- Column matching by name, not position (CSV-05) — already implemented in CDCMS preprocessor

### Claude's Discretion
- Two-endpoint vs single-endpoint architecture for the parse → preview → process split
- Exact loading animation and transition timing
- Mobile responsive breakpoints for the driver preview table
- Error handling for edge cases (empty file, no DeliveryMan column, all orders filtered out)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `UploadRoutes.tsx` (792 lines): Existing upload workflow with drop zone, file validation, results display — extend with new "driver-preview" state
- `UploadRoutes.css` (529 lines): Industrial-utilitarian theme with amber accents — extend for preview table styling
- `auto_create_drivers_from_csv()` (main.py:847-926): Already returns driver summary with new/matched/reactivated/existing categorization
- `_is_cdcms_format()` (main.py:627-652): CDCMS detection function — needs fix for .xlsx files
- `_read_cdcms_file()` (cdcms_preprocessor.py:481-514): Already handles .xlsx via pandas `read_excel()`
- DaisyUI `tw:table`, `tw:checkbox`, `tw:badge` components available for the preview table
- `EmptyState` component for edge cases (no drivers found)

### Established Patterns
- Workflow state machine in UploadRoutes: `idle → selected → uploading → success | error` — add `driver-preview` state
- Repository pattern for all DB operations (driver CRUD already complete)
- API returns Pydantic models (`OptimizationSummary`) — extend or add new response model for parse-only step
- DaisyUI components with `tw:` prefix (colon, not hyphen)
- Tailwind v4 responsive: `lg:tw:stats-horizontal`

### Integration Points
- `POST /api/upload-orders`: Needs splitting or new endpoint for parse-only step
- `UploadRoutes.tsx` state machine: Add `driver-preview` between `uploading` and `success`
- Driver summary data already flows from backend — just needs dashboard rendering
- `preprocess_cdcms()` filter parameters: `filter_delivery_man` already supports per-driver filtering

</code_context>

<specifics>
## Specific Ideas

- The preview table should feel like a natural extension of the existing upload page — same industrial-utilitarian aesthetic, not a jarring new component
- Stats bar gives office staff instant situational awareness before they scan the table
- Fuzzy match scores visible because office staff are the ones who know if "SURESH K" is really "SURESH KUMAR" — the percentage helps them decide if they need to fix it later
- "Back" is a clean reset because re-parsing is cheap and avoids stale state bugs

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 17-csv-upload-and-xlsx-detection*
*Context gathered: 2026-03-13*
