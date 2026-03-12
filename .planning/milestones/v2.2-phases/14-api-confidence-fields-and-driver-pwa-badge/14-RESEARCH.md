# Phase 14: API Confidence Fields and Driver PWA Badge - Research

**Researched:** 2026-03-11
**Domain:** API response extension + Driver PWA (vanilla JS/HTML) UI indicators
**Confidence:** HIGH

## Summary

Phase 14 is a straightforward data-plumbing and UI-rendering phase. The geocode_confidence and geocode_method data already exists on `OrderDB` (persisted in Phase 13). The work is: (1) propagate these fields through the `route_db_to_pydantic()` conversion and the API endpoint's stop serialization dict, (2) add `location_approximate` as a computed boolean (confidence < 0.5), (3) render a DaisyUI badge on the hero card, (4) render an orange superscript dot on compact cards, and (5) color map pins orange for approximate stops.

The Driver PWA is a single `index.html` file with vanilla JS -- no build step, no framework. Tailwind v4 + DaisyUI are compiled via `scripts/build-pwa-css.sh` using `tailwindcss-extra` binary. Since `tw:badge` and `tw:badge-warning` classes are not currently used in the HTML, the compiled `tailwind.css` file does NOT include badge styles. The CSS must be rebuilt after adding badge markup.

**Primary recommendation:** Three-layer implementation: (1) API field additions in `main.py` + `route.py`, (2) Driver PWA badge/dot rendering in `index.html`, (3) CSS rebuild and map pin coloring. No database schema changes needed.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Badge placement: below the address text, before the meta line (qty/weight/distance)
- Badge content: "Warning Approx. location" -- icon + text, using DaisyUI `badge-warning`
- Badge persists across all delivery states (pending, delivered, failed) -- location accuracy is a fact about the data, not the delivery status
- Navigate button stays unchanged (no visual modification for approximate stops)
- Same badge for all approximate stops (centroid 0.3 and depot 0.1 get identical badge -- no tiered severity)
- Small superscript dot (6-8px solid orange circle) positioned at the top-right corner of the stop number circle, like a notification badge
- Dot only -- no text label on compact cards (hero card has the full text badge; drivers learn the association)
- Dot persists alongside delivered/failed status indicators -- both are true facts about the stop
- Badge text is exactly "Warning Approx. location" -- no additional hint text, no tooltip, no tap interaction
- Approximate stops show as orange Leaflet markers instead of the default color on the map view
- `GET /api/routes/{vehicle_id}` response includes three new fields per stop: `geocode_confidence` (float), `location_approximate` (boolean), `geocode_method` (string)
- `location_approximate` = true when `geocode_confidence < 0.5` (strictly less than)
- NULL confidence (pre-Phase 13 orders) -> `geocode_confidence: null`, `geocode_method: null`, `location_approximate: false` (no badge shown)
- `geocode_method` exposed for debugging and future dashboard use, but NOT shown in driver UI

### Claude's Discretion
- Exact CSS for the orange dot (positioning, z-index, shadow)
- DaisyUI badge size class for the hero card badge
- Leaflet marker icon implementation for orange approximate pins
- Any necessary refactoring of the stop serialization in the route endpoint

### Deferred Ideas (OUT OF SCOPE)
- Batch-level "all approximate" banner in Driver PWA when API key is invalid (tracked as AINT-03 in REQUIREMENTS.md)
- Map view clustering of approximate stops
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| APUI-01 | API route response includes geocode_confidence field for each delivery stop | Data exists on OrderDB (geocode_confidence, Float, nullable). Must propagate through `stop_db.order.geocode_confidence` in `route_db_to_pydantic()` and add to API serialization dict at main.py:1559-1574. |
| APUI-02 | API route response includes location_approximate flag (true when confidence < 0.5) | Computed field: `location_approximate = (geocode_confidence is not None and geocode_confidence < 0.5)`. NULL -> false per user decision. |
| APUI-03 | Driver PWA hero card shows "Approx. location" warning badge for approximate stops | `renderHeroCard()` at index.html:1374. Insert badge div after `.hero-address-raw`, before `.hero-meta`. Uses DaisyUI `tw:badge tw:badge-warning`. Requires CSS rebuild. |
| APUI-04 | Driver PWA compact cards show orange dot indicator for approximate stops | `renderCompactCard()` at index.html:1409. Add 6-8px orange circle to `.stop-number` div. CSS-only positioning with `position: absolute` on the dot relative to `.stop-number` container. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | (existing) | API endpoint modification | Already in use; stop serialization dict is where fields are added |
| Pydantic v2 | (existing) | RouteStop model extension | Optional fields with None defaults for backward compat |
| Leaflet.js | 1.9.4 | Map pin orange coloring | Already loaded via CDN; L.divIcon inline styles |
| Tailwind v4 + DaisyUI | (existing) | badge-warning component | Already configured with `tw:` prefix; requires CSS rebuild |
| tailwindcss-extra | (existing) | CSS compilation | `scripts/build-pwa-css.sh` compiles PWA CSS |

### Supporting
No additional libraries needed. Everything required is already in the stack.

## Architecture Patterns

### Data Flow: OrderDB -> API Response -> Driver PWA

```
OrderDB.geocode_confidence  (Float, nullable)
OrderDB.geocode_method      (String(20), nullable)
        |
        v
route_db_to_pydantic()  -- reads stop_db.order.geocode_confidence/geocode_method
        |                  (order is eagerly loaded via selectinload)
        v
RouteStop Pydantic model -- needs new optional fields
        |
        v
GET /api/routes/{vehicle_id} serialization dict -- adds 3 fields per stop
        |
        v
Driver PWA JavaScript -- reads stop.geocode_confidence, stop.location_approximate
        |
        v
renderHeroCard() / renderCompactCard() / showRouteOnMap() -- conditional UI elements
```

### Pattern 1: API Field Addition
**What:** Add computed and pass-through fields to the stop serialization dict
**When to use:** When data exists in DB but isn't exposed in API response
**Example:**
```python
# In main.py GET /api/routes/{vehicle_id}, inside the stops list comprehension:
{
    # ... existing fields ...
    "geocode_confidence": stop.geocode_confidence,
    "geocode_method": stop.geocode_method,
    "location_approximate": (
        stop.geocode_confidence is not None
        and stop.geocode_confidence < 0.5
    ),
}
```

### Pattern 2: Conditional Badge Rendering (Vanilla JS)
**What:** Conditionally render HTML elements based on API response data
**When to use:** When a UI indicator depends on a boolean/nullable field
**Example:**
```javascript
// In renderHeroCard():
const approxBadge = stop.location_approximate
    ? '<div class="tw:badge tw:badge-warning approx-badge">&#9888; Approx. location</div>'
    : '';
```

### Pattern 3: Superscript Notification Dot (CSS)
**What:** Small colored circle overlapping a container element
**When to use:** Mobile notification badge pattern
**Example:**
```css
.approx-dot {
    position: absolute;
    top: -2px;
    right: -2px;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--color-accent);
    border: 1.5px solid var(--color-surface);
}
```

### Pattern 4: Conditional Leaflet Marker Color
**What:** Change L.divIcon background color based on stop data
**When to use:** When map pins should reflect data attributes
**Example:**
```javascript
// In showRouteOnMap():
const isApprox = stop.location_approximate;
const color = stop.status === 'delivered' ? '#00C853'
    : stop.status === 'failed' ? '#FF3B30'
    : isApprox ? '#FF9410' : '#FF9410';  // pending always orange in current code
// For approximate stops, override the text color to differentiate
```

### Anti-Patterns to Avoid
- **Adding fields to RouteStopDB schema:** The geocode data lives on OrderDB, not RouteStopDB. Do NOT add columns to route_stops table. Access via `stop_db.order.geocode_confidence`.
- **Building custom CSS for badge-warning:** DaisyUI provides this. Use the `tw:badge tw:badge-warning` classes.
- **Using tooltip/popover for badge:** User locked decision says no tooltip, no tap interaction.
- **Tiered badge severity:** User locked decision says same badge for all approximate stops regardless of confidence value.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Warning badge styling | Custom CSS badge | DaisyUI `tw:badge tw:badge-warning` | Consistent with design system, responsive, accessible |
| Notification dot pattern | Complex CSS positioning from scratch | Standard `position: absolute` on `position: relative` parent | Well-established mobile pattern |
| Null-safe field access in JS | Complex null checking chains | Optional chaining (`stop.location_approximate`) with falsy default | API guarantees boolean (never null for location_approximate) |

**Key insight:** This phase has no complex algorithms or library integrations. The difficulty is ensuring correct data propagation across 4 layers (DB -> Pydantic -> API -> JS) and rebuilding CSS after adding DaisyUI classes.

## Common Pitfalls

### Pitfall 1: Missing CSS Rebuild After Adding DaisyUI Badge Classes
**What goes wrong:** Adding `tw:badge tw:badge-warning` to index.html but not rebuilding the CSS. The compiled `tailwind.css` currently has zero badge styles because no badge classes are used in the scanned HTML file.
**Why it happens:** Tailwind v4 tree-shakes unused classes. The CSS build scans `index.html` for class usage. If you add new classes but don't rebuild, they have no styles.
**How to avoid:** Run `bash scripts/build-pwa-css.sh` after modifying index.html. The `tailwindcss-extra` binary must exist at `tools/tailwindcss-extra`.
**Warning signs:** Badge text appears but without background color, padding, or border-radius.

### Pitfall 2: Eager Loading Chain Not Reaching OrderDB
**What goes wrong:** `stop_db.order.geocode_confidence` raises `MissingGreenlet` in async context because the order relationship wasn't eagerly loaded.
**Why it happens:** SQLAlchemy async mode prohibits lazy loading. If `selectinload(RouteStopDB.order)` is missing from the query, accessing `.order` triggers a sync lazy load that fails.
**How to avoid:** The existing `get_route_for_vehicle()` already includes `.options(selectinload(RouteDB.stops).selectinload(RouteStopDB.order))`. Verify this chain is intact and covers all code paths. No changes needed to the query itself.
**Warning signs:** `MissingGreenlet` exception when accessing `stop_db.order`.

### Pitfall 3: Null Propagation for Pre-Phase 13 Orders
**What goes wrong:** Pre-Phase 13 orders have `geocode_confidence = NULL` and `geocode_method = NULL` in the database. If the code does `confidence < 0.5` without checking for None first, it will raise a TypeError in Python or produce wrong results in JS.
**Why it happens:** Old data doesn't have these fields populated.
**How to avoid:**
- Python: `location_approximate = (gc is not None and gc < 0.5)` where `gc = stop_db.order.geocode_confidence`
- JavaScript: `stop.location_approximate` is a boolean from API (never null), so JS side is safe. But `stop.geocode_confidence` can be null -- don't compare directly.
**Warning signs:** Badges appearing on all old orders, or Python errors during serialization.

### Pitfall 4: stop_db.order Could Be None
**What goes wrong:** `route_db_to_pydantic()` already handles `stop_db.order` being None (line 844: uses `str(stop_db.order_id)` as fallback). The geocode field access must also guard against this.
**Why it happens:** If an order was deleted or FK integrity issue.
**How to avoid:** Use `stop_db.order.geocode_confidence if stop_db.order else None` pattern, consistent with existing code.
**Warning signs:** AttributeError when serializing a stop whose order FK is broken.

### Pitfall 5: Map Pin Color Logic Conflict
**What goes wrong:** The current map pin color logic uses status-based coloring: delivered=green, failed=red, pending=orange (#FF9410). Adding "approximate=orange" creates a visual conflict because pending stops are ALREADY orange.
**Why it happens:** The accent color (#FF9410) is used for both the brand/pending state and the "approximate" indicator.
**How to avoid:** For approximate stops, the user decision says "orange Leaflet markers" -- but since pending is already orange, the differentiation is only relevant for delivered/failed stops that happen to be approximate. For pending stops, approximate and non-approximate look the same on the map (both orange). Consider adding a dashed border or different icon to distinguish approximate pending pins, at Claude's discretion.
**Warning signs:** All pending stops looking identical on the map regardless of approximate status.

### Pitfall 6: DaisyUI Badge Prefix Must Be tw:
**What goes wrong:** Using `badge badge-warning` instead of `tw:badge tw:badge-warning`. The project uses `tw:` prefix for ALL Tailwind/DaisyUI classes.
**Why it happens:** DaisyUI docs show unprefixed classes. This project configured `prefix(tw)` in pwa-input.css.
**How to avoid:** Always use `tw:` prefix: `tw:badge`, `tw:badge-warning`, `tw:badge-sm`, etc.
**Warning signs:** CSS classes not applying, badge rendering as plain text.

## Code Examples

### 1. RouteStop Pydantic Model Extension
```python
# core/models/route.py - Add to RouteStop class
class RouteStop(BaseModel):
    # ... existing fields ...
    status: str = "pending"
    # Phase 14: Geocode confidence fields for "Approx. location" badge
    geocode_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Geocode confidence score. None for pre-Phase 13 orders.",
    )
    geocode_method: str | None = Field(
        default=None,
        description="Geocoding method used: 'direct', 'area_retry', 'centroid', 'depot'. None for pre-Phase 13 orders.",
    )
```

### 2. route_db_to_pydantic() Modification
```python
# core/database/repository.py - In route_db_to_pydantic(), modify the RouteStop creation
stops.append(
    RouteStop(
        # ... existing fields ...
        status=stop_db.status or "pending",
        # Phase 14: Propagate geocode fields from linked OrderDB
        geocode_confidence=(
            stop_db.order.geocode_confidence if stop_db.order else None
        ),
        geocode_method=(
            stop_db.order.geocode_method if stop_db.order else None
        ),
    )
)
```

### 3. API Endpoint Stop Serialization
```python
# apps/kerala_delivery/api/main.py - In GET /api/routes/{vehicle_id}
"stops": [
    {
        # ... existing fields ...
        "status": stop.status,
        # Phase 14: Geocode confidence for "Approx. location" badge
        "geocode_confidence": stop.geocode_confidence,
        "geocode_method": stop.geocode_method,
        "location_approximate": (
            stop.geocode_confidence is not None
            and stop.geocode_confidence < 0.5
        ),
    }
    for stop in route.stops
],
```

### 4. Hero Card Badge (renderHeroCard)
```javascript
// Conditional badge after address_raw, before hero-meta
const approxBadge = stop.location_approximate
    ? '<div class="approx-badge tw:badge tw:badge-warning tw:badge-sm">&#9888; Approx. location</div>'
    : '';

// In the template literal, after address_raw line, before hero-meta:
// ${stop.address_raw ? `<div class="hero-address-raw">...</div>` : ''}
// ${approxBadge}
// <div class="hero-meta">...
```

### 5. Compact Card Orange Dot (renderCompactCard)
```javascript
// Conditional dot inside stop-number div
const approxDot = stop.location_approximate
    ? '<div class="approx-dot"></div>'
    : '';

// In the template:
// <div class="stop-number">
//     <div class="stop-number-inner">${stop.sequence}</div>
//     ${approxDot}
// </div>
```

### 6. CSS for Orange Dot
```css
/* Approximate location dot — notification badge pattern */
.stop-number {
    position: relative;  /* Already has display:flex; add position:relative */
}
.approx-dot {
    position: absolute;
    top: 2px;
    right: 2px;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--color-accent);  /* #FF9410 — orange */
    border: 1.5px solid var(--color-surface);
    z-index: 1;
}
```

### 7. Map Pin Conditional Coloring
```javascript
// In showRouteOnMap() — modify the color logic
const isApprox = stop.location_approximate;
const color = stop.status === 'delivered' ? '#00C853'
    : stop.status === 'failed' ? '#FF3B30'
    : '#FF9410';  // pending is already orange

// For approximate delivered/failed stops, add orange border
const border = isApprox && stop.status !== 'pending'
    ? '3px solid #FF9410'
    : '2px solid rgba(255,255,255,0.9)';

// Or: override entire color for approximate stops regardless of status
// const color = isApprox ? '#FF9410'
//     : stop.status === 'delivered' ? '#00C853'
//     : stop.status === 'failed' ? '#FF3B30' : '#FF9410';
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No geocode confidence in API | Phase 13 stored it in OrderDB | Phase 13 (2026-03-12) | Data is there, just not exposed |
| No visual indicator for approximate stops | Phase 14 adds badge/dot/pin color | This phase | Drivers get situational awareness |

**Deprecated/outdated:** None. This phase builds on Phase 13's data foundation.

## Implementation Strategy

### Recommended Task Decomposition

**Layer 1: API (Python)**
- Add `geocode_confidence` and `geocode_method` optional fields to RouteStop Pydantic model
- Modify `route_db_to_pydantic()` to pass geocode fields from `stop_db.order`
- Add three fields to the stop serialization dict in `GET /api/routes/{vehicle_id}`
- location_approximate is computed in the serialization, not stored

**Layer 2: Driver PWA (HTML/CSS/JS)**
- Add badge HTML to `renderHeroCard()` function
- Add dot HTML to `renderCompactCard()` function
- Add `.approx-dot` CSS and `.approx-badge` margin styles
- Modify `showRouteOnMap()` for conditional orange pin coloring
- Rebuild Tailwind CSS via `scripts/build-pwa-css.sh`

### CSS Rebuild Requirement

**CRITICAL:** The `tailwind.css` file must be rebuilt after adding `tw:badge` and `tw:badge-warning` classes to `index.html`. Without rebuild, badge styles are missing.

```bash
bash scripts/build-pwa-css.sh
```

Prerequisite: `tools/tailwindcss-extra` binary must exist. If missing:
```bash
curl -sLO https://github.com/dobicinaitis/tailwind-cli-extra/releases/latest/download/tailwindcss-extra-linux-x64
mv tailwindcss-extra-linux-x64 tools/tailwindcss-extra && chmod +x tools/tailwindcss-extra
```

### Docker Rebuild Requirement

API changes require Docker rebuild:
```bash
docker compose build api && docker compose up -d --no-deps api
```

## Files Modified

| File | Change | Type |
|------|--------|------|
| `core/models/route.py` | Add `geocode_confidence`, `geocode_method` to RouteStop | Model extension |
| `core/database/repository.py` | Propagate geocode fields in `route_db_to_pydantic()` | Data plumbing |
| `apps/kerala_delivery/api/main.py` | Add 3 fields to stop serialization in GET route endpoint | API extension |
| `apps/kerala_delivery/driver_app/index.html` | Badge in hero card, dot in compact card, CSS, map pins | UI rendering |
| `apps/kerala_delivery/driver_app/tailwind.css` | Rebuilt to include DaisyUI badge-warning styles | CSS rebuild (generated) |

No new files. No database migrations. No new dependencies.

## Open Questions

1. **Map pin color for approximate pending stops**
   - What we know: Pending stops are already orange (#FF9410). Approximate stops should be orange per user decision.
   - What's unclear: How to visually distinguish an approximate pending stop from a normal pending stop on the map.
   - Recommendation: For pending stops, add a pulsing animation or dashed border on approximate pins. For delivered/failed stops, override the green/red with orange when approximate. This falls under Claude's discretion per CONTEXT.md.

2. **DaisyUI badge-sm vs default size**
   - What we know: User says DaisyUI badge-warning, size is Claude's discretion.
   - What's unclear: Whether `tw:badge-sm` (smaller) or default badge size looks better on mobile hero card.
   - Recommendation: Use `tw:badge-sm` to avoid dominating the hero card layout. The 22px address text is large; the badge should be subordinate.

## Sources

### Primary (HIGH confidence)
- Codebase: `core/database/models.py` -- OrderDB has geocode_confidence (Float, nullable, line 201) and geocode_method (String(20), nullable, line 202)
- Codebase: `core/database/repository.py` -- `route_db_to_pydantic()` (lines 833-868), `get_route_for_vehicle()` with selectinload chain (lines 297-309)
- Codebase: `apps/kerala_delivery/api/main.py` -- GET route endpoint (lines 1520-1576), stop serialization dict (lines 1559-1574)
- Codebase: `apps/kerala_delivery/driver_app/index.html` -- renderHeroCard (line 1374), renderCompactCard (line 1409), showRouteOnMap (line 1458), .stop-number CSS (line 433)
- Codebase: `scripts/build-pwa-css.sh` -- CSS build script with tailwindcss-extra
- Codebase: `apps/kerala_delivery/driver_app/pwa-input.css` -- `@import "tailwindcss" prefix(tw); @plugin "daisyui";`
- Phase 13 verification: All geocode fields confirmed stored on OrderDB and propagated during upload

### Secondary (MEDIUM confidence)
- Tailwind v4 tree-shaking behavior: unused classes are excluded from compiled CSS (standard Tailwind behavior, verified by absence of badge styles in current tailwind.css)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - all tools already in codebase, no new dependencies
- Architecture: HIGH - data flow fully traced from DB to API to JS rendering
- Pitfalls: HIGH - CSS rebuild and null handling are the only real risks, both straightforward
- Code examples: HIGH - based on direct reading of actual source code

**Research date:** 2026-03-11
**Valid until:** 2026-04-11 (stable -- no external dependencies changing)
