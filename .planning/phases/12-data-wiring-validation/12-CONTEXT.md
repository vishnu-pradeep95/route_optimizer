# Phase 12: Data Wiring & Validation - Context

**Gathered:** 2026-03-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire the existing `save_driver_verified()` function into the delivery status endpoint so driver GPS data builds a verified geocoding database. Validate duplicate detection thresholds against actual production geocode_cache data. Requirements: API-07, DATA-01.

</domain>

<decisions>
## Implementation Decisions

### Driver verification trigger (API-07)
- Call `save_driver_verified()` ONLY when status is "delivered" AND GPS coordinates are present in the request
- Do NOT fire on "failed" status — driver may not be at the exact address
- Do NOT fire when GPS coords are missing — no location data to save
- Silent no-op when conditions aren't met (no error, just skip)

### Threshold validation approach (DATA-01)
- Write a SQL query that counts `location_type` distribution in `geocode_cache` table
- Run the query against the production database
- Document findings in a markdown report in the phase directory
- If data shows current thresholds (rooftop=10m, interpolated=20m, geometric_center=50m, approximate=100m) need adjustment, adjust them in the code
- Evidence-based: the report must show the data that justifies the threshold values

### Claude's Discretion
- How to instantiate CachedGeocoder in the endpoint (session management)
- Whether to log the save_driver_verified call or keep it silent beyond existing logging
- SQL query structure and exact report format
- Whether thresholds need adjustment based on data findings

</decisions>

<specifics>
## Specific Ideas

- `save_driver_verified()` already sets confidence=0.95 and source="driver_verified" — just needs to be called
- The endpoint already receives `body.latitude` and `body.longitude` and constructs a `Location` object
- Duplicate detector thresholds are passed as a dict parameter, not hardcoded — easy to adjust

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `save_driver_verified()` in `core/geocoding/cache.py:246` — fully implemented with tests, calls `repo.save_geocode_cache()` internally
- `CachedGeocoder` class needs a DB session — endpoint already has one via `SessionDep`
- `duplicate_detector.py` `detect_duplicate_locations()` accepts thresholds as a dict parameter

### Established Patterns
- Endpoint uses `session: AsyncSession = SessionDep` for DB access
- `repo.update_stop_status()` already called in the endpoint — save_driver_verified is a parallel call
- Mid-function imports used in cache.py (`from core.database import repository as repo`)

### Integration Points
- `POST /api/routes/{vehicle_id}/stops/{order_id}/status` in `main.py:1267` — wire save_driver_verified after successful status update
- `geocode_cache` table — query for location_type distribution
- Thresholds used in `main.py` where `detect_duplicate_locations()` is called with the threshold dict

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 12-data-wiring-validation*
*Context gathered: 2026-03-04*
