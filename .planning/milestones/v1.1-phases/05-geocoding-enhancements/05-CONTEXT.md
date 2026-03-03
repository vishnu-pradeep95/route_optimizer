# Phase 5: Geocoding Enhancements - Context

**Gathered:** 2026-03-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Office staff can see which addresses cost money (API calls vs cache hits) and get warned when multiple orders in an upload resolve to suspiciously close GPS coordinates. This phase adds cost transparency (GEO-04) and duplicate location detection (GEO-03) to the existing upload workflow. No new pages, no new endpoints — enhancements to the existing POST /api/upload-orders response and dashboard upload results panel.

</domain>

<decisions>
## Implementation Decisions

### Cost Reporting (GEO-04)
- Summary totals at top of upload response: cache hits (free) vs API calls, with estimated cost
- Per-address source tagging: each geocoded order tagged as "cached" or "API call" in the response
- Cost estimate includes free-tier awareness: "12 API calls (~$0.06) — within $200/month free tier"
- Cost calculation uses fixed $0.005/request (Google standard rate)
- Display in upload response only — no persistence to Run History (keeps Phase 5 focused)

### Duplicate Warning Display (GEO-03)
- Grouped clusters, not pair-by-pair: "Orders 101, 205, 312 resolve within 15m of each other"
- Non-blocking: optimization proceeds normally, warnings shown alongside results
- Each cluster shows: order IDs, address text for each order, distance between orders
- Dedicated "Duplicate Location Warnings" section in upload results — visually distinct from validation warnings/failures
- Only compare within current upload (not against previous runs)

### Confidence Thresholds
- Confidence-weighted distance thresholds: tighter for ROOFTOP, wider for GEOMETRIC_CENTER
- Thresholds configurable in config.py (DUPLICATE_THRESHOLDS dict or similar) for easy tuning after real-world testing
- Actual threshold meter values and mixed-confidence approach at Claude's discretion — optimize for minimizing false positives in dense Vatakara streets

### Same-Address Handling
- Exclude orders with exact same normalized address from duplicate detection — multiple orders to same household is legitimate for LPG delivery (multi-cylinder)
- Only flag different addresses that resolve to nearby GPS coordinates
- Skip failed (non-geocoded) orders — no GPS coords to compare

### Claude's Discretion
- Per-address source tag display format (badge vs separate section vs inline annotation)
- Exact confidence threshold values per location_type tier
- Mixed-confidence pair handling (which threshold to use when two orders have different confidence levels)
- Whether to show confidence/accuracy context in duplicate warnings for non-technical staff
- Loading skeleton design for any new UI sections

</decisions>

<specifics>
## Specific Ideas

- Free-tier awareness in cost display reminds staff they're not actually being billed yet ("within $200/month free tier")
- Duplicate clusters should be immediately actionable — staff sees order IDs, both addresses, and distance so they can decide if it's a data entry error without clicking through

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `CachedGeocoder.stats` dict: Already tracks `{"hits": 0, "misses": 0, "errors": 0}` per instance — foundation for GEO-04
- `CachedGeocoder.get_stats_summary()`: Returns human-readable cache performance string
- `GeocodingResult.confidence`: 0.0–1.0 score mapped from Google's `location_type` (ROOFTOP=0.95, RANGE_INTERPOLATED=0.80, GEOMETRIC_CENTER=0.60, APPROXIMATE=0.40)
- `GeocodeCacheDB.source` field: Already tracks "google" vs "driver_verified" vs "manual"
- PostGIS `ST_DistanceSphere`: Available for proximity queries between geocoded coordinates

### Established Patterns
- `OptimizationSummary` Pydantic model: Upload response schema — new fields can be added with defaults for backward compatibility
- `ImportFailure` model: Existing pattern for per-row diagnostic reporting (row_number, address_snippet, reason, stage)
- Config constants in `apps/kerala_delivery/config.py`: Business-specific values (depot coords, fleet size, cylinder weights) — thresholds belong here
- Upload endpoint iterates orders for geocoding sequentially via `CachedGeocoder.geocode()` — duplicate check can run after all orders are geocoded

### Integration Points
- `apps/kerala_delivery/api/main.py` upload_and_optimize(): Main endpoint that needs cost stats + duplicate warnings in response
- `OptimizationSummary`: Response model needs new fields for cache stats, cost estimate, and duplicate warnings
- `apps/kerala_delivery/dashboard/src/pages/UploadRoutes.tsx`: Frontend needs to render the new warning section and cost breakdown

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-geocoding-enhancements*
*Context gathered: 2026-03-01*
