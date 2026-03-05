# Project Research Summary

**Project:** Kerala LPG Delivery Route Optimizer — v1.3 Office-Ready Deployment
**Domain:** Deployment scripting, documentation UX, and error messaging for Docker Compose logistics app
**Researched:** 2026-03-04
**Confidence:** HIGH

## Executive Summary

This milestone (v1.3) is a pure deployment and documentation hardening pass on a fully-functional, already-deployed LPG delivery routing system. The system's Python/FastAPI/React/Docker stack is locked; no application code changes are in scope. The core work is closing the gap between "works on a developer machine" and "a non-technical office employee in Kerala can use this reliably every morning without IT assistance." The recommended approach is two new entrypoint scripts (`bootstrap.sh` for first-time WSL setup, `start.sh` for daily startup), a consolidated `CSV_FORMAT.md` reference document, plain-English error messages in the upload pipeline, and targeted documentation corrections across `README.md` and `DEPLOY.md`.

The critical risk in this milestone is not technical — it is usability. Every pitfall identified maps back to one root cause: scripts and documentation that were written by and for developers. A non-technical user who hits "Cannot connect to the Docker daemon" or "missing required columns: {'OrderNo'}" has no path to self-recovery. The prevention strategy is a `start.sh` that wraps all daily startup into one zero-input command, a `CSV_FORMAT.md` that documents the CDCMS workflow from the user's perspective (not the system's schema), and error messages that say "Re-export from CDCMS with Allocated-Printed filter" rather than "KeyError: OrderStatus".

The secondary risk is WSL2-specific infrastructure brittleness: Docker does not auto-start after a Windows reboot, OSRM silently OOM-kills on 8 GB laptops, and projects cloned to the Windows filesystem (`/mnt/c/`) produce CRLF errors and 10x slower I/O. These are all addressable in the install script with guards and `wsl.conf` configuration, and all must land before v1.3 ships. A test on an actual 8 GB laptop with a fresh WSL install is required for the install script phase — developer-machine testing will not surface the OSRM memory issue.

## Key Findings

### Recommended Stack

No new runtime dependencies are introduced in v1.3. Every tool is bash (already on Ubuntu), `apt` (for Docker CE auto-install), `docker compose` (already in use), and plain GitHub-Flavored Markdown (for docs). The Docker CE install must use the official apt repository (`download.docker.com/linux/ubuntu`), not the `get.docker.com` convenience script or the Snap package. WSL Docker auto-start must use `/etc/wsl.conf` `[boot] command = "service docker start"` rather than a `.bashrc` hack — it fires once at WSL launch, requires no password, and does not pollute every new terminal session.

**Core technologies:**
- Bash 5.x (Ubuntu 22.04+): bootstrap and daily-start scripts — zero new dependencies, works before Docker is up
- Docker CE via official apt repo: auditable, idempotent, correct install method — not Snap, not get.docker.com
- `/etc/wsl.conf` `[boot]` section: Docker auto-start on WSL launch — eliminates daily sudo password prompt
- `docker compose` plugin v2: already in use — installed automatically alongside `docker-ce`
- GitHub-Flavored Markdown: CSV documentation — no build step, renders natively in GitHub and VS Code

**What NOT to add:**
- Docker Desktop (Windows): requires Pro/Enterprise license; WSL2 + Docker Engine is free and faster
- Ansible/Chef/Puppet: overkill for single-machine setup; pure bash is the correct scope
- Snap docker package: known WSL networking issues; use official apt repo
- Interactive `read` prompts in `start.sh`: daily script must be zero-input

### Expected Features

The features divide cleanly into two parallel workstreams: scripting and documentation. Scripting is entirely independent from documentation and can be built and tested first.

**Must have (P1 — v1.3 completion):**
- `start.sh` at project root — single daily startup: start Docker daemon, `docker compose up -d`, 60s health poll, print dashboard URL
- `bootstrap.sh` at project root — one-time WSL setup: install Docker CE via apt, add docker group, git clone, call `install.sh`
- `CSV_FORMAT.md` — consolidated single-page CSV reference with exact CDCMS column names, rejection reasons, address cleaning examples, Excel warning
- README.md container name fix — `routing-db` → `lpg-db`, `routeopt` → `routing` in health check example
- `<REPO_URL>` placeholder filled in README.md and DEPLOY.md
- Plain-English error messages in upload pipeline — at minimum: missing column, empty file, wrong file type, geocoding failure

**Should have (P2 — add during v1.3 if time permits):**
- `scripts/status.sh` — `docker compose ps` wrapper with health check; gives staff a "is it running?" command
- Docker auto-start opt-in in `install.sh` (writes `/etc/wsl.conf`)
- Geocoding error codes (`REQUEST_DENIED`, `ZERO_RESULTS`) translated to plain English
- Cross-links from README.md and DEPLOY.md to `CSV_FORMAT.md`
- "Did you mean...?" fuzzy column name suggestion in error messages (Levenshtein distance, message-only — never auto-fix)
- Address cleaning examples expanded to all 10 documented steps

**Defer (v1.4+):**
- Structured `UploadError` Pydantic model with `error_code` + `remediation` fields (requires coordinated API + dashboard change)
- Desktop shortcut / `.bat` file for Windows launcher
- Per-service status breakdown with suggested fixes in `status.sh`

### Architecture Approach

The architecture for v1.3 is a thin scripting layer added above the existing, unchanged Docker Compose stack. `bootstrap.sh` is a one-time system-provisioning wrapper that delegates all project-level setup to the existing `install.sh` — no logic duplication. `start.sh` is a daily fast-path that does exactly three things and no more: start Docker daemon, run `docker compose up -d` (no `--build`), poll `/health`. The key architectural rule is that documentation follows code, never the reverse: fix `README.md` to show `lpg-db`, do not rename the container in `docker-compose.yml` (which would silently break `backup_db.sh`'s hardcoded container name detection at lines 37-46).

**Major components:**
1. `bootstrap.sh` (new, project root) — fresh-machine entrypoint: installs Docker CE, clones repo, delegates to `install.sh`; idempotent guards on every step
2. `start.sh` (new, project root) — daily entrypoint: starts Docker daemon, brings compose up, verifies health, prints URLs; zero prompts, zero rebuilds
3. `scripts/install.sh` (minor update) — add bootstrap context note in header; no logic changes; remains the developer setup tool
4. `DEPLOY.md` (targeted updates) — Section 3.1: replace 4-command block with `./start.sh`; Section 2.3: reference `bootstrap.sh`
5. `README.md` (targeted corrections) — Docker Services table: fix `routing-db` → `lpg-db`; Quick Start: lead with `./scripts/install.sh`
6. `CSV_FORMAT.md` (new) — standalone CSV specification with CDCMS workflow, rejection reasons, column constraints
7. Upload pipeline error messages (targeted string updates) — wrap Google Maps error codes and validation failures in plain English

**Unchanged (frozen — do not touch):**
- `scripts/deploy.sh`, `scripts/backup_db.sh`, `docker-compose.yml`, `docker-compose.prod.yml` — any container rename breaks backup auto-detection
- All API Python code and React dashboard code — out of scope for v1.3
- Driver PWA — out of scope for v1.3

### Critical Pitfalls

1. **Docker does not auto-start after Windows reboot** — Configure `/etc/wsl.conf` `[boot] command = "service docker start"` during installation. Without this, the office employee faces a cryptic "Cannot connect to Docker daemon" error every morning after a laptop reboot. Currently `install.sh` does not write `wsl.conf`.

2. **OSRM OOM-kills silently on 8 GB laptops** — Add a memory check before OSRM init: if WSL2 memory is below 5 GB, warn and print `.wslconfig` instructions before attempting preprocessing. Container exits with code 137 and the generic timeout message gives no diagnosis. Test specifically on a 4 GB WSL2 machine.

3. **Project cloned to Windows filesystem breaks everything** — Add a filesystem check in `install.sh`: if `$(pwd)` starts with `/mnt/`, abort with a clear message. CRLF line endings break bash scripts (`/bin/bash^M: bad interpreter`), file permissions are fake (NTFS), and OSRM I/O is 10x slower on the translation layer.

4. **OSRM `:latest` image tag causes silent version drift** — Pin `osrm-init` and `osrm` to a specific version tag in `docker-compose.yml`. A `docker compose pull` after an OSRM major release will silently break existing preprocessed data — the init container skips reprocessing (data exists) but the runtime container fails to load incompatible files.

5. **CSV documentation describes internals, not the user's workflow** — Write `CSV_FORMAT.md` backward from the CDCMS export workflow. Use exact CDCMS column names (`OrderNo`, `ConsumerAddress`), not internal system names (`order_id`, `address`). The most common errors (wrong export page, wrong status filter, Excel resave as XLSX) are workflow errors, not schema errors.

## Implications for Roadmap

Based on research, suggested phase structure:

### Phase 1: Install Script Hardening

**Rationale:** The highest-risk items are the pitfalls that prevent the system from starting at all after a Windows reboot or on a low-memory machine. These must be fixed before any other work is usable by the target user. `install.sh` hardening is also a prerequisite for `bootstrap.sh` — bootstrap delegates to install, so install must be correct first.

**Delivers:** Reliable single-command installation on any 8 GB+ Windows laptop with WSL2 Ubuntu; automatic Docker startup after reboot; clear OOM and filesystem error messages; OSRM image version pinned

**Addresses (from FEATURES.md):** Docker auto-start in wsl.conf, non-zero exit with human-readable reason on failure, idempotent re-run behavior, memory check before OSRM init

**Avoids (from PITFALLS.md):** Pitfall 1 (Docker not auto-starting), Pitfall 2 (OSRM OOM kill), Pitfall 3 (Windows filesystem clone), Pitfall 4 (interactive read hang), Pitfall 7 (OSRM image version drift), Pitfall 12 (health check timeout hides which service is stuck)

**Research flag:** No deeper research needed — patterns are fully documented in official Docker and Microsoft WSL docs.

### Phase 2: Daily Startup Script (`start.sh`)

**Rationale:** `start.sh` is the highest daily-impact change and lowest risk — it calls only `docker compose up -d` and `curl`. It can be tested on the existing running system. Building this second (after install hardening) means it can rely on the wsl.conf auto-start from Phase 1. Getting `start.sh` right first also establishes the color/output conventions before writing the more complex `bootstrap.sh`.

**Delivers:** Single command daily startup with 60s health check, URL output, and graceful "already running" handling; zero prompts; no image rebuilds

**Addresses (from FEATURES.md):** Single script for daily startup (P1), success output with actionable URLs (P1), idempotent re-run behavior (P1), graceful timeout feedback (P2)

**Avoids (from PITFALLS.md):** Pitfall 5 (daily workflow too complex), Pitfall 8 (sudo password required daily — wsl.conf from Phase 1 eliminates the need); Anti-Pattern 2 (start.sh that rebuilds images); Anti-Pattern 4 (prompting for credentials in start.sh)

**Research flag:** No deeper research needed — standard shell scripting with documented WSL2 patterns.

### Phase 3: `bootstrap.sh` (Fresh Machine Entrypoint)

**Rationale:** `bootstrap.sh` depends on `install.sh` being correct (Phase 1) and reuses the script conventions from Phase 2. The Docker CE install sequence is well-documented; the main complexity is the docker group restart requirement, which has a known idiomatic solution (exit-and-rerun pattern: add user to group, instruct terminal restart, rerun on next invocation).

**Delivers:** True one-command first-time setup on a fresh WSL Ubuntu install — covers Docker CE installation via official apt repo, docker group, repo clone, and delegation to `install.sh`

**Addresses (from FEATURES.md):** One-command install for non-technical user (core v1.3 goal from PROJECT.md)

**Avoids (from PITFALLS.md):** Pitfall 3 (bootstrap targets Linux home directory `~/routing_opt` explicitly); Anti-Pattern 1 (Docker install logic inside install.sh — kept separate); Anti-Pattern 5 (monolithic script)

**Research flag:** No deeper research needed — Docker CE official apt install is exactly documented with auditable steps.

### Phase 4: CSV Documentation (`CSV_FORMAT.md`)

**Rationale:** Documentation is independent of script work and can be written in parallel with Phases 2-3. Writing it after install hardening is confirmed means no documentation promises the system cannot keep. `CSV_FORMAT.md` must exist before Phase 5 (error messages can reference it) and before Phase 6 (DEPLOY.md cross-links to it).

**Delivers:** Single-page CSV reference covering both CDCMS and generic formats; exact column names from actual CDCMS exports; rejection reasons with plain-English explanations; address cleaning before/after examples; explicit Excel warning; pre-upload checklist

**Addresses (from FEATURES.md):** CSV_FORMAT.md (P1), single-page CSV cheat sheet (P2), error message glossary (P2), address cleaning examples expanded to all 10 steps (P2)

**Avoids (from PITFALLS.md):** Pitfall 6 (CSV docs describe internals not workflow — write workflow-first), Pitfall 10 (path substitution in docs)

**Research flag:** No deeper research needed — content is extracted directly from existing code (`cdcms_preprocessor.py`, `csv_importer.py`) and existing `DEPLOY.md`.

### Phase 5: Documentation Corrections (README + DEPLOY)

**Rationale:** Documentation corrections are the lowest-risk changes and are ordered after the scripts exist so docs describe what actually ships. DEPLOY.md updates reference `start.sh` and `bootstrap.sh`; README corrections are independent of everything. This phase also includes the DEPLOY.md restructuring for non-technical users: prominent Ubuntu terminal warning, git clone to Linux home directory, and daily use section that fits on one printed page.

**Delivers:** Accurate README Docker Services table; filled `<REPO_URL>` placeholder; DEPLOY.md Section 3.1 replaced with `./start.sh`; DEPLOY.md Section 2.3 referencing `bootstrap.sh`; prominent warning that all commands run in Ubuntu terminal not PowerShell; cross-links to `CSV_FORMAT.md`

**Addresses (from FEATURES.md):** README container name fixes (P1), REPO_URL placeholder filled (P1), CSV_FORMAT.md cross-links (P2), version badge/last-updated date (P2)

**Avoids (from PITFALLS.md):** Pitfall 3 (doc must warn "Ubuntu terminal not PowerShell"), Pitfall 5 (documentation not readable by non-technical users), Pitfall 11 (stale container names break copy-paste troubleshooting)

**Research flag:** No deeper research needed — pure documentation corrections against known ground truth (`docker-compose.yml` container names).

### Phase 6: Plain-English Error Messages

**Rationale:** Error message improvements touch Python API upload pipeline code and are more invasive than documentation-only changes. Ordering last ensures `CSV_FORMAT.md` exists so error messages can reference it. P1 items (missing column, empty file, wrong file type) are simple string changes with zero architectural impact; the P2 geocoding error translation requires wrapping Google Maps API error codes.

**Delivers:** Human-readable upload error messages for the three most common failure cases; geocoding error codes (`REQUEST_DENIED`, `ZERO_RESULTS`, `OVER_DAILY_LIMIT`) translated to staff-facing language with remediation steps linking to `CSV_FORMAT.md`

**Addresses (from FEATURES.md):** Plain-English error messages in upload pipeline (P1), geocoding error plain-English (P2), "Did you mean...?" column name suggestion (P2)

**Avoids (from PITFALLS.md):** Pitfall 6 (cryptic error messages cause users to give up); Anti-Feature "auto-correct column names" — suggest but never silently fix

**Research flag:** P1 string changes need no research. If the P3 structured `UploadError` model is pursued, it requires a coordinated dashboard UI change — flag for a dedicated planning discussion before that sub-task begins.

### Phase Ordering Rationale

- Phases 1-3 (scripting) are ordered by dependency: install hardening enables both `start.sh` and `bootstrap.sh`. Writing scripts before docs prevents documentation from making promises the scripts cannot keep.
- Phases 4 and 5 can be parallelized with Phases 2-3 if two people are available — they have no script dependencies, only the constraint that Phase 4 precedes Phase 5 (DEPLOY.md cross-links to `CSV_FORMAT.md`).
- Phase 6 (error messages) comes last because it modifies Python API code and benefits from `CSV_FORMAT.md` existing as a reference target in remediation text.
- `start.sh` before `bootstrap.sh` because `start.sh` validates the output conventions and can be tested immediately on the running system; `bootstrap.sh` cannot be tested without a fresh machine.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 6 (structured UploadError model, P3 only):** If the structured error response with `error_code` + `remediation` fields is pursued, it requires coordinated FastAPI and React dashboard changes. Flag for a dedicated research pass on the `ImportSummary` dashboard component before planning that sub-task.

Phases with standard patterns (skip research-phase):
- **Phase 1** (install script hardening): Official Docker CE apt install and WSL `wsl.conf` patterns are fully documented with exact commands.
- **Phase 2** (`start.sh`): Standard bash scripting; WSL2 health-check pattern already exists in `install.sh` — reuse it.
- **Phase 3** (`bootstrap.sh`): Docker CE install sequence is exactly documented; docker group restart pattern is canonical.
- **Phase 4** (`CSV_FORMAT.md`): Content is entirely in existing codebase; no external research needed.
- **Phase 5** (documentation corrections): Pure text corrections against known ground truth in `docker-compose.yml`.
- **Phase 6, P1** (plain-English strings): Simple string edits in `cdcms_preprocessor.py` and `google_adapter.py`.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All technologies already in use; Docker CE apt install verified against official docs 2026-03-04; no new dependencies introduced |
| Features | HIGH | Full codebase audit performed; gap analysis against PROJECT.md v1.3 goals; all P1 items are string or file changes, not architectural |
| Architecture | HIGH | Based on direct inspection of all scripts (install.sh 324 lines, deploy.sh, backup_db.sh lines 37-46) and docker-compose.yml; no assumptions |
| Pitfalls | HIGH | WSL/Docker issues verified against official docs and community issue trackers; OOM and CRLF pitfalls verified with multiple sources |

**Overall confidence:** HIGH

### Gaps to Address

- **8 GB laptop testing:** All install script hardening (Phase 1) must be validated on a machine with 4 GB WSL2 memory allocation, not just a developer machine. The OSRM OOM pitfall (exit 137) will not surface on a 16 GB machine with ample WSL2 memory.
- **Actual REPO_URL:** The `<REPO_URL>` placeholder fix (Phase 5) requires knowing the actual repository URL or a decision on whether to replace it with a specific URL or a "contact IT" instruction. Clarify before Phase 5.
- **OSRM version to pin:** The correct specific OSRM version tag to use in `docker-compose.yml` must match what was used to preprocess the existing Kerala OSM data. Check the actual installed image version before Phase 1 to avoid forcing a re-preprocessing during the upgrade.
- **wsl.conf edge case:** If the target machine already has a `[boot]` section in `/etc/wsl.conf` for another purpose, the sed-based insertion needs testing. The research-provided idempotency snippet handles this case but it should be verified on a machine with an existing wsl.conf.

## Sources

### Primary (HIGH confidence)
- `scripts/install.sh` — 324 lines, direct inspection; health check pattern, spinner, color output conventions, existing prereq check structure
- `scripts/deploy.sh` — direct inspection; production deploy flow, container name references
- `scripts/backup_db.sh` — direct inspection; lines 37-46, hardcoded container name auto-detection (`lpg-db`/`lpg-db-prod`)
- `docker-compose.yml` — direct inspection; 6 services, actual container names, `service_completed_successfully` conditions
- `DEPLOY.md` — direct inspection; daily workflow (3-command block in Section 3.1), CSV docs, Section 2.3 manual Docker install
- `README.md` — direct inspection; stale container name at lines 403-408 (`routing-db`), REPO_URL placeholder at line 15
- `.env.example` — direct inspection; all environment variables with defaults
- [Docker Engine install on Ubuntu — official docs](https://docs.docker.com/engine/install/ubuntu/) — GPG key setup, apt repo, exact package names
- [Docker post-install steps — official docs](https://docs.docker.com/engine/install/linux-postinstall/) — docker group, usermod pattern, restart requirement
- [WSL systemd support — Microsoft Learn](https://learn.microsoft.com/en-us/windows/wsl/systemd) — wsl.conf `[boot]` section, WSL version requirements, `service docker start` pattern
- [Google Maps Geocoding API billing and quotas](https://developers.google.com/maps/documentation/geocoding/usage-and-billing) — free tier limits, quota cap configuration

### Secondary (MEDIUM confidence)
- [Docker compose `--wait-timeout` bug — docker/compose#12134](https://github.com/docker/compose/issues/12134) — `service_completed_successfully` hang; confirmed issue; use manual health polling instead
- [WSL2 docker auto-start options — codestudy.net](https://www.codestudy.net/blog/sudo-systemctl-enable-docker-not-available-automatically-run-docker-at-boot-on-wsl2-using-a-sysvinit-init-command-or-a-workaround/) — sysvinit vs systemd comparison, wsl.conf boot command pattern; consistent with Microsoft docs
- [WSL2 file permissions and /mnt/c gotchas — turek.dev](https://www.turek.dev/posts/fix-wsl-file-permissions/) — CRLF, permission bits, I/O performance
- [Docker `:latest` tag pitfalls — vsupalov.com](https://vsupalov.com/docker-latest-tag/) — version drift, backward-compatibility breakage
- [WSL2 memory configuration — ITNEXT](https://itnext.io/wsl2-tips-limit-cpu-memory-when-using-docker-c022535faf6f) — `.wslconfig` memory limits, recommended values

### Tertiary (LOW confidence)
- [CSV/Excel encoding pitfalls — hilton.org.uk](https://hilton.org.uk/blog/csv-excel) — BOM, CRLF, XLSX resave encoding; consistent with known Excel behavior
- [Bash pitfalls — Greg's Wiki](https://mywiki.wooledge.org/BashPitfalls) — stdin detection pattern, `[ -t 0 ]` usage

---
*Research completed: 2026-03-04*
*Ready for roadmap: yes*
