---
phase: 19-pin-osrm-docker-image
plan: 01
subsystem: infra
tags: [docker, osrm, docker-compose, alpine, posix]

# Dependency graph
requires:
  - phase: 13-install-script
    provides: Docker compose orchestration for fresh deployments
provides:
  - Pinned OSRM images (v5.27.1) across all operational files
  - POSIX-compatible entrypoints (/bin/sh) for Alpine-based images
affects: [daily-startup, install-script, deployment]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Pin Docker images to specific versions instead of :latest"]

key-files:
  created: []
  modified:
    - docker-compose.yml
    - docker-compose.prod.yml
    - scripts/osrm_setup.sh
    - SETUP.md

key-decisions:
  - "Pin to v5.27.1 (last known working version) rather than building custom image"
  - "Switch /bin/bash to /bin/sh for Alpine compatibility (all entrypoint scripts use POSIX constructs only)"

patterns-established:
  - "Docker image pinning: always use specific version tags, never :latest, for reproducible builds"

requirements-completed: [INST-01, DAILY-01]

# Metrics
duration: 1min
completed: 2026-03-07
---

# Phase 19 Plan 01: Pin OSRM Docker Image Summary

**Pinned osrm/osrm-backend to v5.27.1 and switched entrypoints from /bin/bash to /bin/sh across all 4 operational files, fixing exit 127 on fresh Alpine-based deployments**

## Performance

- **Duration:** 1 min
- **Started:** 2026-03-07T15:43:53Z
- **Completed:** 2026-03-07T15:45:03Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Eliminated osrm-init exit 127 that blocked all fresh deployments (upstream Alpine image lacks /bin/bash)
- Pinned all 5 osrm-backend image references to v5.27.1 across docker-compose.yml, docker-compose.prod.yml, scripts/osrm_setup.sh, and SETUP.md
- Switched entrypoints from /bin/bash to /bin/sh in both dev and prod compose files
- Zero occurrences of osrm-backend:latest or /bin/bash remain in operational files

## Task Commits

Each task was committed atomically:

1. **Task 1: Pin OSRM image and fix shell in Docker Compose files** - `5b308c3` (fix)
2. **Task 2: Pin OSRM image in standalone script and documentation** - `8e8b456` (fix)

## Files Created/Modified
- `docker-compose.yml` - Pinned osrm-init and osrm images to v5.27.1, switched osrm-init entrypoint to /bin/sh
- `docker-compose.prod.yml` - Switched osrm-init entrypoint to /bin/sh (images already pinned)
- `scripts/osrm_setup.sh` - Updated OSRM_IMAGE variable from :latest to v5.27.1
- `SETUP.md` - Updated all 3 manual OSRM docker run examples from :latest to v5.27.1

## Decisions Made
- Pin to v5.27.1 (last known Debian-based release) rather than building a custom image or using a different tag
- Switch /bin/bash to /bin/sh since all entrypoint command blocks use only POSIX constructs (set -e, [ ] tests, ||, standard redirects)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- All OSRM-related files now consistently reference v5.27.1
- Fresh deployments will pull the pinned Debian-based image instead of broken Alpine :latest
- osrm-init container will successfully start with /bin/sh on all image variants

## Self-Check: PASSED

All files exist. All commits verified (5b308c3, 8e8b456).

---
*Phase: 19-pin-osrm-docker-image*
*Completed: 2026-03-07*
