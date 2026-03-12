---
phase: quick-4
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - CLAUDE.md
  - docs/DEPLOY.md
  - docs/SETUP.md
  - docs/GUIDE.md
  - docs/INDEX.md
  - docs/DISTRIBUTION.md
  - docs/LICENSING.md
  - docs/ENV-COMPARISON.md
autonomous: true
requirements: [AUDIT-01]

must_haves:
  truths:
    - "All test count references match the actual count (561 tests, not 420+)"
    - "All script references in docs point to files that actually exist"
    - "End-of-day stop command in DEPLOY.md mentions stop.sh (not raw docker compose down)"
    - "SETUP.md batch script references use correct CLI flags"
    - "GUIDE.md project status reflects v2.2 completion"
    - "No stale version references or outdated workflow instructions remain"
  artifacts:
    - path: "CLAUDE.md"
      provides: "Corrected test count, accurate script/command references"
    - path: "docs/DEPLOY.md"
      provides: "Corrected end-of-day command, accurate new-computer flow"
    - path: "docs/SETUP.md"
      provides: "Corrected references, accurate quick-reference table"
    - path: "docs/GUIDE.md"
      provides: "Updated project status to include v2.0-v2.2 milestones"
  key_links: []
---

<objective>
Audit and fix all operator-facing documentation for freshness, accuracy, and completeness
-- especially around setup/reset/nuke workflows for deploying on a new computer.

Purpose: Ensure that someone cloning this repo on a brand new machine can follow
the docs end-to-end without hitting stale references, wrong test counts, missing
script mentions, or outdated workflow descriptions.

Output: Updated CLAUDE.md + docs/*.md files with all identified staleness fixed.
</objective>

<context>
@CLAUDE.md
@docs/DEPLOY.md
@docs/SETUP.md
@docs/GUIDE.md
@docs/INDEX.md
@docs/CSV_FORMAT.md
@docs/DISTRIBUTION.md
@docs/LICENSING.md
@docs/ENV-COMPARISON.md
@docs/ERROR-MAP.md
@docs/ATTRIBUTION.md
@docs/GOOGLE-MAPS.md
@scripts/bootstrap.sh
@scripts/install.sh
@scripts/start.sh
@scripts/stop.sh
@scripts/reset.sh
@scripts/deploy.sh
@scripts/backup_db.sh
@scripts/build-dist.sh
@scripts/verify-dist.sh
@scripts/osrm_setup.sh
@scripts/build-pwa-css.sh
@.env.example
</context>

<tasks>

<task type="auto">
  <name>Task 1: Fix stale facts and numbers across all docs</name>
  <files>
    CLAUDE.md
    docs/GUIDE.md
    docs/DEPLOY.md
    docs/SETUP.md
  </files>
  <action>
Fix every stale factual reference identified in the audit. Here is the complete
list of issues found:

**CLAUDE.md:**
1. Test count says "All 420+ tests" -- actual count is 561. Change to "All 560+ tests".
2. Verify all API endpoint paths in the E2E checklist are still accurate by
   grepping `apps/kerala_delivery/api/main.py` for route definitions. Update any
   that have changed.

**docs/GUIDE.md:**
1. Section 12 "Project Status" says "24 development phases (milestones v1.0
   through v1.4)". This is stale -- project is now through v2.2 with 35+ phases.
   Update to: "The platform is fully functional through 35 development phases
   across milestones v1.0 through v2.2. All core features are complete: CDCMS/CSV
   upload, geocoding with PostGIS caching, VROOM+OSRM route optimization, driver
   PWA, operations dashboard, GPS telemetry, fleet management, hardware-bound
   licensing, address preprocessing pipeline, and production deployment with
   Caddy reverse proxy."
2. The "See ROADMAP.md (the Development Phases section) or .planning/PROJECT.md"
   link says `../README.md` but should link to planning docs since ROADMAP is in
   .planning/. Update to just reference `.planning/PROJECT.md` and `.planning/ROADMAP.md`.
3. Section 6 folder tree does not mention `core/licensing/` or `core/data_import/cdcms_preprocessor.py`.
   Add `core/licensing/` line after `core/data_import/` with description
   "Hardware-bound license key validation".

**docs/DEPLOY.md:**
1. End-of-day section shows `docker compose down` as the stop command. The project
   has a dedicated `./scripts/stop.sh` script with GC capabilities. Update to:
   ```
   # Stop all services (optional -- saves laptop battery)
   cd ~/routing_opt
   ./scripts/stop.sh
   ```
   And add a note: "To also clean up disk space: `./scripts/stop.sh --gc`"
2. Quick Reference Card's "END OF DAY" item #6 shows `docker compose down`.
   Update to `./scripts/stop.sh`.
3. The "How to update the system" section tells users to run `./scripts/bootstrap.sh`
   after `git pull`. This is correct -- verify bootstrap.sh handles re-runs
   gracefully (it does -- it preserves .env and skips Docker install if present).
   No change needed here.

**docs/SETUP.md:**
1. Step 5 Node.js: recommends `setup_22.x` from NodeSource. CLAUDE.md says
   Node.js v24 is the current version. Update to `setup_24.x` and the verify
   output to "v24.x".
2. Step 9 OSRM Data Preparation: manually runs docker commands for osrm-extract,
   osrm-partition, osrm-customize. The project has `scripts/osrm_setup.sh` that
   automates all of this. Add a note at the top of Step 9:
   "**Quick option:** Run `./scripts/osrm_setup.sh` to automate all OSRM steps below."
3. Quick Reference table: "Run backend server" shows
   `uvicorn apps.kerala_delivery.api.main:app --reload`. This works but is
   inconsistent with Docker-based workflow. Add note "(without Docker)" after it.
4. Quick Reference table: missing entries for `./scripts/start.sh`,
   `./scripts/stop.sh`, `./scripts/reset.sh`, `./scripts/backup_db.sh`. Add them:
   - `Start system (daily)` | `./scripts/start.sh`
   - `Stop system` | `./scripts/stop.sh`
   - `Stop + cleanup` | `./scripts/stop.sh --gc`
   - `Reset for fresh deploy` | `./scripts/reset.sh`
   - `Backup database` | `./scripts/backup_db.sh`
5. The "Deploying on a New Laptop" section at the bottom is good but does not
   mention the license activation step. Add step between current 5 and 6:
   "5b. **Activate license:** See [LICENSING.md](LICENSING.md) for license key setup"
  </action>
  <verify>
    <automated>grep -c "560+" CLAUDE.md && grep "v2.2" docs/GUIDE.md && grep "stop.sh" docs/DEPLOY.md && grep "setup_24" docs/SETUP.md && grep "start.sh" docs/SETUP.md</automated>
  </verify>
  <done>
    - CLAUDE.md test count updated to 560+
    - GUIDE.md project status reflects v2.2 with accurate phase count
    - GUIDE.md folder tree includes core/licensing/
    - DEPLOY.md end-of-day uses stop.sh instead of raw docker compose down
    - SETUP.md Node.js version updated to v24
    - SETUP.md references osrm_setup.sh
    - SETUP.md quick reference includes all operator scripts
    - SETUP.md new-laptop checklist includes license activation
  </done>
</task>

<task type="auto">
  <name>Task 2: Verify cross-doc consistency and fix remaining gaps</name>
  <files>
    docs/DISTRIBUTION.md
    docs/INDEX.md
    docs/ERROR-MAP.md
  </files>
  <action>
Verify and fix remaining cross-document consistency issues:

**docs/DISTRIBUTION.md:**
1. "What's included" table says `docs/DEPLOY.md, docs/CSV_FORMAT.md, docs/SETUP.md`
   as user-facing docs. Verify this matches what build-dist.sh actually includes.
   Looking at the rsync excludes: GUIDE.md is excluded, but GOOGLE-MAPS.md,
   ERROR-MAP.md, and LICENSING.md are NOT excluded -- meaning they ARE included
   in the distribution. Update the "What's included" table to add:
   - `docs/GOOGLE-MAPS.md` | Google Maps API setup guide
   - `docs/ERROR-MAP.md` | Error message traceability
   - `docs/INDEX.md` | Documentation index
   Also check if docs/ENV-COMPARISON.md is included (it is, since it's not in
   the exclude list). Add it:
   - `docs/ENV-COMPARISON.md` | Dev vs prod differences
2. Version example throughout uses `v1.4` and `v1.3`. These are fine as examples
   since they are generic placeholders. No change needed.
3. Verify the "What's excluded" table matches current rsync excludes in
   build-dist.sh. The script excludes `plan/` but the table does not list it.
   This is a no-op since `plan/` does not exist in the repo. No change needed.

**docs/INDEX.md:**
1. Currently lists 10 documents. Verify all 10 docs still exist (they do -- confirmed).
2. The index does not list `docs/GOOGLE-MAPS.md` separately -- wait, it DOES
   list it. Good. All docs are present and the index is complete.
3. No changes needed -- INDEX.md is accurate and complete.

**docs/ERROR-MAP.md:**
1. Header says "Verified: 2026-03-10". The line numbers in the code locations
   may have drifted since then due to v2.1 and v2.2 changes. Run a spot-check
   on 3-4 key error messages to verify the line numbers are still accurate.
   Grep for the exact error message strings in the source files and update any
   line numbers that have shifted.
2. Update the "Verified" date to today's date after confirming accuracy.
  </action>
  <verify>
    <automated>grep "GOOGLE-MAPS.md" docs/DISTRIBUTION.md && grep "2026-03-12" docs/ERROR-MAP.md</automated>
  </verify>
  <done>
    - DISTRIBUTION.md "What's included" table lists all docs that actually ship
    - ERROR-MAP.md line number references spot-checked and corrected if drifted
    - ERROR-MAP.md verified date updated
    - INDEX.md confirmed accurate (no changes needed)
  </done>
</task>

</tasks>

<verification>
After both tasks complete:
1. `grep -r "420" CLAUDE.md docs/` should return 0 results (stale test count gone)
2. `grep "stop.sh" docs/DEPLOY.md` should find the updated end-of-day command
3. `grep "v2.2" docs/GUIDE.md` should find the updated project status
4. All docs referenced in docs/INDEX.md should exist: `for f in DEPLOY CSV_FORMAT GOOGLE-MAPS SETUP GUIDE DISTRIBUTION LICENSING ENV-COMPARISON ATTRIBUTION ERROR-MAP; do test -f "docs/${f}.md" && echo "OK: $f" || echo "MISSING: $f"; done`
</verification>

<success_criteria>
- Zero stale test count references (420 -> 560+)
- DEPLOY.md end-of-day workflow uses scripts/stop.sh
- SETUP.md quick reference includes all operator scripts (start, stop, reset, backup)
- SETUP.md new-laptop section includes license activation step
- SETUP.md Node.js version matches project reality (v24)
- GUIDE.md project status reflects all milestones through v2.2
- DISTRIBUTION.md included-docs table matches what build-dist.sh actually ships
- ERROR-MAP.md line numbers spot-checked and verified date updated
</success_criteria>
