# Phase 22: Google Routes Validation - Research

**Researched:** 2026-03-14
**Domain:** Google Routes API integration, route comparison, cost tracking
**Confidence:** HIGH

## Summary

Phase 22 adds a manual "Validate with Google" feature to route cards. When clicked, the backend calls the Google Routes API `computeRoutes` endpoint with the route's stops (lat/lng waypoints), requesting Google to re-optimize stop order. The response distance and duration are compared against the VROOM/OSRM values already stored in the database. Results persist in a new `route_validations` table with cumulative cost tracking.

The Google Routes API uses a REST endpoint at `https://routes.googleapis.com/directions/v2:computeRoutes` with API key authentication via `X-Goog-Api-Key` header. Waypoints are specified using lat/lng coordinates (already available from the route stops), so no additional geocoding is needed. The `optimizeWaypointOrder: true` flag triggers Google's own stop reordering, which means the comparison measures both road-network accuracy AND optimization quality -- matching the user's decision.

**Primary recommendation:** Use Google Routes API `computeRoutes` with `optimizeWaypointOrder: true` and `TRAFFIC_UNAWARE` routing preference, sending waypoints as lat/lng (not addresses). This avoids geocoding costs and gives a clean distance/duration comparison. Billing tier is Pro ($0.01 per request / approximately INR 0.93).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Inline in route card -- no modal or separate panel. Validation results expand within the existing RouteList card after the current stats
- "Validate with Google" button visible on every route card (not just selected)
- One-at-a-time only -- no "Validate All" batch button
- Display: OSRM distance, Google distance, delta %. Same for time. Plus a colored confidence badge
- Confidence indicator based on distance delta only (time varies with traffic, distance is stable)
- Google re-optimizes stop order -- comparison measures both road-network accuracy and optimization quality
- Show per-request estimated cost AND cumulative tracker (validations count + total estimated cost)
- Always warn on every validation click -- no "don't ask again" option
- If Google Maps API key is not configured: show message with link/button to Settings page (button still visible)
- Validation results stored in database (not session-only) -- needs DB migration
- Previously-validated routes show cached result inline with a "Re-validate" button (no re-calling Google)
- Cumulative validation count and cost persist in DB for budgeting
- Validation history card added to Settings page (total validations, total cost, recent validations with results)
- Google should re-optimize stop order (not follow VROOM sequence) -- measures total routing quality
- Cost tracker shows something like "INR 0.42 per validation (12 validations today, ~INR 5.04 total)"
- When no API key configured, button click shows "Google API key required" with a link to Settings page
- Cached validation results should show the date they were validated, so user knows how fresh the comparison is

### Claude's Discretion
- Confidence thresholds (green/amber/red delta percentages)
- Badge visual style (dot+text vs percentage badge)
- Cost warning confirmation UX (modal vs popover)
- Google Routes API vs Directions API choice
- DB schema for validation results and cost tracking
- How to handle Google API errors (timeout, quota exceeded, invalid key)
- Whether to store per-stop comparison or route-level only

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| VAL-01 | User can trigger Google Routes API comparison for a generated route | Google Routes API computeRoutes endpoint identified; lat/lng waypoint format avoids re-geocoding; optimizeWaypointOrder enables stop reordering |
| VAL-02 | System displays VROOM/OSRM vs Google Routes distance/time comparison with confidence indicator | Response provides distanceMeters and duration fields; confidence thresholds researched; badge pattern exists in StatusBadge.tsx |
| VAL-03 | System shows cost warning before running Google Routes validation | Pro tier pricing confirmed: $0.01/request (~INR 0.93); DaisyUI modal pattern established in Settings.tsx |
| VAL-04 | Google Routes validation is never triggered automatically (user-initiated only) | Architecture ensures validation only runs on explicit button click with cost confirmation |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| httpx | (existing) | Google Routes API HTTP calls | Already used for Google Geocoding calls in google_adapter.py |
| SQLAlchemy 2.0 | (existing) | RouteValidation ORM model | Established pattern for all DB models |
| Alembic | (existing) | Database migration for validation table | Used for all schema changes |
| React 19 | (existing) | Frontend validation UI components | Dashboard framework |
| DaisyUI v5 | (existing) | Modal, badge, card components | Established UI library |
| lucide-react | (existing) | Icons for validate button | Icon library already in use |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| FastAPI | (existing) | New validation API endpoint | Backend API framework |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Google Routes API | Google Directions API | Routes API is the newer replacement; Directions API is legacy; Routes API has cleaner JSON format and explicit waypoint optimization support |
| Pro tier (with optimization) | Essentials tier (without optimization) | User explicitly wants Google to re-optimize stop order, so Pro tier is required |

**Installation:**
No new packages needed. All dependencies are already installed.

## Architecture Patterns

### Recommended Project Structure
```
core/database/models.py          # Add RouteValidationDB model
core/database/repository.py      # Add validation CRUD methods
infra/alembic/versions/          # New migration for route_validations table
apps/kerala_delivery/api/main.py # New POST /api/routes/{vehicle_id}/validate endpoint
apps/kerala_delivery/dashboard/
  src/types.ts                   # Add ValidationResult type
  src/lib/api.ts                 # Add validateRoute() client function
  src/components/RouteList.tsx   # Add validate button + inline results
  src/components/RouteList.css   # Styles for validation section
  src/pages/Settings.tsx         # Add Validation History card
```

### Pattern 1: Google Routes API Call (Backend)
**What:** POST to Google Routes API with route stops as lat/lng waypoints
**When to use:** When user clicks "Validate with Google" button
**Example:**
```python
# Source: https://developers.google.com/maps/documentation/routes/reference/rest/v2/TopLevel/computeRoutes
async def call_google_routes_api(
    api_key: str,
    depot_lat: float,
    depot_lng: float,
    stops: list[tuple[float, float]],  # (lat, lng) pairs
) -> dict:
    """Call Google Routes API computeRoutes with waypoint optimization."""
    # Build waypoints from lat/lng -- no geocoding needed
    intermediates = [
        {"location": {"latLng": {"latitude": lat, "longitude": lng}}}
        for lat, lng in stops
    ]

    body = {
        "origin": {"location": {"latLng": {"latitude": depot_lat, "longitude": depot_lng}}},
        "destination": {"location": {"latLng": {"latitude": depot_lat, "longitude": depot_lng}}},
        "intermediates": intermediates,
        "travelMode": "DRIVE",
        "optimizeWaypointOrder": True,
        "routingPreference": "TRAFFIC_UNAWARE",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://routes.googleapis.com/directions/v2:computeRoutes",
            json=body,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": "routes.distanceMeters,routes.duration,routes.optimizedIntermediateWaypointIndex",
            },
        )
        resp.raise_for_status()
        return resp.json()
```

### Pattern 2: Inline Validation Results in Route Card
**What:** Validation results displayed inline within the route card after stats
**When to use:** After validation completes or when showing cached results
**Example:**
```tsx
{/* After route-stats div, before progress bar */}
{validationResult && (
  <div className="route-validation">
    <div className="validation-comparison">
      <div className="validation-row">
        <span>Distance</span>
        <span className="numeric">{route.total_distance_km.toFixed(1)} km</span>
        <span className="numeric">{validationResult.google_distance_km.toFixed(1)} km</span>
        <ConfidenceBadge delta={validationResult.distance_delta_pct} />
      </div>
      <div className="validation-row">
        <span>Time</span>
        <span className="numeric">{route.total_duration_minutes.toFixed(0)} min</span>
        <span className="numeric">{validationResult.google_duration_minutes.toFixed(0)} min</span>
      </div>
    </div>
    <div className="validation-meta">
      Validated {formatRelativeDate(validationResult.validated_at)}
    </div>
  </div>
)}
```

### Pattern 3: Cost Warning Modal (DaisyUI)
**What:** DaisyUI modal confirming cost before API call
**When to use:** Every time user clicks "Validate with Google"
**Example:**
```tsx
{/* Reuse exact pattern from Settings.tsx clear cache modal */}
<div className="tw:modal tw:modal-open">
  <div className="tw:modal-box">
    <h3 className="tw:font-bold tw:text-lg">Validate Route with Google?</h3>
    <p className="tw:py-4">
      This will call the Google Routes API.
      Estimated cost: <strong>~INR 0.93</strong> per validation.
    </p>
    <p className="tw:text-sm tw:opacity-70">
      {cumulativeStats.count} validations so far (~INR {cumulativeStats.total_cost.toFixed(2)} total)
    </p>
    <div className="tw:modal-action">
      <button className="tw:btn" onClick={onCancel}>Cancel</button>
      <button className="tw:btn tw:btn-primary" onClick={onConfirm}>
        Validate
      </button>
    </div>
  </div>
  <div className="tw:modal-backdrop" onClick={onCancel} />
</div>
```

### Anti-Patterns to Avoid
- **Automatic validation:** Never trigger Google API call without explicit user click + cost confirmation. This is a non-negotiable requirement (VAL-04).
- **Storing full Google response:** Only store the comparison metrics (distance, duration, waypoint order), not the full API response blob. Keeps the DB lean.
- **Using address strings for waypoints:** Always use lat/lng from existing route stops. Address-based waypoints would trigger additional geocoding costs and may not match the exact locations used by VROOM.
- **Batch validation endpoint:** No "Validate All" -- user explicitly decided one-at-a-time only.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Cost confirmation dialog | Custom modal HTML | DaisyUI `tw:modal` | Already established pattern in Settings.tsx (clear cache modal) |
| Color-coded badges | Custom badge component | DaisyUI `tw:badge` with semantic classes | StatusBadge.tsx already defines the pattern with `tw:badge-success`, `tw:badge-warning`, `tw:badge-error` |
| API key retrieval | New key lookup | Existing `_cached_api_key` module variable | Already loaded at startup, updated on settings change (Phase 21) |
| HTTP client | requests or urllib | httpx (async) | Already used for Google API calls throughout the project |

**Key insight:** The entire infrastructure for Google API calls, API key management, DaisyUI modals, and color-coded badges already exists. This phase is primarily about wiring a new Google API endpoint and adding inline UI.

## Common Pitfalls

### Pitfall 1: Wrong Google API (Directions vs Routes)
**What goes wrong:** Using the legacy Directions API instead of the Routes API
**Why it happens:** Many tutorials reference the older `maps.googleapis.com/maps/api/directions/json` endpoint
**How to avoid:** Use `routes.googleapis.com/directions/v2:computeRoutes` with `X-Goog-Api-Key` and `X-Goog-FieldMask` headers
**Warning signs:** Using `key=` query parameter instead of headers; getting XML responses

### Pitfall 2: Missing or Wrong Field Mask
**What goes wrong:** Getting empty responses or paying for fields not needed
**Why it happens:** Google Routes API REQUIRES the `X-Goog-FieldMask` header; without it, responses may be empty
**How to avoid:** Always include `X-Goog-FieldMask: routes.distanceMeters,routes.duration,routes.optimizedIntermediateWaypointIndex`
**Warning signs:** Empty `routes` array in response; unexpected billing

### Pitfall 3: Duration Format Parsing
**What goes wrong:** Treating Google's duration as minutes when it's actually seconds in "1234s" format
**Why it happens:** Google Routes API returns duration as a string like "1234s" (seconds), not minutes
**How to avoid:** Parse the numeric value before "s" suffix and convert to minutes: `int(duration.rstrip('s')) / 60`
**Warning signs:** Google time values appearing 60x larger than expected

### Pitfall 4: Distance Unit Mismatch
**What goes wrong:** Comparing meters to kilometers
**Why it happens:** Google returns `distanceMeters` (meters), VROOM/OSRM stores `total_distance_km` (kilometers)
**How to avoid:** Convert Google meters to km: `distance_meters / 1000`
**Warning signs:** Google distances appearing 1000x larger than OSRM values

### Pitfall 5: Depot as Both Origin AND Destination
**What goes wrong:** Not setting depot as both origin and destination for round-trip comparison
**Why it happens:** VROOM optimizes round-trip routes (start and end at depot), but developer forgets to mirror this in the Google request
**How to avoid:** Set both `origin` and `destination` to the depot lat/lng; stops go in `intermediates`
**Warning signs:** Google distance significantly lower than OSRM (missing return leg)

### Pitfall 6: Waypoint Limit
**What goes wrong:** API error when route has >25 stops
**Why it happens:** When using place IDs, limit is 25 intermediates. When using lat/lng, limit is 98.
**How to avoid:** Since we use lat/lng, the 98-waypoint limit is unlikely to be hit (Kerala routes typically have 5-20 stops). But add a guard.
**Warning signs:** HTTP 400 errors on large routes

### Pitfall 7: API Key Not Configured
**What goes wrong:** 401/403 errors from Google, or the validation button confuses the user
**Why it happens:** User hasn't entered a Google Maps API key in Settings
**How to avoid:** Check `has_api_key` before enabling the validate button; show "API key required" message with Settings link
**Warning signs:** Google API errors about authentication

## Code Examples

### Google Routes API Response Parsing
```python
# Source: https://developers.google.com/maps/documentation/routes/reference/rest/v2/TopLevel/computeRoutes
def parse_routes_response(data: dict) -> tuple[float, float, list[int]]:
    """Parse Google Routes API response into comparison values.

    Returns:
        (distance_km, duration_minutes, optimized_waypoint_order)
    """
    route = data["routes"][0]

    # distanceMeters is an integer in meters
    distance_km = route["distanceMeters"] / 1000.0

    # duration is a string like "1234s" (seconds)
    duration_seconds = int(route["duration"].rstrip("s"))
    duration_minutes = duration_seconds / 60.0

    # Optimized waypoint order (0-based indices)
    waypoint_order = route.get("optimizedIntermediateWaypointIndex", [])

    return distance_km, duration_minutes, waypoint_order
```

### DB Schema for Validation Results
```python
# RouteValidationDB model (add to core/database/models.py)
class RouteValidationDB(Base):
    """Stores Google Routes validation results for route comparison."""
    __tablename__ = "route_validations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("routes.id", ondelete="CASCADE"), nullable=False
    )
    # OSRM/VROOM values (snapshot at validation time)
    osrm_distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    osrm_duration_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    # Google Routes values
    google_distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    google_duration_minutes: Mapped[float] = mapped_column(Float, nullable=False)
    # Computed deltas
    distance_delta_pct: Mapped[float] = mapped_column(Float, nullable=False)
    duration_delta_pct: Mapped[float] = mapped_column(Float, nullable=False)
    # Google's re-optimized stop order (JSON array of 0-based indices)
    google_waypoint_order: Mapped[str | None] = mapped_column(Text)
    # Cost tracking
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.01)
    # Timestamps
    validated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

### Confidence Thresholds (Claude's Discretion)
```python
# Recommended thresholds for distance delta
# Based on practical routing accuracy expectations:
# - <10% delta: OSRM routing is closely aligned with Google
# - 10-25% delta: Noticeable difference, worth investigating
# - >25% delta: Significant divergence, OSRM data may need updating
CONFIDENCE_THRESHOLDS = {
    "green": 10.0,   # delta <= 10% -> good agreement
    "amber": 25.0,   # delta <= 25% -> moderate divergence
    # "red":          # delta > 25% -> significant divergence
}
```

### Cumulative Cost Tracking (via SettingsDB)
```python
# Use existing SettingsDB key-value store for cumulative stats
# Keys: "validation_count", "validation_total_cost_usd"
# Updated atomically on each validation
async def increment_validation_stats(session, cost_usd: float):
    count = await get_setting(session, "validation_count")
    total = await get_setting(session, "validation_total_cost_usd")
    await set_setting(session, "validation_count", str(int(count or "0") + 1))
    await set_setting(session, "validation_total_cost_usd", str(float(total or "0") + cost_usd))
```

## Discretion Recommendations

### API Choice: Google Routes API (not Directions API)
**Recommendation:** Use Google Routes API (`computeRoutes`)
**Rationale:** Routes API is the modern replacement for Directions API. It uses cleaner JSON (not XML), supports explicit `optimizeWaypointOrder` flag, and uses header-based auth (`X-Goog-Api-Key`) instead of query params. The field mask feature avoids paying for unnecessary response data.

### Confidence Thresholds
**Recommendation:** Green <= 10%, Amber <= 25%, Red > 25%
**Rationale:** OSRM uses OpenStreetMap data which is generally accurate for main roads in Kerala but can miss recent changes. A 10% tolerance accounts for minor road network differences. Beyond 25% suggests either the OSM data is stale or the VROOM optimization found a fundamentally different route structure.

### Badge Style
**Recommendation:** Percentage badge with colored background (e.g., `tw:badge-success` showing "+8.2%")
**Rationale:** This follows the existing StatusBadge pattern in the codebase and provides both the color signal AND the numeric value in a compact format. Matches the `tw:badge tw:badge-sm` pattern already used throughout the dashboard.

### Cost Warning UX
**Recommendation:** DaisyUI modal (not popover)
**Rationale:** The clear-cache confirmation in Settings.tsx already uses a DaisyUI modal for destructive/cost-bearing actions. This is a proven pattern in the codebase. A popover would be too easy to accidentally dismiss and wouldn't feel "weighty" enough for a cost-bearing action.

### Storage Granularity
**Recommendation:** Route-level only (not per-stop)
**Rationale:** The primary comparison is total distance and total duration. Per-stop comparison is complex because Google re-optimizes stop order (the stops won't even be in the same sequence). Store the Google-optimized waypoint order as a JSON array for reference, but the main comparison is route totals.

### Error Handling
**Recommendation:** Show user-friendly error messages, never expose raw API errors
- **No API key:** "Google API key required" with link to Settings page
- **Invalid API key:** "Google API key is invalid. Check Settings."
- **Quota exceeded:** "Google API quota exceeded. Try again later."
- **Timeout:** "Google API request timed out. Try again."
- **Too many waypoints:** "Route has too many stops for Google validation (max 98)."

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Google Directions API | Google Routes API | 2022 (GA) | Cleaner JSON, field masks, header auth, explicit waypoint optimization |
| $200/month free credit | 10,000 free events/month per SKU | March 2025 | Pricing restructured, but validation volume (~10-50/month) is well within free tier |
| Query-param API key | Header-based X-Goog-Api-Key | Routes API launch | More secure, no key in URL/logs |

**Deprecated/outdated:**
- Google Directions API: Still works but Routes API is the recommended replacement
- `$200/month credit` model: Replaced with per-SKU free tiers as of March 2025

## Pricing Analysis

| Item | Value |
|------|-------|
| API | Google Routes API `computeRoutes` |
| SKU | Compute Routes Pro (due to `optimizeWaypointOrder`) |
| Rate | $0.01 per request ($10 per 1,000) |
| INR equivalent | ~INR 0.93 per request (at 1 USD = 92.5 INR) |
| Free tier | 10,000 events/month at Essentials tier |
| Free tier for Pro | Not explicitly documented; assume billed from first request |
| Expected usage | ~10-50 validations/month (manual, one-at-a-time) |
| Expected monthly cost | $0.10 - $0.50 (INR 9 - 46) |

**Note:** The CONTEXT.md references "INR 0.42 per validation" which appears to be an estimate. The actual Pro tier cost is closer to INR 0.93 per validation. Use the accurate figure.

## Open Questions

1. **Exact Pro tier free threshold**
   - What we know: Essentials has 10,000 free events/month. Pro tier pricing documentation does not explicitly state a free threshold.
   - What's unclear: Whether Pro tier has its own free threshold or if the 10,000 free events applies across all tiers.
   - Recommendation: Assume $0.01 per request with no free tier for Pro. At expected volumes (~50/month), the cost is trivial ($0.50/month). Display the cost honestly.

2. **Routes API "Routes Preferred" vs standard Routes API**
   - What we know: Some Google docs reference "Routes Preferred" as a separate product. The standard `computeRoutes` endpoint supports `optimizeWaypointOrder` directly.
   - What's unclear: Whether waypoint optimization requires "Routes Preferred" activation in Google Cloud Console.
   - Recommendation: Use the standard `routes.googleapis.com/directions/v2:computeRoutes` endpoint. If it returns errors about waypoint optimization, the API may need explicit enablement in Google Cloud Console. Handle this gracefully with an error message.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.x + FastAPI TestClient |
| Config file | `pytest.ini` |
| Quick run command | `pytest tests/apps/kerala_delivery/api/test_settings.py -x` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| VAL-01 | Validate route endpoint calls Google API | unit | `pytest tests/apps/kerala_delivery/api/test_validation.py::test_validate_route -x` | Wave 0 |
| VAL-01 | Validate route endpoint returns comparison data | unit | `pytest tests/apps/kerala_delivery/api/test_validation.py::test_validate_response_format -x` | Wave 0 |
| VAL-02 | Confidence badge computation from delta | unit | `pytest tests/apps/kerala_delivery/api/test_validation.py::test_confidence_levels -x` | Wave 0 |
| VAL-03 | Cost estimate returned in pre-validation info | unit | `pytest tests/apps/kerala_delivery/api/test_validation.py::test_cost_estimate -x` | Wave 0 |
| VAL-04 | No automatic validation triggered | manual-only | Verify no scheduled/automatic API calls in code | N/A |
| VAL-01 | Cached validation returned for re-validated routes | unit | `pytest tests/apps/kerala_delivery/api/test_validation.py::test_cached_validation -x` | Wave 0 |
| VAL-01 | Error handling for missing API key | unit | `pytest tests/apps/kerala_delivery/api/test_validation.py::test_no_api_key -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/apps/kerala_delivery/api/test_validation.py -x`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/apps/kerala_delivery/api/test_validation.py` -- covers VAL-01, VAL-02, VAL-03
- [ ] Mock Google Routes API responses (follow pattern from test_settings.py)

## Sources

### Primary (HIGH confidence)
- [Google Routes API computeRoutes reference](https://developers.google.com/maps/documentation/routes/reference/rest/v2/TopLevel/computeRoutes) -- endpoint URL, request/response schema, field mask requirement
- [Google Routes API waypoint optimization](https://developers.google.com/maps/documentation/routes/opt-way) -- optimizeWaypointOrder usage, limitations, billing impact (Pro tier)
- [Google Maps Platform pricing](https://developers.google.com/maps/billing-and-pricing/pricing) -- Essentials $5/1000, Pro $10/1000, free tier thresholds
- [Google Routes API usage and billing](https://developers.google.com/maps/documentation/routes/usage-and-billing) -- SKU classification (Essentials/Pro/Enterprise)

### Secondary (MEDIUM confidence)
- [Google Routes API specify locations](https://developers.google.com/maps/documentation/routes/specify_location) -- lat/lng waypoint format (`location.latLng.latitude/longitude`)

### Tertiary (LOW confidence)
- INR/USD exchange rate (~92.5 INR per USD) -- rate varies; cost display should be approximate

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in the project; no new dependencies
- Architecture: HIGH -- follows established patterns (httpx for Google APIs, repository pattern, DaisyUI modals/badges, Alembic migrations)
- Pitfalls: HIGH -- verified against official Google API documentation; duration format and field mask requirements confirmed
- Pricing: MEDIUM -- Pro tier rate confirmed; free tier applicability to Pro SKU unclear

**Research date:** 2026-03-14
**Valid until:** 2026-04-14 (30 days -- Google pricing is stable)
