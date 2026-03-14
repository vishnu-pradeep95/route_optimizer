# Roadmap: Kerala LPG Delivery Route Optimizer

## Milestones

- ✅ **v1.0 Infrastructure** -- Phases 1-3 (shipped 2026-03-01)
- ✅ **v1.1 Polish & Reliability** -- Phases 4-7 (shipped 2026-03-03)
- ✅ **v1.2 Tech Debt & Cleanup** -- Phases 8-12 (shipped 2026-03-04)
- ✅ **v1.3 Office-Ready Deployment** -- Phases 13-20 (shipped 2026-03-07)
- ✅ **v1.4 Ship-Ready QA** -- Phases 21-24 (shipped 2026-03-09)
- ✅ **v2.0 Documentation & Error Handling** -- Phases 1-4 (shipped 2026-03-10)
- ✅ **v2.1 Licensing & Distribution Security** -- Phases 5-10 (shipped 2026-03-11)
- ✅ **v2.2 Address Preprocessing Pipeline** -- Phases 11-15 (shipped 2026-03-12)
- 🚧 **v3.0 Driver-Centric Model** -- Phases 16-22 (in progress)

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
<summary>v2.1 Licensing & Distribution Security (Phases 5-10) -- SHIPPED 2026-03-11</summary>

- [x] Phase 5: Fingerprinting Overhaul (2/2 plans) -- completed 2026-03-10
- [x] Phase 6: Build Pipeline -- Dev-Mode Stripping and Cython Compilation (3/3 plans) -- completed 2026-03-10
- [x] Phase 7: Enforcement Module (2/2 plans) -- completed 2026-03-10
- [x] Phase 8: Runtime Protection (2/2 plans) -- completed 2026-03-11
- [x] Phase 9: License Management (2/2 plans) -- completed 2026-03-10
- [x] Phase 10: End-to-End Validation (2/2 plans) -- completed 2026-03-11

</details>

<details>
<summary>v2.2 Address Preprocessing Pipeline (Phases 11-15) -- SHIPPED 2026-03-12</summary>

- [x] Phase 11: Foundation Fixes (3/3 plans) -- completed 2026-03-11
- [x] Phase 12: Place Name Dictionary and Address Splitter (3/3 plans) -- completed 2026-03-12
- [x] Phase 13: Geocode Validation and Fallback Chain (3/3 plans) -- completed 2026-03-12
- [x] Phase 14: API Confidence Fields and Driver PWA Badge (2/2 plans) -- completed 2026-03-12
- [x] Phase 15: Integration Testing and Accuracy Metrics (2/2 plans) -- completed 2026-03-12

</details>

### v3.0 Driver-Centric Model (In Progress)

**Milestone Goal:** Replace the vehicle-fleet model with a driver-centric model where drivers are created from CDCMS CSV uploads, optimization runs per-driver (TSP), and the dashboard becomes the primary interface for office staff.

- [x] **Phase 16: Driver Database Foundation** - Driver entity with CRUD, fuzzy name matching, auto-creation from CSV, and driver management page (completed 2026-03-13)
- [x] **Phase 17: CSV Upload and XLSX Detection** - Fix .xlsx detection bug, add driver preview step, driver selection before processing (completed 2026-03-13)
- [x] **Phase 18: Address Preprocessing Fixes** - Fix trailing-letter split garbling, (H) expansion, PO concatenation, and tighten geocode validation (completed 2026-03-14)
- [x] **Phase 19: Per-Driver TSP Optimization** - Group orders by driver, run VROOM TSP per driver, store all routes under single optimization run (completed 2026-03-14)
- [ ] **Phase 20: UI Terminology Rename** - Change "Vehicle" to "Driver" in all dashboard labels while keeping API field names backward-compatible
- [ ] **Phase 21: Dashboard Settings and Cache Management** - Settings page with API key management, upload history, geocode cache stats and export/import
- [ ] **Phase 22: Google Routes Validation** - User-triggered OSRM vs Google Routes distance/time comparison with cost warning and confidence indicator

## Phase Details

### Phase 16: Driver Database Foundation
**Goal**: Users can manage drivers as first-class entities -- view, create, edit, deactivate -- and the system auto-creates drivers from CSV uploads without duplicates
**Depends on**: Phase 15 (v2.2 complete)
**Requirements**: DRV-01, DRV-02, DRV-03, DRV-04, DRV-05, DRV-06, DRV-07
**Success Criteria** (what must be TRUE):
  1. User can open the Driver Management page and see a list of all drivers with their name and active/inactive status
  2. User can add a new driver by name, edit an existing driver's name, and deactivate a driver -- all from the dashboard
  3. When a CSV with a DeliveryMan column is uploaded, any new driver names are auto-created in the database without duplicates (fuzzy matching catches "SURESH K" vs "SURESH KUMAR")
  4. The system starts with zero drivers -- no pre-loaded fleet data -- and the driver list grows organically from CSV uploads and manual additions
**Plans:** 3/3 plans complete
Plans:
- [ ] 16-01-PLAN.md -- Schema reshape, repository CRUD, fuzzy matching with RapidFuzz
- [ ] 16-02-PLAN.md -- Driver API endpoints, DriverManagement dashboard page, sidebar wiring
- [ ] 16-03-PLAN.md -- CSV upload auto-creation with fuzzy matching, driver summary in response

### Phase 17: CSV Upload and XLSX Detection
**Goal**: Users can upload both .csv and .xlsx CDCMS files, see which drivers are in the file, and select which drivers to process before optimization runs
**Depends on**: Phase 16
**Requirements**: CSV-01, CSV-02, CSV-03, CSV-04, CSV-05
**Success Criteria** (what must be TRUE):
  1. User can upload a CDCMS .xlsx file and have it correctly detected and parsed (not rejected as invalid format)
  2. After uploading a multi-driver CSV/XLSX, user sees a list of drivers found in the file with order counts before processing begins
  3. User can select a subset of drivers from the uploaded file to generate routes for (deselected drivers are skipped)
  4. System filters to "Allocated-Printed" OrderStatus by default and correctly parses columns regardless of column order in the file
**Plans:** 4/4 plans complete
Plans:
- [x] 17-01-PLAN.md -- Fix XLSX detection, parse-upload endpoint, TypeScript types and API client
- [x] 17-02-PLAN.md -- Upload-orders endpoint extension, driver preview UI with checkbox table and stats bar
- [x] 17-03-PLAN.md -- Gap closure: fix matched driver status from 'existing' to 'matched' in parse-upload
- [ ] 17-04-PLAN.md -- Gap closure: geocoding filter bug, Allocation Pending filter, button alignment

### Phase 18: Address Preprocessing Fixes
**Goal**: Address cleaning produces correct results for known garbling patterns and geocode validation uses a tighter geographic boundary
**Depends on**: Phase 15 (v2.2 complete, independent of Phases 16-17)
**Requirements**: ADDR-01, ADDR-02, ADDR-03, ADDR-04, ADDR-05
**Success Criteria** (what must be TRUE):
  1. Address containing "MUTTUNGAL" is preserved as one word (not split into "MUTTUN GAL" or similar by trailing-letter heuristic)
  2. Address containing "(H)" expands correctly to "House" without splitting or garbling adjacent words
  3. Address containing concatenated "PO" abbreviation (e.g., "MUTTUNGALPOBALAVADI") correctly separates "P.O." without mangling surrounding text
  4. Geocode results outside a 20km radius from the Vatakara depot (from config) are flagged as out-of-zone, using Vatakara depot as the centroid
**Plans:** 4/4 plans complete
Plans:
- [ ] 18-01-PLAN.md -- Fix (HO), (PO), and (H) regex patterns with unit tests
- [ ] 18-02-PLAN.md -- Zone radius 30->20km, env var config, dictionary rebuild, test updates
- [ ] 18-03-PLAN.md -- API config endpoint update, dashboard zone circle overlay
- [ ] 18-04-PLAN.md -- API-level pytest tests and Playwright E2E for address cleaning with Refill.xlsx

### Phase 19: Per-Driver TSP Optimization
**Goal**: Each driver's assigned orders are optimized independently as a TSP problem, producing optimal stop ordering per driver while maintaining fleet-wide visibility
**Depends on**: Phase 16, Phase 17
**Requirements**: OPT-01, OPT-02, OPT-03, OPT-04, OPT-05
**Success Criteria** (what must be TRUE):
  1. After CSV upload and driver selection, each driver's orders are grouped separately and optimized via VROOM with 1 vehicle (TSP), producing an optimal stop sequence per driver
  2. All per-driver routes from a single upload are stored under one optimization_run, visible together in the dashboard route list
  3. No order appears in more than one driver's route -- the system validates zero overlap post-optimization
  4. If geographic anomalies are detected across drivers (e.g., two drivers with interleaving delivery areas), validation warnings are surfaced in the optimization results
**Plans:** 3/3 plans complete
Plans:
- [ ] 19-01-PLAN.md -- TSP orchestrator module with tests, DB migration for vehicle_id column widening
- [ ] 19-02-PLAN.md -- Pipeline integration: DeliveryMan column check, replace fleet CVRP with per-driver TSP
- [ ] 19-03-PLAN.md -- Driver PWA QR-only access, QR sheet driver name titles

### Phase 20: UI Terminology Rename
**Goal**: The dashboard speaks in "Driver" terms everywhere users see text, while API field names remain backward-compatible for the Driver PWA
**Depends on**: Phase 16, Phase 19
**Requirements**: UI-01, UI-02, UI-03
**Success Criteria** (what must be TRUE):
  1. All dashboard headers, labels, navigation items, and table columns show "Driver" instead of "Vehicle" (e.g., "Driver Management", "Driver Routes", driver name in route cards)
  2. API responses continue to include vehicle_id fields -- the Driver PWA works without any changes
  3. The Fleet Management page is now the Driver Management page with driver-centric layout (driver names, not vehicle IDs, as primary identifiers)
**Plans**: TBD

### Phase 21: Dashboard Settings and Cache Management
**Goal**: Office staff can manage the Google Maps API key, review upload history, and inspect/export/import the geocode cache -- all from the dashboard
**Depends on**: Phase 16
**Requirements**: SET-01, SET-02, SET-03, SET-04, SET-05, SET-06
**Success Criteria** (what must be TRUE):
  1. User can enter or update the Google Maps API key on the Settings page, and it is stored server-side with only a masked version (e.g., "AIza...****1234") visible in the UI
  2. User can view upload history showing date, filename, driver count, and order count for each past upload
  3. User can view geocode cache statistics (total cached addresses, API calls made, estimated cost) on the Settings page
  4. User can export the entire geocode cache to a JSON file and import a cache JSON file from another machine
**Plans**: TBD

### Phase 22: Google Routes Validation
**Goal**: Users can manually compare a generated route against Google Routes API to assess OSRM routing accuracy, with clear cost transparency before each call
**Depends on**: Phase 19
**Requirements**: VAL-01, VAL-02, VAL-03, VAL-04
**Success Criteria** (what must be TRUE):
  1. User can click a "Validate with Google" button on a route card to trigger a Google Routes API comparison for that route
  2. After validation, the route card shows a side-by-side comparison of VROOM/OSRM vs Google distance and time, with a confidence indicator (green/amber/red based on delta percentage)
  3. Before the Google API call is made, a cost warning is displayed showing the estimated cost of the validation request
  4. Google Routes validation is never triggered automatically -- it only runs when the user explicitly clicks the validate button
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 16 → 17 → 18 → 19 → 20 → 21 → 22

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
| 13. Bootstrap Installation | v1.3 | 1/1 | Complete | 2026-03-05 |
| 14. Daily Startup | v1.3 | 2/2 | Complete | 2026-03-05 |
| 15. CSV Documentation | v1.3 | 1/1 | Complete | 2026-03-05 |
| 16. Documentation Corrections | 3/3 | Complete    | 2026-03-13 | 2026-03-05 |
| 17. Error Message Humanization | 4/4 | Complete    | 2026-03-13 | 2026-03-06 |
| 18. Distribution Build | 4/4 | Complete    | 2026-03-14 | 2026-03-06 |
| 19. Pin OSRM Docker Image | 3/3 | Complete    | 2026-03-14 | 2026-03-07 |
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
| 6. Build Pipeline -- Dev-Mode Stripping and Cython | v2.1 | 3/3 | Complete | 2026-03-10 |
| 7. Enforcement Module | v2.1 | 2/2 | Complete | 2026-03-10 |
| 8. Runtime Protection | v2.1 | 2/2 | Complete | 2026-03-11 |
| 9. License Management | v2.1 | 2/2 | Complete | 2026-03-10 |
| 10. End-to-End Validation | v2.1 | 2/2 | Complete | 2026-03-11 |
| 11. Foundation Fixes | v2.2 | 3/3 | Complete | 2026-03-11 |
| 12. Place Name Dictionary and Address Splitter | v2.2 | 3/3 | Complete | 2026-03-12 |
| 13. Geocode Validation and Fallback Chain | v2.2 | 3/3 | Complete | 2026-03-12 |
| 14. API Confidence Fields and Driver PWA Badge | v2.2 | 2/2 | Complete | 2026-03-12 |
| 15. Integration Testing and Accuracy Metrics | v2.2 | 2/2 | Complete | 2026-03-12 |
| 16. Driver Database Foundation | v3.0 | 0/3 | Not started | - |
| 17. CSV Upload and XLSX Detection | v3.0 | 3/4 | Gap closure | - |
| 18. Address Preprocessing Fixes | v3.0 | 0/4 | Not started | - |
| 19. Per-Driver TSP Optimization | v3.0 | 0/3 | Not started | - |
| 20. UI Terminology Rename | v3.0 | 0/TBD | Not started | - |
| 21. Dashboard Settings and Cache Management | v3.0 | 0/TBD | Not started | - |
| 22. Google Routes Validation | v3.0 | 0/TBD | Not started | - |

---
*Full phase details for v1.x and v2.x archived in `.planning/milestones/`*
