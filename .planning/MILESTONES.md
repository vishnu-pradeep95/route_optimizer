# Milestones

## v1.3 Office-Ready Deployment (Shipped: 2026-03-07)

**Phases completed:** 8 phases (13-20), 10 plans
**Timeline:** 14 days (2026-02-21 → 2026-03-07)
**Git range:** `5ebbf56`..`f533d85` (77 commits)
**Files modified:** 75 (+10,300 / -380)

**Key accomplishments:**
- One-command WSL bootstrap installer (bootstrap.sh) with Docker CE auto-install, environment guards, and two-phase resume for Docker group membership
- Zero-input daily startup script (start.sh) with 60s health polling, container-state diagnosis, and failure recovery guidance
- Comprehensive CSV format reference (CSV_FORMAT.md) with error glossary, address cleaning pipeline, and copy-pasteable example rows
- Humanized error messages across all upload and geocoding paths -- plain English "problem -- fix action" pattern replacing Python internals
- Distribution build script (build-dist.sh) producing versioned tarballs with compiled licensing module (.pyc only)
- Documentation overhaul for non-technical office employees: README accuracy fixes, DEPLOY.md restructured with script references, error message traceability artifact

---

## v1.2 Tech Debt & Cleanup (Shipped: 2026-03-04)

**Phases completed:** 5 phases (8-12), 9 plans
**Timeline:** 2 days (2026-03-03 → 2026-03-04)
**Git range:** `a92bcff`..`0305804` (43 commits)
**Files modified:** 48 (+4,345 / -196)

**Key accomplishments:**
- Removed all dead code from API: `_build_fleet()`, unused imports, stale `OSRM_URL` config, incorrect docstrings
- Created typed PostGIS geometry helpers (`_point_lat`/`_point_lng`) eliminating all `type: ignore` suppressions
- Consolidated config into single `GET /api/config` endpoint serving depot coords, safety multiplier, and office phone number
- Hardened Driver PWA: real phone number from API, GPS `watchPosition` leak fix, styled offline `<dialog>`, PNG icons, SW pre-cache, debug logging gate
- Cleaned dashboard: dead CSS alias removal, design token consistency, `RouteDetail` type fix, exhaustive `StatusBadge` switch, batch route loading replacing N+1
- Wired driver-verified geocode saves into delivery status endpoint; validated duplicate detection thresholds against 54 production geocode entries

---

## v1.1 Polish & Reliability (Shipped: 2026-03-03)

**Phases completed:** 4 phases (4-7), 16 plans
**Timeline:** 3 days (2026-03-01 -> 2026-03-03)
**Git range:** `939e8fc`..`6e72d5a` (77 commits)
**Files modified:** 76 (+10,306 / -1,612)

**Key accomplishments:**
- Unified geocoding cache with single `normalize_address()` function; deprecated file-based cache for DB-only caching
- Geocoding cost transparency: cache hits vs API calls with estimated cost; duplicate location warnings within 15m proximity
- Dashboard UI overhaul: all 4 pages migrated to DaisyUI components, lucide-react icons, responsive 3-tier sidebar, skeleton loading, empty states
- Driver PWA refresh: WCAG AAA outdoor contrast, hero card next-stop architecture, segmented progress bar, dark fail dialog, Call Office FAB
- Print-optimized QR sheets with 210px codes for arm-length scanning in three-wheeler cabs
- Reusable component system: EmptyState, StatusBadge, deriveRouteStatus() shared across all dashboard pages

---

## v1.0 Infrastructure (Shipped: 2026-03-01)

**Phases completed:** 3 phases, 8 plans, 0 tasks

**Key accomplishments:**
- (none recorded)

---

