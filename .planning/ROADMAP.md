# Roadmap: Kerala LPG Delivery Route Optimizer

## Milestones

- ✅ **v1.0 Infrastructure** -- Phases 1-3 (shipped 2026-03-01)
- ✅ **v1.1 Polish & Reliability** -- Phases 4-7 (shipped 2026-03-03)
- ✅ **v1.2 Tech Debt & Cleanup** -- Phases 8-12 (shipped 2026-03-04)
- [ ] **v1.3 Office-Ready Deployment** -- Phases 13-18 (in progress)

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

### v1.3 Office-Ready Deployment (In Progress)

**Milestone Goal:** Make the system installable and usable by a non-technical office employee -- one-command install from WSL, one-command daily startup, comprehensive documentation of CSV formats and workflow.

- [x] **Phase 13: Bootstrap Installation** - One-command WSL setup with Docker CE auto-install and environment guards (completed 2026-03-05)
- [x] **Phase 14: Daily Startup** - Zero-input daily startup script with health polling and URL output (gap closure in progress) (completed 2026-03-05)
- [x] **Phase 15: CSV Documentation** - Single-page CSV reference covering CDCMS workflow, columns, rejections, and address cleaning (completed 2026-03-05)
- [x] **Phase 16: Documentation Corrections** - README and DEPLOY.md accuracy fixes for non-technical audience (completed 2026-03-05)
- [ ] **Phase 17: Error Message Humanization** - Plain-English upload and geocoding errors replacing Python internals
- [ ] **Phase 18: Distribution Build** - Licensing module compilation for customer delivery

## Phase Details

### Phase 13: Bootstrap Installation
**Goal**: A non-technical user can install the entire system from a fresh WSL2 Ubuntu terminal with a single command
**Depends on**: Nothing (first phase of v1.3)
**Requirements**: INST-01, INST-02, INST-03, INST-04, INST-05
**Success Criteria** (what must be TRUE):
  1. Running `bootstrap.sh` on a fresh WSL2 Ubuntu installs Docker CE, adds user to docker group, and delegates to `install.sh` without manual intervention
  2. After a Windows reboot, Docker daemon starts automatically in WSL without requiring sudo or manual `service docker start`
  3. Running `bootstrap.sh` from `/mnt/c/` (Windows filesystem) aborts immediately with a clear message directing the user to clone in the Linux home directory
  4. Running `bootstrap.sh` on a machine with less than 5 GB available WSL memory prints a warning about OSRM memory requirements and `.wslconfig` instructions
  5. Running `bootstrap.sh` on WSL1 fails immediately with a clear message explaining WSL2 is required and how to upgrade
**Plans:** 1/1 plans complete

Plans:
- [x] 13-01-PLAN.md -- Create bootstrap.sh with environment guards, Docker CE install, auto-start config, .env generation, and two-phase resume

### Phase 14: Daily Startup
**Goal**: Office employee starts the system every morning with one command and zero prompts
**Depends on**: Phase 13
**Requirements**: DAILY-01
**Success Criteria** (what must be TRUE):
  1. Running `start.sh` brings up all Docker Compose services, polls the health endpoint for up to 60 seconds, and prints the dashboard URL on success
  2. Running `start.sh` when services are already running completes gracefully without errors or duplicate containers
  3. If health check times out, `start.sh` prints which service failed and a suggested next step (not a raw Docker error)
**Plans:** 2/2 plans complete

Plans:
- [x] 14-01-PLAN.md -- Create scripts/start.sh with Docker daemon guard, idempotent compose up, 60s health polling, failure diagnosis, and success banner
- [x] 14-02-PLAN.md -- Fix unreachable failure path: replace bare poll_health + $? with if/else pattern for set -euo pipefail compatibility

### Phase 15: CSV Documentation
**Goal**: Office employee can look up any CSV question -- column names, rejection reasons, address formatting -- in one document without asking IT
**Depends on**: Nothing (independent of script phases)
**Requirements**: CSV-01, CSV-02, CSV-03, CSV-04, CSV-05, CSV-06
**Success Criteria** (what must be TRUE):
  1. CSV_FORMAT.md documents both CDCMS (.csv) and standard CSV formats with exact column names matching what the office employee sees in their export
  2. CSV_FORMAT.md lists every rejection reason the system can produce alongside plain-English explanations of what went wrong and how to fix it
  3. CSV_FORMAT.md documents the address cleaning pipeline with before/after examples showing what transformations the system applies
  4. CSV_FORMAT.md includes copy-pasteable example rows for both CDCMS and standard CSV formats that pass validation when uploaded
**Plans:** 1/1 plans complete

Plans:
- [x] 15-01-PLAN.md -- Create CSV_FORMAT.md with source-verified format specs, rejection reasons, address cleaning pipeline, and example rows

### Phase 16: Documentation Corrections
**Goal**: README and DEPLOY.md are accurate, reference the correct container names and scripts, and are written for the non-technical office employee audience
**Depends on**: Phase 13, Phase 14, Phase 15
**Requirements**: DOCS-01, DOCS-02, DOCS-03, DOCS-04
**Success Criteria** (what must be TRUE):
  1. README Docker Services table shows `lpg-db` (not `routing-db`) and all container names match `docker-compose.yml`
  2. README and DEPLOY.md contain no `<REPO_URL>` placeholders -- all replaced with the actual repository URL or clear instructions
  3. DEPLOY.md daily usage section references `./scripts/start.sh` instead of multi-command Docker workflows, and fits on one printed page
  4. DEPLOY.md is structured for a non-technical reader: prominent "use Ubuntu terminal, not PowerShell" warning, step numbering, and cross-links to CSV_FORMAT.md
**Plans:** 2/2 plans complete

Plans:
- [ ] 16-01-PLAN.md -- Fix README.md and SETUP.md factual inaccuracies: container names, credential defaults, REPO_URL notes, automated step annotations
- [ ] 16-02-PLAN.md -- Restructure DEPLOY.md for non-technical audience: script references, Ubuntu warning, CSV cross-link, Quick Reference Card

### Phase 17: Error Message Humanization
**Goal**: Upload and geocoding errors speak the office employee's language -- no Python tracebacks, no set notation, no raw API error codes
**Depends on**: Phase 15
**Requirements**: ERR-01, ERR-02
**Success Criteria** (what must be TRUE):
  1. Uploading a CSV with missing required columns shows an error like "Column 'OrderNo' is missing" instead of Python set notation like `{'OrderNo', 'ConsumerAddress'}`
  2. Geocoding failures display office-friendly descriptions (e.g., "Address not found -- check spelling in CDCMS" for ZERO_RESULTS, "Google Maps quota exceeded -- contact IT" for OVER_DAILY_LIMIT) instead of raw API error codes
**Plans**: TBD

Plans:
- [ ] 17-01: TBD

### Phase 18: Distribution Build
**Goal**: Customer delivery package contains compiled licensing module without exposable Python source
**Depends on**: Nothing (independent)
**Requirements**: DIST-01
**Success Criteria** (what must be TRUE):
  1. Build script produces `.pyc` files for the licensing module and strips corresponding `.py` source files from the distribution package
  2. The system starts and runs correctly using only the compiled `.pyc` licensing module (no `.py` source required at runtime)
**Plans**: TBD

Plans:
- [ ] 18-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 13 -> 14 -> 15 -> 16 -> 17 -> 18

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
| 16. Documentation Corrections | 2/2 | Complete    | 2026-03-05 | - |
| 17. Error Message Humanization | v1.3 | 0/? | Not started | - |
| 18. Distribution Build | v1.3 | 0/? | Not started | - |

---
*Full phase details for v1.0-v1.2 archived in `.planning/milestones/`*
