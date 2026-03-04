# Phase 9: Config Consolidation - Context

**Gathered:** 2026-03-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Create a single API config endpoint (`GET /api/config`) that serves depot coordinates, safety multiplier, and office phone number from `config.py`. Replace the QR sheet magic number with a named constant. This phase creates the endpoint — consumer wiring (Driver PWA, dashboard) happens in Phase 10.

</domain>

<decisions>
## Implementation Decisions

### Endpoint design
- Path: `GET /api/config`
- Response: minimal JSON with exactly 3 values — depot lat/lng, safety multiplier, office phone number
- Authentication: public (no API key required) — these values aren't secrets
- Caching: none — simple JSON response, config changes require redeploy anyway
- No version field or ETag

### Phone number source
- Add `OFFICE_PHONE_NUMBER` constant to `config.py` alongside other business constants
- Format: E.164 (`+91XXXXXXXXXX`)
- Value: placeholder for now (e.g., `+910000000000`) — clearly marked for replacement with real number
- Not sourced from env var or database — consistent with depot/multiplier pattern

### QR sheet buffer alignment
- Add `QR_SHEET_DURATION_BUFFER = 1.2` named constant to `config.py`
- Replace magic `1.2` in QR sheet HTML generation (main.py line ~1422) with this constant
- Keep as a separate concept from `SAFETY_MULTIPLIER` (different purposes: display range vs routing estimate)
- API-internal only — not served via `/api/config` (only server-rendered QR sheet uses it)

### Consumer migration scope
- Phase 9 scope: create the endpoint + fix QR magic number only
- Driver PWA wiring (phone number, depot coords): deferred to Phase 10 (already in Phase 10 requirements)
- Dashboard: does not need `/api/config` — depot/multiplier already flow through route data
- QR sheet: server-rendered, reads `config.py` directly (no endpoint consumption needed)

### Claude's Discretion
- Pydantic response model structure for the config endpoint
- Exact constant naming conventions (follow existing config.py patterns)
- Placement of endpoint in main.py (near other read-only endpoints)

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches. Follow existing `config.py` documentation style with section headers and comments explaining each constant.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `config.py`: Well-organized with section headers, docstring explaining single-source-of-truth pattern. New constants follow the same pattern.
- `verify_read_key` dependency: Exists but not needed (endpoint is public)
- `html_module.escape`: Already used in QR sheet for XSS prevention

### Established Patterns
- Config values are Python constants in `config.py`, not env vars (except external service URLs)
- All GET endpoints return JSON via FastAPI's automatic Pydantic serialization
- QR sheet is server-rendered HTML in `get_qr_sheet()` endpoint

### Integration Points
- `config.py` line 84: `SAFETY_MULTIPLIER = 1.3` — already exists, will be served via endpoint
- `config.py` line 23-27: `DEPOT_LOCATION` — already exists as `Location` object, endpoint serves lat/lng
- `main.py` line 1422: `total_duration_minutes * 1.2` — magic number to replace with new constant
- Driver PWA line 843: `tel:+919876543210` — placeholder phone, will be wired in Phase 10

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 09-config-consolidation*
*Context gathered: 2026-03-04*
