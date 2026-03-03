# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

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

### Cumulative Quality

| Milestone | LOC (Python) | LOC (TS) | LOC (HTML/JS) | Key Addition |
|-----------|-------------|----------|---------------|-------------|
| v1.0 | 16.6k | 3.3k | -- | Security headers, test baseline |
| v1.1 | 17.5k | 3.6k | 1.8k | DaisyUI migration, PWA refresh |

### Top Lessons (Verified Across Milestones)

1. Foundation phases (design system, test infra, security) pay off immediately in subsequent phases
2. Data integrity before UI polish — always fix the data pipeline before making it look good
3. CSS conventions must be established and enforced in the first phase — late fixes are expensive
