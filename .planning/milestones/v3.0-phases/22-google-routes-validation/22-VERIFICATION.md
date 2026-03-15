---
phase: 22-google-routes-validation
verified: 2026-03-15T00:30:00Z
status: passed
score: 14/14 must-haves verified
re_verification: false
---

# Phase 22: Google Routes Validation Verification Report

**Phase Goal:** Users can manually compare a generated route against Google Routes API to assess OSRM routing accuracy, with clear cost transparency before each call
**Verified:** 2026-03-15T00:30:00Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths — Plan 01 (Backend)

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | POST /api/routes/{vehicle_id}/validate calls Google Routes API and returns comparison data | VERIFIED | `main.py:3787` — `httpx.AsyncClient.post("https://routes.googleapis.com/directions/v2:computeRoutes", ...)` with full response parsing and return object |
| 2  | GET /api/validation-stats returns cumulative validation count and total cost | VERIFIED | `main.py:3886-3905` — endpoint calls `repo.get_validation_stats(session)`, returns count/total_cost_usd/estimated_cost_inr |
| 3  | Validation endpoint returns cached result when route was previously validated | VERIFIED | `main.py:3728-3745` — `get_route_validation()` called before API; if found and `force=False`, returns cached dict with `"cached": True` |
| 4  | Validation endpoint returns 400 with helpful message when no Google API key is configured | VERIFIED | `main.py:3707-3716` — checks `_cached_api_key or os.environ.get("GOOGLE_MAPS_API_KEY")`, returns 400 with `{"error": "google_api_key_required", "message": "..."}` |
| 5  | Validation endpoint never triggers automatically — only responds to explicit POST requests | VERIFIED | `main.py:3683` — `@app.post(...)` decorator; VAL-04 compliance comment at `main.py:3697`; no scheduler, no background task, no auto-call path |
| 6  | Confidence level is computed from distance delta percentage (green <=10%, amber <=25%, red >25%) | VERIFIED | `repository.py:1233` — `confidence_level()` helper; tested by 6 boundary tests all passing |

### Observable Truths — Plan 02 (Frontend)

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 7  | User can click a Validate with Google button on any route card | VERIFIED | `RouteList.tsx:369` — `{validation ? "Re-validate" : "Validate with Google"}` rendered inside every route card's map loop |
| 8  | Before Google API call, a DaisyUI modal shows estimated cost and cumulative stats | VERIFIED | `RouteList.tsx:104,391+` — `showCostModal` state triggers modal; `handleValidateClick` only sets `showCostModal`, does NOT call API; `handleValidateConfirm` calls `validateRoute` after modal confirmation |
| 9  | After validation, route card shows inline OSRM vs Google distance and time with delta percentages | VERIFIED | `RouteList.tsx:319+` — `div.route-validation` section renders comparison grid with `validation.osrm_distance_km`, `validation.google_distance_km`, `validation.distance_delta_pct` |
| 10 | Confidence badge shows green/amber/red based on distance delta | VERIFIED | `RouteList.tsx:333-337` — `tw:badge-success`/`tw:badge-warning`/`tw:badge-error` applied conditionally on `validation.confidence` |
| 11 | Previously validated routes show cached result inline with Re-validate button and validation date | VERIFIED | `RouteList.tsx:369` — button text is "Re-validate" when `validationResults.has(vehicleId)`; validation date rendered as `validation-meta`; `force=true` passed for re-validate |
| 12 | When no API key configured, button click shows message with link to Settings page | VERIFIED | `RouteList.tsx:107,160-162,295,311` — `noApiKey` error property detected, `noApiKeyVehicle` state set, `no-api-key-message` div with "Configure in Settings" link rendered |
| 13 | Settings page has a Validation History card showing total validations, total cost, and recent results | VERIFIED | `Settings.tsx:466+` — Card 4 "Validation History" with `validationStats.count`, `estimated_cost_inr.toFixed(2)`, recent validations table |
| 14 | Validation is never triggered automatically — only on explicit button click with cost confirmation | VERIFIED | `RouteList.tsx:23,151` — `validateRoute` called only at line 151 inside `handleValidateConfirm`, which fires only after user clicks "Validate" in the cost modal; `useEffect` on mount only fetches stats, not triggers validation |

**Score:** 14/14 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `core/database/models.py` | RouteValidationDB ORM model | VERIFIED | `class RouteValidationDB(Base):` at line 402; all required columns present |
| `core/database/repository.py` | Validation CRUD: save, get, stats, increment, recent, confidence_level | VERIFIED | All 6 functions present at lines 1233–1402+ |
| `infra/alembic/versions/f7b2d4e19a33_add_route_validations_table.py` | Alembic migration creating route_validations table | VERIFIED | File exists; creates `route_validations` table with index on `route_id`; `down_revision = "e4a1c7f83b21"` |
| `apps/kerala_delivery/api/main.py` | POST validate + GET stats endpoints | VERIFIED | `validate_route` at line 3685; `get_validation_stats` at 3886; `get_recent_validations` at 3907 |
| `tests/apps/kerala_delivery/api/test_validation.py` | Unit tests, min 100 lines | VERIFIED | 582 lines; 20 tests; all pass |
| `apps/kerala_delivery/dashboard/src/types.ts` | ValidationResult, ValidationStats, RecentValidation interfaces | VERIFIED | `ValidationResult` at line 285; all three interfaces present |
| `apps/kerala_delivery/dashboard/src/lib/api.ts` | validateRoute, fetchValidationStats, fetchRecentValidations | VERIFIED | All three functions present at lines 649, 694, 699 |
| `apps/kerala_delivery/dashboard/src/components/RouteList.tsx` | Validate button, cost modal, inline comparison | VERIFIED | "Validate with Google" text confirmed; modal at line 391+; comparison grid at line 319+ |
| `apps/kerala_delivery/dashboard/src/components/RouteList.css` | Styles for validation section | VERIFIED | `.route-validation`, `.validation-comparison`, `.validation-row`, `.validation-header`, `.validation-meta`, `.validation-error`, `.no-api-key-message` all present |
| `apps/kerala_delivery/dashboard/src/pages/Settings.tsx` | Validation History card | VERIFIED | Card 4 at line 466; stats and recent validations table present |
| `apps/kerala_delivery/dashboard/src/pages/Settings.css` | Validation stat styles | VERIFIED | `.validation-stats-row` at line 136, `.validation-stat` at line 143 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `main.py` | `routes.googleapis.com/directions/v2:computeRoutes` | `httpx.AsyncClient POST` in `validate_route` | WIRED | `main.py:3787` — direct POST with X-Goog-Api-Key and X-Goog-FieldMask headers, response parsed |
| `main.py` | `core/database/repository.py` | `save_route_validation` and `get_route_validation` calls | WIRED | `main.py:3729` — `get_route_validation`; `main.py:3855` — `save_route_validation`; `main.py:3865` — `increment_validation_stats` |
| `main.py` | `core/database/models.py` | `RouteValidationDB` ORM (via repository) | WIRED | `repository.py:1233+` — `RouteValidationDB` used in all repository functions; `main.py` uses `repo.*` functions |
| `RouteList.tsx` | `/api/routes/{vehicle_id}/validate` | `validateRoute()` after modal confirmation | WIRED | `RouteList.tsx:151` — `validateRoute(vehicleId, isRevalidate)` called only inside `handleValidateConfirm`; `api.ts:649` — POSTs to correct URL |
| `RouteList.tsx` | `/api/validation-stats` | `fetchValidationStats()` for modal cumulative display | WIRED | `RouteList.tsx:111` — fetched on mount for modal; `RouteList.tsx:158` — refreshed after successful validation |
| `Settings.tsx` | `/api/validation-stats` | `fetchValidationStats()` and `fetchRecentValidations()` on mount | WIRED | `Settings.tsx:109-110` — both called in parallel in mount `useEffect`; results stored in state and rendered |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| VAL-01 | 22-01, 22-02 | User can trigger Google Routes API comparison for a generated route | SATISFIED | Validate button in RouteList.tsx; POST endpoint in main.py |
| VAL-02 | 22-01, 22-02 | System displays VROOM/OSRM vs Google Routes distance/time comparison with confidence indicator | SATISFIED | Inline comparison grid in RouteList.tsx; confidence badge; confidence_level() in repository.py |
| VAL-03 | 22-02 | System shows cost warning before running Google Routes validation | SATISFIED | DaisyUI cost modal shown before every API call; fetchValidationStats() loads cumulative stats for the modal |
| VAL-04 | 22-01, 22-02 | Google Routes validation is never triggered automatically | SATISFIED | validateRoute only called in handleValidateConfirm (user click); POST endpoint only; no scheduler/background task/useEffect auto-trigger |

No orphaned requirements — all four VAL IDs are claimed by plans 22-01 and/or 22-02.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `main.py` | 645-646 | `placeholder_values = {"your-key-here", ...}` | INFO | Not a code stub — this is legitimate code checking whether the API key itself is a placeholder string. Not a concern. |

No blocker or warning anti-patterns found in any phase file.

---

### Human Verification Required

The following items require a running Docker stack with a real Google Maps API key to verify end-to-end:

**1. Validate button click triggers modal (not API call)**

Test: Upload a CSV, observe the route cards, click "Validate with Google", confirm the cost modal appears before any network call to Google.
Expected: DaisyUI modal appears with "~INR 0.93 per validation" and cumulative stats. No Google API call fires until user clicks "Validate".
Why human: Requires visual confirmation and network traffic inspection; can't be scripted without Google API key.

**2. Inline comparison display with colored confidence badge**

Test: Confirm validation with a real API key. Observe the route card after validation completes.
Expected: Inline 4-column grid appears with OSRM vs Google distance and time, delta %, and a green/amber/red badge.
Why human: Visual and interactive; requires real Google response data.

**3. Re-validate button and cached result display**

Test: After validating once, click "Re-validate". Confirm cached result shows with validation date before re-call.
Expected: "Re-validate" button appears; clicking it opens the modal; confirming calls API with `?force=true`.
Why human: Requires a real validation record in the DB.

**4. No-API-key message with Settings link**

Test: Remove Google Maps API key in Settings, then click "Validate with Google" on a route card.
Expected: No modal appears; instead an amber "Google API key required — Configure in Settings" message appears inline on the route card.
Why human: Requires runtime state change; Settings link navigation needs visual confirmation.

**5. Settings page Validation History card**

Test: Navigate to Settings page after performing at least one validation.
Expected: Card 4 "Validation History" shows count, total cost in INR, and a table row with the validated route's driver name, distance delta, confidence badge, and date.
Why human: Requires visual inspection of Settings page with real data.

---

### Gaps Summary

No gaps. All 14 must-have truths are verified with substantive, wired implementations. All 20 backend tests pass. Dashboard builds successfully. No automatic validation triggers exist. All four VAL requirements are fully satisfied.

---

_Verified: 2026-03-15T00:30:00Z_
_Verifier: Claude (gsd-verifier)_
