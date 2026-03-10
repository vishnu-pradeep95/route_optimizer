---
phase: 06-build-pipeline
plan: 03
subsystem: infra
tags: [cython, docker, build-pipeline, distribution, security]

# Dependency graph
requires:
  - phase: 06-01
    provides: "Production-default ENVIRONMENT logic in main.py (_is_dev_mode pattern)"
  - phase: 06-02
    provides: "Rotated HMAC seed/salt/iterations, clean __init__.py stub"
provides:
  - "Cython compilation pipeline (Dockerfile.build + cython_build.py)"
  - "Full build-dist.sh pipeline: stage -> strip-devmode -> strip-validate -> hash -> compile -> validate-import -> clean -> package"
  - "Distribution tarball with .so licensing modules (not .py or .pyc)"
  - "Zero ENVIRONMENT references in distributed Python files"
affects: [07-enforcement, 08-runtime-enforcement, 10-migration]

# Tech tracking
tech-stack:
  added: [Cython==3.2.4, setuptools]
  patterns: [docker-based-compilation, sed-strip-devmode, bind-mount-so-extraction]

key-files:
  created:
    - infra/Dockerfile.build
    - infra/cython_build.py
  modified:
    - scripts/build-dist.sh

key-decisions:
  - "Added setuptools to Dockerfile.build pip install -- python:3.12-slim does not include it"
  - "Used sed '/ENVIRONMENT/d' to strip comment lines mentioning ENVIRONMENT from staged main.py -- zero-tolerance validation catches comments too"
  - "embedsignature=False controls Cython signature embedding, not docstring removal -- docstrings preserved in .so is acceptable since code is native machine code"

patterns-established:
  - "Docker-based Cython compilation: build in python:3.12-slim, extract .so via bind mount"
  - "Dev-mode stripping: sed-replace ENVIRONMENT gates to False, then delete ENVIRONMENT comment lines"
  - "Distribution validation: grep -r ENVIRONMENT zero-match check on staged directory"

requirements-completed: [ENF-01, ENF-02, BLD-01, BLD-02, BLD-03]

# Metrics
duration: 6min
completed: 2026-03-10
---

# Phase 6 Plan 3: Cython Build Pipeline Summary

**Cython compilation pipeline producing distribution tarballs with native .so licensing modules, zero ENVIRONMENT references, and Docker-based platform-compatible build/validation**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-10T22:43:21Z
- **Completed:** 2026-03-10T22:49:45Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Created Dockerfile.build with python:3.12-slim + gcc + python3-dev + Cython 3.2.4 for ABI-compatible .so compilation
- Created cython_build.py with -O2 optimization and embedsignature=False directives
- Upgraded build-dist.sh from .pyc compileall to full 8-step Cython pipeline
- Distribution tarball verified: .so present, license_manager.py absent, __init__.py stub kept, zero ENVIRONMENT references
- All 495 tests passing (source code unchanged, only build pipeline added)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create Cython build infrastructure (Dockerfile.build + cython_build.py)** - `982a4d2` (feat)
2. **Task 2: Upgrade build-dist.sh with full Cython pipeline** - `0b1831f` (feat)

## Files Created/Modified
- `infra/Dockerfile.build` - Cython build image: python:3.12-slim + gcc + python3-dev + setuptools + Cython 3.2.4, compiles license_manager.py to .so, validates import
- `infra/cython_build.py` - Cython Extension configuration: -O2 optimization, embedsignature=False, language_level=3, scoped to license_manager.py only
- `scripts/build-dist.sh` - Full pipeline: stage -> strip-devmode (sed) -> strip-validate (zero ENVIRONMENT grep) -> hash -> compile (Docker Cython) -> validate-import (Docker) -> clean -> package

## Decisions Made
- Added `setuptools` to Dockerfile.build pip install because python:3.12-slim (Debian Trixie) no longer bundles setuptools -- blocking issue resolved inline
- Used `sed '/ENVIRONMENT/d'` to delete comment lines mentioning ENVIRONMENT from staged main.py, since the zero-ENVIRONMENT validation correctly catches all references including comments
- Accepted that `embedsignature=False` does not remove Python docstrings from .so (only controls Cython signature annotation) -- native .so compilation itself provides the security hardening

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added setuptools to Dockerfile.build pip install**
- **Found during:** Task 1 (Docker build)
- **Issue:** python:3.12-slim does not include setuptools, causing `ModuleNotFoundError: No module named 'setuptools'` when running cython_build.py
- **Fix:** Added `setuptools` to the `pip install` command alongside Cython==3.2.4
- **Files modified:** infra/Dockerfile.build
- **Verification:** Docker build completes successfully, .so produced and imports validated
- **Committed in:** 982a4d2 (Task 1 commit)

**2. [Rule 3 - Blocking] Stripped ENVIRONMENT comment lines from staged main.py**
- **Found during:** Task 2 (build-dist.sh strip-validate step)
- **Issue:** Two comment lines (lines 235-236) in main.py referenced ENVIRONMENT, causing the zero-ENVIRONMENT validation to fail even though code references were already stripped
- **Fix:** Added `sed -i '/ENVIRONMENT/d'` after the code-level sed replacements to remove comment lines mentioning ENVIRONMENT
- **Files modified:** scripts/build-dist.sh
- **Verification:** `grep -r ENVIRONMENT --include="*.py"` returns 0 matches on staged directory
- **Committed in:** 0b1831f (Task 2 commit)

**3. [Rule 3 - Blocking] Fixed grep pipefail exit code in strip-validate step**
- **Found during:** Task 2 (build-dist.sh strip-validate step)
- **Issue:** `grep | wc -l` returns exit code 1 when grep finds zero matches (correct behavior), but `set -euo pipefail` caused the script to abort prematurely
- **Fix:** Added `|| true` to the grep pipeline to handle the zero-match case
- **Files modified:** scripts/build-dist.sh
- **Verification:** Script completes successfully through the validation step
- **Committed in:** 0b1831f (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (3 blocking)
**Impact on plan:** All auto-fixes necessary for correct execution. No scope creep.

## Issues Encountered
None beyond the auto-fixed blocking issues documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Security audit finding #4 (.pyc decompilation trivial) is now closed -- licensing module distributed as native .so
- Security audit finding #1 (ENVIRONMENT bypass) is enforced at build time -- zero ENVIRONMENT references in distribution
- Distribution tarball ready for Phase 7 integrity manifest (file hashes already recorded as placeholder)
- Phase 8 runtime enforcement can rely on .so licensing module being import-compatible
- Phase 10 migration can use the build pipeline to produce customer distribution packages

## Self-Check: PASSED

All 3 created/modified files verified on disk. All 2 task commits verified in git log.

---
*Phase: 06-build-pipeline*
*Completed: 2026-03-10*
