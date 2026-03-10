---
gsd_state_version: 1.0
milestone: v2.1
milestone_name: Licensing & Distribution Security
status: executing
stopped_at: Completed 06-02-PLAN.md
last_updated: "2026-03-10T22:36:14Z"
last_activity: 2026-03-10 -- Phase 6 Plan 02 complete (HMAC credential rotation)
progress:
  total_phases: 6
  completed_phases: 0
  total_plans: 3
  completed_plans: 1
  percent: 22
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-10)

**Core value:** Every delivery address uploaded must appear on the map and be assigned to an optimized route -- no silent drops, no missing stops.
**Current focus:** v2.1 Licensing & Distribution Security -- Phase 6 (Build Pipeline)

## Current Position

Phase: 6 -- Build Pipeline (Dev-Mode Stripping and Cython Compilation)
Plan: 2 of 3 complete (06-02 done, 06-01 and 06-03 remaining)
Status: Executing
Last activity: 2026-03-10 -- Phase 6 Plan 02 complete (HMAC credential rotation)

Progress: [##░░░░░░░░] 22% (3/12 plans across 6 phases)

## Performance Metrics

**Velocity:**
- Total plans completed: 64 (across v1.0-v2.0)

**By Milestone:**

| Milestone | Phases | Plans | Timeline |
|-----------|--------|-------|----------|
| v1.0 Infrastructure | 3 (1-3) | 8 | 2026-03-01 |
| v1.1 Polish & Reliability | 4 (4-7) | 16 | 2026-03-01 -> 2026-03-03 |
| v1.2 Tech Debt & Cleanup | 5 (8-12) | 9 | 2026-03-03 -> 2026-03-04 |
| v1.3 Office-Ready Deployment | 8 (13-20) | 10 | 2026-02-21 -> 2026-03-07 |
| v1.4 Ship-Ready QA | 4 (21-24) | 10 | 2026-03-08 -> 2026-03-09 |
| v2.0 Doc & Error Handling | 4 (1-4) | 9 | 2026-03-09 -> 2026-03-10 |
| v2.1 Licensing Security | 6 (5-10) | TBD | 2026-03-10 -> ... |

## Accumulated Context

### Decisions

- Phase 5-01: Dropped MAC from fingerprint (WSL2 generates random MAC on reboot, microsoft/WSL#5352)
- Phase 5-01: Used exact match (not similarity scoring) for fingerprint validation
- Phase 5-02: Read-only bind mount (:ro) for /etc/machine-id to prevent container writes to host identity
- Phase 6-02: HMAC seed stored as bytes.fromhex() -- not greppable, not human-readable
- Phase 6-02: PBKDF2 iterations doubled to 200k for stronger key derivation
- Phase 6-02: Migration docs written in Phase 6 while context fresh (execution deferred to Phase 10)

See also: PROJECT.md Key Decisions table, `.planning/milestones/` for full phase details per milestone.

### Pending Todos

2 pending -- see `.planning/todos/pending/`

### Blockers/Concerns

- BREAKING CHANGE: Fingerprint formula change (Phase 5) invalidates all existing customer licenses. Must coordinate migration in Phase 10.
- Cython async limitation: `async def` cannot be compiled by Cython (FastAPI#1921). Enforcement middleware must call synchronous compiled functions from an uncompiled async wrapper.
- Physical Android device testing required for outdoor contrast validation.
- Google Maps API key is currently invalid (REQUEST_DENIED) -- E2E tests must use pre-geocoded seed data.

### Security Audit Findings (v2.1 trigger)

| # | Loophole | Severity | Phase |
|---|----------|----------|-------|
| 1 | ENVIRONMENT=development bypass | CRITICAL | Phase 6 |
| 2 | Enforcement in plain-text main.py | CRITICAL | Phase 7 |
| 3 | ~~Fingerprint spoofable via Docker~~ | ~~MEDIUM~~ | ✓ Phase 5 |
| 4 | .pyc decompilation trivial | MEDIUM | Phase 6 |
| 5 | License checked only at startup | LOW-MEDIUM | Phase 8 |
| 6 | No file integrity verification | LOW-MEDIUM | Phase 7 |

## Performance Metrics (v2.1)

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| 05-01 | Fingerprint formula | 5min | 3 | 3 |
| 05-02 | Docker compose bind mount | 2min | 2 | 2 |
| 06-02 | HMAC credential rotation | 5min | 3 | 4 |

## Session Continuity

Last session: 2026-03-10T22:36:14Z
Stopped at: Completed 06-02-PLAN.md
Resume file: .planning/milestones/v2.1-phases/06-build-pipeline/06-02-SUMMARY.md
