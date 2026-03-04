# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

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

### Cumulative Quality

| Milestone | LOC (Python) | LOC (TS) | LOC (HTML/JS) | Key Addition |
|-----------|-------------|----------|---------------|-------------|
| v1.0 | 16.6k | 3.3k | -- | Security headers, test baseline |
| v1.1 | 17.5k | 3.6k | 1.8k | DaisyUI migration, PWA refresh |
| v1.2 | 8.3k | 3.7k | 1.9k | Dead code removed (-9.2k Python), typed helpers, config consolidation |

### Top Lessons (Verified Across Milestones)

1. Foundation phases (design system, test infra, security) pay off immediately in subsequent phases
2. Data integrity before UI polish — always fix the data pipeline before making it look good
3. CSS conventions must be established and enforced in the first phase — late fixes are expensive
4. Tech debt milestones with specific, measurable requirements (not vague "cleanup") execute faster and verify unambiguously
5. Config consolidation eliminates cross-codebase drift — do it early in the project lifecycle
