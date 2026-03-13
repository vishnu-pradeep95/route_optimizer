# Phase 18: Address Preprocessing Fixes - Context

**Gathered:** 2026-03-13
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix known address garbling patterns in CDCMS preprocessing and tighten geocode validation from 30km to 20km. Address cleaning for MUTTUNGAL, (H), and PO patterns was implemented in v2.2 — this phase verifies those implementations against real data (Refill.xlsx), fixes any remaining issues, reduces the zone radius, rebuilds the place name dictionary at 20km, and adds comprehensive test coverage at all levels (unit, API, Playwright E2E).

</domain>

<decisions>
## Implementation Decisions

### Verify vs Fix Scope
- v2.2 already implemented MUTTUNGAL protection, (H) expansion, and PO two-pass splitting
- This phase runs real CDCMS data (data/Refill.xlsx) through the pipeline to verify correctness
- If bugs are found, fix in existing v2.2 code (extend protected words, regex, dictionary — not new layers)
- Comprehensive tests at all levels — unit tests, API-level tests, and Playwright E2E — no shortcuts

### Testing Strategy
- Use real data/Refill.xlsx for both API-level and Playwright E2E testing
- API-level tests: POST to upload endpoints, verify cleaned address text and valid coordinates
- Playwright E2E: upload Refill.xlsx through dashboard, verify addresses display correctly in route view
- Add targeted unit tests for specific MUTTUNGAL/(H)/PO patterns found in Refill.xlsx
- Comprehensive coverage — don't cheap out on test count

### Zone Radius Reduction
- Change GEOCODE_ZONE_RADIUS_KM from 30 to 20 (hard boundary, no buffer zone)
- Make depot lat/lon env-configurable (DEPOT_LAT, DEPOT_LON env vars override config.py defaults)
- Make zone radius env-configurable (GEOCODE_ZONE_RADIUS_KM env var, default 20)
- Rebuild place_names_vatakara.json dictionary at 20km radius (rerun OSM Overpass, same approach as v2.2)
- No audit log of removed entries — trust the radius

### API and Dashboard
- Expose zone_radius_km in /api/config response alongside depot coordinates
- Draw a dashed 20km zone circle on the dashboard live map showing the delivery boundary
- Out-of-zone addresses (>20km) are hard-rejected — flagged as out-of-zone with UI warning

### Edge Case Handling
- Don't pre-guess edge cases — let the real data reveal them
- Process Refill.xlsx through the pipeline, examine output for garbling
- Fix any found issues in existing v2.2 code (extend patterns, not new heuristics)
- If no issues found, phase focuses on radius change + env config + map circle + tests

### Claude's Discretion
- OSM Overpass query parameters for 20km dictionary rebuild
- Exact Playwright test structure and assertion patterns
- How to integrate zone circle with existing MapLibre live map component
- Whether to use MapLibre Circle or GeoJSON polygon for the zone boundary

</decisions>

<specifics>
## Specific Ideas

- Zone circle should be dashed/subtle — informational overlay, not a dominant visual element
- Refill.xlsx is the ground truth for testing — real CDCMS data from the Vatakara office

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/data_import/cdcms_preprocessor.py`: Full address cleaning pipeline (Steps 1-7) with protected words, regex, two-pass abbreviation
- `core/data_import/address_splitter.py`: RapidFuzz dictionary-based word splitting (AddressSplitter class)
- `core/geocoding/validator.py`: GeocodeValidator with haversine zone check, area-name retry, centroid fallback
- `apps/kerala_delivery/config.py`: DEPOT_LOCATION, GEOCODE_ZONE_RADIUS_KM, CDCMS_AREA_SUFFIX
- `data/place_names_vatakara.json`: 381-entry Kerala place name dictionary (OSM Overpass, currently 30km)

### Established Patterns
- Config values in `config.py` with env var overrides (see existing POSTGRES_PASSWORD, GOOGLE_MAPS_API_KEY patterns)
- /api/config endpoint serves frontend-needed config values (depot coords, safety multiplier, office phone)
- Confidence tiers: 1.0 (direct hit), 0.7 (area retry), 0.3 (centroid fallback), 0.0 (out of zone)
- Dashboard live map uses MapLibre GL JS with GeoJSON layers

### Integration Points
- `config.py:39` — GEOCODE_ZONE_RADIUS_KM (change 30 → 20, add env var)
- `config.py:22-26` — DEPOT_LOCATION (add DEPOT_LAT/DEPOT_LON env vars)
- `api/main.py` /api/config endpoint — add zone_radius_km to response
- Dashboard live map component — add zone circle overlay layer
- `tests/core/geocoding/test_interfaces_method.py:70` — assert radius == 20
- `tests/core/geocoding/test_validator.py:83` — zone_radius_m=20_000

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 18-address-preprocessing-fixes*
*Context gathered: 2026-03-13*
