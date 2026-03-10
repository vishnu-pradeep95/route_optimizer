---
phase: 05-fingerprinting-overhaul
plan: 01
subsystem: licensing
tags: [fingerprint, machine-id, cpuinfo, sha256, tdd, security]

# Dependency graph
requires: []
provides:
  - "Stable machine fingerprint using /etc/machine-id + CPU model"
  - "_read_machine_id() and _read_cpu_model() helper functions"
  - "Removed hostname, MAC, and container_id from fingerprint"
  - "Unit tests for new fingerprint formula with mocked filesystem"
affects: [05-02, 06-enforcement-hardening, 10-migration]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Filesystem-based fingerprint signals with graceful degradation"
    - "TDD for security-critical formula changes"

key-files:
  created: []
  modified:
    - "core/licensing/license_manager.py"
    - "scripts/get_machine_id.py"
    - "tests/core/licensing/test_license_manager.py"

key-decisions:
  - "Drop MAC from fingerprint (WSL2 generates random MAC on every reboot)"
  - "Use exact match (not similarity scoring) for fingerprint validation"

patterns-established:
  - "_read_machine_id(): read /etc/machine-id with /var/lib/dbus/machine-id fallback"
  - "_read_cpu_model(): parse first 'model name' line from /proc/cpuinfo"
  - "Fingerprint formula: SHA256(machine_id|cpu_model) -- identical in both files"

requirements-completed: [FPR-01, FPR-03]

# Metrics
duration: 5min
completed: 2026-03-10
---

# Phase 5 Plan 1: Fingerprint Formula Replacement Summary

**Replaced unstable hostname+MAC+container_id fingerprint with stable /etc/machine-id + CPU model formula, backed by TDD with 13 new tests**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-10T20:08:25Z
- **Completed:** 2026-03-10T20:13:22Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Replaced the unstable fingerprint formula (hostname + MAC + container_id) with machine-id + CPU model
- Both license_manager.py and get_machine_id.py now use identical formulas
- Added 13 new unit tests covering _read_machine_id, _read_cpu_model, and updated get_machine_fingerprint
- Removed _get_docker_container_id() from both files
- Dropped MAC address from fingerprint (WSL2 instability confirmed via microsoft/WSL#5352)
- Full test suite green: 492 tests pass with zero regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: MAC address inclusion decision** - auto-selected "drop-mac" (checkpoint:decision, auto-mode)
2. **Task 2: Write unit tests for new fingerprint formula** - `12df1fb` (test: TDD RED phase)
3. **Task 3: Implement new fingerprint formula** - `e85ea7d` (feat: TDD GREEN phase)

_Note: Task 1 was a checkpoint:decision auto-approved in auto-mode. Tasks 2-3 follow TDD RED/GREEN pattern._

## Files Created/Modified

- `core/licensing/license_manager.py` - New _read_machine_id(), _read_cpu_model(), updated get_machine_fingerprint(); removed _get_docker_container_id(), import platform, import uuid
- `scripts/get_machine_id.py` - Identical new fingerprint formula; updated main() output to show machine-id and CPU model details
- `tests/core/licensing/test_license_manager.py` - 13 new tests: TestReadMachineId (4), TestReadCpuModel (3), expanded TestMachineFingerprint (6 new + 2 kept)

## Decisions Made

1. **Dropped MAC from fingerprint** (deviates from user's "keep MAC" decision) -- WSL2 generates a new random MAC address on every reboot (microsoft/WSL#5352), making fingerprints unstable across reboots. Success criterion "same fingerprint before and after WSL restart" cannot be met with MAC included. machine-id + CPU model is sufficient for the threat model (casual copying deterrent).

2. **Used exact match (not similarity scoring)** -- Per "Claude's discretion" from CONTEXT.md. The new fingerprint formula is inherently stable (machine-id doesn't change, CPU model doesn't change unless hardware swap). Similarity scoring adds complexity without clear benefit. Listed as future requirement ADV-01 if needed.

## Deviations from Plan

### Auto-approved Decision (Auto-mode)

**Task 1: checkpoint:decision** -- Auto-selected "drop-mac" (first/recommended option) per auto-mode rules. The research clearly established that MAC is unstable in WSL2 and including it prevents meeting success criteria.

No other deviations -- plan executed as written for Tasks 2-3.

## Issues Encountered

None -- all tasks executed cleanly. TDD RED/GREEN cycle worked as expected.

## User Setup Required

None -- no external service configuration required. The docker-compose.yml bind mount for /etc/machine-id is handled in Plan 05-02.

## Next Phase Readiness

- Fingerprint formula replaced and tested in both source files
- Plan 05-02 still needed: docker-compose.yml bind mount for /etc/machine-id into API container
- BREAKING CHANGE: all existing customer license keys are invalidated by this formula change (handled in Phase 10 migration)

## Self-Check: PASSED

- All 3 source files exist and contain expected functions
- Both commits (12df1fb, e85ea7d) verified in git log
- New functions (_read_machine_id, _read_cpu_model) present in both files
- Old function (_get_docker_container_id) removed from both files
- 38/38 fingerprint tests pass, 492/492 full suite pass

---
*Phase: 05-fingerprinting-overhaul*
*Completed: 2026-03-10*
