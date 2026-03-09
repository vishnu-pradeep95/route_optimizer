# Phase 1: Documentation Restructure & Validation - Research

**Researched:** 2026-03-09
**Domain:** Documentation restructure, content validation, cross-reference integrity
**Confidence:** HIGH

## Summary

This phase restructures ~3,600 lines of documentation across 11 root-level .md files into an organized `docs/` directory, validates all content against the current codebase (post-v1.4), fixes drift, and adds audience separation. The work is purely documentation -- no code logic changes, no new features.

The primary complexity is the cross-reference web. There are 30+ internal markdown links between documents that must be updated after files move from root to `docs/`. Additionally, GUIDE.md contains stale references to `plan/` directory content, and DISTRIBUTION.md's inclusion/exclusion lists reference root-level doc paths that will change. The `.github/` agent files also reference `plan/` and doc paths that need updating.

**Primary recommendation:** Execute in three waves: (1) move files and update all cross-references, (2) validate and fix content drift, (3) add audience badges and create INDEX.md. This ordering prevents double-work on cross-references.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Move all docs except README.md and CLAUDE.md into a `docs/` directory (flat, no subdirectories)
- Create `docs/INDEX.md` as a table of contents with one-line descriptions and audience tags
- Move `apps/kerala_delivery/api/ERROR-MAP.md` to `docs/` with the rest
- Delete `plan/` directory entirely (kerala_delivery_route_system_design.md and session-journal.md are stale)
- Clean up any other stale/unnecessary artifacts found during implementation (Claude's discretion)
- README.md becomes overview-only -- remove setup/install instructions, link to SETUP.md and DEPLOY.md
- DEPLOY.md and SETUP.md stay separate (different audiences: office employee vs developer)
- GUIDE.md handling: Claude's discretion on whether to keep as one file or split based on overlap found during validation
- ENV-COMPARISON.md stays as its own file, updated for accuracy
- Systematic audit: check every command, file path, endpoint, and environment variable mentioned in docs against actual codebase
- Fix drift in-place directly -- no separate validation report needed
- Validate and fix all internal cross-references (links between docs) after restructure
- Validate CLAUDE.md too -- verify test checklist, file paths, and conventions are still accurate
- Each doc gets a header badge: `> **Audience:** Office Employee` or `> **Audience:** Developer`
- docs/INDEX.md table also shows audience per document
- Office-employee docs use plain English only -- no jargon
- README.md is developer-focused -- office employees directed to DEPLOY.md immediately
- GOOGLE-MAPS.md kept as generic troubleshooting guide -- no reference to current invalid API key situation

### Claude's Discretion
- Whether to split GUIDE.md into focused docs (DAILY-OPS, TROUBLESHOOTING) vs keeping as one file
- Which additional stale artifacts to clean up beyond plan/ directory
- Exact INDEX.md format and descriptions

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

## Standard Stack

This phase is purely documentation work. No libraries or build tools are involved.

### Core Tools
| Tool | Purpose | Why Standard |
|------|---------|--------------|
| Git | Track file moves with history | `git mv` preserves file history across renames |
| Markdown | Documentation format | Already in use throughout the project |
| grep/find | Validation audit | Systematic check of file paths, commands, env vars in docs vs codebase |

### Supporting
| Tool | Purpose | When to Use |
|------|---------|-------------|
| `wc -l` | Line count verification | Confirm no content lost during restructure |
| `diff` | Before/after comparison | Verify only intended changes were made |

## Architecture Patterns

### Current Documentation Structure
```
routing_opt/
├── README.md          (544 lines) -- overview + quick start + architecture
├── CLAUDE.md          (93 lines)  -- AI assistant instructions (STAYS IN ROOT)
├── DEPLOY.md          (343 lines) -- office employee setup guide
├── SETUP.md           (438 lines) -- developer setup guide
├── GUIDE.md           (644 lines) -- beginner's guide to the platform
├── CSV_FORMAT.md      (236 lines) -- CSV format reference
├── DISTRIBUTION.md    (280 lines) -- distribution build workflow
├── ENV-COMPARISON.md  (114 lines) -- dev vs production comparison
├── GOOGLE-MAPS.md     (193 lines) -- API key troubleshooting
├── LICENSING.md       (492 lines) -- license lifecycle docs
├── ATTRIBUTION.md     (216 lines) -- third-party attribution
└── plan/              (stale, to be deleted)
    ├── kerala_delivery_route_system_design.md (superseded by PROJECT.md)
    ├── session-journal.md (obsolete)
    └── images/
```

### Target Documentation Structure
```
routing_opt/
├── README.md          -- overview-only, links to docs/
├── CLAUDE.md          -- AI assistant instructions (STAYS IN ROOT)
└── docs/
    ├── INDEX.md       -- table of contents with audience tags
    ├── DEPLOY.md      -- office employee setup (Audience: Office Employee)
    ├── SETUP.md       -- developer setup (Audience: Developer)
    ├── GUIDE.md       -- platform guide (Audience: Developer) [see recommendation below]
    ├── CSV_FORMAT.md  -- CSV format reference (Audience: Both)
    ├── DISTRIBUTION.md -- distribution workflow (Audience: Developer)
    ├── ENV-COMPARISON.md -- env comparison (Audience: Developer)
    ├── GOOGLE-MAPS.md -- API troubleshooting (Audience: Both)
    ├── LICENSING.md   -- license lifecycle (Audience: Developer)
    ├── ATTRIBUTION.md -- third-party licenses (Audience: Developer)
    └── ERROR-MAP.md   -- error message traceability (Audience: Developer)
```

### Pattern: Cross-Reference Update After Move

When files move from root to `docs/`, all internal links must be updated:

**Links FROM docs/ files TO other docs/ files (same directory):**
- Before: `[SETUP.md](SETUP.md)` -- relative to root
- After: `[SETUP.md](SETUP.md)` -- UNCHANGED (both files in docs/)

**Links FROM README.md (root) TO docs/ files:**
- Before: `[DEPLOY.md](DEPLOY.md)`
- After: `[DEPLOY.md](docs/DEPLOY.md)`

**Links FROM docs/ files TO README.md (root):**
- Before: `[README.md](README.md)`
- After: `[README.md](../README.md)`

### GUIDE.md Recommendation (Claude's Discretion)

**Recommendation: Keep GUIDE.md as a single file.** Rationale:

1. GUIDE.md is a developer-focused "beginner's guide" -- it explains architecture, code organization, data flow, and how to read the code. It is NOT an operations manual.
2. It has minimal overlap with other docs: Section 9 ("Setup & Running") duplicates SETUP.md content (lines 397-446), but the rest is unique conceptual content not found elsewhere.
3. Splitting into DAILY-OPS/TROUBLESHOOTING would be misleading -- GUIDE.md doesn't contain daily ops or troubleshooting content. DEPLOY.md already serves that role for office employees.
4. The only fix needed: remove Section 9's duplicate quick-start, replace with a link to SETUP.md, and fix stale references (plan/ paths, "Phase 4" outdated status, "351 tests" count).

### Anti-Patterns to Avoid
- **Moving files without updating cross-references first:** Results in broken links across the repository. Update all references in the same commit or immediately after.
- **Using `cp` instead of `git mv`:** Loses git file history. Always use `git mv` for the initial move.
- **Updating .github/ agent files that reference plan/:** These files reference `plan/kerala_delivery_route_system_design.md` and `plan/session-journal.md` in 15+ locations. After `plan/` is deleted, these references would be broken. These agent files SHOULD be updated or cleaned up.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Finding all cross-references | Manual text search | `grep -rn '\.md)' *.md` patterns | Ensures complete coverage |
| Verifying file paths in docs | Reading each doc manually | `grep -oP '\b[a-z_/]+\.(py\|sh\|yml\|md)' file.md \| while read f; do test -f "$f" && echo "OK: $f" \|\| echo "MISSING: $f"; done` | Catches drift systematically |
| Verifying endpoints in docs | Manual API inspection | Cross-reference with `grep '@app\.(get\|post)' main.py` | API has 20+ endpoints; manual checking is error-prone |

## Common Pitfalls

### Pitfall 1: ERROR-MAP.md Location Mismatch
**What goes wrong:** CONTEXT.md says ERROR-MAP.md is at `apps/kerala_delivery/api/ERROR-MAP.md`, but it actually lives at `.planning/milestones/v1.3-phases/20-sync-error-message-documentation/ERROR-MAP.md`.
**Why it happens:** ERROR-MAP.md was created as a planning artifact during v1.3 Phase 20, stored in the milestone directory, not the API directory.
**How to avoid:** Copy from the actual location: `.planning/milestones/v1.3-phases/20-sync-error-message-documentation/ERROR-MAP.md`. The file is 49 lines and traces 25 error messages to source code.
**Warning signs:** `apps/kerala_delivery/api/` only contains `__init__.py`, `main.py`, and `qr_helpers.py` -- no markdown files.

### Pitfall 2: Distribution Build Script Path Breakage
**What goes wrong:** `scripts/build-dist.sh` has rsync exclude patterns that reference root-level doc files. After moving docs to `docs/`, the build would accidentally include developer-only docs in customer distributions.
**Why it happens:** The build script excludes `GUIDE.md` and `CLAUDE.md` by name at root level. After moving GUIDE.md to `docs/GUIDE.md`, the exclude pattern `--exclude='GUIDE.md'` would still match (rsync exclude patterns match basenames), but the "What's included" table in DISTRIBUTION.md lists root-level paths.
**How to avoid:** After restructure, verify `scripts/build-dist.sh` exclude patterns still work correctly with the new `docs/` structure. Update DISTRIBUTION.md's included/excluded tables to reference `docs/` paths.
**Warning signs:** Run `./scripts/build-dist.sh test-v && tar tzf dist/kerala-delivery-test-v.tar.gz | grep -i guide` to verify exclusion.

### Pitfall 3: Stale .github/ Agent References to plan/
**What goes wrong:** 15+ references to `plan/kerala_delivery_route_system_design.md` and `plan/session-journal.md` across `.github/agents/`, `.github/instructions/`, and `.github/skills/` files. After `plan/` is deleted, these references become dead links.
**Why it happens:** The `.github/` agent ecosystem was created early in development when `plan/` was the primary planning directory. It was superseded by `.planning/PROJECT.md` but agent files were never updated.
**How to avoid:** Update or remove stale `plan/` references in `.github/` files as part of cleanup. Replace with references to `.planning/PROJECT.md` where appropriate, or remove the reference if the content is obsolete.
**Affected files (confirmed via grep):**
- `.github/instructions/git-integration.instructions.md` (1 reference)
- `.github/instructions/continuation-format.instructions.md` (2 references)
- `.github/agents/codebase-mapper.agent.md` (1 reference)
- `.github/agents/plan-checker.agent.md` (6 references)
- `.github/agents/session-journal.agent.md` (4 references)
- `.github/skills/diagnose-issues/SKILL.md` (1 reference)

### Pitfall 4: GUIDE.md Contains Outdated Information
**What goes wrong:** Multiple stale claims in GUIDE.md:
- References `plan/kerala_delivery_route_system_design.md` and `plan/session-journal.md` (lines 640-641) -- being deleted
- Says "Through Phase 4" (line 559) -- project is now at Phase 24 (v1.4 shipped)
- References "351 tests" (lines 424, 444, 580) -- likely outdated
- Directory tree (line 252) includes `plan/` -- being deleted
- "What's Built vs. What's Planned" section (557-601) is completely outdated
**How to avoid:** Audit GUIDE.md section by section. Remove or update stale references. The "What's Built vs. What's Planned" section should either be removed entirely or replaced with a link to ROADMAP.md.

### Pitfall 5: README.md Quick Start Section Removal Scope
**What goes wrong:** README.md has a 40-line Quick Start section (lines 13-55) plus additional architecture/setup content. The decision says "remove setup/install instructions" but README.md also contains API endpoint documentation, architecture diagrams, contributing guidelines, and a documentation table -- all of which should stay.
**Why it happens:** README.md is 544 lines, only ~50 lines are "setup/install" content. The rest is valuable overview content.
**How to avoid:** Only remove the Quick Start code block and "Stopping & Restarting" section. Keep: project description, architecture overview, API endpoints table, contributing section. Update the documentation table links to point to `docs/` paths.

### Pitfall 6: README.md Links to plan/ Design Document
**What goes wrong:** README.md line 540 links to `plan/kerala_delivery_route_system_design.md` in the "Key References" section.
**How to avoid:** Remove this reference entirely since `plan/` is being deleted and the content is superseded by `.planning/PROJECT.md`.

### Pitfall 7: DISTRIBUTION.md Includes/Excludes Tables Need Updating
**What goes wrong:** DISTRIBUTION.md (lines 49-78) lists which files are included/excluded in customer distributions. After restructure:
- "What's excluded" lists `GUIDE.md, CLAUDE.md, pytest.ini` -- GUIDE.md will be at `docs/GUIDE.md`
- "What's excluded" lists `plan/, .planning/` -- `plan/` will no longer exist
- "What's included" lists `README.md, DEPLOY.md, CSV_FORMAT.md, SETUP.md` at root level -- DEPLOY.md etc. will be in `docs/`
**How to avoid:** Update both tables to reflect the new `docs/` structure.

## Code Examples

### Moving Files with Git History Preservation
```bash
# Create docs/ directory
mkdir -p docs/

# Move files preserving git history
git mv DEPLOY.md docs/DEPLOY.md
git mv SETUP.md docs/SETUP.md
git mv GUIDE.md docs/GUIDE.md
git mv CSV_FORMAT.md docs/CSV_FORMAT.md
git mv DISTRIBUTION.md docs/DISTRIBUTION.md
git mv ENV-COMPARISON.md docs/ENV-COMPARISON.md
git mv GOOGLE-MAPS.md docs/GOOGLE-MAPS.md
git mv LICENSING.md docs/LICENSING.md
git mv ATTRIBUTION.md docs/ATTRIBUTION.md

# Copy ERROR-MAP.md from its actual location (not tracked separately, so use cp)
cp .planning/milestones/v1.3-phases/20-sync-error-message-documentation/ERROR-MAP.md docs/ERROR-MAP.md
git add docs/ERROR-MAP.md

# Delete plan/ directory
git rm -r plan/
```

### Cross-Reference Update Map

All internal markdown links that need updating after the move:

**README.md (root) -> docs/ files (9 links):**
```
DEPLOY.md       -> docs/DEPLOY.md
SETUP.md        -> docs/SETUP.md
LICENSING.md    -> docs/LICENSING.md
DISTRIBUTION.md -> docs/DISTRIBUTION.md
ENV-COMPARISON.md -> docs/ENV-COMPARISON.md
GOOGLE-MAPS.md  -> docs/GOOGLE-MAPS.md
ATTRIBUTION.md  -> docs/ATTRIBUTION.md
CSV_FORMAT.md   -> docs/CSV_FORMAT.md
GUIDE.md        -> docs/GUIDE.md
```

**docs/ files linking to each other (same directory, NO change needed):**
- DEPLOY.md -> CSV_FORMAT.md (stays as-is)
- LICENSING.md -> GOOGLE-MAPS.md (stays as-is)
- LICENSING.md -> DISTRIBUTION.md (stays as-is)
- GOOGLE-MAPS.md -> CSV_FORMAT.md (stays as-is)
- GOOGLE-MAPS.md -> LICENSING.md (stays as-is)
- DISTRIBUTION.md -> LICENSING.md (stays as-is)
- SETUP.md -> DEPLOY.md (stays as-is)

**docs/ files linking to README.md (root):**
- GUIDE.md -> `[README.md](README.md)` becomes `[README.md](../README.md)`

**docs/ files linking to SETUP.md (now same directory):**
- GUIDE.md -> `[SETUP.md](SETUP.md)` -- NO change needed (same dir)

### Audience Badge Format
```markdown
> **Audience:** Office Employee
```
or
```markdown
> **Audience:** Developer
```

### INDEX.md Template
```markdown
# Documentation Index

| Document | Description | Audience |
|----------|-------------|----------|
| [DEPLOY.md](DEPLOY.md) | Office setup and daily use guide | Office Employee |
| [CSV_FORMAT.md](CSV_FORMAT.md) | Upload file format reference | Both |
| [GOOGLE-MAPS.md](GOOGLE-MAPS.md) | Google Maps API troubleshooting | Both |
| [SETUP.md](SETUP.md) | Developer environment setup | Developer |
| [GUIDE.md](GUIDE.md) | Platform architecture and learning path | Developer |
| [DISTRIBUTION.md](DISTRIBUTION.md) | Build and deliver customer distributions | Developer |
| [LICENSING.md](LICENSING.md) | License generation, activation, lifecycle | Developer |
| [ENV-COMPARISON.md](ENV-COMPARISON.md) | Dev vs production environment differences | Developer |
| [ATTRIBUTION.md](ATTRIBUTION.md) | Third-party licenses and attribution | Developer |
| [ERROR-MAP.md](ERROR-MAP.md) | Error message traceability (message -> source code) | Developer |
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 10 root-level .md files | docs/ directory with INDEX.md | This phase | Cleaner repo root, discoverable docs |
| plan/ directory for design docs | .planning/PROJECT.md | v1.0 milestone (2026-03-01) | plan/ is stale, needs deletion |
| No audience separation | Header badges + plain English for employees | This phase | Clearer who each doc is for |

**Deprecated/outdated items found during research:**
- `plan/` directory: Both files superseded by `.planning/PROJECT.md` and GSD planning structure
- GUIDE.md Section 12 ("What's Built vs. What's Planned"): References Phase 4 as current; project is now at Phase 24
- GUIDE.md "Need Help?" section (lines 640-644): Links to plan/ files being deleted
- README.md "Key References" table (line 540): Links to plan/ design doc being deleted
- GUIDE.md test count: Says "351 tests" in multiple places; likely outdated post-v1.4
- `.planning/codebase/STRUCTURE.md`: References `plan/` directory (line 52-54, 164-166) -- not user-facing but should be noted

## Comprehensive Cross-Reference Inventory

### Files That Link TO Other Docs (must update after restructure)

| Source File | Links To | Line(s) | Update Required |
|-------------|----------|---------|-----------------|
| README.md | DEPLOY.md | 9, 524 | Add `docs/` prefix |
| README.md | SETUP.md | 57, 416, 516, 525 | Add `docs/` prefix |
| README.md | LICENSING.md | 457, 526 | Add `docs/` prefix |
| README.md | DISTRIBUTION.md | 527 | Add `docs/` prefix |
| README.md | ENV-COMPARISON.md | 528 | Add `docs/` prefix |
| README.md | GOOGLE-MAPS.md | 529 | Add `docs/` prefix |
| README.md | ATTRIBUTION.md | 530 | Add `docs/` prefix |
| README.md | CSV_FORMAT.md | 531 | Add `docs/` prefix |
| README.md | GUIDE.md | 532 | Add `docs/` prefix |
| README.md | plan/...design.md | 540 | Remove (plan/ deleted) |
| GUIDE.md | plan/...design.md | 640 | Remove (plan/ deleted) |
| GUIDE.md | plan/session-journal.md | 641 | Remove (plan/ deleted) |
| GUIDE.md | SETUP.md | 434, 642 | No change (same dir) |
| GUIDE.md | README.md | 643 | Change to `../README.md` |
| DEPLOY.md | CSV_FORMAT.md | 177, 227 | No change (same dir) |
| SETUP.md | DEPLOY.md | 7 | No change (same dir) |
| LICENSING.md | GOOGLE-MAPS.md | 492 | No change (same dir) |
| LICENSING.md | DISTRIBUTION.md | 305 | No change (same dir) |
| DISTRIBUTION.md | LICENSING.md | 128, 198, 233, 265 | No change (same dir) |
| GOOGLE-MAPS.md | CSV_FORMAT.md | 171 | No change (same dir) |
| GOOGLE-MAPS.md | LICENSING.md | 20 | No change (same dir) |

### Files Outside docs/ That Reference Doc Paths

| Source File | References | Action |
|-------------|-----------|--------|
| `.github/copilot-instructions.md` | `SETUP.md` (2 refs) | Update to `docs/SETUP.md` |
| `.github/agents/kerala-delivery-route-architect.agent.md` | `SETUP.md` (2 refs) | Update to `docs/SETUP.md` |
| `.github/instructions/git-integration.instructions.md` | `SETUP.md`, `plan/` | Update paths |
| `.github/instructions/continuation-format.instructions.md` | `plan/` (2 refs) | Remove or update |
| `.github/agents/codebase-mapper.agent.md` | `plan/` (1 ref) | Remove or update |
| `.github/agents/plan-checker.agent.md` | `plan/` (6 refs) | Remove or update |
| `.github/agents/session-journal.agent.md` | `plan/` (4 refs) | Remove or update |
| `.github/skills/diagnose-issues/SKILL.md` | `plan/` (1 ref) | Remove or update |
| `DISTRIBUTION.md` exclusion table | Root-level doc names | Update to `docs/` paths |
| `scripts/build-dist.sh` | Exclude `GUIDE.md` | Verify still works with `docs/GUIDE.md` |

## Drift Validation Checklist

The following items need systematic verification during the validation wave:

### Commands to Verify
- [ ] All `docker compose` commands in docs match actual service names
- [ ] `./scripts/start.sh` and `./scripts/bootstrap.sh` references are correct
- [ ] `python scripts/import_orders.py` and `python scripts/geocode_batch.py` commands work
- [ ] `curl http://localhost:8000/health` endpoint exists (confirmed: yes)
- [ ] `pytest tests/ -v` works as documented
- [ ] Dashboard paths: `apps/kerala_delivery/dashboard` exists (confirmed: yes)

### File Paths to Verify
- [ ] All `core/` paths mentioned in GUIDE.md exist
- [ ] All `scripts/` referenced in docs exist (SETUP.md references `import_orders.py`, `geocode_batch.py`)
- [ ] `data/osrm/` path exists (confirmed: yes, in .gitignore)
- [ ] `infra/alembic/` path (GUIDE.md references `infra/alembic/alembic.ini` -- actual path is `alembic.ini` at root)

### Endpoints to Verify
- [ ] All API endpoints listed in CLAUDE.md match `@app.get/@app.post` in `main.py`
- [ ] CLAUDE.md lists `GET /api/vehicles` -- confirmed present in main.py
- [ ] CLAUDE.md lists `POST /api/telemetry` -- confirmed present in main.py

### Environment Variables to Verify
- [ ] All env vars mentioned in docs exist in `.env.example`
- [ ] `CORS_ALLOWED_ORIGINS` format matches actual usage
- [ ] `RATE_LIMIT_ENABLED` is documented correctly

### CLAUDE.md Specific Checks
- [ ] Driver PWA path: `apps/kerala_delivery/driver_app/` (confirmed: exists)
- [ ] Tailwind v4 prefix conventions (confirmed: `tw:` colon syntax)
- [ ] API endpoint list matches actual endpoints
- [ ] Test checklist items are still accurate for current PWA state

## Open Questions

1. **Test count in GUIDE.md**
   - What we know: GUIDE.md says "351 tests" in multiple places (lines 424, 444, 580)
   - What's unclear: Actual current test count after v1.4 (Playwright E2E tests were added)
   - Recommendation: Run `pytest tests/ --collect-only -q 2>/dev/null | tail -1` during implementation to get actual count, update accordingly

2. **OSRM health endpoint claim**
   - What we know: README.md line 416 says "OSRM has no /health endpoint" but GUIDE.md line 442 says to check `curl http://localhost:5000/health`
   - What's unclear: These contradict each other -- one doc says OSRM has no health endpoint, another says to curl it
   - Recommendation: Verify during implementation which is correct and fix the inconsistent doc

3. **scripts/ directory drift**
   - What we know: STRUCTURE.md (from March 1) lists 5 scripts. Actual directory has 18 scripts (many added post-v1.0: bootstrap.sh, build-dist.sh, deploy.sh, install.sh, start.sh, stop.sh, reset.sh, etc.)
   - What's unclear: Whether any docs reference scripts that have been renamed or removed
   - Recommendation: Cross-reference all script mentions in docs against actual `scripts/` contents during validation

4. **DISTRIBUTION.md's included files list accuracy**
   - What we know: Lists specific files included in distribution tarball
   - What's unclear: Whether the list matches current `build-dist.sh` rsync excludes (the authoritative source)
   - Recommendation: After restructure, run a test build and verify included/excluded files match documentation

## Sources

### Primary (HIGH confidence)
- Direct file system inspection of all 11 root-level .md files
- `grep` search of all cross-references between markdown files
- `apps/kerala_delivery/api/main.py` endpoint inspection (20+ routes confirmed)
- `scripts/build-dist.sh` exclusion list inspection
- `.planning/milestones/v1.3-phases/20-sync-error-message-documentation/ERROR-MAP.md` -- actual location confirmed
- `.github/` directory inspection for plan/ references

### Secondary (MEDIUM confidence)
- `.planning/codebase/STRUCTURE.md` -- dated 2026-03-01, some entries may be outdated (scripts list is incomplete)
- GUIDE.md content analysis for overlap/split decision

## Metadata

**Confidence breakdown:**
- File structure and cross-references: HIGH -- verified via direct file system inspection
- Drift identification: HIGH -- cross-referenced docs against actual codebase
- GUIDE.md split recommendation: HIGH -- thorough content analysis performed
- .github/ agent cleanup scope: MEDIUM -- confirmed references exist but full impact of removal not assessed

**Research date:** 2026-03-09
**Valid until:** 2026-04-09 (documentation structure -- stable domain)
