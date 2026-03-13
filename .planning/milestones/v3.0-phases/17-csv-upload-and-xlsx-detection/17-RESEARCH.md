# Phase 17: CSV Upload and XLSX Detection - Research

**Researched:** 2026-03-13
**Domain:** File parsing, XLSX detection fix, React form state machine, FastAPI endpoint splitting
**Confidence:** HIGH

## Summary

Phase 17 transforms the existing single-step upload-and-optimize endpoint into a two-step flow: parse-then-preview, then process-selected-drivers. The core backend change is splitting the monolithic `POST /api/upload-orders` into a parse-only step (returns driver list with order counts) and a process step (runs geocoding + optimization for selected drivers only). The frontend adds a `driver-preview` state to the existing UploadRoutes state machine.

The critical bug fix is in `_is_cdcms_format()` (main.py:627-652): it opens files as UTF-8 text and checks for tab-separated headers, which fails silently on `.xlsx` files (ZIP-based binary format). The fix is straightforward -- check file extension first, and for `.xlsx` files, read headers via `pandas.read_excel()` to detect CDCMS columns.

All building blocks already exist. The `auto_create_drivers_from_csv()` function (main.py:847-926) already returns categorized driver summaries (new/matched/reactivated/existing). The `preprocess_cdcms()` function already supports `filter_delivery_man` for per-driver filtering. The `UploadRoutes.tsx` state machine already handles idle/selected/uploading/success/error transitions. The work is connecting these pieces with a new intermediate step.

**Primary recommendation:** Two-endpoint architecture: `POST /api/parse-upload` (parse + driver auto-create, returns preview data) and extend existing `POST /api/upload-orders` with a `selected_drivers` query parameter to filter which drivers get routes.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Checkbox table with columns: checkbox, driver name, order count, status badge
- Fuzzy match details shown as inline sub-rows (indented, always visible): "ANIL PK" -> Anil P (92%)
- Semantic color badges: Green = Existing, Blue = New, Amber = Matched, Purple = Reactivated
- Stats bar above the table: "4 drivers . 41 orders . 2 new . 1 matched . 1 reactivated"
- "Select All (N)" / "Deselect All" toggle above the table with selected count
- All drivers selected by default -- user unchecks the ones they don't want
- Deselected drivers' orders are imported and geocoded but NOT optimized (no route generated)
- All drivers from CSV are auto-created in DB regardless of selection -- selection only controls route generation
- Informational fuzzy match only -- auto-merge as Phase 16 decided, no confirm/reject per match
- Match score (e.g., 92%) is visible to the user for transparency
- Reactivated drivers shown with Purple status badge + sub-row note, no special warning banner
- Wrong matches are fixed on the Driver Management page after processing
- In-page steps (no separate pages or modals): Upload -> Driver Preview -> Results
- Step 1 (Upload): Drop zone + file picker, "Upload" button parses file only (no geocoding/optimization)
- Between steps: inline progress text spinner ("Parsing file...") on the upload button
- Step 2 (Driver Preview): Shows filename, stats bar, checkbox table, "<- Back" and "Process Selected ->" buttons
- Step 3 (Results): Existing import summary + route cards + QR codes (unchanged from current)
- "Back" button returns to empty file picker (clean reset, discards parse)
- Always show preview -- even for single-driver files, no auto-skip
- Processing state between Step 2 and Step 3: existing upload progress pattern
- Fix `_is_cdcms_format()` to handle .xlsx binary files
- "Allocated-Printed" OrderStatus filter applied by default (CSV-04)
- Column matching by name, not position (CSV-05) -- already implemented in CDCMS preprocessor

### Claude's Discretion
- Two-endpoint vs single-endpoint architecture for the parse -> preview -> process split
- Exact loading animation and transition timing
- Mobile responsive breakpoints for the driver preview table
- Error handling for edge cases (empty file, no DeliveryMan column, all orders filtered out)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CSV-01 | System correctly detects CDCMS format in .xlsx Excel files | Fix `_is_cdcms_format()` to check extension first, then read headers via pandas for .xlsx. See "XLSX Detection Fix" in Architecture Patterns |
| CSV-02 | User can see which drivers are found in the uploaded CSV before processing | New `POST /api/parse-upload` endpoint returns driver preview data; new `driver-preview` state in UploadRoutes.tsx renders the checkbox table |
| CSV-03 | User can select which drivers' routes to generate from a multi-driver CSV | Frontend tracks selection state; `POST /api/upload-orders` gains `selected_drivers` parameter; `preprocess_cdcms()` filter_delivery_man used per-driver |
| CSV-04 | System filters to "Allocated-Printed" OrderStatus by default | Already implemented: `preprocess_cdcms()` default `filter_status="Allocated-Printed"`. Verify it's called correctly in parse endpoint |
| CSV-05 | Column order in CSV/XLSX does not affect parsing | Already implemented: `_validate_cdcms_columns()` checks column names in a set, `preprocess_cdcms()` accesses by name. Verify with test |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pandas | 2.x | XLSX/CSV parsing via `read_excel()` and `read_csv()` | Already used in cdcms_preprocessor.py, handles both formats |
| openpyxl | (pandas dependency) | Engine for `read_excel()` | Already installed, pandas uses it for .xlsx |
| FastAPI | 0.115+ | API endpoints with `UploadFile`, `File`, `Query` | Already the API framework |
| React 19 | 19.x | Frontend state machine and UI | Already in dashboard |
| DaisyUI 5 | 5.x | `tw:table`, `tw:checkbox`, `tw:badge` components | Already used, matches design system |
| lucide-react | latest | Icons for UI elements | Already imported in UploadRoutes.tsx |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Pydantic | 2.x | Response model for parse-preview endpoint | Already used for OptimizationSummary |
| RapidFuzz | 3.x | Fuzzy driver name matching | Already used in repository.find_similar_drivers() |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Two endpoints (parse + process) | Single endpoint with `preview_only` flag | Two endpoints is cleaner -- parse returns fast, process is long-running. Single endpoint would require complex state management on server |
| DaisyUI table | Custom HTML table | DaisyUI `tw:table` already used elsewhere, consistent styling, less CSS to write |

**Installation:** No new packages needed. All dependencies already installed.

## Architecture Patterns

### Recommended Endpoint Architecture: Two Endpoints

**What:** Split the upload flow into two API calls:
1. `POST /api/parse-upload` -- fast, parse-only, returns driver preview
2. `POST /api/upload-orders` -- extended with `selected_drivers` parameter

**Why two endpoints (not one with a flag):**
- Parse is fast (~100ms for 50 orders). Process is slow (geocoding + VROOM, 5-30 seconds). Different timeout expectations.
- Parse returns a different response shape (driver list, not optimization summary). Cleaner API contract.
- The file is uploaded once to parse, then referenced by a server-side token for process. Avoids re-uploading the same file.
- "Back" button discards the parse cleanly -- no server-side state to clean up beyond the temp file.

**Parse endpoint response shape:**
```python
class ParsePreviewResponse(BaseModel):
    """Response from POST /api/parse-upload."""
    upload_token: str  # UUID referencing the temp file on disk
    filename: str
    total_rows: int
    filtered_rows: int  # After Allocated-Printed filter
    drivers: list[DriverPreview]

class DriverPreview(BaseModel):
    """One driver found in the uploaded file."""
    csv_name: str  # Name as it appears in the CSV
    display_name: str  # Title-cased display name
    order_count: int
    status: Literal["existing", "new", "matched", "reactivated"]
    matched_to: str | None = None  # For matched/reactivated: the DB driver name
    match_score: float | None = None  # Fuzzy match score (0-100)
```

**Process endpoint extension:**
```python
@app.post("/api/upload-orders")
async def upload_and_optimize(
    request: Request,
    file: UploadFile = File(None),  # Optional if upload_token provided
    upload_token: str = Form(None),  # Reference to previously parsed file
    selected_drivers: str = Form(None),  # Comma-separated driver names to optimize
    session: AsyncSession = SessionDep,
):
```

### XLSX Detection Fix

**What:** Fix `_is_cdcms_format()` to handle .xlsx binary files.

**Current bug:** The function opens any file as UTF-8 text (line 642), reads the first line, and checks for tab-separated CDCMS column names. `.xlsx` files are ZIP archives -- opening as text produces garbage, and the function returns `False`. The file then falls through to the standard CSV path which also fails.

**Fix pattern:**
```python
def _is_cdcms_format(file_path: str) -> bool:
    """Detect whether a file is a raw CDCMS export (tab-separated CSV or Excel)."""
    ext = pathlib.Path(file_path).suffix.lower()

    # For Excel files: read headers via pandas and check column names
    if ext in (".xlsx", ".xls"):
        try:
            df = pd.read_excel(file_path, nrows=0, dtype=str)
            columns = set(df.columns)
            cdcms_markers = {CDCMS_COL_ORDER_NO, CDCMS_COL_ADDRESS}
            return cdcms_markers.issubset(columns)
        except Exception:
            return False

    # For CSV/text files: existing logic (check for tabs + column names)
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            header_line = f.readline().strip()
        if "\t" not in header_line:
            return False
        columns = [col.strip() for col in header_line.split("\t")]
        cdcms_markers = {CDCMS_COL_ORDER_NO, CDCMS_COL_ADDRESS}
        return cdcms_markers.issubset(set(columns))
    except (OSError, UnicodeDecodeError):
        return False
```

**Key insight:** `pd.read_excel(file_path, nrows=0)` reads only headers without loading data. Fast and handles all Excel formats. This is already how `_read_cdcms_file()` works -- the detection function just needs the same approach.

### Frontend State Machine Extension

**Current states:** `idle -> selected -> uploading -> success | error`

**New states:** `idle -> selected -> parsing -> driver-preview -> uploading -> success | error`

```typescript
type WorkflowState =
  | "idle"            // No file selected, show drop zone
  | "selected"        // File chosen, ready to parse
  | "parsing"         // Parsing file (fast, ~100ms)
  | "driver-preview"  // Show driver checkbox table
  | "uploading"       // Geocoding + optimization in progress
  | "success"         // Routes generated, showing results
  | "error";          // Something went wrong
```

**New state data:**
```typescript
// Added to UploadRoutes component state
const [parseResult, setParseResult] = useState<ParsePreviewResponse | null>(null);
const [selectedDrivers, setSelectedDrivers] = useState<Set<string>>(new Set());
```

**State transitions:**
- `idle -> selected`: File chosen (existing behavior)
- `selected -> parsing`: "Upload" button clicked (renamed to "Parse" / "Upload & Preview")
- `parsing -> driver-preview`: Parse API returns successfully
- `parsing -> error`: Parse API fails
- `driver-preview -> idle`: "Back" button clicked (clean reset)
- `driver-preview -> uploading`: "Process Selected" button clicked
- `uploading -> success`: Process API returns successfully
- `uploading -> error`: Process API fails

### Upload Token Pattern

**What:** Server stores parsed file temporarily, returns a UUID token. Client sends token back to process endpoint.

**Why:** Avoids re-uploading the file. The file is already validated, saved to disk, and preprocessed. The token references the temp file path.

**Implementation:**
```python
# Server-side: simple dict mapping token -> file info
_upload_tokens: dict[str, dict] = {}  # token -> {path, filename, created_at, preprocessed_df}

# Token includes preprocessed DataFrame so we don't re-parse
# Tokens expire after 30 minutes (cleanup in background or on access)
```

**Security:** Token is a UUID4 -- unguessable. File is already validated. Temp files are cleaned up on process or expiration.

### Anti-Patterns to Avoid
- **Re-parsing the file on process:** Parse once, store result, reference by token. Re-parsing wastes time and could produce different results if the temp file is modified.
- **Storing driver selection on the server:** Client sends selected drivers with the process request. No server-side session state needed.
- **Auto-skipping preview for single-driver files:** CONTEXT.md explicitly says "Always show preview -- even for single-driver files, no auto-skip."
- **Modal dialogs for preview:** CONTEXT.md explicitly says "In-page steps (no separate pages or modals)."

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| XLSX parsing | Custom ZIP/XML parser | `pandas.read_excel()` | Already used in `_read_cdcms_file()`, handles all Excel formats |
| Fuzzy name matching | Custom string distance | `rapidfuzz` via `repo.find_similar_drivers()` | Already configured with 85 threshold, tested in Phase 16 |
| Checkbox table | Custom checkbox + table HTML | DaisyUI `tw:table` + `tw:checkbox` | Consistent with existing dashboard components |
| File validation | Manual extension/size/type checks | Existing validation in `upload_and_optimize()` | Already handles extension, content-type, size checks |
| Driver auto-creation | New driver creation logic | `auto_create_drivers_from_csv()` | Already handles new/matched/reactivated/existing categorization |

**Key insight:** Nearly all the backend logic exists. Phase 17 is primarily about *orchestrating* existing functions in a new order and building the frontend preview UI.

## Common Pitfalls

### Pitfall 1: Upload Token Memory Leak
**What goes wrong:** `_upload_tokens` dict grows forever if users parse files but never process them.
**Why it happens:** User closes browser, navigates away, or clicks "Back" (which discards parse client-side but doesn't notify server).
**How to avoid:** Add expiration (30 min). Clean up expired tokens on every new parse request. Also delete temp files on expiration.
**Warning signs:** Server memory grows over time; temp directory fills up.

### Pitfall 2: XLSX Detection vs Standard CSV Confusion
**What goes wrong:** An `.xlsx` file that is NOT a CDCMS export (e.g., a standard CSV saved as Excel) passes CDCMS detection because it has columns named "OrderNo" and "ConsumerAddress" by coincidence.
**Why it happens:** The detection only checks for two column names -- a false positive is possible.
**How to avoid:** The existing detection is sufficient for this use case (employees only upload CDCMS exports). Don't over-engineer detection. If false positive occurs, the preprocessor will fail gracefully on missing optional columns.
**Warning signs:** Non-CDCMS Excel files being preprocessed incorrectly.

### Pitfall 3: Race Condition on Upload Token
**What goes wrong:** User clicks "Process Selected" twice rapidly, causing two process requests with the same token.
**Why it happens:** Button not disabled during processing.
**How to avoid:** Disable "Process Selected" button immediately on click (transition to `uploading` state). Delete token after first use.
**Warning signs:** Duplicate optimization runs.

### Pitfall 4: Selected Drivers Name Mismatch
**What goes wrong:** Driver names in `selected_drivers` don't match the preprocessed DataFrame's `delivery_man` column exactly.
**Why it happens:** Case sensitivity, whitespace differences, or title-casing mismatches between display name and CSV name.
**How to avoid:** Use the exact CSV name (as returned by parse endpoint's `csv_name` field) for selection, not the display name. The backend matches against `delivery_man` column which is the original CSV value.
**Warning signs:** Zero orders after filtering by selected drivers.

### Pitfall 5: Stale Tailwind Prefix
**What goes wrong:** New CSS classes use wrong prefix syntax (`tw-` instead of `tw:`).
**Why it happens:** Autopilot from other projects or older code patterns.
**How to avoid:** Always use colon syntax: `tw:table`, `tw:checkbox`, `tw:badge`. In CSS selectors: `.tw\:table`.
**Warning signs:** Unstyled components, missing DaisyUI styles.

### Pitfall 6: FormData vs JSON for Process Endpoint
**What goes wrong:** Trying to send `upload_token` and `selected_drivers` as JSON body alongside a file upload.
**Why it happens:** FastAPI's `File()` and `Form()` use multipart encoding, not JSON.
**How to avoid:** Use `Form()` parameters for upload_token and selected_drivers when file upload is involved. Or better: if the file is already on server (referenced by token), use a JSON body endpoint.
**Warning signs:** 422 Validation Error from FastAPI.

## Code Examples

### Parse Endpoint (Backend)
```python
# Source: Architecture recommendation based on existing codebase patterns

class DriverPreview(BaseModel):
    csv_name: str
    display_name: str
    order_count: int
    status: Literal["existing", "new", "matched", "reactivated"]
    matched_to: str | None = None
    match_score: float | None = None

class ParsePreviewResponse(BaseModel):
    upload_token: str
    filename: str
    total_rows: int
    filtered_rows: int
    drivers: list[DriverPreview]

@app.post("/api/parse-upload", dependencies=[Depends(verify_api_key)])
@limiter.limit("10/minute")
async def parse_upload(
    request: Request,
    file: UploadFile = File(...),
    session: AsyncSession = SessionDep,
):
    # 1. Validate file (reuse existing validation logic)
    # 2. Save to temp file
    # 3. Detect CDCMS format (with XLSX fix)
    # 4. Run preprocess_cdcms() to get DataFrame
    # 5. Run auto_create_drivers_from_csv() to get driver summary
    # 6. Count orders per driver from preprocessed_df
    # 7. Generate upload_token, store {path, df, filename}
    # 8. Return ParsePreviewResponse
    pass
```

### Driver Preview Table (Frontend)
```typescript
// Source: Architecture recommendation following DaisyUI + tw: prefix conventions

interface DriverPreview {
  csv_name: string;
  display_name: string;
  order_count: number;
  status: "existing" | "new" | "matched" | "reactivated";
  matched_to?: string;
  match_score?: number;
}

// Status badge colors matching CONTEXT.md decisions
const STATUS_CONFIG = {
  existing: { label: "Existing", class: "tw:badge-success" },
  new: { label: "New", class: "tw:badge-info" },
  matched: { label: "Matched", class: "tw:badge-warning" },
  reactivated: { label: "Reactivated", class: "tw:badge-secondary" },  // Purple via custom
} as const;
```

### DaisyUI Checkbox Table Pattern
```tsx
// Source: DaisyUI 5 table + checkbox components with tw: prefix

<div className="tw:overflow-x-auto">
  <table className="tw:table">
    <thead>
      <tr>
        <th>
          <label>
            <input
              type="checkbox"
              className="tw:checkbox"
              checked={allSelected}
              onChange={toggleAll}
            />
          </label>
        </th>
        <th>Driver</th>
        <th>Orders</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      {drivers.map((d) => (
        <tr key={d.csv_name}>
          <th>
            <label>
              <input
                type="checkbox"
                className="tw:checkbox"
                checked={selectedDrivers.has(d.csv_name)}
                onChange={() => toggleDriver(d.csv_name)}
              />
            </label>
          </th>
          <td>
            <div>{d.display_name}</div>
            {d.matched_to && d.status === "matched" && (
              <div className="tw:text-xs tw:text-warning tw:pl-4">
                "{d.csv_name}" matched to {d.matched_to} ({d.match_score}%)
              </div>
            )}
          </td>
          <td className="numeric">{d.order_count}</td>
          <td>
            <span className={`tw:badge tw:badge-sm ${STATUS_CONFIG[d.status].class}`}>
              {STATUS_CONFIG[d.status].label}
            </span>
          </td>
        </tr>
      ))}
    </tbody>
  </table>
</div>
```

### Stats Bar Pattern
```tsx
// Source: Existing DaisyUI stats pattern from UploadRoutes.tsx results section

<div className="tw:stats tw:stats-horizontal tw:shadow tw:w-full tw:mb-4">
  <div className="tw:stat tw:py-2 tw:px-4">
    <div className="tw:stat-title tw:text-xs">Drivers</div>
    <div className="tw:stat-value tw:text-lg numeric">{drivers.length}</div>
  </div>
  <div className="tw:stat tw:py-2 tw:px-4">
    <div className="tw:stat-title tw:text-xs">Orders</div>
    <div className="tw:stat-value tw:text-lg numeric">{totalOrders}</div>
  </div>
  <div className="tw:stat tw:py-2 tw:px-4">
    <div className="tw:stat-title tw:text-xs">New</div>
    <div className="tw:stat-value tw:text-lg tw:text-info numeric">{newCount}</div>
  </div>
  <div className="tw:stat tw:py-2 tw:px-4">
    <div className="tw:stat-title tw:text-xs">Matched</div>
    <div className="tw:stat-value tw:text-lg tw:text-warning numeric">{matchedCount}</div>
  </div>
</div>
```

### API Client Extension (Frontend)
```typescript
// Source: Following existing api.ts patterns (FormData for file, apiFetch for JSON)

export interface ParsePreviewResponse {
  upload_token: string;
  filename: string;
  total_rows: number;
  filtered_rows: number;
  drivers: DriverPreview[];
}

export async function parseUpload(file: File): Promise<ParsePreviewResponse> {
  const url = `${BASE_URL}/api/parse-upload`;
  const formData = new FormData();
  formData.append("file", file);

  const headers: Record<string, string> = {};
  const apiKey = import.meta.env.VITE_API_KEY;
  if (apiKey) headers["X-API-Key"] = apiKey;

  const response = await fetch(url, { method: "POST", headers, body: formData });
  if (!response.ok) {
    // Error handling matching existing uploadAndOptimize pattern
    const errorBody = await response.text();
    try {
      const parsed = JSON.parse(errorBody);
      if (isApiError(parsed)) throw new ApiUploadError(parsed);
    } catch (parseErr) {
      if (parseErr instanceof ApiUploadError) throw parseErr;
    }
    throw new Error(`Parse failed (${response.status}): ${errorBody || response.statusText}`);
  }
  return (await response.json()) as ParsePreviewResponse;
}

export async function processSelected(
  uploadToken: string,
  selectedDrivers: string[],
): Promise<UploadResponse> {
  const url = `${BASE_URL}/api/upload-orders`;
  const formData = new FormData();
  formData.append("upload_token", uploadToken);
  formData.append("selected_drivers", JSON.stringify(selectedDrivers));

  const headers: Record<string, string> = {};
  const apiKey = import.meta.env.VITE_API_KEY;
  if (apiKey) headers["X-API-Key"] = apiKey;

  const response = await fetch(url, { method: "POST", headers, body: formData });
  // ... same error handling as uploadAndOptimize
  return (await response.json()) as UploadResponse;
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `_is_cdcms_format()` reads text for all files | Check extension first, use pandas for .xlsx | Phase 17 | Fixes CSV-01: .xlsx files now detected correctly |
| Single `upload-orders` endpoint does everything | Parse + preview + process split | Phase 17 | Enables driver selection before expensive geocoding/optimization |
| All drivers always get routes | Selected drivers get routes, deselected drivers still created | Phase 17 | Office staff control over which routes to generate |

**Already working (no changes needed):**
- Column matching by name (CSV-05): `_validate_cdcms_columns()` and `preprocess_cdcms()` already use column names, not positions
- Allocated-Printed filter (CSV-04): `preprocess_cdcms(filter_status="Allocated-Printed")` is the default
- Driver auto-creation from CSV: `auto_create_drivers_from_csv()` already categorizes drivers

## Open Questions

1. **Upload token storage: in-memory dict vs filesystem marker**
   - What we know: In-memory dict is simplest but lost on server restart. Filesystem marker (e.g., `token.json` next to temp file) survives restarts.
   - What's unclear: How often does the server restart between parse and process? (Probably never in practice.)
   - Recommendation: Use in-memory dict with TTL. Simple, fast, and server restarts between parse and process within 30 minutes are extremely unlikely for a single-user office tool.

2. **Process endpoint: extend existing or new endpoint**
   - What we know: CONTEXT.md says Claude's discretion. Extending existing `POST /api/upload-orders` with optional `upload_token` + `selected_drivers` parameters means backward compatibility (existing flow still works if no token provided).
   - What's unclear: Does adding Form() parameters break the existing UploadFile-only flow?
   - Recommendation: Extend existing endpoint. FastAPI supports `File(None)` (optional file) + `Form(None)` (optional form fields) in the same endpoint. If `upload_token` is provided, skip file upload and use stored data. If `file` is provided (no token), run the old flow for backward compatibility.

3. **DaisyUI badge colors for driver status**
   - What we know: CONTEXT.md specifies Green=Existing, Blue=New, Amber=Matched, Purple=Reactivated.
   - DaisyUI 5 badge variants: `tw:badge-success` (green), `tw:badge-info` (blue), `tw:badge-warning` (amber/yellow). No built-in purple variant.
   - Recommendation: Use `tw:badge-success`, `tw:badge-info`, `tw:badge-warning` for first three. For purple (reactivated), use `tw:badge-secondary` and override via custom CSS or inline style to get purple color matching the design system.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + asyncio_mode=auto |
| Config file | `pytest.ini` |
| Quick run command | `pytest tests/core/data_import/test_cdcms_preprocessor.py tests/apps/kerala_delivery/api/test_api.py -x -v` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CSV-01 | XLSX files detected as CDCMS format | unit | `pytest tests/apps/kerala_delivery/api/test_api.py -k "xlsx_cdcms_detect" -x` | No -- Wave 0 |
| CSV-02 | Parse endpoint returns driver preview with counts | unit | `pytest tests/apps/kerala_delivery/api/test_api.py -k "parse_upload_preview" -x` | No -- Wave 0 |
| CSV-03 | Selected drivers filter controls route generation | unit | `pytest tests/apps/kerala_delivery/api/test_api.py -k "selected_drivers" -x` | No -- Wave 0 |
| CSV-04 | Allocated-Printed filter applied by default | unit | `pytest tests/core/data_import/test_cdcms_preprocessor.py -k "allocated_printed" -x` | Likely exists (check) |
| CSV-05 | Column order does not affect parsing | unit | `pytest tests/core/data_import/test_cdcms_preprocessor.py -k "column_order" -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/core/data_import/test_cdcms_preprocessor.py tests/apps/kerala_delivery/api/test_api.py -x -v`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/apps/kerala_delivery/api/test_api.py` -- add tests for `_is_cdcms_format()` with .xlsx files (CSV-01)
- [ ] `tests/apps/kerala_delivery/api/test_api.py` -- add tests for parse-upload endpoint (CSV-02)
- [ ] `tests/apps/kerala_delivery/api/test_api.py` -- add tests for selected_drivers filtering (CSV-03)
- [ ] `tests/core/data_import/test_cdcms_preprocessor.py` -- add column order independence test (CSV-05)
- [ ] No new framework install needed -- pytest infrastructure complete

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `apps/kerala_delivery/api/main.py` lines 627-652 (`_is_cdcms_format`), 847-926 (`auto_create_drivers_from_csv`), 929-1500 (`upload_and_optimize`)
- Codebase analysis: `core/data_import/cdcms_preprocessor.py` -- `preprocess_cdcms()`, `_read_cdcms_file()`, `_validate_cdcms_columns()`
- Codebase analysis: `apps/kerala_delivery/dashboard/src/pages/UploadRoutes.tsx` -- full state machine and UI
- Codebase analysis: `apps/kerala_delivery/dashboard/src/lib/api.ts` -- existing API client patterns
- Codebase analysis: `apps/kerala_delivery/dashboard/src/types.ts` -- existing TypeScript interfaces

### Secondary (MEDIUM confidence)
- DaisyUI 5 component patterns inferred from existing codebase usage (tw:table, tw:badge, tw:checkbox, tw:stats)
- FastAPI File + Form parameter coexistence -- standard FastAPI pattern, well-documented

### Tertiary (LOW confidence)
- None -- all findings based on direct codebase analysis

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use, no new dependencies
- Architecture: HIGH -- two-endpoint pattern follows existing codebase conventions, all building blocks exist
- Pitfalls: HIGH -- identified from direct code analysis of current implementation
- Frontend patterns: HIGH -- extending existing state machine with new state, reusing DaisyUI components already in use

**Research date:** 2026-03-13
**Valid until:** 2026-04-13 (stable -- no external dependency changes expected)
