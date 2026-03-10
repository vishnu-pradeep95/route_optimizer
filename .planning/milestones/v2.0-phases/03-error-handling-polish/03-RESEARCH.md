# Phase 3: Error Handling Polish - Research

**Researched:** 2026-03-10
**Domain:** Frontend API error handling, documentation anchor repair
**Confidence:** HIGH

## Summary

This phase closes two specific integration gaps identified by the v1.0 milestone audit. Both are precisely scoped, well-understood problems with deterministic fixes.

**Gap 1 -- fetchHealth 503 handling:** The backend `/health` endpoint returns HTTP 503 with a JSON body containing per-service status when the system is degraded or unhealthy. The frontend `apiFetch()` function throws on any non-2xx response. In `App.tsx`, the `checkHealth()` callback calls `fetchHealth()` inside a try/catch -- when `apiFetch` throws on 503, the catch block sets `healthData` to `null`, losing the per-service breakdown. The health bar then shows only "Unhealthy" instead of listing which specific services (postgresql, osrm, vroom, google_api) are down. This is the worst-case scenario for the feature: the detailed health data is most valuable precisely when services are degraded, but that is exactly when it gets discarded.

**Gap 2 -- ERROR_HELP_URLS broken anchors:** All 15 help URL entries in both `api/errors.py` and `dashboard/src/lib/errors.ts` use anchor fragments that don't match the actual heading anchors in the target markdown files (`docs/CSV_FORMAT.md`, `docs/GOOGLE-MAPS.md`, `docs/SETUP.md`). Users navigate to the correct file but land at the top of the page instead of the relevant section.

**Primary recommendation:** Fix `apiFetch` or `fetchHealth` to parse JSON from 503 responses instead of throwing, then do a systematic anchor-to-heading alignment across all 15 ERROR_HELP_URLS entries in both Python and TypeScript files.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ERR-01 | ErrorResponse model with consistent JSON | Anchor fragment repair ensures help_url field provides correct navigation to documentation sections |
| ERR-05 | Enhanced /health with per-service status | Fix apiFetch 503 handling so per-service data is preserved and displayed in the health bar |
| ERR-09 | Dashboard health status bar with per-service display | Health bar in App.tsx needs healthData to be populated even on 503 responses |
</phase_requirements>

## Architecture Patterns

### Issue 1: apiFetch 503 Handling -- Root Cause Analysis

**The throw chain:**

1. Backend `health_check()` in `main.py:804` sets `status_code = 200 if overall == "healthy" else 503`
2. Returns `JSONResponse(status_code=status_code, content={...services...})`
3. Frontend `apiFetch()` in `api.ts:70` checks `if (!response.ok)` -- 503 is not ok
4. `apiFetch` attempts to parse JSON and check for `isApiError()` shape -- but the health response is NOT an ApiError (it has `status`, `services`, etc., not `error_code`, `user_message`)
5. `isApiError()` returns false, so apiFetch falls through to `throw new Error("API error 503: ...")`
6. In `App.tsx:104`, the `catch` block sets `setHealthData(null)` and `setApiHealthy(false)`
7. `healthSummaryText(null)` returns "Checking..." initially, then on next poll shows "Offline"

**The fix pattern -- two viable approaches:**

**Approach A (Recommended): Dedicated fetchHealth that handles 503.**
Create a specialized fetch function that doesn't use `apiFetch()`. Instead, call `fetch()` directly for `/health`, always parse the JSON body regardless of status code, and return the `HealthResponse`. This is the cleanest approach because `/health` is intentionally designed to return useful data on non-2xx codes.

```typescript
// Approach A: Replace fetchHealth with a direct fetch
export async function fetchHealth(): Promise<HealthResponse> {
  const url = `${BASE_URL}/health`;
  const response = await fetch(url, { cache: "no-store" });
  // Always parse body -- /health returns valid JSON on both 200 and 503
  return (await response.json()) as HealthResponse;
}
```

**Approach B: Make apiFetch configurable to not throw on specific status codes.**
Add a parameter or overload to `apiFetch` to allow non-2xx responses to be parsed. This is more complex and changes the apiFetch contract for all callers.

**Recommendation: Use Approach A.** It is a 5-line change, self-contained, and does not affect any other endpoint. The health endpoint is the only one designed to return useful data on 503.

**App.tsx checkHealth changes:**
The current catch block needs updating to handle the case where the response is successfully parsed but indicates degraded/unhealthy status:

```typescript
const checkHealth = useCallback(async () => {
  try {
    const res = await fetchHealth();
    setHealthData(res);
    setApiHealthy(res.status === "healthy" || res.status === "ok");
  } catch {
    // Only reaches here on actual network errors (server completely unreachable)
    setApiHealthy(false);
    setHealthData(null);
  }
}, []);
```

After the fix, `setApiHealthy` should be `false` when status is "unhealthy"/"degraded" (since `fetchHealth` now returns the parsed body), and `setHealthData` should contain the full per-service breakdown. The existing `checkHealth` logic already handles this correctly -- the only issue was that `fetchHealth` threw before returning the data.

### Issue 2: ERROR_HELP_URLS Anchor Mapping

**Current broken anchors vs. actual headings:**

Markdown heading anchors are generated by: lowercase, replace spaces with hyphens, strip non-alphanumeric characters (except hyphens). GitHub-style anchor generation.

| Error Code | Current Anchor | Target File | Actual Heading | Correct Anchor |
|------------|---------------|-------------|----------------|----------------|
| UPLOAD_INVALID_FORMAT | `#file-level-errors` | CSV_FORMAT.md | "Before Processing (File-Level Errors)" | `#before-processing-file-level-errors` |
| UPLOAD_FILE_TOO_LARGE | `#file-level-errors` | CSV_FORMAT.md | "Before Processing (File-Level Errors)" | `#before-processing-file-level-errors` |
| UPLOAD_EMPTY_FILE | `#file-level-errors` | CSV_FORMAT.md | "Before Processing (File-Level Errors)" | `#before-processing-file-level-errors` |
| UPLOAD_NO_VALID_ORDERS | `#row-level-errors` | CSV_FORMAT.md | "During Processing (Row-Level Errors)" | `#during-processing-row-level-errors` |
| UPLOAD_NO_ALLOCATED | `#cdcms-format` | CSV_FORMAT.md | "CDCMS Export Format" | `#cdcms-export-format` |
| GEOCODING_NOT_CONFIGURED | `#api-key-setup` | GOOGLE-MAPS.md | "Setting Up a Google Maps API Key" | `#setting-up-a-google-maps-api-key` |
| GEOCODING_QUOTA_EXCEEDED | `#quota` | GOOGLE-MAPS.md | "OVER_QUERY_LIMIT" (closest) | `#over_query_limit` |
| GEOCODING_FAILED | `#troubleshooting` | GOOGLE-MAPS.md | "Common Errors" or "Still Not Working?" | `#common-errors` |
| OPTIMIZER_UNAVAILABLE | `#osrm-vroom` | SETUP.md | "OSRM Not Ready" | `#osrm-not-ready` |
| OPTIMIZER_TIMEOUT | `#osrm-vroom` | SETUP.md | "OSRM Not Ready" | `#osrm-not-ready` |
| OPTIMIZER_ERROR | `#osrm-vroom` | SETUP.md | "OSRM Not Ready" | `#osrm-not-ready` |
| FLEET_NO_VEHICLES | `#fleet-setup` | SETUP.md | No matching heading | (see note below) |
| AUTH_KEY_INVALID | `#api-key` | SETUP.md | "Environment Variables" (closest) | `#step-6-environment-variables` |
| AUTH_KEY_MISSING | `#api-key` | SETUP.md | "Environment Variables" (closest) | `#step-6-environment-variables` |
| SERVICE_UNAVAILABLE | `#services` | SETUP.md | "Troubleshooting" (second one) | `#troubleshooting-1` |

**Notes on specific anchors:**

1. **FLEET_NO_VEHICLES -> `#fleet-setup`**: SETUP.md has no "Fleet Setup" heading. The closest is "Step 11: CDCMS Data Workflow" which covers CSV upload but not fleet configuration. The fleet is managed via the dashboard's Fleet page. Consider pointing to a more relevant section or removing the anchor (just link to the file root).

2. **GEOCODING_QUOTA_EXCEEDED -> `#quota`**: No heading contains just "quota". The closest match is the "OVER_QUERY_LIMIT" subsection under "Common Errors" which discusses quota exhaustion.

3. **GEOCODING_FAILED -> `#troubleshooting`**: GOOGLE-MAPS.md doesn't have a heading literally called "Troubleshooting". The closest relevant sections are "Common Errors" (`#common-errors`) or "Still Not Working?" (`#still-not-working`).

4. **Duplicate anchors**: SETUP.md has two `## Troubleshooting` headings (lines 266 and 413). GitHub renders the second as `#troubleshooting-1`.

**Files that need updating:**
1. `apps/kerala_delivery/api/errors.py` -- `ERROR_HELP_URLS` dict (15 entries)
2. `apps/kerala_delivery/dashboard/src/lib/errors.ts` -- `ERROR_HELP_URLS` const (15 entries, must match Python)

### Anti-Patterns to Avoid

- **Do NOT change the apiFetch contract globally.** The fix should be scoped to fetchHealth only. All other endpoints correctly throw on non-2xx.
- **Do NOT change the backend /health endpoint status codes.** The 503 on degraded is the correct HTTP semantic. The frontend needs to handle it.
- **Do NOT guess anchor fragments.** Every anchor must be verified against the actual markdown heading text in the documentation files.
- **Keep Python and TypeScript ERROR_HELP_URLS in sync.** The backend populates `help_url` in ErrorResponse, and the frontend has a client-side mirror for synthetic errors. Both must have identical mappings.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Markdown heading anchor generation | Custom slug algorithm | Standard GitHub anchor rules | Well-defined spec: lowercase, spaces to hyphens, strip special chars except hyphens |
| Health endpoint 503 handling | Complex apiFetch refactor | Direct `fetch()` call in fetchHealth | Only /health needs this behavior; apiFetch contract should stay simple |

## Common Pitfalls

### Pitfall 1: Duplicate Heading Anchors in SETUP.md
**What goes wrong:** SETUP.md has two `## Troubleshooting` headings. GitHub/markdown viewers append `-1` to the second occurrence.
**Why it happens:** The doc was restructured without noticing the duplicate heading.
**How to avoid:** When mapping SERVICE_UNAVAILABLE to the second Troubleshooting section, use `#troubleshooting-1` as the anchor. Verify by viewing the rendered markdown.
**Warning signs:** Links land at the wrong Troubleshooting section (Docker issues instead of OSRM issues).

### Pitfall 2: Forgetting to Update Both Files
**What goes wrong:** Python and TypeScript ERROR_HELP_URLS get out of sync.
**Why it happens:** The mapping exists in two places for different use cases (backend for ErrorResponse, frontend for synthetic errors).
**How to avoid:** Update both files in the same task. Add a comment in each file referencing the other. Consider a verification step that compares them.
**Warning signs:** Backend errors have correct help links but frontend-generated errors don't, or vice versa.

### Pitfall 3: Network Error vs. 503 Confusion in App.tsx
**What goes wrong:** After fixing fetchHealth, developers may conflate "server returned 503 with health data" and "server is completely unreachable."
**Why it happens:** Both currently land in the catch block.
**How to avoid:** After the fix, only actual network errors (fetch throws) should set `healthData(null)`. A 503 with valid JSON should set `healthData` with the response body and `apiHealthy(false)`.

### Pitfall 4: Anchor Fragment Special Characters
**What goes wrong:** Anchors with parentheses, colons, or quotes don't render correctly.
**Why it happens:** Markdown anchor generation strips some special characters but keeps others.
**How to avoid:** Test each anchor by generating it programmatically: heading.toLowerCase().replace(/[^\w\s-]/g, '').replace(/\s+/g, '-').
**Warning signs:** The heading "Before Processing (File-Level Errors)" generates `#before-processing-file-level-errors` (parentheses and their contents are kept but special chars stripped).

## Code Examples

### Fix 1: fetchHealth Direct Fetch (Approach A)

```typescript
// Source: apps/kerala_delivery/dashboard/src/lib/api.ts
// Replace the current fetchHealth implementation

/** Check if the backend API is reachable and healthy.
 *
 * Uses direct fetch instead of apiFetch because /health intentionally
 * returns 503 with valid JSON body on degraded/unhealthy state.
 * apiFetch throws on non-2xx, which would discard the per-service data.
 */
export async function fetchHealth(): Promise<HealthResponse> {
  const url = `${BASE_URL}/health`;
  const response = await fetch(url, { cache: "no-store" });
  // /health always returns valid JSON regardless of status code (200 or 503)
  return (await response.json()) as HealthResponse;
}
```

### Fix 2: Corrected ERROR_HELP_URLS (Python)

```python
# Source: apps/kerala_delivery/api/errors.py
ERROR_HELP_URLS: dict[str, str] = {
    ErrorCode.UPLOAD_INVALID_FORMAT: "/docs/CSV_FORMAT.md#before-processing-file-level-errors",
    ErrorCode.UPLOAD_FILE_TOO_LARGE: "/docs/CSV_FORMAT.md#before-processing-file-level-errors",
    ErrorCode.UPLOAD_EMPTY_FILE: "/docs/CSV_FORMAT.md#before-processing-file-level-errors",
    ErrorCode.UPLOAD_NO_VALID_ORDERS: "/docs/CSV_FORMAT.md#during-processing-row-level-errors",
    ErrorCode.UPLOAD_NO_ALLOCATED: "/docs/CSV_FORMAT.md#cdcms-export-format",
    ErrorCode.GEOCODING_NOT_CONFIGURED: "/docs/GOOGLE-MAPS.md#setting-up-a-google-maps-api-key",
    ErrorCode.GEOCODING_QUOTA_EXCEEDED: "/docs/GOOGLE-MAPS.md#over_query_limit",
    ErrorCode.GEOCODING_FAILED: "/docs/GOOGLE-MAPS.md#common-errors",
    ErrorCode.OPTIMIZER_UNAVAILABLE: "/docs/SETUP.md#osrm-not-ready",
    ErrorCode.OPTIMIZER_TIMEOUT: "/docs/SETUP.md#osrm-not-ready",
    ErrorCode.OPTIMIZER_ERROR: "/docs/SETUP.md#osrm-not-ready",
    ErrorCode.FLEET_NO_VEHICLES: "/docs/SETUP.md#step-11-cdcms-data-workflow",
    ErrorCode.AUTH_KEY_INVALID: "/docs/SETUP.md#step-6-environment-variables",
    ErrorCode.AUTH_KEY_MISSING: "/docs/SETUP.md#step-6-environment-variables",
    ErrorCode.SERVICE_UNAVAILABLE: "/docs/SETUP.md#troubleshooting-1",
}
```

### Fix 3: Corrected ERROR_HELP_URLS (TypeScript)

```typescript
// Source: apps/kerala_delivery/dashboard/src/lib/errors.ts
export const ERROR_HELP_URLS: Record<string, string> = {
  UPLOAD_INVALID_FORMAT: "/docs/CSV_FORMAT.md#before-processing-file-level-errors",
  UPLOAD_FILE_TOO_LARGE: "/docs/CSV_FORMAT.md#before-processing-file-level-errors",
  UPLOAD_EMPTY_FILE: "/docs/CSV_FORMAT.md#before-processing-file-level-errors",
  UPLOAD_NO_VALID_ORDERS: "/docs/CSV_FORMAT.md#during-processing-row-level-errors",
  UPLOAD_NO_ALLOCATED: "/docs/CSV_FORMAT.md#cdcms-export-format",
  GEOCODING_NOT_CONFIGURED: "/docs/GOOGLE-MAPS.md#setting-up-a-google-maps-api-key",
  GEOCODING_QUOTA_EXCEEDED: "/docs/GOOGLE-MAPS.md#over_query_limit",
  GEOCODING_FAILED: "/docs/GOOGLE-MAPS.md#common-errors",
  OPTIMIZER_UNAVAILABLE: "/docs/SETUP.md#osrm-not-ready",
  OPTIMIZER_TIMEOUT: "/docs/SETUP.md#osrm-not-ready",
  OPTIMIZER_ERROR: "/docs/SETUP.md#osrm-not-ready",
  FLEET_NO_VEHICLES: "/docs/SETUP.md#step-11-cdcms-data-workflow",
  AUTH_KEY_INVALID: "/docs/SETUP.md#step-6-environment-variables",
  AUTH_KEY_MISSING: "/docs/SETUP.md#step-6-environment-variables",
  SERVICE_UNAVAILABLE: "/docs/SETUP.md#troubleshooting-1",
};
```

## Exact File Change Map

| File | Change | Lines Affected |
|------|--------|---------------|
| `apps/kerala_delivery/dashboard/src/lib/api.ts` | Replace `fetchHealth()` to use direct `fetch()` instead of `apiFetch()` | Lines 258-260 (3 lines -> ~10 lines) |
| `apps/kerala_delivery/api/errors.py` | Update 15 anchor fragments in `ERROR_HELP_URLS` dict | Lines 73-89 |
| `apps/kerala_delivery/dashboard/src/lib/errors.ts` | Update 15 anchor fragments in `ERROR_HELP_URLS` const | Lines 83-99 |

**Total: 3 files, ~45 lines changed.**

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `apiFetch<HealthResponse>("/health")` | Direct `fetch()` for /health only | Phase 3 (this fix) | Per-service health data preserved on 503 |
| Guessed anchor fragments | Verified heading-to-anchor mapping | Phase 3 (this fix) | Help links navigate to correct doc section |

## Open Questions

1. **FLEET_NO_VEHICLES anchor target**
   - What we know: SETUP.md has no "Fleet Setup" heading. Fleet management is done via the dashboard UI, not CLI setup.
   - What's unclear: Whether we should point to the CDCMS data workflow section (closest existing heading) or to a different doc file entirely.
   - Recommendation: Use `/docs/SETUP.md#step-11-cdcms-data-workflow` as the closest match. The error message itself ("No vehicles configured") already tells users what to do. A future phase could add a dedicated fleet setup section to the docs.

2. **Second Troubleshooting heading disambiguation**
   - What we know: SETUP.md has `## Troubleshooting` at line 266 (Docker/Python issues) and `## Troubleshooting` at line 413 (OSRM issues). The second renders as `#troubleshooting-1`.
   - What's unclear: Whether the duplicate heading should be renamed for clarity.
   - Recommendation: Use `#troubleshooting-1` for now (the OSRM-specific one). Renaming headers is out of scope for this phase and would be a doc structure change.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x (backend), Playwright (E2E) |
| Config file | `pytest.ini` / `playwright.config.ts` |
| Quick run command | `pytest tests/apps/kerala_delivery/api/test_errors.py tests/apps/kerala_delivery/api/test_health.py -x` |
| Full suite command | `pytest tests/ -x && npx playwright test --project=dashboard e2e/dashboard-errors.spec.ts` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ERR-01 | ERROR_HELP_URLS anchors match actual doc headings | unit | `pytest tests/apps/kerala_delivery/api/test_errors.py -x` | Exists (may need anchor validation test) |
| ERR-05 | /health 503 response parsed with per-service data | integration | `pytest tests/apps/kerala_delivery/api/test_health.py -x` | Exists |
| ERR-09 | Health bar shows per-service breakdown on degraded | e2e | `npx playwright test --project=dashboard e2e/dashboard-errors.spec.ts` | Exists (test covers health bar visibility) |

### Sampling Rate
- **Per task commit:** `pytest tests/apps/kerala_delivery/api/test_errors.py tests/apps/kerala_delivery/api/test_health.py -x`
- **Per wave merge:** `pytest tests/ -x && cd apps/kerala_delivery/dashboard && npx tsc --noEmit`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
None -- existing test infrastructure covers all phase requirements. The `fetchHealth` fix is a frontend change that can be verified via the existing Playwright health bar test. The anchor fixes are data changes that can be verified by visual inspection or a simple test that checks each URL fragment exists as a heading anchor in the target file.

## Sources

### Primary (HIGH confidence)
- `apps/kerala_delivery/dashboard/src/lib/api.ts` -- apiFetch implementation, lines 51-101; fetchHealth, lines 258-260
- `apps/kerala_delivery/api/main.py` -- /health endpoint, lines 759-814 (returns 503 with JSON body on degraded)
- `apps/kerala_delivery/dashboard/src/App.tsx` -- checkHealth callback, lines 99-108 (catch discards healthData)
- `apps/kerala_delivery/api/errors.py` -- ERROR_HELP_URLS dict, lines 73-89
- `apps/kerala_delivery/dashboard/src/lib/errors.ts` -- ERROR_HELP_URLS const, lines 83-99
- `docs/CSV_FORMAT.md` -- actual headings verified via grep
- `docs/GOOGLE-MAPS.md` -- actual headings verified via grep
- `docs/SETUP.md` -- actual headings verified via grep (including duplicate Troubleshooting sections)
- `.planning/v1.0-MILESTONE-AUDIT.md` -- gap identification, issues 1 and 2

### Secondary (MEDIUM confidence)
- GitHub markdown anchor generation rules -- standard algorithm: lowercase, spaces to hyphens, strip non-alphanumeric except hyphens, append `-N` for duplicates

## Metadata

**Confidence breakdown:**
- fetchHealth 503 fix: HIGH -- complete code trace from backend through apiFetch to App.tsx catch block
- ERROR_HELP_URLS anchors: HIGH -- all headings extracted from actual doc files, anchors computed deterministically
- FLEET_NO_VEHICLES target: MEDIUM -- no perfect heading match exists; best available option selected

**Research date:** 2026-03-10
**Valid until:** Indefinitely (this is a one-time fix for known gaps, not a moving target)
