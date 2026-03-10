# Roadmap: Kerala LPG Delivery Route Optimizer

## Milestones

- ✅ **v1.0 Infrastructure** -- Phases 1-3 (shipped 2026-03-01)
- ✅ **v1.1 Polish & Reliability** -- Phases 4-7 (shipped 2026-03-03)
- ✅ **v1.2 Tech Debt & Cleanup** -- Phases 8-12 (shipped 2026-03-04)
- ✅ **v1.3 Office-Ready Deployment** -- Phases 13-20 (shipped 2026-03-07)
- ✅ **v1.4 Ship-Ready QA** -- Phases 21-24 (shipped 2026-03-09)
- ✅ **v2.0 Documentation & Error Handling** -- Phases 1-4 (shipped 2026-03-10)
- 🚧 **v2.1 Licensing & Distribution Security** -- Phases 5-10 (in progress)

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

<details>
<summary>✅ v1.4 Ship-Ready QA (Phases 21-24) -- SHIPPED 2026-03-09</summary>

- [x] Phase 21: Playwright E2E Test Suite (3/3 plans) -- completed 2026-03-08
- [x] Phase 22: CI/CD Pipeline Integration (2/2 plans) -- completed 2026-03-08
- [x] Phase 23: Distribution Verification & Ops (2/2 plans) -- completed 2026-03-08
- [x] Phase 24: Documentation Consolidation (3/3 plans) -- completed 2026-03-09

</details>

<details>
<summary>✅ v2.0 Documentation & Error Handling (Phases 1-4) -- SHIPPED 2026-03-10</summary>

- [x] Phase 1: Documentation Restructure & Validation (2/2 plans) -- completed 2026-03-09
- [x] Phase 2: Error Handling Infrastructure (4/4 plans) -- completed 2026-03-10
- [x] Phase 3: Error Handling Polish (1/1 plan) -- completed 2026-03-10
- [x] Phase 4: Documentation Accuracy Refresh (2/2 plans) -- completed 2026-03-10

</details>

### 🚧 v2.1 Licensing & Distribution Security (In Progress)

**Milestone Goal:** Close all identified loopholes in the licensing and distribution system that allow customers to circumvent license enforcement.

- [ ] **Phase 5: Fingerprinting Overhaul** - Replace unstable Docker/MAC fingerprint with machine-id + CPU model signals
- [ ] **Phase 6: Build Pipeline -- Dev-Mode Stripping and Cython Compilation** - Strip dev bypass from builds and compile licensing modules to native .so
- [ ] **Phase 7: Enforcement Module** - Move enforcement logic and integrity manifest into compiled module with single entry point
- [ ] **Phase 8: Runtime Protection** - Add periodic license and integrity re-validation during operation
- [ ] **Phase 9: License Management** - Renewal mechanism and expiry visibility for monitoring
- [ ] **Phase 10: End-to-End Validation** - E2E tests exercising the full security pipeline plus customer migration documentation

## Phase Details

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
- [ ] 05-01-PLAN.md — TDD fingerprint formula: MAC decision + tests + implementation in license_manager.py and get_machine_id.py
- [ ] 05-02-PLAN.md — Docker bind mounts + integration verification of host-container fingerprint match

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

Plans:
- [ ] 06-01: TBD
- [ ] 06-02: TBD
- [ ] 06-03: TBD

### Phase 7: Enforcement Module
**Goal**: All enforcement logic lives in a compiled module with a single entry point; main.py contains no inline enforcement code
**Depends on**: Phase 6 (Cython compilation pipeline must be working)
**Requirements**: ENF-03, RTP-01
**Success Criteria** (what must be TRUE):
  1. `main.py` calls `enforce(app)` (or equivalent single function) and contains zero lines of license validation, middleware registration, or enforcement logic
  2. A SHA256 integrity manifest of protected files is embedded in the compiled `.so` and verified at startup -- tampering with `main.py` causes the API to refuse to start with a clear error
  3. The enforcement module stores license state internally (not on `app.state` or any other Python-accessible object)
**Plans**: TBD

Plans:
- [ ] 07-01: TBD
- [ ] 07-02: TBD

### Phase 8: Runtime Protection
**Goal**: License validity and file integrity are continuously verified during operation, not just at startup
**Depends on**: Phase 7 (enforcement module with integrity checking must exist)
**Requirements**: RTP-02, RTP-03
**Success Criteria** (what must be TRUE):
  1. After the API has been running and served 500+ requests, modifying a protected file (e.g., `main.py`) causes the next request to fail with a license/integrity error
  2. After the API has been running and served 500+ requests with an expired license, the next periodic check causes requests to fail with a license expiry error
  3. Re-validation runs fully offline (no network calls) and does not block the event loop (response latency stays under 100ms during re-validation)
**Plans**: TBD

Plans:
- [ ] 08-01: TBD

### Phase 9: License Management
**Goal**: License renewal is a simple file drop without re-keying, and license expiry is visible to monitoring tools
**Depends on**: Phase 5 (stable fingerprint for renewal keys)
**Requirements**: LIC-01, LIC-02, LIC-03
**Success Criteria** (what must be TRUE):
  1. Generating a renewal key with `generate_license.py --renew` and dropping it as `renewal.key` in the deployment extends the license expiry without requiring a new fingerprint exchange
  2. API responses include an `X-License-Expires-In` header showing remaining days (e.g., `X-License-Expires-In: 45d`)
  3. The `/health` endpoint body includes license status fields (valid/expired/grace period, expiry date, fingerprint match)
**Plans**: TBD

Plans:
- [ ] 09-01: TBD
- [ ] 09-02: TBD

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

Plans:
- [ ] 10-01: TBD
- [ ] 10-02: TBD
- [ ] 10-03: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 5 -> 6 -> 7 -> 8 -> 9 -> 10
(Phase 9 depends on Phase 5, not Phase 8, so could theoretically run after Phase 5, but sequencing after Phase 8 avoids context-switching)

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
| 21. Playwright E2E Test Suite | v1.4 | 3/3 | Complete | 2026-03-08 |
| 22. CI/CD Pipeline Integration | v1.4 | 2/2 | Complete | 2026-03-08 |
| 23. Distribution Verification & Ops | v1.4 | 2/2 | Complete | 2026-03-08 |
| 24. Documentation Consolidation | v1.4 | 3/3 | Complete | 2026-03-09 |
| 1. Documentation Restructure & Validation | v2.0 | 2/2 | Complete | 2026-03-09 |
| 2. Error Handling Infrastructure | v2.0 | 4/4 | Complete | 2026-03-10 |
| 3. Error Handling Polish | v2.0 | 1/1 | Complete | 2026-03-10 |
| 4. Documentation Accuracy Refresh | v2.0 | 2/2 | Complete | 2026-03-10 |
| 5. Fingerprinting Overhaul | v2.1 | 0/2 | Not started | - |
| 6. Build Pipeline -- Dev-Mode Stripping and Cython | v2.1 | 0/? | Not started | - |
| 7. Enforcement Module | v2.1 | 0/? | Not started | - |
| 8. Runtime Protection | v2.1 | 0/? | Not started | - |
| 9. License Management | v2.1 | 0/? | Not started | - |
| 10. End-to-End Validation | v2.1 | 0/? | Not started | - |

---
*Full phase details archived in `.planning/milestones/`*
