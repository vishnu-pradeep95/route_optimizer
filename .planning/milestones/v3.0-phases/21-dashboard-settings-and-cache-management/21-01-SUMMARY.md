---
phase: 21-dashboard-settings-and-cache-management
plan: 01
subsystem: api, database
tags: [settings, geocode-cache, fastapi, sqlalchemy, alembic, key-value-store]

# Dependency graph
requires: []
provides:
  - SettingsDB key-value model and Alembic migration
  - 6 repository functions (get/set setting, cache stats/export/import/clear)
  - 7 API endpoints for settings CRUD and cache management
  - _get_geocoder() DB-key fallback (priority: DB > env var)
  - API key validation via test geocode request
  - Masked API key display (first 4 + last 4 chars)
affects: [21-02-frontend-settings-page]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "SettingsDB key-value store for runtime configuration"
    - "DB-stored API key with module-level cache for sync access"
    - "API key validation via test geocode request before save"

key-files:
  created:
    - infra/alembic/versions/e4a1c7f83b21_add_settings_table.py
    - tests/apps/kerala_delivery/api/test_settings.py
  modified:
    - core/database/models.py
    - core/database/repository.py
    - apps/kerala_delivery/api/main.py

key-decisions:
  - "SettingsDB uses key-value schema (not typed columns) per user decision"
  - "DB-stored API key cached in module-level _cached_api_key for sync _get_geocoder() access"
  - "API key validated via real geocode request to Google Maps before saving"
  - "Startup handler loads DB key into _cached_api_key using async_session_factory directly"

patterns-established:
  - "Settings key-value pattern: SettingsDB(key PK, value text, updated_at)"
  - "Cache management: stats/export/import/clear as separate repository functions"

requirements-completed: [SET-01, SET-02, SET-03, SET-04, SET-05, SET-06]

# Metrics
duration: 7min
completed: 2026-03-14
---

# Phase 21 Plan 01: Settings Backend Summary

**SettingsDB key-value model with 7 API endpoints for Google Maps API key management and geocode cache CRUD (stats, export, import, clear)**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-14T21:46:16Z
- **Completed:** 2026-03-14T21:53:14Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- SettingsDB model (key-value schema) with Alembic migration for the settings table
- 6 repository functions: get/set_setting, get_geocode_cache_stats, export/import/clear_geocode_cache
- 7 API endpoints: settings GET/PUT, API key validate, cache stats/export/import/clear
- _get_geocoder() now checks DB settings before env var fallback
- API key validation via test geocode request (validates before saving)
- 21 unit tests covering all repository functions, endpoints, and helper

## Task Commits

Each task was committed atomically:

1. **Task 1: SettingsDB model, migration, repository functions, and tests** - `6bab708` (feat)
2. **Task 2: API endpoints for settings, cache, and geocoder DB-key fallback** - `c885d23` (feat)

_Note: Task 1 used TDD -- tests written first (RED), then implementation (GREEN)_

## Files Created/Modified
- `core/database/models.py` - Added SettingsDB model (key PK, value text, updated_at)
- `core/database/repository.py` - Added 6 functions: get/set_setting, cache stats/export/import/clear
- `apps/kerala_delivery/api/main.py` - Added _cached_api_key, modified _get_geocoder(), 7 new endpoints, mask_api_key(), _validate_google_api_key()
- `infra/alembic/versions/e4a1c7f83b21_add_settings_table.py` - Alembic migration for settings table
- `tests/apps/kerala_delivery/api/test_settings.py` - 21 tests covering all new functionality

## Decisions Made
- Used SQLAlchemy merge() for settings upsert (simpler than insert-on-conflict)
- Startup handler uses async_session_factory() directly since get_session() is a FastAPI dependency generator
- API key validation makes a real geocode request to "Vatakara, Kerala, India" (known address in the deployment area)
- GET endpoints use verify_read_key, write endpoints use verify_api_key (consistent with existing auth pattern)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All 7 backend endpoints ready for the frontend Settings page (Plan 02)
- Settings page can call GET /api/settings to check current state
- PUT /api/settings/api-key validates before saving
- Cache management endpoints ready for export/import/clear UI

## Self-Check: PASSED

All 5 files verified present. Both task commits (6bab708, c885d23) verified in git log.

---
*Phase: 21-dashboard-settings-and-cache-management*
*Completed: 2026-03-14*
