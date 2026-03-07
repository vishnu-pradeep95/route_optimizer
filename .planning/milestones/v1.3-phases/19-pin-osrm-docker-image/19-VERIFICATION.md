---
phase: 19-pin-osrm-docker-image
verified: 2026-03-07T16:00:00Z
status: passed
score: 3/3 must-haves verified
re_verification: false
---

# Phase 19: Pin OSRM Docker Image -- Verification Report

**Phase Goal:** Fix osrm-init container failure (exit 127) that blocks all fresh deployments
**Verified:** 2026-03-07T16:00:00Z
**Status:** passed
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | osrm-init container entrypoint uses /bin/sh, not /bin/bash, in both dev and prod compose files | VERIFIED | `docker-compose.yml:75` has `entrypoint: ["/bin/sh", "-c"]`; `docker-compose.prod.yml:92` has `entrypoint: ["/bin/sh", "-c"]`; `grep -c '/bin/bash'` returns 0 for both files |
| 2 | All osrm/osrm-backend image references in operational files use v5.27.1, not :latest | VERIFIED | `docker-compose.yml` lines 71, 107; `docker-compose.prod.yml` lines 88, 124; `scripts/osrm_setup.sh` line 41; `SETUP.md` lines 307, 312, 317 -- all reference `v5.27.1`; `grep -c 'osrm-backend:latest'` returns 0 for all 4 files |
| 3 | docker compose config --quiet validates without errors after changes | VERIFIED | Dev compose (`docker compose config --quiet`) exits 0. Prod compose exits 1 due to pre-existing `API_KEY` required variable (unrelated to phase 19 -- confirmed present before commit 5b308c3) |

**Score:** 3/3 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `docker-compose.yml` | Dev compose with pinned OSRM images and POSIX shell entrypoint | VERIFIED | Lines 71 and 107: `osrm/osrm-backend:v5.27.1`; Line 75: `/bin/sh` entrypoint; Zero `:latest` or `/bin/bash` references |
| `docker-compose.prod.yml` | Prod compose with POSIX shell entrypoint | VERIFIED | Line 92: `/bin/sh` entrypoint; Lines 88, 124: `v5.27.1` (pre-existing, confirmed intact); Zero `/bin/bash` references |
| `scripts/osrm_setup.sh` | Standalone OSRM setup with pinned image version | VERIFIED | Line 41: `OSRM_IMAGE="osrm/osrm-backend:v5.27.1"`; Zero `:latest` references |
| `SETUP.md` | Setup documentation with pinned image version | VERIFIED | Lines 307, 312, 317: all three `docker run` examples use `osrm/osrm-backend:v5.27.1`; Zero `:latest` references |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| docker-compose.yml (osrm-init) | osrm/osrm-backend:v5.27.1 | image tag + entrypoint shell | WIRED | Line 71 pins v5.27.1, line 75 uses /bin/sh; osrm service at line 107 also pinned |
| docker-compose.yml (osrm) | osrm-init | service_completed_successfully | WIRED | Line 116: `condition: service_completed_successfully` -- osrm waits for osrm-init to exit 0 |
| scripts/start.sh | docker compose up -d | osrm-init must exit 0 for osrm to start | WIRED | Line 169: `docker compose up -d` triggers osrm-init, which will now use /bin/sh on v5.27.1 image |
| docker-compose.prod.yml (osrm-init) | osrm/osrm-backend:v5.27.1 | image tag + entrypoint shell | WIRED | Line 88 pins v5.27.1, line 92 uses /bin/sh; Line 131: `service_completed_successfully` chains to osrm |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| INST-01 (re-satisfied) | 19-01-PLAN | Bootstrap script auto-installs Docker CE in WSL if missing | SATISFIED | bootstrap.sh delegates to install.sh which runs `docker compose up -d`; osrm-init now uses /bin/sh on pinned v5.27.1 image, eliminating exit 127 on fresh deployments |
| DAILY-01 (re-satisfied) | 19-01-PLAN | Single start.sh command starts Docker, runs compose up, polls health, prints URL | SATISFIED | start.sh line 169 calls `docker compose up -d`; osrm-init entrypoint fix ensures the init container completes successfully, unblocking osrm, vroom, and api services |

No orphaned requirements found -- REQUIREMENTS.md does not map any additional IDs to Phase 19 beyond what the PLAN claims.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| (none) | - | - | - | No anti-patterns detected in any of the 4 modified files |

No TODO, FIXME, PLACEHOLDER, or stub patterns found in any modified file.

### Human Verification Required

### 1. Docker Compose Full Stack Smoke Test

**Test:** Run `docker compose up -d` on a fresh machine (or after removing OSRM data) and verify osrm-init exits 0
**Expected:** osrm-init container starts with /bin/sh, downloads and preprocesses Kerala map data, exits with code 0; osrm service then starts and passes healthcheck
**Why human:** Requires Docker daemon running, network access to download OSM data, and ~5-10 minutes of preprocessing time

### 2. Production Compose Smoke Test

**Test:** Set required env vars and run `docker compose -f docker-compose.prod.yml up -d`
**Expected:** Same as above -- osrm-init uses /bin/sh and exits 0 on the v5.27.1 image
**Why human:** Requires production environment configuration (.env.production with API_KEY, POSTGRES_PASSWORD, etc.)

### Gaps Summary

No gaps found. All three observable truths are verified. All four artifacts exist, are substantive (contain the expected pinned version and POSIX shell references), and are wired (compose files chain via service_completed_successfully, start.sh invokes docker compose up). Both requirement IDs (INST-01, DAILY-01) are re-satisfied by the fix. Zero `:latest` or `/bin/bash` references remain in operational files. Both documented commits (5b308c3, 8e8b456) are confirmed in git history with correct file changes.

---

_Verified: 2026-03-07T16:00:00Z_
_Verifier: Claude (gsd-verifier)_
