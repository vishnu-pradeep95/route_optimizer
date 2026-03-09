---
phase: 23-distribution-verification-operational-scripts
plan: 01
subsystem: infra
tags: [bash, docker-compose, operations, shutdown, cleanup]

# Dependency graph
requires:
  - phase: none
    provides: n/a
provides:
  - "scripts/stop.sh -- graceful shutdown with optional GC mode"
affects: [deploy, operations, daily-workflow]

# Tech tracking
tech-stack:
  added: []
  patterns: ["docker compose stop for graceful shutdown", "log truncation before container removal"]

key-files:
  created: [scripts/stop.sh]
  modified: []

key-decisions:
  - "Truncate container logs BEFORE docker compose down (down removes containers and their logs)"
  - "Use sudo test -f for root-owned Docker log file access checks"

patterns-established:
  - "GC flow: capture log paths -> stop -> truncate logs -> down -> prune images"

requirements-completed: [OPS-01, OPS-02]

# Metrics
duration: 6min
completed: 2026-03-08
---

# Phase 23 Plan 01: Stop Script Summary

**Graceful shutdown script (stop.sh) with docker compose stop and --gc flag for dangling image prune, orphan removal, and log truncation**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-08T22:16:02Z
- **Completed:** 2026-03-08T22:22:17Z
- **Tasks:** 2
- **Files modified:** 1

## Accomplishments
- Created scripts/stop.sh matching project boilerplate (colors, helpers, SCRIPT_DIR/PROJECT_ROOT)
- Default mode: docker compose stop preserves containers and volumes, exits cleanly when already stopped
- GC mode (--gc): truncates root-owned container logs, removes orphan containers/networks, prunes dangling images
- Smoke-tested all three modes (already-stopped, default stop, GC) against live Docker stack

## Task Commits

Each task was committed atomically:

1. **Task 1: Create scripts/stop.sh with graceful stop and --gc mode** - `869f45c` (feat)
2. **Task 2: Smoke test stop.sh against running Docker stack** - `39db9f2` (fix -- log truncation ordering and sudo access)

## Files Created/Modified
- `scripts/stop.sh` - Graceful shutdown script with optional --gc garbage collection mode

## Decisions Made
- Moved log truncation step BEFORE `docker compose down` because down removes containers and Docker cleans up their log files
- Used `sudo test -f` instead of bare `-f` for Docker log file existence checks (files are root-owned under /var/lib/docker/containers/)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Log file access check fails without sudo**
- **Found during:** Task 2 (smoke testing --gc mode)
- **Issue:** `-f "$log_path"` returns false for Docker log files at /var/lib/docker/containers/ because they are root-owned
- **Fix:** Changed to `sudo test -f "$log_path"` and removed bare `-f` pre-check when capturing paths
- **Files modified:** scripts/stop.sh
- **Verification:** GC mode now correctly reaches log truncation logic
- **Committed in:** 39db9f2 (Task 2 commit)

**2. [Rule 1 - Bug] Log truncation after docker compose down finds no files**
- **Found during:** Task 2 (smoke testing --gc mode)
- **Issue:** Plan specified truncation after `docker compose down`, but down removes containers and Docker daemon cleans up their log files
- **Fix:** Restructured GC flow: capture log paths -> stop -> truncate logs -> down -> prune images
- **Files modified:** scripts/stop.sh
- **Verification:** Logs are now accessible for truncation when containers are stopped but not yet removed
- **Committed in:** 39db9f2 (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (2 bugs)
**Impact on plan:** Both fixes necessary for correct GC operation. No scope creep.

## Issues Encountered
None beyond the deviations documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- stop.sh is ready for daily use by office operators
- Complements existing start.sh for the daily startup/shutdown workflow
- Phase 23 Plan 02 can proceed independently

---
*Phase: 23-distribution-verification-operational-scripts*
*Completed: 2026-03-08*
