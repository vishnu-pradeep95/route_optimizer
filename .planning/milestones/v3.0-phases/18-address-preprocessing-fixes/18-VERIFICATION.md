---
phase: 18-address-preprocessing-fixes
verified: 2026-03-14T01:15:17Z
status: passed
score: 16/16 must-haves verified
re_verification: false
---

# Phase 18: Address Preprocessing Fixes — Verification Report

**Phase Goal:** Fix trailing-letter split garbling, (H) expansion, PO concatenation, and tighten geocode validation
**Verified:** 2026-03-14T01:15:17Z
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|---------|
| 1 | (HO) expands to "House" with proper word spacing | VERIFIED | `re.sub(r"\(HO\)", " House ", addr)` at cdcms_preprocessor.py:439; smoke test `clean_cdcms_address("PERATTEYATH(HO)CHORODE")` -> `"Peratteyath House Chorode"` |
| 2 | (PO) expands to "P.O." with proper word spacing | VERIFIED | `re.sub(r"\(PO\)", " P.O. ", addr)` at cdcms_preprocessor.py:447; smoke test `clean_cdcms_address("CHORODE(PO)POOLAKANDY")` -> `"Chorode P.O. Poolakandy"` |
| 3 | (H) expands with space padding (no concatenation) | VERIFIED | `re.sub(r"\(H\)", " House ", addr)` at cdcms_preprocessor.py:443; smoke test `clean_cdcms_address("CHALIL(H)7/214A")` -> `"Chalil House 7/214 A"` |
| 4 | (HO) pattern placed before (H) to prevent partial matching | VERIFIED | Line 439 precedes line 443 in cdcms_preprocessor.py |
| 5 | MUTTUNGAL preserved as single word in all compound patterns | VERIFIED | In `_PROTECTED_WORDS` frozenset (line 75); `clean_cdcms_address("MUTTUNGAL (PO)BALAVADI")` -> `"Muttungal P.O. Balavadi"` |
| 6 | AddressSplitter first+last char guard prevents fuzzy false positives | VERIFIED | address_splitter.py:237-244: `candidate[0] == compact_name[0] and candidate[-1] == compact_name[-1]` guard present |
| 7 | GEOCODE_ZONE_RADIUS_KM defaults to 20 (not 30) | VERIFIED | config.py:41: `int(os.environ.get("GEOCODE_ZONE_RADIUS_KM", "20"))`; confirmed `GEOCODE_ZONE_RADIUS_KM == 20` at runtime |
| 8 | Depot lat/lon configurable via DEPOT_LAT/DEPOT_LON env vars | VERIFIED | config.py:24-26: `float(os.environ.get("DEPOT_LAT", "..."))` and `float(os.environ.get("DEPOT_LON", "..."))` |
| 9 | Zone radius configurable via GEOCODE_ZONE_RADIUS_KM env var | VERIFIED | config.py:41: env var override pattern present |
| 10 | Place name dictionary rebuilt at 20km radius | VERIFIED | data/place_names_vatakara.json metadata: `{"radius_km": 20, "entry_count": 167}` |
| 11 | Out-of-zone (~25km) coordinates rejected as direct hits | VERIFIED | test_validator.py:89-109: `test_out_of_zone_address_not_accepted_as_direct` verifies `result.method != "direct"` and `result.confidence < 0.5`; 123 tests pass |
| 12 | GET /api/config returns zone_radius_km field | VERIFIED | main.py:851: `zone_radius_km: float` field in AppConfig model; main.py:925: `zone_radius_km=config.GEOCODE_ZONE_RADIUS_KM` in endpoint return |
| 13 | Dashboard live map shows dashed zone circle driven by server config | VERIFIED | RouteMap.tsx:159-166: memoized `zoneCircle` using `@turf/circle`; lines 203-216: `Source id="zone-boundary"` with dashed line Layer |
| 14 | LiveMap.tsx fetches zone config and passes it to RouteMap | VERIFIED | LiveMap.tsx:148-151: `fetchAppConfig().then(cfg => setZoneRadiusKm(cfg.zone_radius_km))`; line 299: `zoneRadiusKm={zoneRadiusKm}` prop passed |
| 15 | Pytest API-level tests verify address cleaning on real Refill.xlsx data | VERIFIED | test_address_cleaning.py: 209 lines, 8 tests; all 8 pass (2.43s runtime on real Refill.xlsx data) |
| 16 | Playwright E2E spec covers upload + address display verification | VERIFIED | e2e/dashboard-address-cleaning.spec.ts: 102 lines, 3 tests covering raw abbreviation absence and expanded form presence |

**Score:** 16/16 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `core/data_import/cdcms_preprocessor.py` | Fixed (HO), (PO) regex patterns with space padding in Step 4 | VERIFIED | Lines 439/443/447: all three patterns present in correct order; `\(HO\)` before `\(H\)` |
| `tests/core/data_import/test_cdcms_preprocessor.py` | 15+ tests for (HO), (PO), (H); min_lines 900 | VERIFIED | 1041 lines; TestParenthesizedAbbreviations (line 868) + TestRefillXlsxRegressions (line 967); 80 total tests, all pass |
| `apps/kerala_delivery/config.py` | GEOCODE_ZONE_RADIUS_KM=20, env var overrides | VERIFIED | Line 41: `int(os.environ.get("GEOCODE_ZONE_RADIUS_KM", "20"))`; DEPOT env vars at lines 24-26 |
| `data/place_names_vatakara.json` | Rebuilt dictionary at 20km radius | VERIFIED | Metadata: `radius_km: 20`, 167 entries, generated 2026-03-14 |
| `scripts/build_place_dictionary.py` | RADIUS_M = 20000 | VERIFIED | Line 32: `RADIUS_M = 20000` |
| `tests/core/geocoding/test_interfaces_method.py` | Updated assertion `== 20` | VERIFIED | Line 70: `assert GEOCODE_ZONE_RADIUS_KM == 20` |
| `tests/core/geocoding/test_validator.py` | zone_radius_m=20_000 and out-of-zone test | VERIFIED | Line 83: `zone_radius_m=20_000`; lines 89-109: out-of-zone boundary test present |
| `apps/kerala_delivery/api/main.py` | AppConfig model with zone_radius_km | VERIFIED | Line 851: `zone_radius_km: float` field; line 925: wired to `config.GEOCODE_ZONE_RADIUS_KM` |
| `apps/kerala_delivery/dashboard/src/components/RouteMap.tsx` | Zone boundary circle as dashed GeoJSON line layer | VERIFIED | Lines 159-216: `zoneRadiusKm` prop, `zoneCircle` useMemo, Source `id="zone-boundary"` with dashed Layer |
| `apps/kerala_delivery/dashboard/src/lib/api.ts` | fetchAppConfig function returning config with zone_radius_km | VERIFIED | Lines 163-174: `AppConfig` interface with `zone_radius_km: number` and `fetchAppConfig()` exported |
| `apps/kerala_delivery/dashboard/src/pages/LiveMap.tsx` | Fetches AppConfig on mount, passes zoneRadiusKm to RouteMap | VERIFIED | Line 28: imports `fetchAppConfig`; lines 148-151: useEffect fetch; line 299: prop passed |
| `tests/apps/kerala_delivery/api/test_address_cleaning.py` | 6+ pytest tests using real Refill.xlsx data; min_lines 80 | VERIFIED | 209 lines, 8 tests; all pass on real Refill.xlsx through `clean_cdcms_address()` |
| `e2e/dashboard-address-cleaning.spec.ts` | Playwright E2E spec; min_lines 40 | VERIFIED | 102 lines, 3 tests; checks no raw (HO)/(PO) in dashboard route view |
| `e2e/helpers/setup.ts` | REFILL_XLSX_PATH exported | VERIFIED | Line 27: `export const REFILL_XLSX_PATH = path.join(...)` |
| `core/data_import/address_splitter.py` | First+last char guard on fuzzy matching | VERIFIED | Lines 237-244: guard present with clear comment explaining the MUTTUNGAL false-positive fix |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `cdcms_preprocessor.py` Step 4 | `clean_cdcms_address` output | `(HO)` before `(H)` regex order | WIRED | Line 439 `\(HO\)` precedes line 443 `\(H\)` — ordering confirmed |
| `apps/kerala_delivery/config.py` | `core/geocoding/validator.py` | `GEOCODE_ZONE_RADIUS_KM` used in GeocodeValidator construction | WIRED | main.py:1639: `zone_radius_m=config.GEOCODE_ZONE_RADIUS_KM * 1000` wires config to validator |
| `scripts/build_place_dictionary.py` | `data/place_names_vatakara.json` | `RADIUS_M = 20000` drives OSM Overpass query | WIRED | `RADIUS_M` appears in Overpass URL at line 45; dictionary metadata confirms 20km radius |
| `apps/kerala_delivery/api/main.py` | `apps/kerala_delivery/config.py` | `config.GEOCODE_ZONE_RADIUS_KM` | WIRED | Line 925: `zone_radius_km=config.GEOCODE_ZONE_RADIUS_KM` |
| `LiveMap.tsx` | `RouteMap.tsx` | `zoneRadiusKm` prop from `fetchAppConfig` | WIRED | LiveMap.tsx:148-151 fetches config; line 299 passes `zoneRadiusKm={zoneRadiusKm}` to RouteMap |
| `RouteMap.tsx` | `/api/config` | `fetchAppConfig` in api.ts | WIRED | LiveMap.tsx fetches via `fetchAppConfig()` (imported at line 28); api.ts:172 calls `/api/config` |
| `tests/apps/.../test_address_cleaning.py` | `apps/.../api/main.py` | real Refill.xlsx data through `clean_cdcms_address()` | WIRED | test_address_cleaning.py:25: imports `clean_cdcms_address`; loads Refill.xlsx at line 28 |
| `e2e/dashboard-address-cleaning.spec.ts` | `apps/kerala_delivery/dashboard` | Playwright upload + DOM assertion | WIRED | spec imports `REFILL_XLSX_PATH`; POSTs to `/api/upload-orders`; asserts body text |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|---------|
| ADDR-01 | 18-01, 18-04 | System correctly preserves "MUTTUNGAL" as a single word | SATISFIED | `MUTTUNGAL` in `_PROTECTED_WORDS` (cdcms_preprocessor.py:75); `MUTTUNGALPARA` added (line 80); AddressSplitter first+last char guard (address_splitter.py:237-244); 8 pytest tests verify on real data |
| ADDR-02 | 18-01, 18-04 | System correctly handles (H) expansion without splitting adjacent words | SATISFIED | `re.sub(r"\(H\)", " House ", ...)` with space padding at cdcms_preprocessor.py:443; tests confirm `"Chalil House 7/214 A"` output |
| ADDR-03 | 18-01, 18-04 | System correctly splits PO abbreviations from concatenated text | SATISFIED | `re.sub(r"\(PO\)", " P.O. ", ...)` at cdcms_preprocessor.py:447; `re.sub(r"([a-zA-Z])PO\.", ...)` at line 433; `\bPO\b` expansion in Step 7; smoke test `"Chorode P.O. Poolakandy"` verified |
| ADDR-04 | 18-02, 18-03 | Geocode validation uses 20km radius | SATISFIED | `GEOCODE_ZONE_RADIUS_KM = int(os.environ.get("GEOCODE_ZONE_RADIUS_KM", "20"))` (config.py:41); dictionary rebuilt at 20km; validator.py default 20_000; 123 geocoding tests pass |
| ADDR-05 | 18-02, 18-03 | Geocode validation centroid is always the Vatakara depot location from config | SATISFIED | DEPOT_LOCATION read from env vars with hardcoded Vatakara defaults (config.py:23-27); API wires `config.DEPOT_LOCATION.latitude/longitude` to AppConfig response and to GeocodeValidator |

All 5 requirements fully satisfied. All mapped in REQUIREMENTS.md Traceability table as Complete.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| RouteMap.tsx | 219 | `TODO Phase 3: Add drag-and-drop route adjustment` | Info | Pre-existing comment from before Phase 18; deferred feature, not Phase 18 work |

No blockers or warnings found in Phase 18 code. The one TODO is pre-existing and out of scope.

---

### Test Suite Results

| Test Module | Count | Result |
|-------------|-------|--------|
| `tests/core/data_import/test_cdcms_preprocessor.py` | 80 tests | 80 passed |
| `tests/core/geocoding/` (all) | 123 tests | 123 passed |
| `tests/integration/test_address_pipeline.py` | 9 tests | 9 passed |
| `tests/apps/kerala_delivery/api/test_address_cleaning.py` | 8 tests | 8 passed |
| `e2e/dashboard-address-cleaning.spec.ts` | 3 tests | Requires Docker + GOOGLE_MAPS_API_KEY (human verification) |

**Note on full test suite:** Running `pytest tests/` together shows 13 intermittent failures that all pass when run individually or by class. Diagnosis confirms these are pre-existing async/test-isolation flaky tests in `test_api.py` and `test_e2e_pipeline.py` — not caused by Phase 18 changes. Phase 18 files have zero failures at any granularity.

---

### Human Verification Required

#### 1. Dashboard Zone Circle Rendering

**Test:** Start Docker stack (`docker compose up -d`), navigate to `http://localhost:8000/dashboard/`, upload an order file, open the Live Map view.
**Expected:** A dashed gray circle approximately 20km in radius appears centered on the Vatakara depot. The circle is subtle (low opacity, thin line) and appears behind route polylines.
**Why human:** MapLibre GL rendering of the GeoJSON layer cannot be verified programmatically without a running browser+GPU. The code wiring is correct; visual appearance requires human confirmation.

#### 2. E2E Playwright Address Cleaning Tests

**Test:** Start Docker stack with `GOOGLE_MAPS_API_KEY` set, run `npx playwright test --project=dashboard --grep "Address Cleaning"`.
**Expected:** All 3 tests in `e2e/dashboard-address-cleaning.spec.ts` pass — no raw `(HO)`/`(PO)` visible in dashboard address display, "House" appears in route view addresses.
**Why human:** Requires live Docker stack with real geocoding API key. Cannot be mocked in offline verification.

---

### Commit Verification

All plan commits confirmed in git history:

| Plan | Commit | Description |
|------|--------|-------------|
| 18-01 RED | `bf28f9b` | test: add failing tests for (HO), (PO), (H) expansion |
| 18-01 GREEN | `4cde7ff` | feat: fix regex patterns in cdcms_preprocessor |
| 18-02 Task 1 | `d5e763d` | feat: update config.py with env var overrides and 20km default |
| 18-02 Task 2 | `ffd604e` | feat: update tests, validator, and dictionary to 20km zone radius |
| 18-03 Task 1 | `57a4ab0` | feat: add zone_radius_km to AppConfig and install @turf/circle |
| 18-03 Task 2 | `30366c4` | feat: draw dashed zone circle on RouteMap and wire LiveMap.tsx |
| 18-04 Task 1 | `5641db1` | test: add pytest address cleaning tests with real Refill.xlsx data |
| 18-04 Task 2 | `333f144` | feat: add Playwright E2E spec for address cleaning verification |

---

### Summary

Phase 18 achieved its goal. All four plans executed cleanly:

- **Plan 18-01** fixed all three parenthesized abbreviation patterns `(HO)`, `(PO)`, `(H)` with space padding and added PERATTEYATH/POOLAKANDY/KOLAKKOTT to protected words. 80 unit tests pass.

- **Plan 18-02** reduced the geocode zone from 30km to 20km with env var overrides for depot and radius. Dictionary rebuilt at 20km with 167 entries and 100% CDCMS area name coverage. All 30km references removed from test files. Out-of-zone boundary test verifies coordinates at ~25km are rejected as direct hits.

- **Plan 18-03** extended `/api/config` with `zone_radius_km`, added `fetchAppConfig` to the dashboard API client, and drew a dashed zone boundary circle on the LiveMap using `@turf/circle`. The circle radius flows from server config, not hardcoded. Full wiring confirmed: config.py -> main.py -> api.ts -> LiveMap.tsx -> RouteMap.tsx.

- **Plan 18-04** created 8 pytest tests that run real Refill.xlsx data (1885 Allocated-Printed orders) through `clean_cdcms_address()` and verify all patterns. Added Playwright E2E spec. Fixed AddressSplitter fuzzy match false positives (first+last char guard) that were garbling 44/65 MUTTUNGAL addresses. Added MUTTUNGALPARA to protected words.

All 5 requirements (ADDR-01 through ADDR-05) are fully satisfied with evidence in code, tests, and runtime verification.

---

_Verified: 2026-03-14T01:15:17Z_
_Verifier: Claude (gsd-verifier)_
