# Phase 20: UI Terminology Rename - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Change all user-facing "Vehicle" text to "Driver" in the dashboard. Remove the Fleet Management page. Keep API field names (vehicle_id) backward-compatible for Driver PWA. Also fix floating-point display noise and improve duplicate location warning UX.

</domain>

<decisions>
## Implementation Decisions

### Fleet Management page
- Remove FleetManagement.tsx entirely — DriverManagement.tsx (Phase 16) is the only management page
- Vehicle properties (weight, type, depot, speed limit) are no longer relevant in driver-centric model (VROOM uses uncapped capacity for per-driver TSP)
- Keep /api/vehicles API endpoints for backward compatibility, but nothing in the dashboard calls them
- Sidebar nav item "Drivers" stays as-is (already correct from Phase 16)

### Sidebar & route list
- Rename sidebar heading from "Vehicles" to "Routes"
- Rename VehicleList.tsx → RouteList.tsx (file rename, not just text change)
- Update all imports referencing VehicleList

### Route card labels
- Claude's discretion on specific label updates — sensible Vehicle→Driver sweep on route cards

### Dashboard summary stats
- Upload results "Vehicles: N" → "Drivers: N"
- Claude sweeps all remaining "Vehicle" text across dashboard — systematic find-and-replace of user-visible strings
- User will review in UAT

### Duplicate location warnings
- Collapsed summary with expand: "8 orders near Mayyannu R — within 0m of each other" as single line
- Click/tap to expand full address list
- Expanded view shows driver name for each order (helps office staff know which driver to contact)
- Optimization warnings (overlap, anomalies) display: Claude decides best format per warning type

### Floating-point display
- Round all numbers to 1 decimal place: weight "14.2 kg", distance "3.5 km", time "101 min"
- Apply to both dashboard AND Driver PWA for consistency
- Fix raw float noise like "14.199999809265137 kg"

### Page titles
- Claude decides browser tab title format — something sensible and driver-centric

### Claude's Discretion
- Route card label specifics
- Optimization warning display format
- Browser tab title text
- Exact collapsed warning component design
- Any remaining Vehicle→Driver text that wasn't specifically discussed

</decisions>

<specifics>
## Specific Ideas

- "Vehicles: 1" in route summary → "Drivers: N" — user specifically flagged this during Phase 19 UAT
- Duplicate warnings were flagged as "should be displayed better" — user saw 15+ clusters with full inline addresses, wants them collapsible
- "14.199999809265137 kg" visible in Driver PWA — raw DB floats leaking through to UI

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- DriverManagement.tsx: Already has driver CRUD with name, active/inactive status — replaces FleetManagement
- DaisyUI collapse/accordion component: Can be used for collapsible duplicate warnings
- Tailwind v4 with `tw:` prefix: All dashboard components use this convention

### Established Patterns
- Dashboard uses React 19 + TypeScript + Vite 7 + MapLibre GL JS
- DaisyUI v5 component library with `tw:` prefix convention
- Driver PWA is vanilla JS single index.html — no build step
- API responses return `vehicle_id` field which now contains driver names (Phase 19 migration)

### Integration Points
- App.tsx NAV_ITEMS: Need to remove any Fleet Management nav reference
- VehicleList.tsx → RouteList.tsx: Used in sidebar of main route view
- FleetManagement.tsx: Can be deleted — DriverManagement.tsx covers driver CRUD
- Upload results page (UploadRoutes.tsx): Shows "Vehicles" stat, duplicate warnings
- Driver PWA index.html: Floating-point formatting in stop rendering

</code_context>

<deferred>
## Deferred Ideas

- Run history navigation (revisiting past optimization sessions) — Phase 21 scope
- Upload history with date, filename, driver count — Phase 21 scope

</deferred>

---

*Phase: 20-ui-terminology-rename*
*Context gathered: 2026-03-14*
