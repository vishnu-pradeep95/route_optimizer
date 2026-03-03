---
phase: 04-geocoding-cache-normalization
plan: 02
subsystem: geocoding
tags: [cache, migration, alembic, normalization, refactor, file-cache-removal]

# Dependency graph
requires:
  - phase: 04-01
    provides: "normalize_address() pure function used by Alembic migration and repository"
provides:
  - "GoogleGeocoder as pure stateless API caller -- no file cache, no hashing"
  - "scripts/migrate_file_cache.py for one-time google_cache.json DB import (27 entries)"
  - "Alembic migration to re-normalize address_norm values and deduplicate collapsed entries"
  - "Upload endpoint using CachedGeocoder for unified cache-then-API flow"
  - "GeocodeCacheDB ORM model with __table_args__ UniqueConstraint matching init.sql"
affects: [duplicate-detection, geocoding-cache]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CachedGeocoder decorator pattern replaces manual cache-then-API logic in endpoints"
    - "Alembic data migration with Python function import for re-normalization"
    - "Backup column pattern (address_norm_old) for reversible data migrations"

key-files:
  created:
    - scripts/migrate_file_cache.py
    - infra/alembic/versions/deb08e55c8a2_renormalize_geocode_cache_addresses.py
  modified:
    - core/geocoding/google_adapter.py
    - core/database/models.py
    - apps/kerala_delivery/api/main.py
    - tests/core/geocoding/test_google_adapter.py

key-decisions:
  - "GoogleGeocoder stripped to pure API caller -- all caching delegated to CachedGeocoder"
  - "Alembic migration uses backup column for reversibility rather than down_revision rollback only"
  - "Upload endpoint falls back to cache-only lookup when no API key configured (graceful degradation)"

patterns-established:
  - "All geocoding in upload endpoint goes through CachedGeocoder -- never manual repo calls"
  - "GoogleGeocoder accepts only api_key and region_bias -- no cache parameters"

requirements-completed: [GEO-01, GEO-02]

# Metrics
duration: 5min
completed: 2026-03-01
---

# Phase 4 Plan 2: File Cache Deprecation and DB Consolidation Summary

**Stripped GoogleGeocoder to pure API caller, created file cache migration script (27 entries), Alembic re-normalization migration with deduplication, and refactored upload endpoint to use CachedGeocoder**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-01T22:39:00Z
- **Completed:** 2026-03-01T22:43:43Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments
- Removed all file cache code from GoogleGeocoder (_load_cache, _save_cache, _address_hash, cache_dir parameter, _cache dict) making it a pure stateless API caller
- Created scripts/migrate_file_cache.py that reads 27 google_cache.json entries and imports them via repo.save_geocode_cache() with proper normalize_address() normalization
- Created reversible Alembic migration (deb08e55c8a2) that re-normalizes all address_norm values using normalize_address() and deduplicates collapsed entries (keeps highest confidence, sums hit_counts)
- Refactored upload endpoint to use CachedGeocoder for unified cache-then-API flow, with cache-only fallback when no API key is configured
- Added UniqueConstraint to GeocodeCacheDB __table_args__ matching the init.sql UNIQUE(address_norm, source) constraint

## Task Commits

Each task was committed atomically:

1. **Task 1: Strip file cache from GoogleGeocoder, create migration script, update ORM model** - `8be2950` (feat)
2. **Task 2: Write Alembic re-normalization migration, update main.py and scripts** - `efb6afa` (feat)

## Files Created/Modified
- `core/geocoding/google_adapter.py` - Stripped to pure API caller: removed hashlib/json/pathlib imports, cache_dir param, _cache dict, _load_cache(), _save_cache(), _address_hash()
- `scripts/migrate_file_cache.py` - One-time script to import google_cache.json entries into PostgreSQL with normalize_address() normalization
- `infra/alembic/versions/deb08e55c8a2_renormalize_geocode_cache_addresses.py` - Alembic migration: backup address_norm, re-normalize via Python, deduplicate collapsed entries
- `core/database/models.py` - Added UniqueConstraint and __table_args__ to GeocodeCacheDB
- `apps/kerala_delivery/api/main.py` - Import CachedGeocoder, refactored upload geocoding loop to use CachedGeocoder with cache-only fallback
- `tests/core/geocoding/test_google_adapter.py` - Updated tests for stateless GoogleGeocoder (removed file cache tests, added API-per-call test)

## Decisions Made
- GoogleGeocoder stripped to pure API caller -- all caching delegated to CachedGeocoder (decorator pattern already existed, just needed to wire it into main.py)
- Alembic migration uses address_norm_old backup column for reversibility (can restore exact previous normalization on downgrade)
- Upload endpoint falls back to cache-only lookup via repo.get_cached_geocode() when no API key is configured -- previously this path was a silent failure

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated test fixture for GoogleGeocoder**
- **Found during:** Task 1 (Strip file cache from GoogleGeocoder)
- **Issue:** Test fixture passed cache_dir parameter and tests verified file cache behavior -- all broke after removing file cache from GoogleGeocoder
- **Fix:** Updated fixture to not pass cache_dir, replaced file-cache-specific tests (cache_prevents_duplicate_api_calls, cache_persists_to_disk, corrupt_cache_file_recovered, non_dict_content_recovered) with stateless API caller tests (each_geocode_call_hits_api, constructor_accepts_only_api_key_and_region_bias, no_file_cache_methods)
- **Files modified:** tests/core/geocoding/test_google_adapter.py
- **Verification:** Full test suite passes (394 tests)
- **Committed in:** 8be2950 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Test update was necessary consequence of removing file cache. No scope creep.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- All geocoding cache operations now go through PostgreSQL only
- normalize_address() is the single source of truth for cache key normalization (Plan 01)
- File cache code fully removed from GoogleGeocoder (Plan 02)
- Alembic migration ready to run on existing databases to re-normalize historical data
- scripts/migrate_file_cache.py ready to import 27 google_cache.json entries before archiving the file
- Phase 4 complete -- ready for Phase 5 (duplicate detection)
- Full test suite passes: 394 tests, zero regressions

## Self-Check: PASSED

All files exist. All commits verified.

---
*Phase: 04-geocoding-cache-normalization*
*Completed: 2026-03-01*
