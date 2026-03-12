# Roadmap: Kerala LPG Delivery Route Optimizer

## Milestones

- ✅ **v1.0 Infrastructure** -- Phases 1-3 (shipped 2026-03-01)
- ✅ **v1.1 Polish & Reliability** -- Phases 4-7 (shipped 2026-03-03)
- ✅ **v1.2 Tech Debt & Cleanup** -- Phases 8-12 (shipped 2026-03-04)
- ✅ **v1.3 Office-Ready Deployment** -- Phases 13-20 (shipped 2026-03-07)
- ✅ **v1.4 Ship-Ready QA** -- Phases 21-24 (shipped 2026-03-09)
- ✅ **v2.0 Documentation & Error Handling** -- Phases 1-4 (shipped 2026-03-10)
- 🚧 **v2.1 Licensing & Distribution Security** -- Phases 5-10 (in progress, main branch)
- 🚧 **v2.2 Address Preprocessing Pipeline** -- Phases 11-15 (in progress, fix/unexpected-route-locations branch)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

<details>
<summary>v1.0 Infrastructure (Phases 1-3) -- SHIPPED 2026-03-01</summary>

- [x] Phase 1: Foundation (3/3 plans) -- completed 2026-03-01
- [x] Phase 2: Security Hardening (2/2 plans) -- completed 2026-03-01
- [x] Phase 3: Data Integrity (3/3 plans) -- completed 2026-03-01

</details>

<details>
<summary>v1.1 Polish & Reliability (Phases 4-7) -- SHIPPED 2026-03-03</summary>

- [x] Phase 4: Geocoding Cache Normalization (2/2 plans) -- completed 2026-03-01
- [x] Phase 5: Geocoding Enhancements (2/2 plans) -- completed 2026-03-02
- [x] Phase 6: Dashboard UI Overhaul (9/9 plans) -- completed 2026-03-02
- [x] Phase 7: Driver PWA Refresh (3/3 plans) -- completed 2026-03-03

</details>

<details>
<summary>v1.2 Tech Debt & Cleanup (Phases 8-12) -- SHIPPED 2026-03-04</summary>

- [x] Phase 8: API Dead Code & Hygiene (2/2 plans) -- completed 2026-03-03
- [x] Phase 9: Config Consolidation (1/1 plan) -- completed 2026-03-04
- [x] Phase 10: Driver PWA Hardening (2/2 plans) -- completed 2026-03-04
- [x] Phase 11: Dashboard Cleanup (2/2 plans) -- completed 2026-03-04
- [x] Phase 12: Data Wiring & Validation (2/2 plans) -- completed 2026-03-04

</details>

<details>
<summary>v1.3 Office-Ready Deployment (Phases 13-20) -- SHIPPED 2026-03-07</summary>

- [x] Phase 13: Bootstrap Installation (1/1 plan) -- completed 2026-03-05
- [x] Phase 14: Daily Startup (2/2 plans) -- completed 2026-03-05
- [x] Phase 15: CSV Documentation (1/1 plan) -- completed 2026-03-05
- [x] Phase 16: Documentation Corrections (2/2 plans) -- completed 2026-03-05
- [x] Phase 17: Error Message Humanization (1/1 plan) -- completed 2026-03-06
- [x] Phase 18: Distribution Build (1/1 plan) -- completed 2026-03-06
- [x] Phase 19: Pin OSRM Docker Image (1/1 plan) -- completed 2026-03-07
- [x] Phase 20: Sync Error Message Documentation (1/1 plan) -- completed 2026-03-07

</details>

<details>
<summary>v1.4 Ship-Ready QA (Phases 21-24) -- SHIPPED 2026-03-09</summary>

- [x] Phase 21: Playwright E2E Test Suite (3/3 plans) -- completed 2026-03-08
- [x] Phase 22: CI/CD Pipeline Integration (2/2 plans) -- completed 2026-03-08
- [x] Phase 23: Distribution Verification & Ops (2/2 plans) -- completed 2026-03-08
- [x] Phase 24: Documentation Consolidation (3/3 plans) -- completed 2026-03-09

</details>

<details>
<summary>v2.0 Documentation & Error Handling (Phases 1-4) -- SHIPPED 2026-03-10</summary>

- [x] Phase 1: Documentation Restructure & Validation (2/2 plans) -- completed 2026-03-09
- [x] Phase 2: Error Handling Infrastructure (4/4 plans) -- completed 2026-03-10
- [x] Phase 3: Error Handling Polish (1/1 plan) -- completed 2026-03-10
- [x] Phase 4: Documentation Accuracy Refresh (2/2 plans) -- completed 2026-03-10

</details>

<details>
<summary>v2.1 Licensing & Distribution Security (Phases 5-10) -- IN PROGRESS (main branch)</summary>

- [x] **Phase 5: Fingerprinting Overhaul** - Replace unstable Docker/MAC fingerprint with machine-id + CPU model signals
- [ ] **Phase 6: Build Pipeline -- Dev-Mode Stripping and Cython Compilation** - Strip dev bypass from builds and compile licensing modules to native .so
- [ ] **Phase 7: Enforcement Module** - Move enforcement logic and integrity manifest into compiled module with single entry point
- [ ] **Phase 8: Runtime Protection** - Add periodic license and integrity re-validation during operation
- [ ] **Phase 9: License Management** - Renewal mechanism and expiry visibility for monitoring
- [ ] **Phase 10: End-to-End Validation** - E2E tests exercising the full security pipeline plus customer migration documentation

</details>

### v2.2 Address Preprocessing Pipeline (In Progress)

**Milestone Goal:** Fix wrong route locations caused by concatenated CDCMS addresses and unvalidated geocoding results -- every address must geocode within the delivery zone or be flagged as approximate.

- [x] **Phase 11: Foundation Fixes** - Fix address_display source and improve regex word splitting for CDCMS concatenation patterns (completed 2026-03-11)
- [x] **Phase 12: Place Name Dictionary and Address Splitter** - Build domain-specific dictionary from OSM/India Post and implement dictionary-powered word splitting (completed 2026-03-12)
- [ ] **Phase 13: Geocode Validation and Fallback Chain** - Validate geocoded coordinates against delivery zone with automatic retry and centroid fallback
- [ ] **Phase 14: API Confidence Fields and Driver PWA Badge** - Surface geocode confidence through the API and display approximate location warnings to drivers
- [ ] **Phase 15: Integration Testing and Accuracy Metrics** - End-to-end pipeline verification with accuracy measurements and NER upgrade criteria

## Phase Details

<details>
<summary>v2.1 Phase Details (Phases 5-10) -- see main branch</summary>

### Phase 5: Fingerprinting Overhaul
**Goal**: Machine identity is stable across container recreation, WSL reboots, and routine Docker operations
**Depends on**: Nothing (first phase in v2.1)
**Requirements**: FPR-01, FPR-02, FPR-03
**Success Criteria** (what must be TRUE):
  1. Running `get_machine_id.py` on the host produces the same fingerprint before and after a WSL restart
  2. Running `get_machine_id.py` inside the Docker API container produces the same fingerprint as the host script
  3. Rebuilding or recreating the API container (`docker compose up -d --force-recreate api`) does not change the fingerprint
  4. The fingerprint formula uses `/etc/machine-id` and `/proc/cpuinfo` CPU model (not container ID or MAC address)
**Plans**: 2 plans

Plans:
- [x] 05-01-PLAN.md -- TDD fingerprint formula: MAC decision + tests + implementation in license_manager.py and get_machine_id.py
- [x] 05-02-PLAN.md -- Docker bind mounts + integration verification of host-container fingerprint match

### Phase 6: Build Pipeline -- Dev-Mode Stripping and Cython Compilation
**Goal**: Distributed builds contain no dev-mode bypass and licensing modules are compiled to native machine code
**Depends on**: Phase 5 (new fingerprint formula must be in place before compiling)
**Requirements**: ENF-01, ENF-02, ENF-04, BLD-01, BLD-02, BLD-03
**Success Criteria** (what must be TRUE):
  1. Running `grep -r "ENVIRONMENT"` on an unpacked distribution tarball returns zero matches in Python source files
  2. The distribution tarball contains `.so` files (not `.py` or `.pyc`) for all `core/licensing/` modules
  3. Running `python -c "from core.licensing.license_manager import get_machine_fingerprint"` inside a Docker container built from the tarball succeeds (no ImportError)
  4. The HMAC derivation seed in the compiled `.so` differs from the seed in any previously shipped `.pyc` file
  5. `build-dist.sh` completes without errors and produces a tarball with the correct pipeline ordering (strip -> hash -> compile -> validate -> package)
**Plans**: TBD

### Phase 7: Enforcement Module
**Goal**: All enforcement logic lives in a compiled module with a single entry point; main.py contains no inline enforcement code
**Depends on**: Phase 6 (Cython compilation pipeline must be working)
**Requirements**: ENF-03, RTP-01
**Success Criteria** (what must be TRUE):
  1. `main.py` calls `enforce(app)` (or equivalent single function) and contains zero lines of license validation, middleware registration, or enforcement logic
  2. A SHA256 integrity manifest of protected files is embedded in the compiled `.so` and verified at startup -- tampering with `main.py` causes the API to refuse to start with a clear error
  3. The enforcement module stores license state internally (not on `app.state` or any other Python-accessible object)
**Plans**: TBD

### Phase 8: Runtime Protection
**Goal**: License validity and file integrity are continuously verified during operation, not just at startup
**Depends on**: Phase 7 (enforcement module with integrity checking must exist)
**Requirements**: RTP-02, RTP-03
**Success Criteria** (what must be TRUE):
  1. After the API has been running and served 500+ requests, modifying a protected file (e.g., `main.py`) causes the next request to fail with a license/integrity error
  2. After the API has been running and served 500+ requests with an expired license, the next periodic check causes requests to fail with a license expiry error
  3. Re-validation runs fully offline (no network calls) and does not block the event loop (response latency stays under 100ms during re-validation)
**Plans**: TBD

### Phase 9: License Management
**Goal**: License renewal is a simple file drop without re-keying, and license expiry is visible to monitoring tools
**Depends on**: Phase 5 (stable fingerprint for renewal keys)
**Requirements**: LIC-01, LIC-02, LIC-03
**Success Criteria** (what must be TRUE):
  1. Generating a renewal key with `generate_license.py --renew` and dropping it as `renewal.key` in the deployment extends the license expiry without requiring a new fingerprint exchange
  2. API responses include an `X-License-Expires-In` header showing remaining days (e.g., `X-License-Expires-In: 45d`)
  3. The `/health` endpoint body includes license status fields (valid/expired/grace period, expiry date, fingerprint match)
**Plans**: TBD

### Phase 10: End-to-End Validation
**Goal**: The complete v2.1 security pipeline is tested end-to-end and customer migration is documented
**Depends on**: Phase 8, Phase 9 (all features must be implemented before full integration testing)
**Requirements**: DOC-01, DOC-02, DOC-03
**Success Criteria** (what must be TRUE):
  1. Playwright E2E tests pass for: integrity tamper detection, periodic re-validation triggering, license renewal via file drop, and fingerprint mismatch rejection
  2. `docs/LICENSING.md` documents the new fingerprint formula, renewal workflow, integrity checking, and periodic re-validation
  3. `docs/SETUP.md` and `docs/ERROR-MAP.md` are updated with all new error messages and configuration changes from v2.1
  4. A customer migration document exists with step-by-step instructions for transitioning from the old fingerprint/HMAC to the new one (covering the breaking change)
**Plans**: TBD

</details>

### Phase 11: Foundation Fixes
**Goal**: Drivers see the correct original address text for every stop, and common CDCMS concatenation patterns are automatically split into readable words
**Depends on**: Nothing (first phase in v2.2; independent of v2.1)
**Requirements**: ADDR-01, ADDR-02, ADDR-03
**Success Criteria** (what must be TRUE):
  1. The Driver PWA hero card and compact cards display the cleaned original CDCMS address (address_raw), not Google's formatted_address, for every delivery stop
  2. The "Navigate" button in the Driver PWA opens Google Maps with the original address text, and Google Maps finds a usable location
  3. Concatenated CDCMS text like `ANANDAMANDIRAMK` is split at the lowercase-to-uppercase transition into `ANANDAMANDIRAM K`
  4. Abbreviation expansion (NR -> Nagar, PO -> P.O.) runs after word splitting so that abbreviations at word boundaries are correctly detected
  5. All existing unit tests for `clean_cdcms_address()` continue to pass (no regressions from step reordering)
**Plans**: 3 plans

Plans:
- [x] 11-01-PLAN.md -- TDD: Word splitting regex and abbreviation step reorder in clean_cdcms_address()
- [x] 11-02-PLAN.md -- Backend data flow fix: address_original column, address_display bug fix, API response update
- [x] 11-03-PLAN.md -- Driver PWA dual-address display and coordinate-based navigation

### Phase 12: Place Name Dictionary and Address Splitter
**Goal**: A domain-specific Kerala place name dictionary powers intelligent word splitting of concatenated CDCMS text, correctly separating addresses like `MUTTUNGALPOBALAVADI` into `MUTTUNGAL P.O. BALAVADI`
**Depends on**: Phase 11 (step reordering in clean_cdcms_address must be complete before splitter integrates)
**Requirements**: ADDR-04, ADDR-05, ADDR-06
**Success Criteria** (what must be TRUE):
  1. `data/place_names_vatakara.json` exists in the repo with 200+ place name entries covering the Vatakara delivery zone
  2. The dictionary covers >80% of distinct area names found in historical CDCMS data (hard gate before proceeding to Phase 13)
  3. Running the build script (`scripts/build_place_dictionary.py`) regenerates the dictionary from OSM Overpass and India Post APIs
  4. Concatenated address text containing known place names is split at place name boundaries (e.g., `MUTTUNGALPOBALAVADI` -> `MUTTUNGAL P.O. BALAVADI`)
  5. Fuzzy matching handles transliteration variants (e.g., `VATAKARA` / `VADAKARA`) without false positives on short names (length-dependent thresholds prevent `EDAPPAL` matching `EDAPALLI`)
**Plans**: 3 plans

Plans:
- [x] 12-01-PLAN.md -- Build place name dictionary from OSM Overpass + India Post APIs + manual seeds
- [x] 12-02-PLAN.md -- TDD: AddressSplitter class with fuzzy matching for transliteration variants
- [x] 12-03-PLAN.md -- Wire splitter into clean_cdcms_address() pipeline and validate coverage gate

### Phase 13: Geocode Validation and Fallback Chain
**Goal**: Every geocoded delivery address is validated against the 30km delivery zone, with automatic fallback to area-level coordinates when Google returns an out-of-zone result
**Depends on**: Phase 12 (dictionary provides area centroid coordinates for fallback)
**Requirements**: GVAL-01, GVAL-02, GVAL-03, GVAL-04
**Success Criteria** (what must be TRUE):
  1. Uploading a CSV where an address geocodes to a location >30km from the Vatakara depot triggers an automatic area-name retry (not silently accepted)
  2. When the area-name retry also fails zone validation, the stop receives centroid coordinates from the place name dictionary and a confidence score of 0.3
  3. A stop that geocodes correctly within the 30km zone on the first try receives a confidence score of 1.0
  4. Three consecutive Google API `REQUEST_DENIED` responses activate a circuit breaker that stops retries for the remainder of the batch
  5. The CachedGeocoder accepts the validator as an optional parameter and works identically to before when no validator is provided (backward compatible)
**Plans**: 3 plans

Plans:
- [ ] 13-01-PLAN.md -- TDD: GeocodeValidator class with zone check, fallback chain, and circuit breaker
- [ ] 13-02-PLAN.md -- GeocodingResult method field, OrderDB migration, CachedGeocoder validator integration
- [ ] 13-03-PLAN.md -- Wire validator into upload pipeline with area_name mapping and confidence propagation

### Phase 14: API Confidence Fields and Driver PWA Badge
**Goal**: Drivers can see at a glance which delivery stops have approximate locations, so they know when to expect navigation imprecision
**Depends on**: Phase 13 (confidence values must come from zone-validated pipeline, not raw Google confidence)
**Requirements**: APUI-01, APUI-02, APUI-03, APUI-04
**Success Criteria** (what must be TRUE):
  1. `GET /api/routes/{vehicle_id}` response includes `geocode_confidence` (float) and `location_approximate` (boolean) for each stop
  2. The Driver PWA hero card displays an "Approx. location" warning badge (DaisyUI badge-warning) when the current stop has `location_approximate: true`
  3. The Driver PWA compact cards show an orange dot indicator next to stops with `location_approximate: true`
  4. Pre-upgrade routes with no confidence data (null) render without badges or errors (graceful null handling)
**Plans**: TBD

Plans:
- [ ] 14-01: TBD
- [ ] 14-02: TBD

### Phase 15: Integration Testing and Accuracy Metrics
**Goal**: The complete address preprocessing pipeline is verified end-to-end with real CDCMS data, accuracy metrics are measured, and the upgrade path to NER is documented with measurable triggers
**Depends on**: Phase 14 (full pipeline including UI must be assembled before integration testing)
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04
**Success Criteria** (what must be TRUE):
  1. A sample CDCMS CSV processed through the full pipeline produces routes where every stop geocodes within 30km of the depot or is flagged with `location_approximate: true`
  2. The known "HDFC ERGO" wrong-location bug is verified fixed -- the address that previously geocoded 40+ km away now either geocodes correctly or is flagged approximate with area-level coordinates
  3. Measured accuracy metrics meet targets: geocode success rate >90%, centroid fallback rate <10%, dictionary coverage >80% of area names
  4. A documented upgrade criteria section specifies that Approach B (NER model) is triggered when validation failures exceed 10% or centroid fallback exceeds 5% over a 30-day window
**Plans**: TBD

Plans:
- [ ] 15-01: TBD
- [ ] 15-02: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 11 -> 12 -> 13 -> 14 -> 15

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Foundation | v1.0 | 3/3 | Complete | 2026-03-01 |
| 2. Security Hardening | v1.0 | 2/2 | Complete | 2026-03-01 |
| 3. Data Integrity | v1.0 | 3/3 | Complete | 2026-03-01 |
| 4. Geocoding Cache Normalization | v1.1 | 2/2 | Complete | 2026-03-01 |
| 5. Geocoding Enhancements | v1.1 | 2/2 | Complete | 2026-03-02 |
| 6. Dashboard UI Overhaul | v1.1 | 9/9 | Complete | 2026-03-02 |
| 7. Driver PWA Refresh | v1.1 | 3/3 | Complete | 2026-03-03 |
| 8. API Dead Code & Hygiene | v1.2 | 2/2 | Complete | 2026-03-03 |
| 9. Config Consolidation | v1.2 | 1/1 | Complete | 2026-03-04 |
| 10. Driver PWA Hardening | v1.2 | 2/2 | Complete | 2026-03-04 |
| 11. Dashboard Cleanup | v1.2 | 2/2 | Complete | 2026-03-04 |
| 12. Data Wiring & Validation | v1.2 | 3/3 | Complete | 2026-03-04 |
| 13. Bootstrap Installation | 1/3 | In Progress|  | 2026-03-05 |
| 14. Daily Startup | v1.3 | 2/2 | Complete | 2026-03-05 |
| 15. CSV Documentation | v1.3 | 1/1 | Complete | 2026-03-05 |
| 16. Documentation Corrections | v1.3 | 2/2 | Complete | 2026-03-05 |
| 17. Error Message Humanization | v1.3 | 1/1 | Complete | 2026-03-06 |
| 18. Distribution Build | v1.3 | 1/1 | Complete | 2026-03-06 |
| 19. Pin OSRM Docker Image | v1.3 | 1/1 | Complete | 2026-03-07 |
| 20. Sync Error Message Documentation | v1.3 | 1/1 | Complete | 2026-03-07 |
| 21. Playwright E2E Test Suite | v1.4 | 3/3 | Complete | 2026-03-08 |
| 22. CI/CD Pipeline Integration | v1.4 | 2/2 | Complete | 2026-03-08 |
| 23. Distribution Verification & Ops | v1.4 | 2/2 | Complete | 2026-03-08 |
| 24. Documentation Consolidation | v1.4 | 3/3 | Complete | 2026-03-09 |
| 1. Documentation Restructure & Validation | v2.0 | 2/2 | Complete | 2026-03-09 |
| 2. Error Handling Infrastructure | v2.0 | 4/4 | Complete | 2026-03-10 |
| 3. Error Handling Polish | v2.0 | 1/1 | Complete | 2026-03-10 |
| 4. Documentation Accuracy Refresh | v2.0 | 2/2 | Complete | 2026-03-10 |
| 5. Fingerprinting Overhaul | v2.1 | 2/2 | Complete | 2026-03-10 |
| 6. Build Pipeline -- Dev-Mode Stripping and Cython | v2.1 | 0/? | Not started | - |
| 7. Enforcement Module | v2.1 | 0/? | Not started | - |
| 8. Runtime Protection | v2.1 | 0/? | Not started | - |
| 9. License Management | v2.1 | 0/? | Not started | - |
| 10. End-to-End Validation | v2.1 | 0/? | Not started | - |
| 11. Foundation Fixes | v2.2 | 3/3 | Complete | 2026-03-11 |
| 12. Place Name Dictionary and Address Splitter | v2.2 | 3/3 | Complete | 2026-03-12 |
| 13. Geocode Validation and Fallback Chain | v2.2 | 0/3 | Planned | - |
| 14. API Confidence Fields and Driver PWA Badge | v2.2 | 0/? | Not started | - |
| 15. Integration Testing and Accuracy Metrics | v2.2 | 0/? | Not started | - |

---
*Full phase details archived in `.planning/milestones/`*
