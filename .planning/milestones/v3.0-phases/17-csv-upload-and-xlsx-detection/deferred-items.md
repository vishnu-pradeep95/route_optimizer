# Deferred Items - Phase 17

## Pre-existing Rate Limit Test Interaction

**Found during:** 17-01 Task 1 regression check
**File:** tests/apps/kerala_delivery/api/test_api.py
**Test:** TestUploadAutoCreatesDrivers::test_upload_driver_names_title_cased_in_summary
**Issue:** This test intermittently fails with 429 Too Many Requests when run as part of the full test suite. The rate limiter counter bleeds across test classes even with `RATE_LIMIT_ENABLED=false` and `limiter.enabled = False`. The test passes in isolation.
**Impact:** Low -- only affects test suite when run in full; does not affect production behavior.
**Not caused by Phase 17 changes** -- reproduces with all new tests excluded.
