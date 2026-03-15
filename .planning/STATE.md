---
gsd_state_version: 1.0
milestone: v3.0
milestone_name: Driver-Centric Model
status: completed
stopped_at: Completed 22-02-PLAN.md
last_updated: "2026-03-15T00:13:49.204Z"
last_activity: "2026-03-15 -- Completed 22-02 (Validation frontend: validate button, cost modal, inline comparison, Settings history card)"
progress:
  total_phases: 7
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-12)

**Core value:** Every delivery address uploaded must appear on the map and be assigned to an optimized route -- no silent drops, no missing stops.
**Current focus:** v3.0 Driver-Centric Model -- Phase 20: UI Terminology Rename (COMPLETE)

## Current Position

Phase: 22 of 22 (Google Routes Validation) -- seventh of 7 phases in v3.0
Plan: 2 of 2
Status: Complete
Last activity: 2026-03-15 -- Completed 22-02 (Validation frontend: validate button, cost modal, inline comparison, Settings history card)

Progress: [▓▓▓▓▓▓▓▓▓▓] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 90 (across v1.0-v2.2)

**By Milestone:**

| Milestone | Phases | Plans | Timeline |
|-----------|--------|-------|----------|
| v1.0 Infrastructure | 3 (1-3) | 8 | 2026-03-01 |
| v1.1 Polish & Reliability | 4 (4-7) | 16 | 2026-03-01 -> 2026-03-03 |
| v1.2 Tech Debt & Cleanup | 5 (8-12) | 9 | 2026-03-03 -> 2026-03-04 |
| v1.3 Office-Ready Deployment | 8 (13-20) | 10 | 2026-02-21 -> 2026-03-07 |
| v1.4 Ship-Ready QA | 4 (21-24) | 10 | 2026-03-08 -> 2026-03-09 |
| v2.0 Doc & Error Handling | 4 (1-4) | 9 | 2026-03-09 -> 2026-03-10 |
| v2.1 Licensing Security | 6 (5-10) | 13 | 2026-03-10 -> 2026-03-11 |
| v2.2 Address Preprocessing | 5 (11-15) | 13 | 2026-03-10 -> 2026-03-12 |
| v3.0 Driver-Centric Model | 7 (16-22) | 5/5+ (phases 16-17) | In progress |
| Phase 16 P03 | 9min | 1 tasks | 2 files |
| Phase 17 P01 | 7min | 2 tasks | 5 files |
| Phase 17 P02 | 7min | 3 tasks | 5 files |
| Phase 17 P03 | 2min | 1 tasks | 2 files |
| Phase 17 P04 | 6min | 2 tasks | 5 files |
| Phase 18 P01 | 2min | 1 tasks | 2 files |
| Phase 18 P02 | 3min | 2 tasks | 8 files |
| Phase 18 P03 | 3min | 2 tasks | 5 files |
| Phase 18 P04 | 7min | 2 tasks | 5 files |
| Phase 19 P01 | 3min | 2 tasks | 5 files |
| Phase 19 P02 | 6min | 2 tasks | 5 files |
| Phase 19 P03 | 3min | 3 tasks | 3 files |
| Phase 20 P01 | 4min | 2 tasks | 9 files |
| Phase 20 P02 | 3min | 2 tasks | 3 files |
| Phase 21 P01 | 7min | 2 tasks | 5 files |
| Phase 21 P02 | 4min | 2 tasks | 5 files |
| Phase 22 P01 | 6min | 2 tasks | 5 files |
| Phase 22 P02 | 4min | 2 tasks | 6 files |

## Accumulated Context

### Decisions

See: PROJECT.md Key Decisions table, `.planning/milestones/` for full phase details per milestone.

- **Phase 16-01:** Fuzzy matching threshold set to 85 (balances catching abbreviations vs avoiding false merges)
- **Phase 16-01:** Removed vehicle seed data from init.sql (DRV-07: zero pre-loaded fleet)
- **Phase 16-02:** check-name route placed before /{id} routes to avoid FastAPI UUID parsing conflict
- **Phase 16-02:** POST /api/drivers returns 201 (not 200) for proper HTTP semantics
- **Phase 16-02:** Sidebar changed from Fleet/Truck to Drivers/Users, page key from "fleet" to "drivers"
- **Phase 16-03:** Snapshot pattern for intra-CSV driver isolation (no cross-matching within same CSV)
- **Phase 16-03:** Driver auto-creation runs before geocoding so drivers are created even if geocoding fails
- [Phase 16]: Snapshot pattern for intra-CSV driver isolation (process against pre-existing DB, not against newly created drivers)
- **Phase 17-01:** pandas import moved to module level in main.py (was local in auto_create_drivers_from_csv)
- **Phase 17-01:** Upload token TTL set to 30 minutes for parse-upload flow
- **Phase 17-01:** Parse endpoint runs driver auto-creation to provide accurate status categories in preview
- **Phase 17-02:** Driver filtering at DataFrame level (order_id -> delivery_man map) since Order model has no delivery_man field
- **Phase 17-02:** Upload token consumed immediately on lookup (before processing) to prevent replay
- **Phase 17-02:** Upload button renamed to "Upload & Preview" for two-step flow clarity
- [Phase 17]: No new patterns needed -- single-line status string fix to emit matched instead of existing for fuzzy-matched drivers
- [Phase 17]: Placeholder filtering at preprocessor level (both parse-upload and upload-and-optimize benefit)
- [Phase 17]: Driver selection filter moved before geocoding to save Google Maps API costs
- [Phase 18]: (HO) regex placed before (H) to prevent partial matching; space padding for all parenthesized abbreviation patterns
- [Phase 18]: Added PERATTEYATH, POOLAKANDY, KOLAKKOTT to _PROTECTED_WORDS to prevent trailing-letter garbling
- [Phase 18]: Zone radius reduced from 30km to 20km to match actual Vatakara delivery area
- [Phase 18]: Depot lat/lon and zone radius made configurable via env vars for deployment flexibility
- [Phase 18]: Zone circle rendered before route polylines for correct z-order
- [Phase 18]: fetchAppConfig failure non-critical -- map works without zone circle
- [Phase 18]: First+last char guard on fuzzy dictionary matching to prevent off-by-one false positives
- [Phase 18]: MUTTUNGALPARA added to _PROTECTED_WORDS to prevent trailing-letter garbling
- [Phase 18]: Focused integration testing approach for address cleaning (real data + direct function, no HTTP mocks)
- **Phase 19-01:** Partial failure returns partial results with warnings (not full batch failure)
- **Phase 19-01:** Shapely for convex hull computation (already installed, no DB round-trip needed)
- **Phase 19-01:** Collinear/degenerate hulls gracefully skipped (only Polygon hulls compared)
- **Phase 19-02:** Non-CDCMS uploads fall back to single 'Driver' group for backward compatibility with per-driver TSP pipeline
- **Phase 19-02:** preprocess_cdcms handles missing DeliveryMan gracefully (fills empty strings for clean validation)
- **Phase 19-02:** Optimization warnings converted to ImportFailure with stage='optimization' for consistent response format
- **Phase 19-03:** No backward compatibility for ?vehicle= parameter (clean break -- QR codes are the only access method)
- **Phase 19-03:** Dual QR code layout on print sheet: top QR for PWA access, bottom QR(s) for Google Maps navigation
- **Phase 19-03:** Driver name as sole card title on QR sheet (vehicle ID no longer displayed)
- **Phase 20-01:** Kept internal prop names (selectedVehicleId, onSelectVehicle) unchanged for backward compatibility
- **Phase 20-01:** Simplified route card header to show only vehicle_id (which is now driver name per Phase 19)
- **Phase 20-01:** Renamed RunHistory detail table headers Vehicle/Driver to Driver/Name
- **Phase 20-02:** Collapsed-by-default duplicate warnings to reduce visual noise for 15+ clusters
- **Phase 20-02:** API-level rounding as primary fix ensures all clients get clean float data
- **Phase 20-02:** Defense-in-depth Number().toFixed(1) in Driver PWA even though API now rounds
- [Phase 21]: SettingsDB uses key-value schema (not typed columns) per user decision
- [Phase 21]: DB-stored API key cached in module-level _cached_api_key for sync _get_geocoder() access
- [Phase 21]: API key validated via real geocode request to Google Maps before saving
- [Phase 21]: SettingsIcon alias for lucide-react Settings import to avoid collision with Settings page component
- [Phase 21]: Direct fetch (not apiFetch) for export/import cache endpoints due to blob/FormData handling
- [Phase 22]: Confidence thresholds: green <=10%, amber <=25%, red >25% distance delta
- [Phase 22]: Google Routes API Pro tier with TRAFFIC_UNAWARE for stable comparison
- [Phase 22]: Cumulative validation stats in SettingsDB key-value store
- [Phase 22]: Route-level comparison only since Google re-optimizes stop order
- [Phase 22]: Cost modal shows ~INR 0.93 per validation with cumulative stats from backend
- [Phase 22]: Settings navigation via DOM querySelector for sidebar button (avoids react-router dependency)

### Pending Todos

2 pending -- see `.planning/todos/pending/`

### Blockers/Concerns

(None)

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 4 | Audit docs for new-computer setup freshness | 2026-03-12 | e0c7e6a | [4-audit-docs-for-new-computer-setup-freshn](./quick/4-audit-docs-for-new-computer-setup-freshn/) |

## Session Continuity

Last session: 2026-03-15T00:08:09Z
Stopped at: Completed 22-02-PLAN.md
Resume file: None
