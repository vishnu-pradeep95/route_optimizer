# Phase 14: API Confidence Fields and Driver PWA Badge - Context

**Gathered:** 2026-03-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Expose geocode confidence data in the route API response and add visual indicators to the Driver PWA so drivers can see at a glance which delivery stops have approximate locations. This covers: API response field additions, hero card warning badge, compact card orange dot indicator, and map view pin coloring. Requirements: APUI-01, APUI-02, APUI-03, APUI-04.

</domain>

<decisions>
## Implementation Decisions

### Hero card badge
- Badge placement: below the address text, before the meta line (qty/weight/distance)
- Badge content: "⚠ Approx. location" — icon + text, using DaisyUI `badge-warning`
- Badge persists across all delivery states (pending, delivered, failed) — location accuracy is a fact about the data, not the delivery status
- Navigate button stays unchanged (no visual modification for approximate stops)
- Same badge for all approximate stops (centroid 0.3 and depot 0.1 get identical badge — no tiered severity)

### Compact card orange dot
- Small superscript dot (6-8px solid orange circle) positioned at the top-right corner of the stop number circle, like a notification badge
- Dot only — no text label on compact cards (hero card has the full text badge; drivers learn the association)
- Dot persists alongside delivered/failed status indicators — both are true facts about the stop

### Driver guidance
- Badge text is exactly "⚠ Approx. location" — no additional hint text, no tooltip, no tap interaction
- Drivers are local and know to call the customer when the pin is off — keep it minimal

### Map view pins
- Approximate stops show as orange Leaflet markers instead of the default color on the map view
- Consistent visual language: orange = approximate across hero card, compact card, and map

### API response fields
- `GET /api/routes/{vehicle_id}` response includes three new fields per stop: `geocode_confidence` (float), `location_approximate` (boolean), `geocode_method` (string)
- `location_approximate` = true when `geocode_confidence < 0.5` (strictly less than)
- NULL confidence (pre-Phase 13 orders) → `geocode_confidence: null`, `geocode_method: null`, `location_approximate: false` (no badge shown)
- `geocode_method` exposed for debugging and future dashboard use, but NOT shown in driver UI

### Claude's Discretion
- Exact CSS for the orange dot (positioning, z-index, shadow)
- DaisyUI badge size class for the hero card badge
- Leaflet marker icon implementation for orange approximate pins
- Any necessary refactoring of the stop serialization in the route endpoint

</decisions>

<specifics>
## Specific Ideas

- The orange dot on compact cards should follow the standard mobile "notification badge" pattern — small circle overlapping the top-right of the stop number
- Phase 13 CONTEXT.md specified: "Phase 14 treats NULL as 'pre-validation data' with no badge/warning shown" — honored by mapping null → location_approximate: false

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `renderHeroCard()` (index.html:1374): Hero card render function — add badge after address, before meta line
- `renderCompactCard()` (index.html:1409): Compact card render function — add dot to stop-number-inner div
- `.hero-card` CSS (index.html:168): Hero card styles — badge goes in new div after `.hero-address-raw`
- `.compact-card .stop-number` CSS (index.html:289): Stop number styles — dot positioned relative to this
- DaisyUI `badge-warning` class: Available via `tw:badge tw:badge-warning` prefix convention
- `geocode_confidence` and `geocode_method` already stored on Order model (Phase 13)
- `route_db_to_pydantic()` in repository.py: Converts DB route to Pydantic — stop data flows through here

### Established Patterns
- `.compact-card::before` (index.html:274): Left border accent pattern for status colors (pending/delivered/failed) — dot uses a different visual channel (superscript) to avoid conflict
- `escapeHtml()`: All dynamic content in cards uses this helper
- Stop object fields accessed as `stop.address`, `stop.latitude`, etc. in render functions
- Tailwind `tw:` prefix for all utility classes (CLAUDE.md convention)

### Integration Points
- `GET /api/routes/{vehicle_id}` endpoint (main.py:1520-1576): Stop serialization dict at lines 1559-1574 — add three new fields
- `route_db_to_pydantic()`: Must propagate geocode_confidence and geocode_method from OrderDB to the Pydantic stop model
- Leaflet map initialization in `initMap()` (index.html:1447): Pin creation happens here — conditional orange color
- `L.marker()` calls in the map rendering code: Need to accept custom icon for approximate stops

</code_context>

<deferred>
## Deferred Ideas

- Batch-level "all approximate" banner in Driver PWA when API key is invalid (tracked as AINT-03 in REQUIREMENTS.md)
- Map view clustering of approximate stops

</deferred>

---

*Phase: 14-api-confidence-fields-and-driver-pwa-badge*
*Context gathered: 2026-03-11*
