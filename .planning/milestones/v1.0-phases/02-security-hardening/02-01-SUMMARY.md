---
phase: 02-security-hardening
plan: 01
subsystem: api
tags: [secweb, csp, cors, security-headers, permissions-policy, fastapi-middleware]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: FastAPI app with rate limiting and docs gating
provides:
  - SecWeb security headers middleware (CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy)
  - Custom PermissionsPolicyMiddleware (geolocation allowed, all other features denied)
  - Hardened CORS with explicit allow_headers and environment-aware origins
  - /redoc gating in production (fixing gap where /docs was gated but /redoc was not)
  - Security header test suite (8 tests covering all requirements)
affects: [03-driver-pwa, 04-offline-maps]

# Tech tracking
tech-stack:
  added: [Secweb==1.30.10]
  patterns: [starlette-middleware-ordering, environment-aware-config, custom-BaseHTTPMiddleware]

key-files:
  created: []
  modified:
    - apps/kerala_delivery/api/main.py
    - requirements.txt
    - tests/apps/kerala_delivery/api/test_api.py

key-decisions:
  - "SecWeb registered as outermost middleware so security headers appear on ALL responses including errors"
  - "Custom PermissionsPolicyMiddleware needed because SecWeb 1.30.x lacks Permissions-Policy support"
  - "CORS allow_headers tightened from wildcard to explicit [Content-Type, X-API-Key, Authorization]"
  - "CORS origins use environment-aware defaults: dev permits localhost:8000/3000/5173, production requires explicit whitelist"
  - "HSTS only enabled in non-development environments to prevent localhost HTTPS lock-in"
  - "CSP allows unsafe-inline styles (required for Leaflet inline map styles)"

patterns-established:
  - "Middleware registration order: SecWeb > PermissionsPolicyMiddleware > CORSMiddleware > license > rate limiter"
  - "Environment-aware security: strict in production, permissive in development"
  - "Module-reload test pattern for environment-dependent FastAPI app configuration"

requirements-completed: [SEC-01, SEC-02, SEC-03, SEC-05]

# Metrics
duration: 3min
completed: 2026-03-01
---

# Phase 02 Plan 01: Security Headers & CORS Hardening Summary

**SecWeb security headers with CSP allowing Leaflet/OSM, Permissions-Policy middleware, hardened CORS with explicit allow_headers, and /redoc production gating**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-01T17:31:31Z
- **Completed:** 2026-03-01T17:34:50Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Every HTTP response now includes CSP, X-Frame-Options (DENY), X-Content-Type-Options (nosniff), Referrer-Policy, and Permissions-Policy headers
- CSP configured for Leaflet requirements: OSM tile servers in img-src, unpkg.com for icons, unsafe-inline for styles
- CORS hardened from wildcard allow_headers to explicit list; origins are environment-aware
- /redoc now returns 404 in production (was previously accessible even when /docs was gated)
- Confirmed python-jose and passlib are not installed (deprecated auth libraries)
- 8 new security tests added; 368 total project tests pass

## Task Commits

Each task was committed atomically (TDD: test then implementation):

1. **Task 1 RED: Failing security header tests** - `94d41fb` (test)
2. **Task 1 GREEN: SecWeb + PermissionsPolicyMiddleware + CORS hardening + /redoc fix** - `21d9b6d` (feat)

_Note: Task 2 (tests, /redoc fix, deprecated library checks) was fully covered by the Task 1 TDD cycle -- tests were written first (RED), then all implementation including /redoc fix was done (GREEN). No separate Task 2 commit needed._

## Files Created/Modified
- `apps/kerala_delivery/api/main.py` - Added SecWeb, PermissionsPolicyMiddleware class, hardened CORS config, _redoc_url gating
- `requirements.txt` - Added Secweb==1.30.10
- `tests/apps/kerala_delivery/api/test_api.py` - Added TestSecurityHeaders class with 8 tests (SEC-01, SEC-02, SEC-03, SEC-05)

## Decisions Made
- Used SecWeb 1.30.10 (latest stable) rather than building CSP middleware from scratch -- proven library with correct header formatting
- Created custom PermissionsPolicyMiddleware because SecWeb stable does not support Permissions-Policy header
- Registered SecWeb FIRST in code (outermost in Starlette's reverse-order wrapping) so even error responses from inner middleware get security headers
- Added expose_headers for X-License-Warning and Retry-After so browser JS can read rate-limit and license grace period warnings
- CORS dev defaults include localhost:5173 (Vite dev server) in addition to localhost:8000 and localhost:3000

## Deviations from Plan

None - plan executed exactly as written. Task 2 was fully absorbed into Task 1's TDD cycle since the tests had to exist before implementation.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Security headers stack is complete and tested
- Ready for 02-02 (remaining security hardening work)
- CSP configuration may need updating in future phases if new external resources are added (e.g., Google Fonts, analytics scripts)

## Self-Check: PASSED

All files exist. All commits verified.

---
*Phase: 02-security-hardening*
*Completed: 2026-03-01*
