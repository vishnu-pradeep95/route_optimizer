# Roadmap: Kerala LPG Delivery Route Optimizer

## Milestones

- ✅ **v1.0 Infrastructure** -- Phases 1-3 (shipped 2026-03-01)
- ✅ **v1.1 Polish & Reliability** -- Phases 4-7 (shipped 2026-03-03)
- ✅ **v1.2 Tech Debt & Cleanup** -- Phases 8-12 (shipped 2026-03-04)
- ✅ **v1.3 Office-Ready Deployment** -- Phases 13-20 (shipped 2026-03-07)
- 🚧 **v1.4 Ship-Ready QA** -- Phases 21-24 (in progress)

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

<details>
<summary>✅ v1.0 Infrastructure (Phases 1-3) -- SHIPPED 2026-03-01</summary>

- [x] Phase 1: Foundation (3/3 plans) -- completed 2026-03-01
- [x] Phase 2: Security Hardening (2/2 plans) -- completed 2026-03-01
- [x] Phase 3: Data Integrity (3/3 plans) -- completed 2026-03-01

</details>

<details>
<summary>✅ v1.1 Polish & Reliability (Phases 4-7) -- SHIPPED 2026-03-03</summary>

- [x] Phase 4: Geocoding Cache Normalization (2/2 plans) -- completed 2026-03-01
- [x] Phase 5: Geocoding Enhancements (2/2 plans) -- completed 2026-03-02
- [x] Phase 6: Dashboard UI Overhaul (9/9 plans) -- completed 2026-03-02
- [x] Phase 7: Driver PWA Refresh (3/3 plans) -- completed 2026-03-03

</details>

<details>
<summary>✅ v1.2 Tech Debt & Cleanup (Phases 8-12) -- SHIPPED 2026-03-04</summary>

- [x] Phase 8: API Dead Code & Hygiene (2/2 plans) -- completed 2026-03-03
- [x] Phase 9: Config Consolidation (1/1 plan) -- completed 2026-03-04
- [x] Phase 10: Driver PWA Hardening (2/2 plans) -- completed 2026-03-04
- [x] Phase 11: Dashboard Cleanup (2/2 plans) -- completed 2026-03-04
- [x] Phase 12: Data Wiring & Validation (2/2 plans) -- completed 2026-03-04

</details>

<details>
<summary>✅ v1.3 Office-Ready Deployment (Phases 13-20) -- SHIPPED 2026-03-07</summary>

- [x] Phase 13: Bootstrap Installation (1/1 plan) -- completed 2026-03-05
- [x] Phase 14: Daily Startup (2/2 plans) -- completed 2026-03-05
- [x] Phase 15: CSV Documentation (1/1 plan) -- completed 2026-03-05
- [x] Phase 16: Documentation Corrections (2/2 plans) -- completed 2026-03-05
- [x] Phase 17: Error Message Humanization (1/1 plan) -- completed 2026-03-06
- [x] Phase 18: Distribution Build (1/1 plan) -- completed 2026-03-06
- [x] Phase 19: Pin OSRM Docker Image (1/1 plan) -- completed 2026-03-07
- [x] Phase 20: Sync Error Message Documentation (1/1 plan) -- completed 2026-03-07

</details>

### 🚧 v1.4 Ship-Ready QA (In Progress)

**Milestone Goal:** Verify the full customer delivery pipeline works end-to-end -- automated E2E tests, CI/CD health, clean install verification, distribution documentation, and operational scripts for graceful shutdown.

- [ ] **Phase 21: Playwright E2E Test Suite** - Automated browser and API tests covering all critical user paths against running Docker stack
- [ ] **Phase 22: CI/CD Pipeline Integration** - E2E tests run automatically in GitHub Actions with failure artifacts and status visibility
- [ ] **Phase 23: Distribution Verification & Operational Scripts** - Clean install from tarball verified, graceful shutdown script with garbage collection
- [ ] **Phase 24: Documentation Consolidation** - Distribution workflow, license lifecycle, environment comparison, API key troubleshooting, and third-party attribution documented

## Phase Details

### Phase 21: Playwright E2E Test Suite
**Goal**: All critical user paths are verified by automated tests that run against the live Docker stack -- API endpoints, Driver PWA upload-to-delivery flow, Dashboard route display, and license validation
**Depends on**: Phase 20 (v1.3 complete -- stable codebase to test against)
**Requirements**: TEST-01, TEST-02, TEST-03, TEST-04, TEST-05
**Success Criteria** (what must be TRUE):
  1. Running `npx playwright test` from the project root executes all E2E tests against the Docker stack at localhost:8000, with zero manual setup beyond `docker compose up`
  2. A developer can upload a CSV through the Driver PWA, select a vehicle, view the route, mark stops done/failed, and see the all-done banner -- all verified by passing Playwright tests
  3. The Dashboard renders route cards, generates a QR sheet, and loads the map after upload -- verified by passing Playwright tests
  4. Accessing the API with an expired, missing, or invalid license key returns HTTP 503 -- verified by a passing Playwright test
  5. All 420+ existing pytest unit tests continue to pass (no regressions from E2E infrastructure additions)
**Plans**: 3 plans

Plans:
- [ ] 21-01-PLAN.md -- Playwright infrastructure (config, fixtures, helpers) + API endpoint tests (TEST-01, TEST-05)
- [ ] 21-02-PLAN.md -- Driver PWA E2E flow tests (TEST-02)
- [ ] 21-03-PLAN.md -- Dashboard E2E tests + License validation tests (TEST-03, TEST-04)

### Phase 22: CI/CD Pipeline Integration
**Goal**: E2E tests run automatically on every push to main, with clear failure diagnostics and visible project health status
**Depends on**: Phase 21 (tests must pass locally before CI integration)
**Requirements**: CICD-01, CICD-02, CICD-03, CICD-04
**Success Criteria** (what must be TRUE):
  1. Pushing a commit to main triggers a GitHub Actions workflow that passes all jobs including the new E2E job
  2. The E2E CI job starts the Docker Compose stack (without OSRM/VROOM), installs Chromium, runs Playwright tests with `--workers=1`, and tears down cleanly
  3. When an E2E test fails in CI, a Playwright HTML report is uploaded as a downloadable GitHub Actions artifact for debugging
  4. The project README.md displays a CI status badge that reflects the current pipeline health (green/red)
**Plans**: TBD

Plans:
- [ ] 22-01: TBD

### Phase 23: Distribution Verification & Operational Scripts
**Goal**: The actual customer deliverable (tarball from build-dist.sh) installs and runs correctly on a fresh environment, and operators have a safe shutdown script for daily use
**Depends on**: Phase 21 (E2E tests validate the running system that the tarball must reproduce)
**Requirements**: OPS-01, OPS-02, OPS-03
**Success Criteria** (what must be TRUE):
  1. Running `scripts/stop.sh` gracefully stops all Docker Compose services (containers halted, all data volumes preserved intact)
  2. Running `scripts/stop.sh --gc` additionally removes dangling images, orphan containers, and truncates container logs -- freeing disk space without destroying data
  3. A fresh environment (no prior git clone, no cached images) can unpack the build-dist.sh tarball, run the install/start scripts, and reach a healthy state where the API responds at /health and the Driver PWA loads
**Plans**: TBD

Plans:
- [ ] 23-01: TBD
- [ ] 23-02: TBD

### Phase 24: Documentation Consolidation
**Goal**: A customer or developer can understand the full distribution, licensing, environment setup, and troubleshooting workflow from documentation alone -- no tribal knowledge required
**Depends on**: Phase 23 (documentation references verified commands and workflows from earlier phases)
**Requirements**: DOCS-01, DOCS-02, DOCS-03, DOCS-04, DOCS-05
**Success Criteria** (what must be TRUE):
  1. A developer can follow the distribution documentation to build a tarball, generate a license, deliver it to a customer, and verify the install -- every step documented with exact commands
  2. A developer or customer can follow the license lifecycle documentation through generate, deliver, activate, monitor grace period, renew, and troubleshoot 503 errors -- each stage documented with expected outputs
  3. A developer can look up any production vs development difference (ports, volumes, environment variables, services, debug settings) in a single comparison document
  4. An office employee encountering a Google Maps error can follow the troubleshooting guide through Cloud Console setup, key validation, and resolution of common errors (REQUEST_DENIED, OVER_QUERY_LIMIT, INVALID_REQUEST)
  5. Third-party license obligations (OSM attribution, OSRM/VROOM licenses, Leaflet/Google Maps terms) are documented with required attribution text and compliance notes

**Plans**: TBD

Plans:
- [ ] 24-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 21 -> 22 -> 23 -> 24

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
| 12. Data Wiring & Validation | v1.2 | 2/2 | Complete | 2026-03-04 |
| 13. Bootstrap Installation | v1.3 | 1/1 | Complete | 2026-03-05 |
| 14. Daily Startup | v1.3 | 2/2 | Complete | 2026-03-05 |
| 15. CSV Documentation | v1.3 | 1/1 | Complete | 2026-03-05 |
| 16. Documentation Corrections | v1.3 | 2/2 | Complete | 2026-03-05 |
| 17. Error Message Humanization | v1.3 | 1/1 | Complete | 2026-03-06 |
| 18. Distribution Build | v1.3 | 1/1 | Complete | 2026-03-06 |
| 19. Pin OSRM Docker Image | v1.3 | 1/1 | Complete | 2026-03-07 |
| 20. Sync Error Message Documentation | v1.3 | 1/1 | Complete | 2026-03-07 |
| 21. Playwright E2E Test Suite | 1/3 | In Progress|  | - |
| 22. CI/CD Pipeline Integration | v1.4 | 0/? | Not started | - |
| 23. Distribution Verification & Ops | v1.4 | 0/? | Not started | - |
| 24. Documentation Consolidation | v1.4 | 0/? | Not started | - |

---
*Full phase details for v1.0-v1.3 archived in `.planning/milestones/`*
