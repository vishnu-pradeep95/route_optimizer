# Phase 23: Distribution Verification & Operational Scripts - Context

**Gathered:** 2026-03-08
**Status:** Ready for planning

<domain>
## Phase Boundary

The actual customer deliverable (tarball from build-dist.sh) installs and runs correctly on a fresh environment, and operators have a safe shutdown script for daily use. No new features, no documentation (Phase 24 handles docs).

</domain>

<decisions>
## Implementation Decisions

### Stop command behavior
- Use `docker compose stop` (halt containers, don't remove) — fast restart on next `start.sh`
- Pre-check: if no services running, print "Services already stopped" and exit 0
- List each container as it stops: "✓ lpg-api stopped", "✓ lpg-db stopped", etc., with total count
- Auto-resolve project root via SCRIPT_DIR pattern (same as start.sh/install.sh)
- Follow existing color helper pattern (info/success/warn/error/header)

### GC mode (--gc flag)
- Remove dangling images only (`docker image prune -f`) — not all unused images
- Remove orphan containers (`docker compose down --remove-orphans`, then stop remaining)
- Truncate all container log files to zero bytes — no partial retention
- No confirmation prompt — user explicitly opted in via --gc flag, matches non-interactive script pattern
- Show what was cleaned with sizes: "Removed 3 dangling images (1.2 GB)"

### Clean install verification
- Automated `scripts/verify-dist.sh` script — not a manual checklist
- Isolation: extract tarball to /tmp, use `COMPOSE_PROJECT_NAME=verify-dist` on different port (8002)
- Auto-generate dummy .env (random API key, random DB password, no Google Maps key, ENVIRONMENT=development)
- Bypass install.sh interactive prompts — pre-create .env before running install
- Verify three endpoints: /health (200), /driver/ (HTML loads), /dashboard/ (React app loads)
- Cleanup: `docker compose down` verify containers + `rm -rf` temp directory
- Trap-based cleanup on script exit (same pattern as build-dist.sh)

### Claude's Discretion
- Exact port mapping strategy for isolated verification (override compose ports)
- How to handle OSRM/VROOM in verification (may need to skip or wait longer)
- Timeout values for verification health polling
- Whether to verify .pyc licensing module loads in the extracted tarball
- Error diagnosis if verification fails (which step, which service)

</decisions>

<specifics>
## Specific Ideas

- stop.sh output style matches the preview: per-container status lines with checkmarks, total count summary
- verify-dist.sh follows the 5-step numbered output pattern shown in discussion
- Existing scripts (start.sh, install.sh, build-dist.sh) all use identical color helpers and header() function — stop.sh and verify-dist.sh must match

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/start.sh`: SCRIPT_DIR resolution, ensure_docker_running(), poll_health(), diagnose_failure() — patterns to reuse in stop.sh
- `scripts/build-dist.sh`: trap cleanup, staged directory, color helpers — patterns to reuse in verify-dist.sh
- `scripts/install.sh`: prerequisite checks, .env creation, health polling — verify-dist.sh can invoke this or replicate key steps

### Established Patterns
- All scripts use `set -euo pipefail`
- Color output disabled if not a terminal (`if [ -t 1 ]`)
- SCRIPT_DIR + PROJECT_ROOT resolution for directory independence
- Spinner animation during health polling (⠋⠙⠹⠸)
- Container names: lpg-api, lpg-db, osrm-kerala (from docker-compose.yml)
- `docker compose` (v2 plugin syntax, not standalone `docker-compose`)

### Integration Points
- `scripts/stop.sh` — new file, complement to start.sh
- `scripts/verify-dist.sh` — new file, uses build-dist.sh output
- `docker-compose.yml` — read container/service names, may need port override for verification
- `install.sh` — verify-dist.sh may invoke this or replicate its .env + build steps

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 23-distribution-verification-operational-scripts*
*Context gathered: 2026-03-08*
