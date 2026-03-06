# Deferred Items -- Phase 17

## Pre-existing Test Failures (Out of Scope)

The following tests fail because mock setup uses `get_active_vehicles = AsyncMock(return_value=[])`,
which triggers "No active vehicles configured" at the API boundary. This is a pre-existing mock
configuration issue, not caused by Phase 17 changes.

- `TestUploadAndOptimize::test_upload_csv_triggers_optimization`
- `TestMonsoonMultiplier::test_monsoon_multiplier_applied_in_july`
- `TestMonsoonMultiplier::test_no_monsoon_in_january`
- `TestGeocodeCacheHit::test_cache_hit_skips_google_api`
- `TestAuthentication::test_upload_accepts_correct_key`
- `TestCdcmsAutoDetection::test_cdcms_file_detected_and_preprocessed`
- `TestCdcmsAutoDetection::test_standard_csv_not_treated_as_cdcms`
- `TestFullUploadOptimizePipeline::test_upload_creates_routes`
- `TestFullUploadOptimizePipeline::test_upload_returns_distance_metrics`

**Fix:** Update mocks to return at least one vehicle in `get_active_vehicles`.
