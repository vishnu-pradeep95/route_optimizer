---
phase: 20-ui-terminology-rename
plan: 01
subsystem: ui
tags: [react, dashboard, terminology, rename, css]

# Dependency graph
requires:
  - phase: 19-per-driver-tsp
    provides: driver-centric data model where vehicle_id contains driver names
provides:
  - RouteList component (renamed from VehicleList) with .route-* CSS classes
  - All user-visible dashboard text uses "Driver"/"Routes" instead of "Vehicle"/"Vehicles"
  - FleetManagement dead code removed
affects: [20-02-PLAN]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "route-* CSS class naming for sidebar route list"
    - "Driver-centric terminology in all dashboard UI text"

key-files:
  created:
    - apps/kerala_delivery/dashboard/src/components/RouteList.tsx
    - apps/kerala_delivery/dashboard/src/components/RouteList.css
  modified:
    - apps/kerala_delivery/dashboard/src/pages/LiveMap.tsx
    - apps/kerala_delivery/dashboard/src/components/StatsBar.tsx
    - apps/kerala_delivery/dashboard/src/pages/UploadRoutes.tsx
    - apps/kerala_delivery/dashboard/src/pages/RunHistory.tsx
    - apps/kerala_delivery/dashboard/src/pages/DriverManagement.css

key-decisions:
  - "Kept prop names (selectedVehicleId, onSelectVehicle, vehicleIndexMap) as internal API for backward compatibility"
  - "Simplified route card header to show only vehicle_id (which is now the driver name per Phase 19)"
  - "Renamed RunHistory detail table Vehicle/Driver columns to Driver/Name"

patterns-established:
  - "route-* CSS class prefix for sidebar route list component"

requirements-completed: [UI-01, UI-03]

# Metrics
duration: 4min
completed: 2026-03-14
---

# Phase 20 Plan 01: UI Terminology Rename Summary

**Renamed VehicleList to RouteList, swept all user-visible "Vehicle" text to "Driver"/"Routes", and deleted dead FleetManagement page**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-14T19:22:06Z
- **Completed:** 2026-03-14T19:26:41Z
- **Tasks:** 2
- **Files modified:** 9 (2 created, 5 modified, 2 deleted)

## Accomplishments
- Renamed VehicleList.tsx/css to RouteList.tsx/css with all .vehicle-* CSS selectors changed to .route-*
- Updated all user-visible "Vehicles" text to "Drivers" across StatsBar, UploadRoutes, and RunHistory
- Deleted FleetManagement.tsx/css (dead code since Phase 16)
- Simplified UploadRoutes route card header to show driver name only
- TypeScript compiles clean and production build succeeds

## Task Commits

Each task was committed atomically:

1. **Task 1: Rename VehicleList to RouteList** - `5398e85` (refactor)
2. **Task 2: Sweep Vehicle-to-Driver text + delete FleetManagement** - `38226aa` (feat)

## Files Created/Modified
- `apps/kerala_delivery/dashboard/src/components/RouteList.tsx` - Renamed from VehicleList with .route-* class names and "Routes" heading
- `apps/kerala_delivery/dashboard/src/components/RouteList.css` - Renamed from VehicleList.css with all .route-* selectors and route-pulse keyframes
- `apps/kerala_delivery/dashboard/src/pages/LiveMap.tsx` - Updated import and JSX from VehicleList to RouteList, updated skeleton CSS classes
- `apps/kerala_delivery/dashboard/src/components/StatsBar.tsx` - "Vehicles Active" changed to "Drivers Active"
- `apps/kerala_delivery/dashboard/src/pages/UploadRoutes.tsx` - "Vehicles" stat titles changed to "Drivers", renamed expandedVehicle/toggleVehicle/vehicleQr to route variants, simplified route card header
- `apps/kerala_delivery/dashboard/src/pages/RunHistory.tsx` - Table headers "Vehicles" to "Drivers", detail table "Vehicle" to "Driver"
- `apps/kerala_delivery/dashboard/src/pages/DriverManagement.css` - Removed stale FleetManagement reference in comment
- `apps/kerala_delivery/dashboard/src/pages/FleetManagement.tsx` - Deleted (dead code)
- `apps/kerala_delivery/dashboard/src/pages/FleetManagement.css` - Deleted (dead code)

## Decisions Made
- Kept internal prop names (selectedVehicleId, onSelectVehicle, vehicleIndexMap) unchanged for backward compatibility -- they are internal code, not user-visible
- Simplified route card header to show only vehicle_id which now IS the driver name per Phase 19 (driver_name is redundant)
- Renamed RunHistory detail table headers from Vehicle/Driver to Driver/Name to avoid redundancy

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All user-visible dashboard terminology now uses "Driver"/"Routes" terminology
- Plan 02 (API response field naming or further cleanup) can proceed
- Production build succeeds with zero TypeScript errors

## Self-Check: PASSED

All files verified present/deleted. All commit hashes confirmed in git log.

---
*Phase: 20-ui-terminology-rename*
*Completed: 2026-03-14*
