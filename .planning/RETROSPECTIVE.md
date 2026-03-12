# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v2.1 — Licensing & Distribution Security

**Shipped:** 2026-03-11
**Phases:** 7 | **Plans:** 13 | **Timeline:** 2 days

### What Was Built
- Stable machine fingerprint using /etc/machine-id + CPU model, replacing spoofable hostname+MAC+container_id with Docker bind mounts
- Cython-compiled licensing modules (.so) with full build pipeline: strip dev-mode -> hash -> compile -> validate -> package
- Single enforce(app) entry point — main.py has zero inline enforcement logic; SHA256 integrity manifest in compiled .so
- Periodic runtime re-validation every 500 requests with one-way state guard and graceful shutdown on integrity failure
- License renewal via renewal.key file drop without re-keying, X-License-Expires-In header, /health license diagnostics
- E2E security test suite with 4 scenarios covering fingerprint mismatch, re-validation, integrity tamper, and renewal
- Complete documentation rewrite: LICENSING.md from scratch, ERROR-MAP.md + SETUP.md + MIGRATION.md updated for v2.1

### What Worked
- TDD approach for all licensing modules — every phase started with failing tests, then implemented to pass
- Cython async limitation identified early (Phase 6 research) — enforcement.py kept as .py wrapper calling compiled sync functions
- Milestone audit → gap closure → re-audit flow caught 2 critical integration breaks (build-dist.sh ENVIRONMENT stripping, docker-compose.prod.yml missing mount)
- Phase 11 (gap closure) was surgical: 1 commit, 3 targeted fixes, re-audit passed immediately
- LICENSING.md written from scratch using codebase as source of truth instead of editing stale content — eliminated all legacy errors
- Module-level state pattern (_license_state, _request_counter) kept enforcement logic self-contained in compiled .so

### What Was Inefficient
- ROADMAP phase checkboxes showed `[ ]` for Phases 7-11 despite being complete — same recurring tracking issue from v2.0
- summary-extract CLI reported 0 phases/plans because phase directories were already moved to milestones/ before milestone complete ran
- Phase 8 directory named `08-api-dead-code-hygiene` (leftover from v1.2 naming) instead of `08-runtime-protection` — no functional impact but confusing in archive

### Patterns Established
- Empty `_INTEGRITY_MANIFEST` dict as dev mode signal — consistent pattern across enforce(), verify_integrity(), and maybe_revalidate()
- _STATUS_SEVERITY one-way state guard — prevents accidental INVALID→VALID transitions without restart
- `hashlib.file_digest()` (Python 3.11+) for clean SHA256 computation — one line per file
- sed pipe delimiters for manifest injection — SHA256 hex is [0-9a-f] only, safe for any delimiter
- Renewal check placed before validate_license() to avoid state guard blocking recovery
- REVALIDATION_INTERVAL as env-var-configurable module constant — testable without recompilation

### Key Lessons
1. Cython cannot compile `async def` — enforcement middleware must use async .py wrapper calling sync compiled functions
2. Milestone audit → gap closure → re-audit is now a proven pattern (v1.3, v2.0, v2.1 all benefited)
3. Build pipeline validation (import checks, ENVIRONMENT stripping) must cover ALL files, not just the obvious ones — enforcement.py was missed initially
4. Docker Compose volume mounts must be consistent across all compose files (dev, test, prod) — production missing /etc/machine-id caused fingerprint mismatch
5. Documentation written from scratch using code as truth > editing existing docs — old content has legacy errors that survive incremental edits
6. Security modules benefit from self-contained state (module-level variables) over app.state — harder to inspect/modify from outside

### Cost Observations
- Model mix: opus for all phases (quality profile)
- Sessions: ~3 sessions across 2 days
- Notable: 13 plans in 2 days (6.5 plans/day) — fastest plans/day rate. Phase 11 gap closure in 1 commit. Average plan duration: ~4 minutes.

---

## Milestone: v2.0 — Documentation & Error Handling

**Shipped:** 2026-03-10
**Phases:** 4 | **Plans:** 9 | **Timeline:** 2 days

### What Was Built
- Consolidated ~3,600 lines of documentation into organized docs/ directory with audience badges and docs/INDEX.md as central hub
- ErrorResponse Pydantic model with 22 namespaced ErrorCodes, request ID tracing via ContextVar middleware, global exception handler
- Startup health gates for PostgreSQL/OSRM/VROOM, enhanced /health endpoint with per-service status, tenacity retry decorators
- Frontend error UI: color-coded ErrorBanner with auto-recovery, inline ErrorTable for CSV failures, collapsible ErrorDetail, per-service health status bar
- Playwright E2E tests for all dashboard error UI components
- Fixed fetchHealth 503 handling and all 15 ERROR_HELP_URLS anchor fragments; updated ERROR-MAP.md line references

### What Worked
- Milestone audit-first approach: initial audit found 4 gaps, Phases 3-4 were added specifically to close them, re-audit passed 100%
- Gap closure phases were surgical and fast (Phase 3: 2min, Phase 4: 4min combined)
- ErrorResponse model with error_response() helper standardized all 30+ HTTPException call sites
- Call-site retry wrapping (instead of modifying core modules) minimized blast radius
- E2E tests used client-side validation errors to avoid API_KEY dependency — pragmatic testing strategy

### What Was Inefficient
- ROADMAP phase 2 plan checkboxes showed `[ ]` despite all 4 plans being complete — execution tracking didn't update them
- summary-extract CLI failed for all 9 SUMMARY files — one_liner field not populated, required manual extraction
- Milestone was labeled "v1.0" in STATE.md but conflicted with existing v1.0 archive — required rename to v2.0 during completion

### Patterns Established
- ErrorResponse model with error_response() helper for consistent API error structure
- ERROR_HELP_URLS mapping from error codes to documentation anchors (Python + TypeScript in sync)
- Direct fetch() for endpoints where non-200 response bodies contain useful data (503 health)
- DaisyUI collapse for progressive disclosure of error details
- force:true click pattern for DaisyUI components with hidden checkbox overlays

### Key Lessons
1. Milestone version numbering should be agreed upfront — reusing "v1.0" when v1.0 archives already exist creates conflicts
2. Error handling infrastructure is best added as a dedicated milestone after the MVP — retrofitting 30+ error responses is manageable when the API surface is stable
3. Audit → gap closure → re-audit is the right flow for milestone completion — it caught 4 real integration issues
4. SUMMARY.md frontmatter fields (one_liner) should be populated during execution, not deferred — CLI tools depend on them
5. Documentation line references drift on every code change — ERROR-MAP.md needs update whenever main.py changes

### Cost Observations
- Model mix: opus for all phases (quality profile)
- Sessions: ~2 sessions across 2 days
- Notable: 9 plans in 2 days (4.5 plans/day). Phase 3 and 4 completed in minutes — gap closure phases are extremely efficient when well-scoped

---

## Milestone: v1.4 — Ship-Ready QA

**Shipped:** 2026-03-09
**Phases:** 4 | **Plans:** 10 | **Timeline:** 2 days

### What Was Built
- 38-test Playwright E2E suite across 4 projects (API, Driver PWA, Dashboard, License) running in ~22s
- CI/CD pipeline expanded to 4 jobs with E2E tests on push to main, failure artifact uploads, and README status badge
- Graceful shutdown script (stop.sh) with --gc mode for log truncation, dangling image pruning, and orphan cleanup
- Automated distribution tarball verification (verify-dist.sh) in isolated Docker stack on port 8002
- Fixed all 426 pytest unit tests with proper vehicle mocking and API_KEY env isolation
- 5 documentation artifacts: DISTRIBUTION.md, LICENSING.md lifecycle, ENV-COMPARISON.md, GOOGLE-MAPS.md, ATTRIBUTION.md

### What Worked
- Milestone audit (17/17 requirements, 4/4 phases, 6/6 E2E flows) gave high confidence before archival
- Parallel plan execution within phases (23-01 and 23-02, 24-01 and 24-02 ran concurrently)
- Pre-geocoded CSV fallback strategy avoided blocking on invalid Google Maps API key
- Docker Compose override pattern for isolated license testing (port 8001) prevented dev stack interference
- Sequential story pattern for PWA tests maintained realistic user flow state across 7 tests
- Documentation extracted commands from actual scripts (build-dist.sh, verify-dist.sh) rather than writing from memory

### What Was Inefficient
- Plan estimated 64 pytest failures but only 12 remained — previous phases had silently fixed most as side effects
- Docker Compose port merging behavior required switching from override to standalone compose file mid-plan (23-02)
- `tr -dc < /dev/urandom | head` SIGPIPE under `set -o pipefail` required openssl rand workaround
- ROADMAP progress table rows for phases 21-24 had incorrect column alignment (missing milestone column)

### Patterns Established
- Playwright 4-project config: separate projects for api, driver-pwa, dashboard, license with different viewports
- UI + API dual verification: test both DOM state change AND separate API GET to confirm server persistence
- Standalone Docker Compose for testing: avoids additive port merging and container_name conflicts
- Copyleft-first attribution: flag restrictive licenses at top for compliance scanning
- Failure-only CI artifacts: upload-artifact with `if: failure()` to minimize storage

### Key Lessons
1. Docker Compose override files merge ports additively — use standalone compose files for isolated test stacks
2. `set -o pipefail` breaks `tr < /dev/urandom | head` with SIGPIPE — use `openssl rand` instead
3. Container logs must be truncated BEFORE `docker compose down` (down removes containers and their log files)
4. Pre-existing test failures should be tracked with exact counts, not estimates — "64 failures" became 12
5. Documentation phases benefit from running in parallel when docs cover independent domains
6. Docker log files are root-owned — need `sudo test -f` not bare `-f` for access checks

### Cost Observations
- Model mix: opus for planning/execution, sonnet for audit/integration checking
- Sessions: ~2 sessions across 2 days
- Notable: 10 plans in 2 days (5 plans/day) — fastest milestone per-plan due to well-scoped automation and documentation tasks

---

## Milestone: v1.3 — Office-Ready Deployment

**Shipped:** 2026-03-07
**Phases:** 8 | **Plans:** 10 | **Timeline:** 14 days

### What Was Built
- One-command WSL bootstrap installer (bootstrap.sh) with Docker CE auto-install, environment guards, and two-phase resume
- Zero-input daily startup script (start.sh) with 60s health polling, container-state diagnosis, and failure recovery
- Comprehensive CSV format reference (CSV_FORMAT.md) with error glossary, address cleaning pipeline, and example rows
- Humanized error messages across upload validation and geocoding (plain English "problem -- fix action" pattern)
- Distribution build script (build-dist.sh) with compiled licensing module (.pyc only)
- OSRM Docker image pinned to v5.27.1 with POSIX-compatible entrypoints
- Documentation overhaul: README, DEPLOY.md, SETUP.md corrected for non-technical audience
- Error message traceability artifact (ERROR-MAP.md) mapping 25 messages to source code

### What Worked
- Milestone audit caught 3 real gaps (documentation drift + deployment blocker) that would have shipped broken
- Gap closure phases (19, 20) were surgical — 1 plan each, completed same day
- Source-code-verified documentation (CSV_FORMAT.md error messages extracted from actual code paths)
- "Problem -- fix action" error pattern created consistent UX across all user-facing errors
- Guard-first architecture in bootstrap.sh: fast-fail prevents partial installations

### What Was Inefficient
- Phase 17 (error humanization) drifted documentation written in Phase 15 — the audit caught this but it should have been a dependency in the roadmap
- Phases 17-20 progress table rows had incorrect column alignment (missing milestone column)
- Some ROADMAP plan checkboxes were `[ ]` despite phases being complete (17, 18, 19, 20)
- 14-day timeline was longer than other milestones because v1.3 included gap closure phases added mid-milestone

### Patterns Established
- Two-phase resume pattern for bash scripts needing session restart (marker file + re-exec)
- if/else pattern for set -euo pipefail safe branching on function return values
- ERROR-MAP.md as traceability artifact for documentation-to-code sync verification
- Pin Docker images to specific versions (never use :latest in operational files)

### Key Lessons
1. Documentation phases should depend on the code phases they document — Phase 15 documenting error messages should have been after Phase 17 (which changed them)
2. Milestone audits are essential before completion — v1.3 audit found a deployment blocker that would have shipped broken to the customer
3. Shell scripts under `set -euo pipefail` need careful branching — bare function calls + `$?` don't work as expected
4. Docker :latest tags are a deployment hazard — always pin versions for operational stability
5. Gap closure phases should be lightweight (1 plan, same day) — they're targeted fixes, not new feature work

### Cost Observations
- Model mix: opus for planning/execution, sonnet for audit/integration checking
- Sessions: ~8 sessions across 14 days
- Notable: gap closure phases (19, 20) at ~2min each — fastest plans in the project

---

## Milestone: v1.2 — Tech Debt & Cleanup

**Shipped:** 2026-03-04
**Phases:** 5 | **Plans:** 9 | **Timeline:** 2 days

### What Was Built
- API dead code removal: `_build_fleet()`, unused imports, stale `OSRM_URL`, incorrect docstrings
- Typed PostGIS geometry helpers (`_point_lat`/`_point_lng`) replacing all `type: ignore` suppressions
- Single `/api/config` endpoint consolidating depot coords, safety multiplier, and office phone number
- Driver PWA safety: real phone from API config, GPS `watchPosition` leak fix, styled offline `<dialog>`
- PWA quality: proper PNG icons (192/512px), tailwind.css in SW pre-cache, debug logging gate
- Dashboard cleanup: dead CSS aliases removed, design tokens, `RouteDetail` type fix, exhaustive `StatusBadge` switch
- Batch route loading (`GET /api/routes?include_stops=true`) replacing N+1 LiveMap pattern
- Driver-verified geocode wiring: successful GPS deliveries auto-populate geocode cache
- Duplicate detection threshold validation against 54 production geocode entries

### What Worked
- Parallel phase execution: Phases 8, 11, 12 ran independently with zero conflicts
- TDD in Phase 12: writing failing tests first for geocode wiring caught guard condition edge cases
- Backward-compatible API changes: `include_stops` query param preserved existing consumers
- Minimal dependency approach: pure Python PNG generation (struct+zlib) avoided adding Pillow
- Config endpoint as forward-wiring: depot_lat/depot_lng served but not yet consumed by PWA, ready for future use

### What Was Inefficient
- Phases 8 and 9 ROADMAP entries still showed "Not started" in the progress table despite being complete — state tracking fell behind
- Phase 9 plan was marked "TBD" in ROADMAP even after execution completed
- SUMMARY.md `one_liner` field was null for all v1.2 phases — not populated during execution

### Patterns Established
- `console.log` override pattern for debug gating: `console.log = () => {}` when `!DEBUG`
- Non-blocking geocache save: try/except after primary commit so cache failures never break delivery flow
- Optional query params for backward-compatible batch endpoints
- Exhaustive switch + `never`-typed default for TypeScript enum-like unions

### Key Lessons
1. Tech debt milestones benefit from fine-grained requirements mapping — 22 specific REQ-IDs made verification unambiguous
2. `type: ignore` suppressions should be replaced with typed helpers as soon as the pattern repeats (PostGIS geometry was 6 sites)
3. Config consolidation should happen early — hardcoded values across 3 codebases (API, PWA, dashboard) create drift risk
4. Production data validation (12-02) is high-value/low-effort — 54 rows confirmed all 4 threshold values were appropriate
5. ROADMAP progress table needs automated sync — manual updates fell behind during rapid phase execution

### Cost Observations
- Model mix: opus for planning/execution, sonnet for integration checker
- Sessions: ~3 sessions across 2 days
- Notable: 9 plans in 2 days (4.5 plans/day) — faster than v1.1's 5.3 plans/day due to cleanup scope being well-defined

---

## Milestone: v1.1 — Polish & Reliability

**Shipped:** 2026-03-03
**Phases:** 4 | **Plans:** 16 | **Timeline:** 3 days

### What Was Built
- Unified geocoding cache with `normalize_address()` pure function and DB-only caching
- Geocoding cost transparency (cache hit vs API call tracking) and duplicate location detection (15m proximity)
- Complete dashboard UI overhaul: 4 pages migrated to DaisyUI components with lucide-react icons, responsive 3-tier sidebar, skeleton loading states, empty states
- Driver PWA refresh: WCAG AAA outdoor contrast, hero card next-stop architecture, segmented progress bar, dark fail dialog, Call Office FAB
- Print-optimized QR sheets with 210px codes for arm-length scanning
- Reusable component library: EmptyState, StatusBadge, deriveRouteStatus()

### What Worked
- Data integrity before cosmetics: fixing geocoding (Phases 4-5) before UI overhaul (Phases 6-7) meant UI work never hit data bugs
- Small, focused plans (avg 1.7 min for Phase 6) enabled rapid iteration with visual verification checkpoints
- Playwright MCP E2E testing caught real bugs that manual review would have missed
- DaisyUI component vocabulary reduced CSS decision fatigue — consistent `tw:btn`, `tw:table`, `tw:badge` patterns
- Phase 7 running parallel to Phase 6 (independent codebases) was validated — no integration conflicts

### What Was Inefficient
- Phase 6 planned for 6 plans but expanded to 9 — visual verification rounds (06-06, 06-07, 06-08, 06-09) added during execution for gap closure
- Tailwind prefix syntax confusion (`tw-` vs `tw:`) caused a full-codebase fix commit mid-milestone
- Milestone audit was performed before Phases 5-7 started — became immediately stale and required no action to close gaps
- ROADMAP.md plan counts fell out of sync with actual execution (6 planned vs 9 delivered for Phase 6)

### Patterns Established
- Tailwind v4 `prefix(tw)` always uses **colon** syntax: `tw:flex`, `tw:card`, `tw:btn`
- CSS selectors escape the colon: `.tw\:flex`, `.tw\:card-body`
- Visual verification as a plan (not just a checkpoint) — creates accountability and summary trail
- Toast-then-advance pattern for mobile UX: 1.5s feedback before auto-advancing
- Two-tier text hierarchy for high-contrast PWAs: primary + secondary only, no muted tier

### Key Lessons
1. Run milestone audits after all phases are complete, not during — early audits create noise without value
2. Plan counts should be treated as estimates; visual verification rounds are natural additions, not scope creep
3. CSS prefix conventions must be established in Phase 1 and enforced immediately — fixing later costs a full-codebase commit
4. Pure function modules (normalize_address) with comprehensive unit tests make refactoring safe and fast
5. DaisyUI component migration is faster page-by-page than component-by-component — each page is a self-contained unit

### Cost Observations
- Model mix: predominantly opus for planning/execution, haiku for subagents
- Sessions: ~6 sessions across 3 days
- Notable: Phase 6 at 1.7 min/plan was the fastest phase due to repetitive page migration pattern

---

## Milestone: v1.0 — Infrastructure

**Shipped:** 2026-03-01
**Phases:** 3 | **Plans:** 8

### What Was Built
- Tailwind 4 + DaisyUI 5 with collision-safe `tw:` prefix
- HTTP security headers (CSP, CORS, Permissions-Policy)
- Geocoding failure reporting with per-row reasons and import summary UI
- Test baseline: Vatakara coordinates, asyncio_mode=auto

### What Worked
- Foundation-first approach: design system before component work
- Security hardening early prevented retrofitting later

### What Was Inefficient
- Limited data available for retrospective (v1.0 completed before retrospective process established)

### Patterns Established
- oklch color format for DaisyUI themes
- CSP allows unsafe-inline styles (required for Leaflet)
- Zero-success returns structured HTTP 200 (not HTTPException 400)

### Key Lessons
1. Establish testing conventions (coordinate system, async config) in Phase 1 to avoid retrofitting
2. Security headers are easier to add fresh than to retrofit — do it early

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Timeline | Phases | Plans | Key Change |
|-----------|----------|--------|-------|------------|
| v1.0 | ~1 day | 3 | 8 | Foundation-first approach |
| v1.1 | 3 days | 4 | 16 | Visual verification as formal plans; Playwright MCP E2E testing |
| v1.2 | 2 days | 5 | 9 | Fine-grained REQ-IDs; parallel independent phases; TDD for data wiring |
| v1.3 | 14 days | 8 | 10 | Milestone audit + gap closure; documentation-as-code traceability |
| v1.4 | 2 days | 4 | 10 | E2E testing as quality gate; parallel doc plans; standalone compose for isolation |
| v2.0 | 2 days | 4 | 9 | Audit-driven gap closure; error handling as dedicated milestone; version naming discipline |
| v2.1 | 2 days | 7 | 13 | TDD for security modules; Cython compilation pipeline; audit→gap→re-audit proven pattern |

### Cumulative Quality

| Milestone | LOC (Python) | LOC (TS) | LOC (HTML/JS) | LOC (Shell) | Key Addition |
|-----------|-------------|----------|---------------|-------------|-------------|
| v1.0 | 16.6k | 3.3k | -- | -- | Security headers, test baseline |
| v1.1 | 17.5k | 3.6k | 1.8k | -- | DaisyUI migration, PWA refresh |
| v1.2 | 8.3k | 3.7k | 1.9k | -- | Dead code removed (-9.2k Python), typed helpers, config consolidation |
| v1.3 | 2.7k | 3.7k | 2.0k | 1.6k | Bootstrap/startup scripts, CSV docs, humanized errors, dist build |
| v1.4 | 17.9k | 5.0k | -- | 3.0k | E2E test suite, CI/CD pipeline, stop/verify scripts, 5 doc artifacts |
| v2.0 | 19.5k | 6.0k | -- | 3.0k | ErrorResponse model, health gates, retry logic, frontend error UI, doc restructure |
| v2.1 | 3.2k | 4.3k | -- | 2.6k | Cython .so licensing, enforce(app), runtime re-validation, renewal mechanism, E2E security tests |

### Top Lessons (Verified Across Milestones)

1. Foundation phases (design system, test infra, security) pay off immediately in subsequent phases
2. Data integrity before UI polish — always fix the data pipeline before making it look good
3. CSS conventions must be established and enforced in the first phase — late fixes are expensive
4. Tech debt milestones with specific, measurable requirements (not vague "cleanup") execute faster and verify unambiguously
5. Config consolidation eliminates cross-codebase drift — do it early in the project lifecycle
6. Milestone audits before completion catch real bugs — v1.3 audit found a deployment blocker and 8 stale docs
7. Documentation phases must depend on the code phases they document — otherwise content drifts immediately
8. Pin Docker image versions in all operational files — :latest is a ticking deployment bomb
9. Docker Compose override files merge ports additively — use standalone compose files for isolated test stacks
10. Container logs must be truncated BEFORE `docker compose down` — down removes containers and their log files
11. Pre-existing test failure counts should be tracked with exact numbers, not estimates carried forward from stale context
12. Error handling infrastructure is best added after MVP — stable API surface makes retrofitting manageable
13. Audit → gap closure → re-audit is the right milestone completion flow — catches real integration issues before shipping
14. Security modules benefit from self-contained state (module-level variables) — harder to inspect/modify from outside the compiled .so
15. Build pipeline validation must cover ALL files (enforcement.py was missed initially) — exhaustive checks prevent gap re-opening
16. Documentation written from scratch using code as truth is more reliable than editing existing docs — legacy errors survive incremental edits
