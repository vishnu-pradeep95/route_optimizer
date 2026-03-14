# Phase 20: UI Terminology Rename - Research

**Researched:** 2026-03-14
**Domain:** React dashboard UI text/label changes, file renames, floating-point display, collapsible warning UX
**Confidence:** HIGH

## Summary

Phase 20 is a UI-focused refactoring phase with no new library dependencies. The work divides into four distinct areas: (1) systematic "Vehicle" to "Driver" text replacement across the dashboard, (2) file rename of VehicleList.tsx to RouteList.tsx with corresponding CSS and import updates, (3) deletion of the FleetManagement page, and (4) cross-cutting fixes for floating-point display noise and improved duplicate location warning UX.

The codebase audit reveals approximately 40+ user-visible "Vehicle" text occurrences across 7 dashboard files, plus internal variable/prop names that use "vehicle" semantics. The key insight is that API field names (`vehicle_id`) MUST remain untouched -- only user-facing strings change. The Driver PWA has "vehicle" in internal JS variable names only (not user-visible text), but has unrounded `weight_kg` values leaking through as raw database floats.

**Primary recommendation:** Execute this as a systematic sweep with file-by-file changes, starting with the file rename (VehicleList -> RouteList) to avoid merge conflicts, then text replacements, then FleetManagement deletion, then the display formatting fixes.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Remove FleetManagement.tsx entirely -- DriverManagement.tsx (Phase 16) is the only management page
- Vehicle properties (weight, type, depot, speed limit) are no longer relevant in driver-centric model (VROOM uses uncapped capacity for per-driver TSP)
- Keep /api/vehicles API endpoints for backward compatibility, but nothing in the dashboard calls them
- Sidebar nav item "Drivers" stays as-is (already correct from Phase 16)
- Rename sidebar heading from "Vehicles" to "Routes"
- Rename VehicleList.tsx to RouteList.tsx (file rename, not just text change)
- Update all imports referencing VehicleList
- Upload results "Vehicles: N" to "Drivers: N"
- Claude sweeps all remaining "Vehicle" text across dashboard -- systematic find-and-replace of user-visible strings
- Collapsed summary with expand: "8 orders near Mayyannu R -- within 0m of each other" as single line
- Click/tap to expand full address list
- Expanded view shows driver name for each order (helps office staff know which driver to contact)
- Round all numbers to 1 decimal place: weight "14.2 kg", distance "3.5 km", time "101 min"
- Apply to both dashboard AND Driver PWA for consistency
- Fix raw float noise like "14.199999809265137 kg"

### Claude's Discretion
- Route card label specifics
- Optimization warning display format
- Browser tab title text
- Exact collapsed warning component design
- Any remaining Vehicle to Driver text that wasn't specifically discussed

### Deferred Ideas (OUT OF SCOPE)
- Run history navigation (revisiting past optimization sessions) -- Phase 21 scope
- Upload history with date, filename, driver count -- Phase 21 scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| UI-01 | Dashboard displays "Driver" instead of "Vehicle" in all user-facing labels, headers, and navigation | Full audit of all "Vehicle" text in 7 dashboard source files -- see Inventory below |
| UI-02 | API field names remain backward-compatible (vehicle_id stays in API responses for PWA compatibility) | Confirmed: API responses use `vehicle_id` field; only UI display strings change. Driver PWA reads `vehicle_id` internally -- no changes needed to PWA logic |
| UI-03 | Fleet Management page becomes Driver Management page with driver-centric UI | FleetManagement.tsx + FleetManagement.css can be deleted; DriverManagement.tsx already exists and handles driver CRUD; App.tsx already routes to DriverManagement |
</phase_requirements>

## Standard Stack

### Core (No New Dependencies)
| Library | Version | Purpose | Status |
|---------|---------|---------|--------|
| React | 19 | Dashboard framework | Already installed |
| TypeScript | - | Type safety | Already installed |
| Vite | 7 | Build tool | Already installed |
| DaisyUI | 5 | Component library (tw: prefix) | Already installed |
| Tailwind | 4 | CSS utility framework | Already installed |

No new libraries needed. This is purely a rename/refactoring phase.

## Architecture Patterns

### File Rename Strategy: VehicleList -> RouteList

The VehicleList component appears in the sidebar of the LiveMap page. It lists routes by driver. The rename to RouteList better reflects what it actually shows.

**Files affected by rename:**
```
src/components/VehicleList.tsx  -> src/components/RouteList.tsx
src/components/VehicleList.css  -> src/components/RouteList.css
src/pages/LiveMap.tsx           -> update import statement
```

**CSS class rename approach:** The CSS uses `.vehicle-*` class names extensively (18+ classes). Two options:
1. **Rename all CSS classes** from `.vehicle-*` to `.route-*` -- cleaner but larger diff
2. **Keep CSS class names as-is** -- smaller diff, less risk

**Recommendation:** Rename CSS classes to `.route-*` since we're already renaming the file. A half-rename is worse than no rename.

### Text Replacement Pattern

User-visible strings that need changing (NOT internal variable/prop names):

**Rule:** If the user sees it on screen, change it. If it's a TypeScript interface field name, prop name, or CSS class name, it's an internal concern -- change only where needed for clarity.

### FleetManagement Deletion

App.tsx already has no nav entry for FleetManagement (the nav was changed in Phase 16 to "Drivers" pointing to DriverManagement). However, the file and its CSS still exist. Clean deletion:
- Delete `src/pages/FleetManagement.tsx`
- Delete `src/pages/FleetManagement.css`
- Remove any remaining imports (currently none in App.tsx)

### Duplicate Warning Redesign

Current implementation: Each duplicate cluster is a DaisyUI collapse, defaultChecked (expanded by default), showing a flat list of order IDs and addresses.

New implementation per CONTEXT.md:
- Collapsed by default (change from `defaultChecked` to unchecked)
- Summary line: "8 orders near [common address substring] -- within 0m of each other"
- Expanded view: shows driver name for each order

**Challenge:** The current `DuplicateLocationWarning` type does not include driver names for each order. The API response only provides `order_ids`, `addresses`, and `max_distance_m`. To show which driver each order belongs to, we need to cross-reference with the route data already available in the upload result.

**Solution approach:** After upload, the dashboard has both the `duplicate_warnings` array and the `routes` data. We can build an `order_id -> driver_name` lookup from the route details and pass it to the DuplicateWarnings component.

### Floating-Point Display Fix

**Root cause:** The database stores `weight_kg` as a SQL `Float` column. Python's `float` serializes with full IEEE 754 precision. The API rounds `total_weight_kg` (line 2093, 2128) but does NOT round individual `stop.weight_kg` (lines 2103, 2184).

**Fix locations:**
1. **API level (best):** Add `round(stop.weight_kg, 1)` in the two API response builders (lines 2103, 2184 of main.py). This fixes it for ALL clients.
2. **Dashboard UI level:** Add `.toFixed(1)` where `stop.weight_kg` is displayed (UploadRoutes.tsx line 999).
3. **Driver PWA level:** Add rounding in `renderHeroCard()` and `renderCompactCard()` where `stop.weight_kg` is interpolated directly (lines 1330, 1364).

**Recommendation:** Fix at API level AND client level for defense in depth. API fix ensures future clients get clean data. Client fix handles any already-cached responses.

**Specific display locations needing `.toFixed(1)` or rounding:**

Dashboard:
- `UploadRoutes.tsx` line 935: `route.total_distance_km` (no .toFixed)
- `UploadRoutes.tsx` line 937: `route.total_weight_kg` (no .toFixed)
- `UploadRoutes.tsx` line 999: `stop.weight_kg` (no .toFixed)
- `UploadRoutes.tsx` line 1001: `stop.distance_from_prev_km` (no .toFixed)

Driver PWA:
- `index.html` line 1330: `stop.weight_kg` in hero card
- `index.html` line 1364: `stop.weight_kg` in compact card
- `index.html` line 1365: `stop.distance_from_prev_km` in compact card
- `index.html` line 1439: `stop.weight_kg` in map popup

Files already handling rounding correctly:
- `VehicleList.tsx` line 150: `route.total_distance_km.toFixed(1)` -- good
- `VehicleList.tsx` line 151: `route.total_weight_kg.toFixed(0)` -- good
- `RunHistory.tsx` lines 307-312: all use `.toFixed()` -- good
- `UploadRoutes.tsx` lines 882, 886: aggregate stats use `.toFixed(1)` -- good

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Collapsible panels | Custom accordion JS | DaisyUI `tw:collapse` component | Already used elsewhere in UploadRoutes; consistent UX |
| Address substring extraction | Complex NLP for "common address" | Simple first-address truncation | For collapsed summary, use first address from cluster truncated to ~30 chars |

## Common Pitfalls

### Pitfall 1: Breaking the Driver PWA
**What goes wrong:** Renaming API field names like `vehicle_id` to `driver_id` would break the Driver PWA, which reads `vehicle_id` from API responses and uses it in local storage keys.
**Why it happens:** Natural instinct to rename everything during a terminology change.
**How to avoid:** NEVER change API response field names. The requirement (UI-02) explicitly states `vehicle_id` stays in API responses. Only change user-visible display strings.
**Warning signs:** Any change to `types.ts` interface field names or to API endpoint paths.

### Pitfall 2: CSS Class Name Confusion After File Rename
**What goes wrong:** Renaming VehicleList.tsx to RouteList.tsx but forgetting to update the CSS class references in JSX, or vice versa.
**How to avoid:** Do the file rename and CSS class rename in the same commit. Search for all `.vehicle-` CSS class usages in the TSX file.
**Warning signs:** Broken styling after the rename.

### Pitfall 3: Missing "Vehicle" Text in Dynamic Content
**What goes wrong:** Finding all hardcoded "Vehicle" strings but missing ones generated from API response fields like `vehicles_used`.
**How to avoid:** The `vehicles_used` field name stays (it's an API field), but the label next to it changes: `"Vehicles"` stat title becomes `"Drivers"`.
**Warning signs:** UAT showing "Vehicles: 3" anywhere in the dashboard.

### Pitfall 4: Duplicate Warning Cross-Reference Failure
**What goes wrong:** Trying to show driver names in duplicate warnings but the route data hasn't loaded yet, or order IDs don't match between warnings and routes.
**Why it happens:** Duplicate warnings come from the upload response. Route details may need a separate fetch.
**How to avoid:** Build the order->driver lookup from the upload response's route data (which is fetched immediately after upload). If route details aren't available, show warnings without driver names (graceful degradation).

### Pitfall 5: Floating-Point Rounding at Wrong Layer
**What goes wrong:** Rounding only in the UI but not in the API, so cached responses or other clients still see raw floats.
**How to avoid:** Fix at API level first (round `stop.weight_kg` in response serialization), then add client-side `.toFixed()` as defense.

## Complete Vehicle Text Inventory

### User-Visible Text to Change (Dashboard)

| File | Line | Current Text | New Text | Type |
|------|------|-------------|----------|------|
| StatsBar.tsx | 100 | `"Vehicles Active"` | `"Drivers Active"` | Label |
| StatsBar.tsx | 22 | Comment: "any vehicle" | "any driver" | Comment only |
| VehicleList.tsx | 72 | `<h3>Vehicles</h3>` | `<h3>Routes</h3>` | Heading |
| VehicleList.tsx | 77 | `title="Show all vehicles"` | `title="Show all routes"` | Tooltip |
| VehicleList.tsx | 189 | `"No active routes..."` | Already correct | - |
| UploadRoutes.tsx | 856 | `"Vehicles"` (stat title) | `"Drivers"` | Label |
| UploadRoutes.tsx | 877 | `"Vehicles"` (stat title) | `"Drivers"` | Label |
| UploadRoutes.tsx | 907 | `{/* Vehicle Route Cards */}` | `{/* Driver Route Cards */}` | Comment |
| RunHistory.tsx | 133 | `<th>Vehicles</th>` | `<th>Drivers</th>` | Table header |
| RunHistory.tsx | 289 | `<th>Vehicle</th>` | `<th>Driver</th>` (expanded detail) | Table header |

### Internal Names That Should Change for Clarity (non-breaking)

| File | Current | New | Notes |
|------|---------|-----|-------|
| VehicleList.tsx -> RouteList.tsx | `VehicleListProps` | `RouteListProps` | Interface name |
| VehicleList.tsx -> RouteList.tsx | `VehicleList` function | `RouteList` function | Export name |
| LiveMap.tsx | `import { VehicleList }` | `import { RouteList }` | Import |
| LiveMap.tsx | `<VehicleList ...>` | `<RouteList ...>` | JSX usage |
| UploadRoutes.tsx | `expandedVehicle` state | `expandedRoute` or keep | Optional clarity |
| UploadRoutes.tsx | `toggleVehicle` function | `toggleRoute` or keep | Optional clarity |

### Internal Names to KEEP (API contract / backward-compatible)

| File | Name | Why Keep |
|------|------|----------|
| types.ts | `vehicle_id` fields | API contract - UI-02 requirement |
| types.ts | `Vehicle` interface | Still used by /api/vehicles endpoint |
| types.ts | `VehiclesResponse` | Still used by /api/vehicles endpoint |
| types.ts | `VEHICLE_COLORS` | Color palette name (could rename but low priority) |
| types.ts | `getVehicleColor()` | Color utility (could rename but low priority) |
| api.ts | All vehicle endpoint functions | API endpoint wrappers still valid |
| RouteMap.tsx | `vehicleIndexMap` prop | Internal prop, not user-visible |
| LiveMap.tsx | `selectedVehicleId` | Internal state, not user-visible |
| All files | `vehicleId` function params | Internal code, not user-visible |

### Files to Delete

| File | Reason |
|------|--------|
| `src/pages/FleetManagement.tsx` | Replaced by DriverManagement.tsx |
| `src/pages/FleetManagement.css` | Styles for deleted page |

## Code Examples

### Duplicate Warning Redesign

Current DuplicateLocationWarning type:
```typescript
// Source: types.ts
export interface DuplicateLocationWarning {
  order_ids: string[];
  addresses: string[];
  max_distance_m: number;
}
```

New collapsed summary pattern using DaisyUI collapse:
```typescript
// Collapsed by default, summary shows first address truncated
<div className="tw:collapse tw:collapse-arrow tw:bg-base-200 tw:mt-2">
  <input type="checkbox" />  {/* unchecked = collapsed by default */}
  <div className="tw:collapse-title tw:font-semibold tw:text-sm">
    {cluster.order_ids.length} orders near {cluster.addresses[0].substring(0, 35)}...
    -- within {cluster.max_distance_m.toFixed(0)}m of each other
  </div>
  <div className="tw:collapse-content">
    <ul className="tw:list-disc tw:pl-4 tw:space-y-1">
      {cluster.order_ids.map((id, i) => (
        <li key={id}>
          <strong>{id}</strong>: {cluster.addresses[i]}
          {orderDriverMap.get(id) && (
            <span className="tw:badge tw:badge-sm tw:badge-ghost tw:ml-2">
              {orderDriverMap.get(id)}
            </span>
          )}
        </li>
      ))}
    </ul>
  </div>
</div>
```

### Floating-Point Rounding (API Level Fix)

```python
# Source: apps/kerala_delivery/api/main.py, lines 2103 and 2184
# Current:
"weight_kg": stop.weight_kg,
# Fixed:
"weight_kg": round(stop.weight_kg, 1),
```

### Floating-Point Rounding (Driver PWA Fix)

```javascript
// Source: apps/kerala_delivery/driver_app/index.html
// Current (line 1330):
${stop.quantity} cyl &middot; ${stop.weight_kg} kg
// Fixed:
${stop.quantity} cyl &middot; ${Number(stop.weight_kg).toFixed(1)} kg

// Current (line 1365):
${stop.distance_from_prev_km > 0 ? ` &middot; ${stop.distance_from_prev_km} km` : ''}
// Fixed:
${stop.distance_from_prev_km > 0 ? ` &middot; ${Number(stop.distance_from_prev_km).toFixed(1)} km` : ''}
```

### RouteList Rename Pattern

```typescript
// Source: LiveMap.tsx -- import change
// Current:
import { VehicleList } from "../components/VehicleList";
// New:
import { RouteList } from "../components/RouteList";

// JSX change:
// Current:
<VehicleList routes={routes} ... />
// New:
<RouteList routes={routes} ... />
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Fleet/Vehicle terminology | Driver-centric terminology | Phase 16 (v3.0) | Dashboard labels, nav items |
| VehicleList sidebar | RouteList sidebar | This phase | File rename + text update |
| FleetManagement page | DriverManagement page | Phase 16 created replacement | Delete old page |
| Raw float display | Rounded to 1 decimal | This phase | Both dashboard + Driver PWA |

## Open Questions

1. **Order-to-driver mapping for duplicate warnings**
   - What we know: Upload response has `duplicate_warnings` (order_ids + addresses) and we fetch routes after upload
   - What's unclear: Whether the route detail data is always available when rendering duplicate warnings
   - Recommendation: Build lookup from `routes` state (RouteSummary has `vehicle_id` which now contains driver names). If individual stop->route mapping is needed, use `routeDetails` map. Fallback: show warnings without driver names if mapping unavailable.

2. **Common address substring for collapsed summary**
   - What we know: Each cluster has an `addresses` array
   - What's unclear: Best way to extract a "common" address substring
   - Recommendation: Use the first address truncated to ~35 characters. This is simpler than actual common-substring extraction and gives office staff enough context to identify the location.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Playwright (E2E) + pytest (API) |
| Config file | `playwright.config.ts` (E2E), `pytest.ini` (Python) |
| Quick run command | `npx playwright test --project=dashboard` |
| Full suite command | `npx playwright test && pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-01 | Dashboard displays "Driver" instead of "Vehicle" | E2E/manual | `npx playwright test --project=dashboard` | Yes (dashboard.spec.ts) |
| UI-02 | API field names remain backward-compatible | unit | `pytest tests/apps/ -k "route" -x` | Yes |
| UI-03 | Fleet Management page removed, Driver Management works | E2E/manual | `npx playwright test --project=dashboard` | Yes |

### Sampling Rate
- **Per task commit:** Visual verification via dev server
- **Per wave merge:** `npx playwright test --project=dashboard`
- **Phase gate:** Full E2E suite green + manual UAT review

### Wave 0 Gaps
None -- existing test infrastructure covers all phase requirements. The changes are primarily text/label updates that are best verified through visual inspection and existing E2E flows.

## Sources

### Primary (HIGH confidence)
- Direct codebase audit of all 7 dashboard source files
- Direct codebase audit of Driver PWA index.html
- Direct codebase audit of API main.py response builders
- CONTEXT.md user decisions from `/gsd:discuss-phase`
- REQUIREMENTS.md requirement definitions (UI-01, UI-02, UI-03)

### Secondary (MEDIUM confidence)
- DaisyUI v5 collapse component pattern (verified from existing usage in UploadRoutes.tsx)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new dependencies, pure refactoring
- Architecture: HIGH - complete codebase audit performed, all files read
- Pitfalls: HIGH - based on direct code analysis of API contracts and field usage

**Research date:** 2026-03-14
**Valid until:** 2026-04-14 (stable -- no external dependency changes)
