# Phase 5: Geocoding Enhancements - Research

**Researched:** 2026-03-01
**Domain:** Geocoding cost transparency + spatial duplicate detection
**Confidence:** HIGH

## Summary

Phase 5 adds two non-blocking enhancements to the existing upload workflow: (1) cost reporting that shows cache hits vs API calls with estimated cost (GEO-04), and (2) duplicate location detection that warns when different addresses resolve to suspiciously close GPS coordinates (GEO-03). Both features enhance the existing `POST /api/upload-orders` response and `UploadRoutes.tsx` -- no new endpoints or pages needed.

The codebase is well-prepared for this phase. `CachedGeocoder.stats` already tracks `{"hits": 0, "misses": 0, "errors": 0}` per instance, providing the exact data needed for GEO-04. The `GeocodingResult.confidence` field (mapped from Google's `location_type`) provides the confidence tiers needed for GEO-03's weighted thresholds. The `OptimizationSummary` Pydantic model supports backward-compatible field additions with defaults. All work is in-memory computation on already-geocoded data -- no new database tables, migrations, or external API calls.

**Primary recommendation:** Implement cost stats as a thin passthrough from `CachedGeocoder.stats` into `OptimizationSummary`, and duplicate detection as a post-geocoding Python function using the Haversine formula with confidence-weighted thresholds and Union-Find clustering.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Cost Reporting (GEO-04)**:
  - Summary totals at top of upload response: cache hits (free) vs API calls, with estimated cost
  - Per-address source tagging: each geocoded order tagged as "cached" or "API call" in the response
  - Cost estimate includes free-tier awareness: "12 API calls (~$0.06) -- within $200/month free tier"
  - Cost calculation uses fixed $0.005/request (Google standard rate)
  - Display in upload response only -- no persistence to Run History (keeps Phase 5 focused)

- **Duplicate Warning Display (GEO-03)**:
  - Grouped clusters, not pair-by-pair: "Orders 101, 205, 312 resolve within 15m of each other"
  - Non-blocking: optimization proceeds normally, warnings shown alongside results
  - Each cluster shows: order IDs, address text for each order, distance between orders
  - Dedicated "Duplicate Location Warnings" section in upload results -- visually distinct from validation warnings/failures
  - Only compare within current upload (not against previous runs)

- **Confidence Thresholds**:
  - Confidence-weighted distance thresholds: tighter for ROOFTOP, wider for GEOMETRIC_CENTER
  - Thresholds configurable in config.py (DUPLICATE_THRESHOLDS dict or similar) for easy tuning after real-world testing
  - Actual threshold meter values and mixed-confidence approach at Claude's discretion

- **Same-Address Handling**:
  - Exclude orders with exact same normalized address from duplicate detection -- multiple orders to same household is legitimate for LPG delivery (multi-cylinder)
  - Only flag different addresses that resolve to nearby GPS coordinates
  - Skip failed (non-geocoded) orders -- no GPS coords to compare

### Claude's Discretion
- Per-address source tag display format (badge vs separate section vs inline annotation)
- Exact confidence threshold values per location_type tier
- Mixed-confidence pair handling (which threshold to use when two orders have different confidence levels)
- Whether to show confidence/accuracy context in duplicate warnings for non-technical staff
- Loading skeleton design for any new UI sections

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| GEO-03 | User sees a warning when two or more orders in an upload resolve to GPS coordinates within 15m of each other | Haversine distance formula (stdlib math), Union-Find clustering algorithm, confidence-weighted thresholds from Google's `location_type`, same-address exclusion via `normalize_address()` |
| GEO-04 | Upload results show how many addresses were cache hits (free) vs Google API calls, with estimated cost | `CachedGeocoder.stats` dict already tracks hits/misses/errors; new fields on `OptimizationSummary` Pydantic model; per-order source tag from geocoding flow; DaisyUI `stats` component for display |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python `math` (stdlib) | 3.11+ | Haversine distance calculation | Zero dependencies; 6-line function; accurate to <0.5% for distances under 1km |
| Pydantic | 2.12.5 | Response model extensions | Already used for `OptimizationSummary`; new fields with defaults for backward compat |
| FastAPI | 0.129.1 | Endpoint (unchanged) | Existing upload endpoint; only response model grows |
| DaisyUI | 5.x | Warning/stats UI components | Already used in `UploadRoutes.tsx` with `tw-` prefix; `alert`, `stat`, `collapse` components |
| Tailwind CSS | 4.x | Utility styling | Already configured with `prefix(tw)` in `index.css` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `core.geocoding.normalize` | existing | `normalize_address()` for same-address detection | Compare normalized addresses to exclude legitimate multi-cylinder orders |
| `core.geocoding.cache` | existing | `CachedGeocoder.stats` dict | Source of truth for hit/miss counts -- already tracked per instance |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Haversine (stdlib math) | PostGIS `ST_DistanceSphere` | PostGIS would require a SQL query on in-memory data that isn't persisted yet; Haversine in Python is simpler for 40-50 orders and avoids DB roundtrip |
| Haversine (stdlib math) | `haversine` PyPI package | Adds a dependency for 6 lines of stdlib code; not justified at this scale |
| Union-Find clustering | scipy `fcluster` | scipy is not in requirements.txt; Union-Find is ~15 lines and handles transitive closure naturally |
| In-memory pairwise scan | PostGIS spatial index | Only 40-50 orders per upload; O(n^2) pairwise is ~1225 comparisons max -- negligible |

**Installation:**
```bash
# No new dependencies required -- everything uses stdlib + existing packages
```

## Architecture Patterns

### Recommended Project Structure
```
core/geocoding/
├── interfaces.py          # GeocodingResult (unchanged)
├── cache.py               # CachedGeocoder.stats (unchanged -- already tracks hits/misses)
├── google_adapter.py      # GoogleGeocoder (unchanged)
├── normalize.py           # normalize_address() (unchanged -- used for same-address check)
└── duplicate_detector.py  # NEW: detect_duplicate_locations() function

apps/kerala_delivery/
├── config.py              # ADD: DUPLICATE_THRESHOLDS dict, GEOCODING_COST_PER_REQUEST
└── api/main.py            # MODIFY: OptimizationSummary fields, post-geocoding duplicate check
                           #   + geocoding cost stats passthrough

apps/kerala_delivery/dashboard/src/
├── types.ts               # MODIFY: UploadResponse type with new fields
└── pages/UploadRoutes.tsx  # MODIFY: CostSummary + DuplicateWarnings components
```

### Pattern 1: Post-Geocoding Duplicate Detection
**What:** After all orders are geocoded (step 2 in `upload_and_optimize`), run a duplicate detection pass before optimization (step 3). This keeps duplicate detection logically separate from the geocoding loop.
**When to use:** Always -- runs after geocoding, before optimization.
**Example:**
```python
# In upload_and_optimize(), after geocoding loop, before step 3:
from core.geocoding.duplicate_detector import detect_duplicate_locations
from apps.kerala_delivery.config import DUPLICATE_THRESHOLDS

duplicate_clusters = detect_duplicate_locations(
    geocoded_orders,
    thresholds=DUPLICATE_THRESHOLDS,
)
# duplicate_clusters is List[DuplicateCluster] -- passed into response
```

### Pattern 2: Confidence-Weighted Threshold Selection
**What:** For each pair of orders, select the distance threshold based on the LOWER confidence of the two orders. When one is ROOFTOP (tight threshold) and the other is GEOMETRIC_CENTER (wide threshold), use the wider threshold because the less-accurate result dominates the uncertainty.
**When to use:** Every pairwise comparison in duplicate detection.
**Rationale:** Using the tighter threshold would cause false positives (flagging orders that are actually apart but one has low-accuracy geocoding). Using the wider threshold minimizes false positives while still catching true duplicates.
**Example:**
```python
# Threshold selection for a pair of orders
def get_threshold_meters(conf_a: float, conf_b: float, thresholds: dict) -> float:
    """Use the wider (looser) threshold -- dominated by less-accurate result."""
    tier_a = confidence_to_tier(conf_a)
    tier_b = confidence_to_tier(conf_b)
    return max(thresholds[tier_a], thresholds[tier_b])
```

### Pattern 3: Haversine Distance (stdlib only)
**What:** Pure Python distance calculation using `math` module. Returns meters between two lat/lon pairs.
**When to use:** All pairwise distance checks in duplicate detection.
**Example:**
```python
import math

def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters between two GPS coordinates."""
    R = 6_371_000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))
```
**Source:** Standard Haversine formula. At Kerala latitudes (~11.6 deg N) and distances under 1km, error vs Vincenty is <0.3%. Verified against [movable-type.co.uk Haversine reference](https://www.movable-type.co.uk/scripts/latlong.html).

### Pattern 4: Union-Find for Transitive Clustering
**What:** When order A is near B, and B is near C, all three should be in one cluster. Union-Find (disjoint set) handles this naturally without needing to re-scan.
**When to use:** After pairwise distance checks, to group orders into clusters.
**Example:**
```python
class UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))
        self.rank = [0] * n

    def find(self, x: int) -> int:
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])  # path compression
        return self.parent[x]

    def union(self, x: int, y: int) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self.rank[rx] < self.rank[ry]:
            rx, ry = ry, rx
        self.parent[ry] = rx
        if self.rank[rx] == self.rank[ry]:
            self.rank[rx] += 1
```

### Pattern 5: Backward-Compatible Response Extension
**What:** Add new optional fields to `OptimizationSummary` with `Field(default_factory=list)` or `Field(default=0)` so existing clients ignore them gracefully.
**When to use:** All new fields on the response model.
**Example:**
```python
class OptimizationSummary(BaseModel):
    # ... existing fields ...

    # GEO-04: Cost transparency
    cache_hits: int = Field(default=0, description="Addresses resolved from cache (free)")
    api_calls: int = Field(default=0, description="Addresses that required Google API call")
    estimated_cost_usd: float = Field(default=0.0, description="Estimated API cost at $0.005/request")
    free_tier_note: str = Field(default="", description="Human-readable free tier context")

    # GEO-03: Duplicate location warnings
    duplicate_warnings: list[DuplicateCluster] = Field(
        default_factory=list,
        description="Groups of orders with suspiciously close GPS coordinates"
    )
```

### Anti-Patterns to Avoid
- **Running duplicate detection inside the geocoding loop:** Geocoding is sequential and potentially slow (API calls). Duplicate detection should run AFTER all orders are geocoded, as a separate O(n^2) pass on the in-memory list. Mixing them creates confusing control flow.
- **Using PostGIS for in-memory data:** The geocoded orders exist as Python objects at this point in the pipeline. Persisting them to the DB just to run a spatial query and then reading them back is wasteful and couples duplicate detection to the database.
- **Pair-by-pair warnings:** Showing "Order A is near Order B, Order A is near Order C, Order B is near Order C" creates 3 warnings instead of 1 cluster. Use Union-Find to group.
- **Blocking optimization on duplicate warnings:** CONTEXT.md explicitly says non-blocking. Warnings are informational only.
- **Persisting duplicate warnings to DB:** CONTEXT.md says display in upload response only, no persistence to Run History.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Haversine distance | N/A (stdlib is the right choice) | `math` module 6-line function | Simpler than adding a dependency; accurate at this scale |
| Transitive clustering | Graph traversal / BFS | Union-Find (15-line class) | Union-Find is the canonical solution; O(n * alpha(n)) nearly-linear |
| Pydantic response extension | Manual dict building | Pydantic `BaseModel` with `Field(default=...)` | Existing pattern; auto-serialization; validation |
| Address normalization | Custom normalization | `core.geocoding.normalize.normalize_address()` | Already the single source of truth (Phase 4 decision) |

**Key insight:** This phase is almost entirely "wiring" -- connecting existing data (geocoder stats, confidence scores, coordinates) to new response fields and UI components. The only new algorithm is the 30-line duplicate detector (Haversine + Union-Find).

## Common Pitfalls

### Pitfall 1: False Positives in Dense Urban Areas
**What goes wrong:** Vatakara has narrow streets where GEOMETRIC_CENTER results can be 50-100m from the actual building. A tight 15m threshold on these results would flag nearly every pair on the same street.
**Why it happens:** Google's `GEOMETRIC_CENTER` location_type means "center of the street/area" not the actual building. Two different addresses on the same short street may both resolve to the street's geometric center.
**How to avoid:** Use confidence-weighted thresholds. ROOFTOP results (building-level precision) get a tight threshold (~10m). GEOMETRIC_CENTER results get a much wider threshold (~50-100m) because the coordinates are inherently imprecise.
**Warning signs:** Many false positive clusters showing up in test uploads with real Vatakara addresses.

### Pitfall 2: Same Household Multi-Cylinder Orders
**What goes wrong:** A household orders 3 cylinders. These appear as 3 separate orders to the same address. Without exclusion, they are flagged as "duplicate locations."
**Why it happens:** Legitimate business case -- LPG dealers deliver multiple cylinders to the same address regularly.
**How to avoid:** Before distance checks, compare normalized addresses (using `normalize_address()`). If two orders have the exact same normalized address, exclude them from duplicate detection. Only flag orders with DIFFERENT addresses that resolve to NEARBY coordinates.
**Warning signs:** Every multi-cylinder upload generates duplicate warnings.

### Pitfall 3: Frontend Type Mismatch
**What goes wrong:** TypeScript `UploadResponse` type in `api.ts` doesn't include new fields. The data arrives from the API but the type system doesn't expose it, leading to undefined values or type errors.
**Why it happens:** Backend adds new Pydantic fields but frontend types aren't updated in sync.
**How to avoid:** Update `UploadResponse` in `apps/kerala_delivery/dashboard/src/lib/api.ts` with all new fields as optional (using `?` suffix) for backward compatibility with older backends.
**Warning signs:** TypeScript compilation errors or runtime `undefined` when accessing new fields.

### Pitfall 4: Cost Calculation During Cache-Only Mode
**What goes wrong:** When no API key is set, `CachedGeocoder` is not instantiated -- the code falls back to direct `repo.get_cached_geocode()` calls. The `CachedGeocoder.stats` dict doesn't exist, so cost reporting would crash.
**Why it happens:** The upload endpoint has two code paths: one with `CachedGeocoder` (when API key exists) and one without.
**How to avoid:** Initialize cost stats as `{"hits": 0, "misses": 0, "errors": 0}` at the start of `upload_and_optimize()`. If `cached_geocoder` exists, read from `cached_geocoder.stats` at the end. If not, count cache hits/misses manually in the fallback path.
**Warning signs:** `AttributeError` or zero stats when running without Google API key configured.

### Pitfall 5: DaisyUI Class Prefix
**What goes wrong:** DaisyUI classes used without the `tw-` prefix don't get styled because the Tailwind config uses `prefix(tw)`.
**Why it happens:** DaisyUI 5 docs show classes like `alert alert-warning`. This project requires `tw-alert tw-alert-warning`.
**How to avoid:** Every DaisyUI/Tailwind class in JSX must use the `tw-` prefix. Check existing `UploadRoutes.tsx` for the established pattern.
**Warning signs:** Components render unstyled or with broken layouts.

## Code Examples

### Complete Duplicate Detection Function
```python
# core/geocoding/duplicate_detector.py
import math
from dataclasses import dataclass, field
from core.geocoding.normalize import normalize_address
from core.models.order import Order


@dataclass
class DuplicateCluster:
    """A group of orders with suspiciously close GPS coordinates."""
    order_ids: list[str]
    addresses: list[str]  # Original address text for each order
    max_distance_m: float  # Largest pairwise distance within the cluster
    center_lat: float
    center_lon: float


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters between two GPS coordinates."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (math.sin(dphi / 2) ** 2
         + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2)
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _confidence_tier(confidence: float) -> str:
    """Map 0.0-1.0 confidence to a threshold tier."""
    if confidence >= 0.90:
        return "rooftop"
    elif confidence >= 0.70:
        return "interpolated"
    elif confidence >= 0.50:
        return "geometric_center"
    else:
        return "approximate"


def detect_duplicate_locations(
    orders: list[Order],
    thresholds: dict[str, float],
) -> list[DuplicateCluster]:
    """Detect orders with different addresses that resolve to nearby coordinates.

    Args:
        orders: Geocoded orders (non-geocoded are skipped).
        thresholds: Dict mapping tier name to distance in meters.
            Example: {"rooftop": 10, "interpolated": 20,
                      "geometric_center": 50, "approximate": 100}

    Returns:
        List of DuplicateCluster objects, each containing 2+ orders.
    """
    # Filter to geocoded orders only
    geocoded = [o for o in orders if o.is_geocoded and o.location]
    if len(geocoded) < 2:
        return []

    # Build normalized address map for same-address exclusion
    norm_addrs = [normalize_address(o.address_raw) for o in geocoded]

    # Union-Find for clustering
    n = len(geocoded)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    # Pairwise comparison
    for i in range(n):
        for j in range(i + 1, n):
            # Skip same normalized address (legitimate multi-cylinder)
            if norm_addrs[i] == norm_addrs[j]:
                continue

            oi, oj = geocoded[i], geocoded[j]
            dist = haversine_meters(
                oi.location.latitude, oi.location.longitude,
                oj.location.latitude, oj.location.longitude,
            )

            # Use the wider threshold (dominated by less-accurate result)
            conf_i = oi.location.geocode_confidence or 0.4
            conf_j = oj.location.geocode_confidence or 0.4
            tier_i = _confidence_tier(conf_i)
            tier_j = _confidence_tier(conf_j)
            threshold = max(thresholds.get(tier_i, 50), thresholds.get(tier_j, 50))

            if dist <= threshold:
                union(i, j)

    # Extract clusters (groups of 2+)
    clusters_map: dict[int, list[int]] = {}
    for i in range(n):
        root = find(i)
        clusters_map.setdefault(root, []).append(i)

    result = []
    for indices in clusters_map.values():
        if len(indices) < 2:
            continue
        cluster_orders = [geocoded[i] for i in indices]

        # Calculate max pairwise distance within cluster
        max_dist = 0.0
        for a in range(len(indices)):
            for b in range(a + 1, len(indices)):
                oa, ob = geocoded[indices[a]], geocoded[indices[b]]
                d = haversine_meters(
                    oa.location.latitude, oa.location.longitude,
                    ob.location.latitude, ob.location.longitude,
                )
                max_dist = max(max_dist, d)

        result.append(DuplicateCluster(
            order_ids=[o.order_id for o in cluster_orders],
            addresses=[o.address_raw for o in cluster_orders],
            max_distance_m=round(max_dist, 1),
            center_lat=sum(o.location.latitude for o in cluster_orders) / len(cluster_orders),
            center_lon=sum(o.location.longitude for o in cluster_orders) / len(cluster_orders),
        ))

    return result
```

### Config Thresholds
```python
# In apps/kerala_delivery/config.py

# Duplicate location detection thresholds (meters).
# Confidence-weighted: tighter for high-accuracy, wider for low-accuracy.
# Tunable after real-world testing with actual Vatakara addresses.
DUPLICATE_THRESHOLDS: dict[str, float] = {
    "rooftop": 10.0,          # ROOFTOP: building-level, very tight
    "interpolated": 20.0,     # RANGE_INTERPOLATED: street-level
    "geometric_center": 50.0, # GEOMETRIC_CENTER: area center, wide
    "approximate": 100.0,     # APPROXIMATE: very rough, widest
}

# Google Maps Geocoding API cost per request.
# $5 per 1000 requests = $0.005 each.
# Source: https://developers.google.com/maps/documentation/geocoding/usage-and-billing
GEOCODING_COST_PER_REQUEST: float = 0.005

# Monthly free tier credit from Google Maps Platform.
GEOCODING_FREE_TIER_USD: float = 200.0
```

### Pydantic Response Extension
```python
# New model for duplicate clusters in the response
class DuplicateLocationWarning(BaseModel):
    """A cluster of orders with suspiciously close GPS coordinates."""
    order_ids: list[str] = Field(..., description="Order IDs in this cluster")
    addresses: list[str] = Field(..., description="Address text for each order")
    max_distance_m: float = Field(..., description="Largest distance between orders in cluster")

# New fields on OptimizationSummary
class OptimizationSummary(BaseModel):
    # ... existing fields ...

    # GEO-04: Cost transparency
    cache_hits: int = Field(default=0)
    api_calls: int = Field(default=0)
    estimated_cost_usd: float = Field(default=0.0)
    free_tier_note: str = Field(default="")

    # GEO-03: Duplicate location warnings
    duplicate_warnings: list[DuplicateLocationWarning] = Field(default_factory=list)
```

### Frontend: Cost Summary Component (DaisyUI 5 + tw- prefix)
```tsx
function CostSummary({ uploadResult }: { uploadResult: UploadResponse }) {
  const hits = uploadResult.cache_hits ?? 0;
  const calls = uploadResult.api_calls ?? 0;
  const cost = uploadResult.estimated_cost_usd ?? 0;
  const note = uploadResult.free_tier_note ?? "";

  if (hits === 0 && calls === 0) return null;

  return (
    <div className="tw-stats tw-stats-vertical lg:tw-stats-horizontal tw-shadow tw-w-full tw-mt-4">
      <div className="tw-stat">
        <div className="tw-stat-title">Cache Hits (Free)</div>
        <div className="tw-stat-value tw-text-success">{hits}</div>
      </div>
      <div className="tw-stat">
        <div className="tw-stat-title">API Calls</div>
        <div className="tw-stat-value">{calls}</div>
        <div className="tw-stat-desc">~${cost.toFixed(2)} estimated</div>
      </div>
      {note && (
        <div className="tw-stat">
          <div className="tw-stat-desc">{note}</div>
        </div>
      )}
    </div>
  );
}
```

### Frontend: Duplicate Warnings Component
```tsx
function DuplicateWarnings({ warnings }: { warnings: DuplicateLocationWarning[] }) {
  if (!warnings || warnings.length === 0) return null;

  return (
    <div className="tw-mt-4">
      <div role="alert" className="tw-alert tw-alert-warning">
        <svg xmlns="http://www.w3.org/2000/svg" className="tw-h-5 tw-w-5 tw-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <span>{warnings.length} group{warnings.length !== 1 ? "s" : ""} of orders resolve to very similar locations</span>
      </div>
      {warnings.map((cluster, idx) => (
        <div key={idx} className="tw-collapse tw-collapse-arrow tw-bg-base-200 tw-mt-2">
          <input type="checkbox" defaultChecked />
          <div className="tw-collapse-title tw-font-semibold">
            Orders {cluster.order_ids.join(", ")} -- within {cluster.max_distance_m.toFixed(0)}m
          </div>
          <div className="tw-collapse-content">
            <ul className="tw-list-disc tw-pl-4">
              {cluster.order_ids.map((id, i) => (
                <li key={id}><strong>{id}</strong>: {cluster.addresses[i]}</li>
              ))}
            </ul>
          </div>
        </div>
      ))}
    </div>
  );
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No cost tracking | `CachedGeocoder.stats` tracks hits/misses (Phase 4) | Phase 4 | Foundation already exists; Phase 5 just surfaces it in the response |
| File-based geocode cache | PostGIS-backed DB cache with normalized keys | Phase 4 | Reliable stats because all cache I/O goes through one path |
| No geocode confidence | `GeocodingResult.confidence` mapped from `location_type` | Phase 4 | Per-order confidence scores available for threshold selection |

**Deprecated/outdated:**
- File-based JSON cache: removed in Phase 4. All geocoding goes through `CachedGeocoder` + PostGIS.

## Confidence Threshold Reasoning

### Recommended Values
| Tier | Google `location_type` | Confidence Score | Threshold (m) | Rationale |
|------|----------------------|------------------|----------------|-----------|
| `rooftop` | ROOFTOP | 0.95 | 10 | Building-level accuracy (~5m). Two buildings 10m apart are genuinely adjacent. |
| `interpolated` | RANGE_INTERPOLATED | 0.80 | 20 | Street-level interpolation. Could be off by 10-15m along a road. |
| `geometric_center` | GEOMETRIC_CENTER | 0.60 | 50 | Center of a street/area. Vatakara streets are 100-200m long; center could be 50m from either end. |
| `approximate` | APPROXIMATE | 0.40 | 100 | Neighborhood-level. Only flag if literally on top of each other at this resolution. |

### Mixed-Confidence Recommendation
When comparing two orders with different confidence levels, use `max(threshold_a, threshold_b)` -- the wider threshold. Rationale: the less-accurate result dominates the uncertainty. If one order is ROOFTOP (10m threshold) and the other is GEOMETRIC_CENTER (50m threshold), the GEOMETRIC_CENTER result could be 50m off, so a 10m threshold would be meaningless.

### Expected False Positive Analysis
For a typical Vatakara upload of 40-50 orders:
- Most addresses geocode to ROOFTOP or RANGE_INTERPOLATED (Google has good India coverage for registered addresses)
- Dense streets may have 2-3 GEOMETRIC_CENTER results per upload
- With the recommended thresholds, expect 0-2 clusters per upload (genuine duplicates or data entry errors)
- If false positives are too high after real-world testing, increase thresholds in config.py

## Open Questions

1. **Per-address source tag in response**
   - What we know: The user wants each geocoded order tagged as "cached" or "API call"
   - What's unclear: Whether to add a `geocode_source` field to each order in the response (would require extending the stops/orders response models) or provide a separate lookup list
   - Recommendation: Add a `per_order_geocode_source` field as a `dict[str, str]` mapping order_id to "cached"/"api_call" in the response. Simpler than modifying the nested order/stop models. Frontend can look up by order_id.

2. **Exact confidence-to-tier boundaries**
   - What we know: Google returns ROOFTOP (0.95), RANGE_INTERPOLATED (0.80), GEOMETRIC_CENTER (0.60), APPROXIMATE (0.40) -- these are already mapped in `google_adapter.py`
   - What's unclear: Driver-verified entries have confidence 0.95 -- should they use ROOFTOP thresholds? Cache entries from previous Google lookups preserve their original confidence.
   - Recommendation: Yes, driver-verified (0.95) should use the `rooftop` tier. The tier function should be based purely on the numeric confidence value, not the source. This is already how the code example above works.

3. **Cost reporting when no API key is configured**
   - What we know: Without an API key, the fallback path uses direct `repo.get_cached_geocode()` -- all results are cache hits, cost is $0.
   - What's unclear: Should the cost summary still appear (showing "0 API calls, $0.00")?
   - Recommendation: Yes, show it. Confirms to staff that the system is operating in cache-only mode. The `free_tier_note` could say "Cache-only mode (no API key configured)" instead of the free tier message.

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `core/geocoding/cache.py` -- CachedGeocoder.stats, get_stats_summary()
- Codebase analysis: `core/geocoding/google_adapter.py` -- confidence_map, location_type mapping
- Codebase analysis: `apps/kerala_delivery/api/main.py` -- OptimizationSummary, upload_and_optimize()
- Codebase analysis: `core/geocoding/normalize.py` -- normalize_address() for same-address exclusion
- [DaisyUI official docs](https://daisyui.com/components/alert) -- alert, stat, collapse components (Context7 /websites/daisyui)
- [Movable Type Haversine reference](https://www.movable-type.co.uk/scripts/latlong.html) -- canonical Haversine formula
- [Google Maps Geocoding API docs](https://developers.google.com/maps/documentation/geocoding/requests-geocoding) -- location_type definitions

### Secondary (MEDIUM confidence)
- Google Maps pricing: $5/1000 requests ($0.005 each) with $200/month free credit -- verified against Google's [billing documentation](https://developers.google.com/maps/documentation/geocoding/usage-and-billing)
- Haversine accuracy: <0.5% error vs Vincenty for sub-km distances at Kerala latitudes -- well-established mathematical property

### Tertiary (LOW confidence)
- GEOMETRIC_CENTER accuracy estimate (50-100m for Vatakara streets): based on general Indian address geocoding experience. Should be validated against actual `geocode_cache` table data once Phase 5 is deployed.
- Threshold values (10/20/50/100m): educated estimates. The blocker in STATE.md notes: "Confidence-weighted duplicate detection thresholds (10m/25m/100m) are estimates -- validate against actual geocode_cache table distribution of location_type values."

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in project; no new dependencies needed
- Architecture: HIGH - Post-geocoding pass with Haversine + Union-Find is textbook; response model extension follows established Pydantic patterns
- Pitfalls: HIGH - False positive analysis based on codebase inspection of confidence scores and threshold math; DaisyUI prefix pattern verified in existing code
- Threshold values: MEDIUM - Mathematical reasoning is sound but values need real-world validation with Vatakara address data

**Research date:** 2026-03-01
**Valid until:** 2026-04-01 (stable domain; thresholds may need tuning sooner based on real data)
