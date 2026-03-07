# Phase 19: Pin OSRM Docker Image - Research

**Researched:** 2026-03-07
**Domain:** Docker image versioning, POSIX shell compatibility
**Confidence:** HIGH

## Summary

The `osrm/osrm-backend:latest` Docker image has migrated from a Debian base to an Alpine Linux base. Alpine does not include `/bin/bash`, causing the `osrm-init` container to fail with exit code 127 ("command not found") when the entrypoint is `["/bin/bash", "-c"]`. This blocks ALL fresh deployments because the `osrm-init` container is a dependency for the `osrm` service, which in turn blocks `vroom` and `api`.

The fix is two-fold: (1) pin both `osrm-init` and `osrm` images to `v5.27.1` in `docker-compose.yml` (matching the already-pinned `docker-compose.prod.yml`), and (2) switch all OSRM entrypoints from `/bin/bash -c` to `/bin/sh -c` for POSIX resilience across both compose files. The entrypoint scripts already use only POSIX-compatible constructs (`set -e`, `[ ]` tests, standard redirects, `||`), so the shell swap requires zero script modifications.

**Primary recommendation:** Pin `osrm/osrm-backend:v5.27.1` and use `/bin/sh -c` entrypoint in all compose files. Also update `scripts/osrm_setup.sh` and `SETUP.md` for consistency.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None explicitly locked -- all items are under Claude's Discretion.

### Claude's Discretion
- Fix scope: Apply both version pin and shell fix to `docker-compose.yml` (dev). Also fix `/bin/bash` -> `/bin/sh` in `docker-compose.prod.yml` for consistency (prod already pins v5.27.1 but is vulnerable to the same shell issue)
- OSRM service pinning: Pin the `osrm` service image in dev to `v5.27.1` as well (currently `:latest`), matching prod for consistency
- Version choice: Use `v5.27.1` to match existing prod configuration -- no reason to evaluate newer versions for a bug fix phase
- Entrypoint scripts already use POSIX-compatible syntax (`[ ]`, `set -e`, no bashisms) so `/bin/sh` swap is safe with no script modifications needed

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INST-01 | Bootstrap script auto-installs Docker CE in WSL if missing | Re-satisfied: bootstrap.sh triggers `docker compose up -d` which depends on osrm-init succeeding. Pinning the image + fixing the shell unblocks the install flow. |
| DAILY-01 | Single `start.sh` command starts Docker, runs compose up, polls health, prints URL | Re-satisfied: start.sh runs `docker compose up -d` which triggers osrm-init. The fix ensures osrm-init no longer exits with 127, unblocking the daily startup flow. |
</phase_requirements>

## Standard Stack

### Core
| Library/Tool | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| osrm/osrm-backend | v5.27.1 | OSRM routing engine Docker image | Already used in production compose; stable Debian-based image with /bin/bash and apt-get available |
| Docker Compose | v2+ | Container orchestration | Already in use; `depends_on` with `service_completed_successfully` is the mechanism that chains osrm-init to osrm |

### Supporting
No additional libraries needed -- this is a configuration-only fix.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| v5.27.1 | Latest OSRM (v5.28+) | Would require testing compatibility with existing preprocessed data format + verifying all init script commands still work on Alpine (apt-get vs apk). Out of scope for a bug fix. |
| /bin/sh | Install bash in Alpine | Adds unnecessary image bloat and complexity. The scripts are already POSIX-compatible. |

## Architecture Patterns

### Change Inventory

All changes are to existing files. No new files created.

**Primary (must-change):**
```
docker-compose.yml          # 3 edits: lines 71, 75, 107
docker-compose.prod.yml     # 1 edit:  line 92
```

**Secondary (should-change for consistency):**
```
scripts/osrm_setup.sh       # 1 edit:  line 41
SETUP.md                    # 3 edits: lines 307, 312, 317
```

**Do NOT modify (.planning/ docs are historical records):**
```
.planning/v1.3-MILESTONE-AUDIT.md
.planning/ROADMAP.md
.planning/research/PITFALLS.md
.planning/codebase/INTEGRATIONS.md
```

### Pattern: Docker Image Version Pinning
**What:** Replace `:latest` with `:v5.27.1` for all `osrm/osrm-backend` references in operational files.
**When to use:** Always for production and dev parity; `:latest` is an anti-pattern for reproducible builds.
**Example:**
```yaml
# BEFORE (broken)
image: osrm/osrm-backend:latest

# AFTER (pinned)
image: osrm/osrm-backend:v5.27.1
```

### Pattern: POSIX Shell Entrypoint
**What:** Replace `/bin/bash -c` with `/bin/sh -c` in Docker entrypoints when scripts use only POSIX constructs.
**When to use:** When the init script does not use bash-specific features (arrays, `[[ ]]`, process substitution, `${var//pattern}`).
**Example:**
```yaml
# BEFORE (fragile — depends on bash being installed)
entrypoint: ["/bin/bash", "-c"]

# AFTER (POSIX-resilient — /bin/sh exists on all Linux images)
entrypoint: ["/bin/sh", "-c"]
```

### Anti-Patterns to Avoid
- **Partial fix:** Do NOT just pin the image without also fixing the shell. If a future OSRM version is also Alpine-based, the same exit 127 would recur on upgrade.
- **Fixing dev but not prod:** The prod compose already pins the image but still uses `/bin/bash`. Fix both for consistency.
- **Forgetting osrm_setup.sh:** The standalone OSRM setup script also references `:latest`. Must update for dev/prod parity.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Shell detection in entrypoint | Don't add `which bash \|\| sh` logic | Just use `/bin/sh` everywhere | The scripts are already POSIX-compatible; shell detection adds unnecessary complexity |
| Version pinning variable | Don't create a `.env` variable for OSRM version | Hardcode `v5.27.1` in compose files | A single source of truth in the compose file is clearer than indirection through env vars for a rarely-changed value |

## Common Pitfalls

### Pitfall 1: apt-get on Alpine
**What goes wrong:** The osrm-init script runs `apt-get update && apt-get install -y wget` to install wget. On Alpine images, `apt-get` does not exist (Alpine uses `apk`).
**Why it happens:** The script was written for Debian-based images.
**How to avoid:** By pinning to v5.27.1 (Debian-based), `apt-get` continues to work. If OSRM is ever upgraded to an Alpine-based version in the future, the init script must be updated to use `apk add wget` or use `curl` (which is typically included in Alpine).
**Warning signs:** `apt-get: not found` in container logs.

### Pitfall 2: Preprocessed Data Version Mismatch
**What goes wrong:** Existing OSRM preprocessed data (generated by `:latest` which was a different version) may be incompatible with `v5.27.1`.
**Why it happens:** OSRM's MLD data format can change between major versions.
**How to avoid:** Not a concern for this phase -- the bug is that osrm-init FAILS on fresh machines (no existing data). On machines that already have preprocessed data, the init is skipped (idempotent check). If data was preprocessed with a different OSRM version, the osrm service may fail at startup; the fix is to delete `data/osrm/*.osrm*` and re-run.
**Warning signs:** OSRM service exits with errors about incompatible data format.

### Pitfall 3: Forgetting Secondary Files
**What goes wrong:** `scripts/osrm_setup.sh` and `SETUP.md` still reference `:latest`, causing confusion when someone follows those instructions.
**Why it happens:** Easy to focus only on the compose files and miss standalone scripts/docs.
**How to avoid:** The change inventory above lists all 6 files. Verify all are updated.
**Warning signs:** `grep -r 'osrm-backend:latest'` returns hits after the fix.

### Pitfall 4: wget --show-progress on /bin/sh
**What goes wrong:** The `--show-progress` flag for `wget` outputs progress to stderr. This works identically under `/bin/sh` and `/bin/bash` -- it is a `wget` flag, not a shell feature. No issue here.
**How to avoid:** Not a real pitfall -- listed for completeness since it was investigated.

## Code Examples

### docker-compose.yml Changes

```yaml
# osrm-init service (lines 71, 75)
osrm-init:
    image: osrm/osrm-backend:v5.27.1    # was :latest
    container_name: osrm-init
    volumes:
      - ./data/osrm:/data
    entrypoint: ["/bin/sh", "-c"]         # was /bin/bash
    command:
      - |
        set -e
        # ... (script body unchanged)

# osrm service (line 107)
osrm:
    image: osrm/osrm-backend:v5.27.1    # was :latest
```

### docker-compose.prod.yml Change

```yaml
# osrm-init service (line 92 only -- image already pinned at line 88)
osrm-init:
    image: osrm/osrm-backend:v5.27.1    # already correct
    ...
    entrypoint: ["/bin/sh", "-c"]         # was /bin/bash
```

### scripts/osrm_setup.sh Change

```bash
# Line 41
OSRM_IMAGE="osrm/osrm-backend:v5.27.1"  # was :latest
```

### SETUP.md Changes

```bash
# Lines 307, 312, 317 — replace all three instances
docker run --rm -v $(pwd)/data/osrm:/data \
  osrm/osrm-backend:v5.27.1 \            # was :latest
  osrm-extract -p /opt/car.lua /data/kerala-latest.osm.pbf
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| osrm/osrm-backend:latest (Debian) | osrm/osrm-backend:latest (Alpine) | 2025-2026 (upstream change) | Breaks /bin/bash entrypoints, breaks apt-get |
| /bin/bash entrypoints | /bin/sh entrypoints | Docker best practice | POSIX shell available on ALL Linux images (Alpine, Debian, Ubuntu) |

**Deprecated/outdated:**
- Using `:latest` for OSRM images: the Docker Wiki now publishes Alpine-based images. The v5.27.1 tag remains Debian-based, but future tags may not be.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Manual Docker verification (no automated test framework for compose files) |
| Config file | N/A |
| Quick run command | `docker compose up osrm-init 2>&1 \| head -5` |
| Full suite command | `docker compose up -d && docker compose ps` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INST-01 (re-satisfied) | osrm-init starts without exit 127 | smoke | `docker compose up osrm-init 2>&1` (check exit code) | N/A -- compose validation |
| DAILY-01 (re-satisfied) | `docker compose up -d` succeeds end-to-end | smoke | `docker compose up -d && docker compose ps --format json` | N/A -- compose validation |

### Sampling Rate
- **Per task commit:** `docker compose config --quiet` (validates YAML syntax)
- **Per wave merge:** `docker compose up -d && docker compose ps` (full stack smoke)
- **Phase gate:** Verify osrm-init exits 0, osrm service starts and passes healthcheck

### Wave 0 Gaps
None -- this is a configuration fix, not application code. Validation is manual Docker commands.

## Open Questions

1. **Will v5.27.1 remain available on Docker Hub indefinitely?**
   - What we know: Docker Hub rarely removes tagged images. The tag has been stable.
   - What's unclear: Docker Hub retention policies could change.
   - Recommendation: Not a concern for this phase. If the tag is ever removed, the fix is to update to the next available Debian-based tag.

2. **Should the comment about "some OSRM images have curl only" be updated?**
   - What we know: The dev init script installs wget via `apt-get`. On v5.27.1 (Debian), this works.
   - What's unclear: Whether v5.27.1 already includes wget.
   - Recommendation: Leave the `apt-get install wget || true` pattern as-is. It's idempotent and handles both cases. Out of scope for this bug fix phase.

## Sources

### Primary (HIGH confidence)
- `docker-compose.yml` (local file) -- confirmed `:latest` tag on lines 71, 107 and `/bin/bash` on line 75
- `docker-compose.prod.yml` (local file) -- confirmed `v5.27.1` on lines 88, 124 and `/bin/bash` on line 92
- `.planning/v1.3-MILESTONE-AUDIT.md` (local file) -- confirmed user-reported exit 127 on fresh machine deployment
- [OSRM Docker Wiki](https://github.com/Project-OSRM/osrm-backend/wiki/Docker-Recipes) -- confirms "lightweight Docker images based on Alpine Linux for each OSRM release"

### Secondary (MEDIUM confidence)
- [Docker Hub osrm/osrm-backend](https://hub.docker.com/r/osrm/osrm-backend/) -- official image repository
- [Alpine Docker & Bash](https://tempered.works/posts/2020/06/07/bashing-alpine/) -- confirms Alpine does not include bash by default

### Tertiary (LOW confidence)
- None -- all findings verified against local files and official documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- pinning to v5.27.1 is directly validated by working docker-compose.prod.yml
- Architecture: HIGH -- all affected files identified by exhaustive grep; POSIX compliance verified by manual inspection
- Pitfalls: HIGH -- root cause well-documented in milestone audit with user-reported reproduction

**Research date:** 2026-03-07
**Valid until:** indefinite (infrastructure fix, version pin is static)
