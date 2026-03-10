# Phase 1: Documentation Restructure & Validation - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Restructure ~3,600 lines of documentation across 10 root-level .md files into an organized docs/ directory, validate all content against the current codebase (post-v1.4), fix drift, and ensure clear audience separation between developer and office-employee docs.

</domain>

<decisions>
## Implementation Decisions

### File Organization
- Move all docs except README.md and CLAUDE.md into a `docs/` directory (flat, no subdirectories)
- Create `docs/INDEX.md` as a table of contents with one-line descriptions and audience tags
- Move `apps/kerala_delivery/api/ERROR-MAP.md` to `docs/` with the rest
- Delete `plan/` directory entirely (kerala_delivery_route_system_design.md and session-journal.md are stale)
- Clean up any other stale/unnecessary artifacts found during implementation (Claude's discretion)

### Content Overlap
- README.md becomes overview-only — remove setup/install instructions, link to SETUP.md and DEPLOY.md
- DEPLOY.md and SETUP.md stay separate (different audiences: office employee vs developer)
- GUIDE.md handling: Claude's discretion on whether to keep as one file or split based on overlap found during validation
- ENV-COMPARISON.md stays as its own file, updated for accuracy

### Drift Validation
- Systematic audit: check every command, file path, endpoint, and environment variable mentioned in docs against actual codebase
- Fix drift in-place directly — no separate validation report needed
- Validate and fix all internal cross-references (links between docs) after restructure
- Validate CLAUDE.md too — verify test checklist, file paths, and conventions are still accurate

### Audience Separation
- Each doc gets a header badge: `> **Audience:** Office Employee` or `> **Audience:** Developer`
- docs/INDEX.md table also shows audience per document
- Office-employee docs use plain English only — no jargon. "Start the system" not "docker compose up". Technical terms get parenthetical explanations if unavoidable
- README.md is developer-focused — office employees directed to DEPLOY.md immediately
- GOOGLE-MAPS.md kept as generic troubleshooting guide — no reference to current invalid API key situation

### Claude's Discretion
- Whether to split GUIDE.md into focused docs (DAILY-OPS, TROUBLESHOOTING) vs keeping as one file
- Which additional stale artifacts to clean up beyond plan/ directory
- Exact INDEX.md format and descriptions

</decisions>

<code_context>
## Existing Code Insights

### Documentation Files (current)
- `README.md` (544 lines) — project overview + quick start + architecture
- `DEPLOY.md` (343 lines) — office employee deployment guide
- `SETUP.md` (438 lines) — developer setup guide
- `GUIDE.md` (644 lines) — daily operations and troubleshooting
- `CSV_FORMAT.md` (236 lines) — CSV format reference
- `DISTRIBUTION.md` (280 lines) — distribution build workflow
- `ENV-COMPARISON.md` (114 lines) — dev vs production comparison
- `GOOGLE-MAPS.md` (193 lines) — API key troubleshooting
- `LICENSING.md` (492 lines) — license lifecycle docs
- `ATTRIBUTION.md` (216 lines) — third-party attribution
- `apps/kerala_delivery/api/ERROR-MAP.md` — error message traceability

### Stale Artifacts
- `plan/kerala_delivery_route_system_design.md` — pre-GSD system design (superseded by PROJECT.md)
- `plan/session-journal.md` — early development journal (obsolete)

### Codebase Maps Available
- `.planning/codebase/` has 7 analysis documents (ARCHITECTURE, CONCERNS, CONVENTIONS, INTEGRATIONS, STACK, STRUCTURE, TESTING) — useful for validating technical accuracy of docs

### Integration Points
- README.md links to DEPLOY.md, SETUP.md (will need path updates)
- CLAUDE.md references file paths and test checklist (needs validation)
- `.github/` has AGENTS-GUIDE.md and copilot-instructions.md (may reference doc paths)

</code_context>

<specifics>
## Specific Ideas

- Existing "Problem -- fix action" error pattern from v1.3 should be maintained in any office-employee documentation
- The `> **Employee?**` callout in current README is the right pattern — direct non-technical users away immediately
- v1.4 ERROR-MAP.md traces 25 error messages to source code — preserve this traceability when moving to docs/

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-documentation-restructure-validation*
*Context gathered: 2026-03-08*
