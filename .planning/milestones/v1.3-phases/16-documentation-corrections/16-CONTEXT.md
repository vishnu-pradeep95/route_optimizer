# Phase 16: Documentation Corrections - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix README.md, DEPLOY.md, and SETUP.md so they reference correct container names, correct scripts, and are written for their respective audiences (developer vs office employee). No new features, no error message changes (Phase 17), no new documentation pages.

</domain>

<decisions>
## Implementation Decisions

### REPO_URL replacement strategy
- Developer pre-fills the actual repository URL before customer delivery (matches Phase 13 pattern where .env.example has real Google Maps key pre-baked)
- DEPLOY.md: skip the `git clone` step entirely — project folder is pre-installed on the laptop by developer/IT before handoff
- README.md: keep `<REPO_URL>` placeholder with a developer-facing note indicating it must be replaced before delivery
- SETUP.md: apply same placeholder treatment as README

### README Quick Start scope
- Add employee callout at top pointing to DEPLOY.md (enhance existing line 7 note)
- Keep manual developer steps (venv, pip, docker compose) — README is developer-facing
- Fix stale commands where automated equivalents exist (Claude's discretion on which to mark as "only if running outside Docker")
- Docker Services table: fix `routing-db` → `lpg-db`, fix health check user `routeopt` → `routing`, keep 4 primary services only (no init containers)
- Keep `docker compose` commands in Stopping & Restarting section as-is (developer-facing)

### DEPLOY.md daily section compression
- Replace 4-command startup (cd, service docker start, docker compose up, source .venv) with single `./start.sh`
- Remove terminal file-copy step for CDCMS exports — dashboard has drag-and-drop upload from Windows
- Remove Sections 4 (Understanding CDCMS Export) and 5 (Address Cleaning) entirely — replaced with single cross-link to CSV_FORMAT.md
- Update Quick Reference Card (Section 9) ASCII art to match simplified flow: Ubuntu → start.sh → Chrome → upload → print QR
- Target: daily usage section fits on one printed page

### DEPLOY.md setup section restructure
- Replace manual Docker install commands (Section 2.2) with `./bootstrap.sh` — matches Phase 13's one-command install
- Assume project pre-installed by developer on the laptop — no clone or USB copy step in DEPLOY.md
- Add prominent "Use Ubuntu terminal, NOT PowerShell" warning at top of document (bold callout box after intro, before Quick Start)
- Troubleshooting section: fix stale commands to reference start.sh/bootstrap.sh, leave error message wording for Phase 17

### Claude's Discretion
- Exact README `<REPO_URL>` note format (developer-facing comment vs callout)
- Which README Quick Start commands to annotate as "only if running outside Docker"
- Troubleshooting section wording updates (command fixes only)
- DEPLOY.md Table of Contents renumbering after section removal
- How much to compress the "How to update the system" subsection

</decisions>

<specifics>
## Specific Ideas

- Phase 13's bootstrap.sh and Phase 14's start.sh replace all manual Docker/compose commands in DEPLOY.md
- CSV_FORMAT.md (Phase 15) replaces DEPLOY.md Sections 4 and 5 — single source of truth for CDCMS format info
- The "pre-installed by developer" approach means DEPLOY.md starts at "Open Ubuntu → cd routing_opt → ./bootstrap.sh" with no prerequisites except WSL

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/bootstrap.sh`: One-command fresh install (Docker CE, .env, map data, compose up) — replaces DEPLOY.md Section 2.2-2.3
- `scripts/start.sh`: Zero-input daily startup (Docker daemon, compose up, health poll, URL output) — replaces DEPLOY.md Section 3.1
- `scripts/install.sh`: Developer-facing install (used by bootstrap.sh internally)
- `CSV_FORMAT.md`: Complete CDCMS reference — replaces DEPLOY.md Sections 4-5

### Confirmed Inaccuracies
- README line 404: container `routing-db` → actual is `lpg-db` (docker-compose.yml line 36)
- README line 404: health check user `routeopt` → actual is `routing` (docker-compose.yml line 54)
- README line 15, DEPLOY.md line 118, SETUP.md line 49: `<REPO_URL>` placeholder unfilled
- DEPLOY.md Section 3.1: 4 manual commands → should be `./start.sh`
- DEPLOY.md Section 2.2: manual Docker install → should be `./bootstrap.sh`

### Integration Points
- DEPLOY.md cross-links to CSV_FORMAT.md (new)
- README employee callout links to DEPLOY.md (existing, enhance)
- DEPLOY.md references bootstrap.sh and start.sh (new)

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 16-documentation-corrections*
*Context gathered: 2026-03-05*
