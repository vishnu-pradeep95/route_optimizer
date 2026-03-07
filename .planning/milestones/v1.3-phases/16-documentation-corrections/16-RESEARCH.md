# Phase 16: Documentation Corrections - Research

**Researched:** 2026-03-05
**Domain:** Documentation accuracy -- README.md, DEPLOY.md, SETUP.md corrections
**Confidence:** HIGH

## Summary

This phase is a documentation-only phase with no code changes. All three documents (README.md, DEPLOY.md, SETUP.md) contain stale references from earlier project phases that predate the Phase 13 bootstrap.sh, Phase 14 start.sh, and Phase 15 CSV_FORMAT.md additions. The inaccuracies are well-defined and can be enumerated exhaustively by cross-referencing each document against docker-compose.yml, .env.example, and the actual script files.

The work divides into two distinct streams: (1) factual corrections across all three docs (container names, credential defaults, stale manual commands), and (2) structural restructuring of DEPLOY.md for the non-technical office employee audience. Stream 1 is mechanical find-and-replace with verification. Stream 2 requires content reorganization -- removing duplicate sections (Sections 4 and 5 are now in CSV_FORMAT.md), replacing multi-command workflows with script references, and adding navigation aids (Ubuntu warning, step numbering, cross-links).

**Primary recommendation:** Execute as two sequential plans -- (1) factual corrections across README/SETUP, (2) DEPLOY.md restructure -- since the DEPLOY.md restructure is a larger editorial task that benefits from the factual corrections being done first.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- REPO_URL replacement strategy: Developer pre-fills before customer delivery; DEPLOY.md skips git clone entirely (pre-installed by developer); README.md keeps `<REPO_URL>` placeholder with developer-facing note; SETUP.md gets same placeholder treatment as README
- README Quick Start scope: Add employee callout at top pointing to DEPLOY.md; keep manual developer steps; fix stale commands; Docker Services table: fix `routing-db` to `lpg-db`, fix health check user `routeopt` to `routing`, keep 4 primary services only
- DEPLOY.md daily section compression: Replace 4-command startup with `./scripts/start.sh`; remove terminal file-copy step; remove Sections 4 and 5 entirely; update Quick Reference Card ASCII art; target one printed page for daily section
- DEPLOY.md setup section restructure: Replace manual Docker install with `./scripts/bootstrap.sh`; assume pre-installed by developer; add prominent Ubuntu-not-PowerShell warning; fix troubleshooting stale commands

### Claude's Discretion
- Exact README `<REPO_URL>` note format (developer-facing comment vs callout)
- Which README Quick Start commands to annotate as "only if running outside Docker"
- Troubleshooting section wording updates (command fixes only)
- DEPLOY.md Table of Contents renumbering after section removal
- How much to compress the "How to update the system" subsection

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DOCS-01 | README fixes stale container names (`routing-db` -> `lpg-db`) | Exact line numbers and correct values identified from docker-compose.yml cross-reference (see Confirmed Inaccuracies section) |
| DOCS-02 | README removes manual steps now automated by db-init | Line 37 `alembic upgrade head` is automated by db-init container; line 32 `sleep 5` + manual health check is automated by start.sh health polling; OSRM init container automates map data prep |
| DOCS-03 | README and DEPLOY.md fill `<REPO_URL>` placeholder | Three files affected: README line 15, DEPLOY.md line 118, SETUP.md line 49. Strategy: README/SETUP keep placeholder with developer note; DEPLOY.md removes git clone entirely |
| DOCS-04 | DEPLOY.md restructured for non-technical office employee audience | Section removal list, cross-link targets, script references, and Quick Reference Card redesign all documented below |

</phase_requirements>

## Confirmed Inaccuracies (Exhaustive Audit)

### README.md

| Line | Current (Wrong) | Correct (Source) | Requirement |
|------|----------------|------------------|-------------|
| 15 | `git clone <REPO_URL> routing_opt` | Keep placeholder, add developer note: "Replace before customer delivery" | DOCS-03 |
| 37 | `alembic upgrade head` | Remove or annotate "automated by db-init container" | DOCS-02 |
| 32-34 | `sleep 5` + manual `curl` + `docker compose ps` | Annotate "only if running outside Docker" or note start.sh handles this | DOCS-02 |
| 404 | Container `routing-db` | `lpg-db` (docker-compose.yml line 36) | DOCS-01 |
| 404 | Health check `pg_isready -U routeopt` | `pg_isready -U routing -d routing_opt` (docker-compose.yml line 54) | DOCS-01 |
| 426 | `POSTGRES_DB` defaults to `routeopt` | Defaults to `routing_opt` (.env.example line 20, docker-compose.yml line 40) | DOCS-01 |

**Note:** README line 425 `POSTGRES_USER` defaults to `routing` -- this IS correct already.

### DEPLOY.md

| Line | Current (Wrong) | Correct (Source) | Requirement |
|------|----------------|------------------|-------------|
| 82-99 | Manual Docker install commands (apt-get, gpg, etc.) | Replace with `./scripts/bootstrap.sh` | DOCS-04 |
| 118 | `git clone <REPO_URL> routing_opt` | Remove entirely (pre-installed assumption) | DOCS-03 |
| 122 | `./scripts/install.sh` | `./scripts/bootstrap.sh` (bootstrap calls install.sh internally) | DOCS-04 |
| 153-156 | 4-command daily startup | Replace with `./scripts/start.sh` | DOCS-04 |
| 167-170 | Terminal cp command for CDCMS file | Remove (dashboard has drag-and-drop upload) | DOCS-04 |
| 225-270 | Section 4: Understanding CDCMS Export | Remove entirely, cross-link to CSV_FORMAT.md | DOCS-04 |
| 274-298 | Section 5: Address Cleaning | Remove entirely, cross-link to CSV_FORMAT.md | DOCS-04 |
| 363-365 | Troubleshooting restart: manual docker compose | Reference `./scripts/start.sh` | DOCS-04 |
| 376-380 | Update system: git pull + venv + alembic + compose | Compress (Claude's discretion) | DOCS-04 |
| 416-445 | Quick Reference Card ASCII art | Update to match: Ubuntu -> start.sh -> Chrome -> upload -> print QR | DOCS-04 |

### SETUP.md

| Line | Current (Wrong) | Correct (Source) | Requirement |
|------|----------------|------------------|-------------|
| 49 | `git clone <REPO_URL> routing_opt` | Keep placeholder with developer note (same as README) | DOCS-03 |
| 179 | `POSTGRES_USER` defaults to `routeopt` | Defaults to `routing` (.env.example line 18) | DOCS-01 |
| 180 | `POSTGRES_DB` defaults to `routeopt` | Defaults to `routing_opt` (.env.example line 20) | DOCS-01 |

## Architecture Patterns

### Pattern 1: Cross-Reference Verification

**What:** Every factual claim in documentation must be verified against its source-of-truth file before committing.

**When to use:** For every container name, command, default value, or file path mentioned in docs.

**Source-of-truth mapping:**

| Doc Claim | Verify Against |
|-----------|---------------|
| Container names | `docker-compose.yml` `container_name:` fields |
| Health checks | `docker-compose.yml` `healthcheck:` blocks |
| Environment defaults | `.env.example` + `docker-compose.yml` environment sections |
| Script commands | Actual scripts in `scripts/` directory |
| Script paths | `ls scripts/` -- files are at `scripts/bootstrap.sh` and `scripts/start.sh`, NOT at project root |

### Pattern 2: Audience-Appropriate Writing

**What:** README and SETUP.md are developer-facing; DEPLOY.md is non-technical office employee-facing.

**Key differences:**

| Aspect | Developer (README/SETUP) | Employee (DEPLOY.md) |
|--------|------------------------|---------------------|
| Terminology | "container", "compose", "venv" | "Ubuntu app", "run this command" |
| Error handling | Show error codes, explain fixes | Show what you see, tell what to do |
| Commands | Multiple steps OK | Single script call |
| Assumptions | Knows git, Docker, Python | Knows how to open Ubuntu, type commands |

### Pattern 3: Section Cross-Linking

**What:** Information should exist in exactly one place, with other docs linking to it.

**This phase establishes:**
- CDCMS format details: single source = CSV_FORMAT.md, cross-linked from DEPLOY.md
- Employee setup: single source = DEPLOY.md, cross-linked from README.md line 7
- Developer setup: single source = SETUP.md/README.md

### Anti-Patterns to Avoid
- **Duplicating content across docs:** DEPLOY.md Sections 4 and 5 duplicate information now in CSV_FORMAT.md. Remove, don't sync.
- **Mixing audiences:** Don't add developer commands (docker compose logs, alembic) to DEPLOY.md daily use sections.
- **Leaving breadcrumbs to removed sections:** After removing Sections 4 and 5, verify no remaining text references "See Section 4" or "See Section 5".

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CDCMS documentation | Re-explain CDCMS in DEPLOY.md | Cross-link to CSV_FORMAT.md | Single source of truth; Phase 15 already created comprehensive reference |
| Docker install instructions | Copy-paste apt commands | Reference `./scripts/bootstrap.sh` | Phase 13 already handles all edge cases (WSL version check, RAM, filesystem) |
| Daily startup procedure | Multi-step manual commands | Reference `./scripts/start.sh` | Phase 14 handles Docker daemon, health polling, error diagnosis |

## Common Pitfalls

### Pitfall 1: Script Path Mismatch
**What goes wrong:** CONTEXT.md uses shorthand `./start.sh` and `./bootstrap.sh` but actual scripts are at `./scripts/start.sh` and `./scripts/bootstrap.sh`.
**Why it happens:** CONTEXT.md discussion used abbreviated names.
**How to avoid:** Always use the full path `./scripts/start.sh` and `./scripts/bootstrap.sh` in documentation.
**Warning signs:** Running `./start.sh` from project root gives "command not found".

### Pitfall 2: Broken Internal References After Section Removal
**What goes wrong:** Removing DEPLOY.md Sections 4 and 5 breaks the Table of Contents anchors and any in-document references.
**Why it happens:** Markdown section links are fragile; removing sections shifts numbering.
**How to avoid:** After section removal, renumber all remaining sections and update the ToC. Search for "Section 4", "Section 5", and any anchor links.
**Warning signs:** Clicking a ToC link scrolls to the wrong section.

### Pitfall 3: Inconsistent POSTGRES_DB Default
**What goes wrong:** README says `routeopt`, docker-compose.yml says `routing_opt`, .env.example says `routing_opt`.
**Why it happens:** Early project used `routeopt` for both user and DB; later renamed DB to `routing_opt` but docs weren't updated.
**How to avoid:** Cross-check every database reference against docker-compose.yml as the canonical source.
**Warning signs:** `routeopt` appearing anywhere in documentation.

### Pitfall 4: Leaving Stale OSRM Manual Steps
**What goes wrong:** README line 409 says "See SETUP.md for download and preprocessing steps" for OSRM. But the osrm-init container now handles this automatically.
**Why it happens:** The OSRM init container was added in Phase 4D but the docs note was never updated.
**How to avoid:** Add a note that OSRM data is auto-downloaded on first `docker compose up`. Keep SETUP.md manual steps for developers who want to run OSRM outside Docker.
**Warning signs:** Users following manual OSRM steps when Docker does it for them.

## Editing Specifications

### README.md Changes (DOCS-01, DOCS-02, DOCS-03)

**Line 7 (employee callout):** Enhance the existing note. Currently:
```markdown
> **Employee?** If you're setting up this system at the office, skip to the [Employee Deployment Guide (DEPLOY.md)](DEPLOY.md) — no programming knowledge required.
```
This is already fine. No change needed unless planner wants to add emphasis.

**Line 15 (REPO_URL):** Add a developer note after or near the placeholder:
```markdown
git clone <REPO_URL> routing_opt && cd routing_opt
# ^^^ Replace <REPO_URL> with the actual repository URL before customer delivery
```

**Lines 32-37 (manual steps automated by init containers):**
- Line 37 `alembic upgrade head`: Add comment "# Automated by db-init container -- only needed outside Docker"
- Lines 32-34 `sleep 5` + manual curl: Add comment "# start.sh handles health polling -- only needed outside Docker"

**Line 404 (Docker Services table):**
```markdown
| PostgreSQL + PostGIS | `lpg-db` | 5432 | `pg_isready -U routing -d routing_opt` |
```

**Line 426 (Environment Variables table):**
```markdown
| `POSTGRES_DB` | No | Defaults to `routing_opt` |
```

### DEPLOY.md Changes (DOCS-03, DOCS-04)

**New element after intro (before Quick Start):** Add Ubuntu warning callout:
```markdown
> **IMPORTANT:** Always use the **Ubuntu** app from the Start menu. Do NOT use
> PowerShell, Command Prompt, or Windows Terminal. All commands in this guide
> must be run in Ubuntu.
```

**Quick Start (Section 0):** Simplify to reference bootstrap.sh:
```markdown
cd ~/routing_opt
./scripts/bootstrap.sh
```

**Section 2.2 (Install Software):** Replace entire manual Docker install block with:
```markdown
Open Ubuntu, navigate to the project folder, and run:
cd ~/routing_opt
./scripts/bootstrap.sh
```

**Section 2.3 (Download and Install):** Remove git clone. The project is pre-installed.

**Section 3.1 (Start the System):** Replace 4-command block with:
```markdown
./scripts/start.sh
```

**Section 3.2 (Export from CDCMS):** Remove the `cp /mnt/c/...` terminal copy step. Keep only "Export from CDCMS" + "drag and drop onto the dashboard".

**Sections 4 and 5:** Remove entirely. Replace with single cross-link:
```markdown
## Understanding CDCMS and CSV Formats

See [CSV_FORMAT.md](CSV_FORMAT.md) for complete documentation on:
- What file types are accepted (.csv, .xlsx, .xls)
- Which CDCMS columns are used and which are ignored
- Standard CSV column reference
- What the system does to clean addresses
- Common error messages and how to fix them
```

**Section 6 (Troubleshooting):** Fix stale commands:
- "Cannot connect to Docker" fix: `./scripts/start.sh` (handles Docker start)
- "System is slow" fix: `./scripts/start.sh` (instead of manual docker compose)
- "How to update" subsection: compress (Claude's discretion)

**Section 9 (Quick Reference Card):** Rewrite ASCII art:
```
1. OPEN Ubuntu from Start menu
2. START: cd ~/routing_opt && ./scripts/start.sh
3. OPEN Chrome: http://localhost:8000/dashboard/
4. UPLOAD CDCMS file (drag & drop)
5. PRINT QR codes for drivers
6. END OF DAY: docker compose down (optional)
```

**Table of Contents:** Renumber after removing Sections 4 and 5. New numbering:
1. What You Need
2. One-Time Setup
3. Daily Use
4. Understanding CDCMS and CSV Formats (cross-link, replaces old 4+5)
5. Troubleshooting (was 6)
6. Costs (was 7)
7. Important Rules (was 8)
8. Quick Reference Card (was 9)

### SETUP.md Changes (DOCS-01, DOCS-03)

**Line 49 (REPO_URL):** Add developer note same as README.

**Lines 179-180 (Postgres defaults):**
```markdown
| `POSTGRES_USER` | Defaults to `routing` | No |
| `POSTGRES_DB` | Defaults to `routing_opt` | No |
```

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Manual verification (documentation phase -- no automated tests) |
| Config file | N/A |
| Quick run command | Visual inspection + grep verification |
| Full suite command | `grep -rn 'routing-db\|routeopt\|REPO_URL\|alembic upgrade' README.md DEPLOY.md SETUP.md` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DOCS-01 | No `routing-db` or `routeopt` in README | smoke | `grep -c 'routing-db' README.md` should return 0 | N/A |
| DOCS-01 | `lpg-db` appears in Docker Services table | smoke | `grep 'lpg-db' README.md` should match | N/A |
| DOCS-02 | `alembic upgrade head` annotated or removed from Quick Start | smoke | `grep -n 'alembic' README.md` -- verify context | N/A |
| DOCS-03 | No bare `<REPO_URL>` without developer note in README | smoke | `grep -c '<REPO_URL>' README.md` -- 1 occurrence with note | N/A |
| DOCS-03 | No `<REPO_URL>` in DEPLOY.md | smoke | `grep -c '<REPO_URL>' DEPLOY.md` should return 0 | N/A |
| DOCS-04 | DEPLOY.md references `./scripts/start.sh` | smoke | `grep 'scripts/start.sh' DEPLOY.md` should match | N/A |
| DOCS-04 | DEPLOY.md references `./scripts/bootstrap.sh` | smoke | `grep 'scripts/bootstrap.sh' DEPLOY.md` should match | N/A |
| DOCS-04 | DEPLOY.md Sections 4/5 removed, cross-link to CSV_FORMAT.md | smoke | `grep 'CSV_FORMAT.md' DEPLOY.md` should match | N/A |
| DOCS-04 | Ubuntu warning present in DEPLOY.md | smoke | `grep -i 'powershell' DEPLOY.md` should match warning | N/A |

### Sampling Rate
- **Per task commit:** Run full grep verification suite
- **Per wave merge:** Visual read-through of all three documents
- **Phase gate:** All grep checks pass + manual read-through confirms coherence

### Wave 0 Gaps
None -- no test infrastructure needed for documentation-only phase.

## Open Questions

1. **Script path in DEPLOY.md: `./scripts/start.sh` vs `./start.sh`**
   - What we know: Scripts live at `scripts/bootstrap.sh` and `scripts/start.sh`. CONTEXT.md shorthand says `./start.sh` and `./bootstrap.sh`.
   - What's unclear: Whether to create root-level symlinks or just use the full `./scripts/` path.
   - Recommendation: Use the actual paths (`./scripts/start.sh`, `./scripts/bootstrap.sh`) in documentation. Do NOT create symlinks -- that would be a code change outside phase scope.

2. **DEPLOY.md one-page target for daily section**
   - What we know: Current DEPLOY.md is 454 lines. Daily section (Section 3) spans lines 144-221 (77 lines). After removing the cp command and reducing to `./scripts/start.sh`, it shrinks significantly.
   - What's unclear: Whether "one printed page" is literally ~60 lines or a rough target.
   - Recommendation: Aim for 40-50 lines for Section 3 after compression. With script references replacing multi-command blocks, this is achievable.

3. **README OSRM note (line 409)**
   - What we know: Says "See SETUP.md for download and preprocessing steps" but osrm-init container automates this.
   - What's unclear: Whether to update this note (not explicitly listed in CONTEXT.md decisions).
   - Recommendation: Update to note automatic handling, since it falls under DOCS-02 (removing manual steps now automated).

## Sources

### Primary (HIGH confidence)
- `docker-compose.yml` -- Container names (line 36: `lpg-db`), health checks (line 54), database config (lines 40-42)
- `.env.example` -- Default values for POSTGRES_USER (`routing`), POSTGRES_DB (`routing_opt`)
- `scripts/bootstrap.sh` -- Full path, behavior, delegations
- `scripts/start.sh` -- Full path, health polling, Docker daemon handling
- `CSV_FORMAT.md` -- Complete CDCMS and CSV reference (Phase 15 output)

### Secondary (MEDIUM confidence)
- CONTEXT.md code_context section -- Pre-identified inaccuracies (verified against primary sources above)

## Metadata

**Confidence breakdown:**
- Factual corrections (DOCS-01, DOCS-02, DOCS-03): HIGH -- All inaccuracies verified against source-of-truth files with exact line numbers
- DEPLOY.md restructure (DOCS-04): HIGH -- Removal targets, cross-link destinations, and script references are all concrete and verified
- Pitfalls: HIGH -- All identified from direct file inspection during this research

**Research date:** 2026-03-05
**Valid until:** 2026-04-05 (stable -- documentation corrections unlikely to change)
