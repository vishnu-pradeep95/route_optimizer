---
gsd_state_version: 1.0
milestone: v2.1
milestone_name: Licensing & Distribution Security
status: completed
stopped_at: Phase 13 context gathered
last_updated: "2026-03-12T01:53:02.522Z"
last_activity: 2026-03-12 -- Completed Plan 12-03 (Pipeline integration & coverage validation)
progress:
  total_phases: 11
  completed_phases: 1
  total_plans: 3
  completed_plans: 3
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-10)

**Core value:** Every delivery address uploaded must appear on the map and be assigned to an optimized route -- no silent drops, no missing stops.
**Current focus:** Phase 12 -- Place Name Dictionary (v2.2 Address Preprocessing Pipeline)

## Current Position

Phase: 12 (2 of 5 in v2.2) -- Place Name Dictionary
Plan: 3 of 3
Status: Complete
Last activity: 2026-03-12 -- Completed Plan 12-03 (Pipeline integration & coverage validation)

Progress: [██████████] 100%

## Performance Metrics

**Velocity:**
- Total plans completed: 64 (across v1.0-v2.0) + 2 (v2.1 Phase 5)

**By Milestone:**

| Milestone | Phases | Plans | Timeline |
|-----------|--------|-------|----------|
| v1.0 Infrastructure | 3 (1-3) | 8 | 2026-03-01 |
| v1.1 Polish & Reliability | 4 (4-7) | 16 | 2026-03-01 -> 2026-03-03 |
| v1.2 Tech Debt & Cleanup | 5 (8-12) | 9 | 2026-03-03 -> 2026-03-04 |
| v1.3 Office-Ready Deployment | 8 (13-20) | 10 | 2026-02-21 -> 2026-03-07 |
| v1.4 Ship-Ready QA | 4 (21-24) | 10 | 2026-03-08 -> 2026-03-09 |
| v2.0 Doc & Error Handling | 4 (1-4) | 9 | 2026-03-09 -> 2026-03-10 |
| v2.1 Licensing Security | 6 (5-10) | TBD | 2026-03-10 -> ... (parallel, main branch) |
| v2.2 Address Preprocessing | 5 (11-15) | TBD | 2026-03-10 -> ... |
| Phase 11 P01 | 11min | 3 tasks | 2 files |
| Phase 11 P02 | 10min | 2 tasks | 14 files |
| Phase 11 P03 | 2min | 2 tasks | 1 file |
| Phase 12 P01 | 3min | 2 tasks | 3 files |
| Phase 12 P02 | 5min | 2 tasks | 2 files |
| Phase 12 P03 | 3min | 2 tasks | 2 files |

## Accumulated Context

### Decisions

- Phase 5-01: Dropped MAC from fingerprint (WSL2 generates random MAC on reboot, microsoft/WSL#5352)
- Phase 5-01: Used exact match (not similarity scoring) for fingerprint validation
- Phase 5-02: Read-only bind mount (:ro) for /etc/machine-id to prevent container writes to host identity
- Phase 11-01: Used protected word set (not pure regex) for trailing letter split -- ALL-CAPS text has no casing cues to distinguish real words from concatenations
- Phase 11-01: Three-priority split heuristic: meaningful suffix (PO/NR/KB) > protected prefix match > single trailing initial
- Phase 11-01: Pipeline expanded from 10 to 12 steps for trailing letter split and second-pass abbreviation expansion

See also: PROJECT.md Key Decisions table, `.planning/milestones/` for full phase details per milestone.
- [Phase 11]: Used protected word set (not pure regex) for trailing letter split
- Phase 11-02: address_display sourced from order.address_raw (not location.address_text) at both bug sites
- Phase 11-02: API field "address_raw" maps to Python model "address_original" to avoid naming confusion
- Phase 11-02: Non-CDCMS uploads backfill address_original = address_raw (no nulls)
- Phase 11-03: Used encodeURIComponent/decodeURIComponent for safe address passing in onclick attributes
- Phase 11-03: Coordinates are primary navigation destination; address text used only as fallback when coords missing/zero
- Phase 11-03: Raw CDCMS text uses monospace font at reduced opacity to visually distinguish from cleaned address
- [Phase 12]: India Post API unavailable at build time; script continued with OSM + manual seeds (381 entries, 100% coverage)
- [Phase 12]: 21 manual seed entries cover all 9 CDCMS area names including compound names (CHORODE EAST, MUTTUNGAL WEST)
- Phase 12-02: Per-token processing (not character-level scanning) to prevent false positives on already-spaced text
- Phase 12-02: Aliases indexed alongside primary names for fuzzy matching (VATAKARA indexed as alias of VADAKARA)
- Phase 12-02: Compound names output with spaces restored; simple names preserve original input case
- Phase 12-03: Dictionary splitter runs as Step 5.5 (before trailing letter split), not Step 6.5 -- prevents Step 6 from damaging known place names before dictionary lookup

### Pending Todos

2 pending -- see `.planning/todos/pending/`

### Blockers/Concerns

- Google Maps API key is currently invalid (REQUEST_DENIED) -- circuit breaker design in Phase 13 must handle this from first upload.
- Physical Android device testing required for outdoor contrast validation of "Approx. location" badge.
- Dictionary coverage (Phase 12) is the primary unknown -- 80% threshold is a hard gate before Phase 13.

## Session Continuity

Last session: 2026-03-12T01:53:02.520Z
Stopped at: Phase 13 context gathered
Resume file: .planning/phases/13-geocode-validation-fallback-chain/13-CONTEXT.md
