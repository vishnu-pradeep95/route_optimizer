# Phase 15: Integration Testing and Accuracy Metrics - Context

**Gathered:** 2026-03-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Verify the complete v2.2 address preprocessing pipeline end-to-end with real CDCMS data, measure accuracy metrics against defined thresholds, confirm the HDFC ERGO regression bug is fixed, and document the NER upgrade path with measurable triggers. Requirements: TEST-01, TEST-02, TEST-03, TEST-04.

</domain>

<decisions>
## Implementation Decisions

### Test execution strategy
- Mock all geocoding -- no live Google API calls in tests (API key is currently invalid; matches existing test_e2e_pipeline.py pattern)
- Standalone tests with pytest skip markers for Docker-dependent scenarios (matches test_osrm_vroom_pipeline.py pattern)
- Use the full `data/sample_cdcms_export.csv` (28 real addresses) as the primary test data source
- Test file: `tests/integration/test_address_pipeline.py` in the existing integration/ directory

### Metrics documentation format
- One-time snapshot documented in `METRICS.md` in `.planning/milestones/v2.2-phases/`
- Full pipeline report: three required thresholds (>90% success, <10% fallback, >80% dictionary coverage) PLUS per-method confidence breakdown (direct/area_retry/centroid/depot counts), address cleaning before/after examples, and individual address outcomes
- Not a repeatable pytest assertion -- this is a validation checkpoint, not ongoing CI enforcement

### HDFC ERGO regression test
- "Fixed" means: the address is recognized as out-of-zone by the validator, falls back to area centroid, and gets `location_approximate: true` -- no silent wrong location 40+ km away
- Two-layer testing: (1) address cleaning produces sensible output from the HDFC ERGO text, (2) mock out-of-zone geocode triggers the fallback chain correctly
- Use the actual HDFC ERGO address text from the original CDCMS data (not synthetic)

### NER upgrade document scope
- Lives as a section in `METRICS.md` (same file as accuracy measurements -- natural flow from "current numbers" to "when to upgrade")
- Audience: developer maintaining this codebase (technical)
- Content: thresholds from roadmap (>10% validation failures or >5% centroid fallback over 30-day window) + how to extract metrics from codebase + NER implementation sketch
- Implementation sketch includes: specific library recommendations (spaCy, HuggingFace, etc.), integration points in the pipeline, and training data requirements (how much labeled data, format, using historical CDCMS + validator results as weak labels)

### Claude's Discretion
- Mock geocoder implementation details (fixture structure, response factories)
- Exact pytest marker names and skip conditions
- METRICS.md document structure and formatting
- NER library evaluation criteria and specific recommendations
- Training data quantity estimates and labeling approach
- Test assertion granularity (per-address vs aggregate)
- Whether to include address cleaning examples as a separate METRICS.md section or inline

</decisions>

<specifics>
## Specific Ideas

- STATE.md flags "Google Maps API key is currently invalid (REQUEST_DENIED)" -- all tests must work without live API
- GeocodeValidator.stats already tracks: direct_count, area_retry_count, centroid_count, depot_count, circuit_breaker_trips -- use these for metrics
- CachedGeocoder.stats tracks: hits, misses, errors + 4 validation method breakdowns -- full picture available
- The "Problem -- fix action" error pattern from v1.3 should carry through to any test output messaging

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `GeocodeValidator` (core/geocoding/validator.py, 333 lines): `.stats` dict with 5 counters, `.validate()` returns ValidationResult with confidence + method
- `CachedGeocoder` (core/geocoding/cache.py, 392 lines): `.stats` dict with 7 counters, `.get_stats_summary()` for human-readable output
- `AddressSplitter` (core/data_import/address_splitter.py, 239 lines): Dictionary-powered splitting with fuzzy matching, 381 entries
- `clean_cdcms_address()` (core/data_import/cdcms_preprocessor.py, 595 lines): 13-step cleaning pipeline
- `data/sample_cdcms_export.csv`: 28 real CDCMS orders with concatenated addresses
- `data/place_names_vatakara.json`: 381 Kerala place names with centroids and aliases
- `tests/conftest.py`: Shared fixtures with Vatakara depot coordinates and sample locations
- `tests/test_e2e_pipeline.py` (420 lines): Full pipeline test pattern (CSV -> Order -> VROOM -> Route)
- `tests/integration/test_osrm_vroom_pipeline.py`: Skip marker pattern for Docker-dependent tests

### Established Patterns
- pytest skip markers: `@pytest.mark.skipif(not OSRM_AVAILABLE, ...)` for optional infrastructure
- Mock geocoding in test_e2e_pipeline.py: Deterministic coordinate responses
- Alembic migrations for schema changes
- ErrorResponse model with ErrorCodes for structured API errors

### Integration Points
- Upload pipeline in main.py (lines 1015-1070): Geocoding loop where validator hooks in
- GeocodingResult.method and .confidence: Pipeline-wide confidence tracking
- `preprocess_cdcms()`: CDCMS CSV -> DataFrame with area field available for testing

</code_context>

<deferred>
## Deferred Ideas

- Batch-level "all approximate" banner in Driver PWA when API key is invalid (tracked as AINT-03 in REQUIREMENTS.md)
- NER model implementation itself (conditional on metrics -- this phase only documents the criteria)
- Circuit breaker for bulk geocoding API failures with batch-level warning (tracked as AINT-02)

</deferred>

---

*Phase: 15-integration-testing-and-accuracy-metrics*
*Context gathered: 2026-03-11*
