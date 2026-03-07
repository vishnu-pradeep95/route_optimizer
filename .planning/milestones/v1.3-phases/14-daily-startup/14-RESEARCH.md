# Phase 14: Daily Startup - Research

**Researched:** 2026-03-05
**Domain:** Bash scripting, Docker Compose lifecycle, health check polling, WSL2 service management
**Confidence:** HIGH

## Summary

Phase 14 creates a `start.sh` script that an office employee runs every morning to bring up the Kerala LPG Delivery Route Optimizer. The script must handle three scenarios: (1) cold start -- services not running, bring everything up and wait for healthy; (2) warm start -- services already running, exit gracefully without errors or duplicate containers; (3) failure -- health check times out, report which service failed with a human-readable next step.

The technical domain is straightforward. `docker compose up -d` is inherently idempotent -- running it when containers are already up simply prints the container names as "Running" and exits cleanly. The existing `install.sh` already demonstrates the health polling pattern (curl loop with timeout against `http://localhost:8000/health`). The main new work is: (1) ensuring Docker daemon is running before compose commands, (2) polling the health endpoint for up to 60 seconds (not 300 like install.sh), (3) on timeout, inspecting individual container states to identify which service failed, and (4) printing the dashboard URL on success.

**Primary recommendation:** Create `scripts/start.sh` as a simple, self-contained script (~80 lines) that reuses the color helpers and health-polling pattern from `install.sh` and `bootstrap.sh`. The script should: start Docker daemon if needed, run `docker compose up -d` (no `--build`, daily startup should not rebuild), poll `/health` for 60 seconds, and on failure inspect `docker compose ps` to identify the unhealthy or exited service.

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DAILY-01 | Single `start.sh` command starts Docker, runs compose up, polls health, prints URL | Docker Compose `up -d` is idempotent; `curl -sf /health` returns `{"status":"ok"}` on success; Docker daemon can be started via `sudo service docker start` or `sudo systemctl start docker`; all patterns already proven in `install.sh` |

</phase_requirements>

## Standard Stack

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| bash | 5.x | Script runtime | Pre-installed on Ubuntu WSL2, `set -euo pipefail` for safety |
| docker compose | v2 plugin | Container orchestration | Already installed by Phase 13 bootstrap, `up -d` is idempotent |
| curl | system | Health endpoint polling | Pre-installed, used by existing install.sh for same purpose |

### Supporting
| Tool | Purpose | When to Use |
|------|---------|-------------|
| `docker compose ps` | Container state inspection | When health check times out, to identify failed service |
| `sudo service docker start` | Docker daemon startup | When Docker daemon is not running (first WSL session after reboot) |
| `systemctl is-active docker` | Docker daemon status check | To determine if Docker needs to be started |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `curl -sf /health` | `docker compose ps --format` | curl checks end-to-end (API responds), compose ps only checks container state. curl is better. |
| `sudo service docker start` | `sudo systemctl start docker` | Both work. `service` command works on both systemd and sysvinit. Using `systemctl` first with `service` as fallback matches bootstrap.sh pattern. |
| `docker compose up -d` | `docker compose start` | `up -d` creates missing containers AND starts stopped ones. `start` only starts existing stopped containers. `up -d` is more robust. |

**Installation:** No new packages needed. All tools are already present after Phase 13 bootstrap.

## Architecture Patterns

### Recommended Script Structure
```
scripts/
  bootstrap.sh      # Phase 13: One-time installation (existing)
  install.sh         # Phase 13: Docker Compose build + first start (existing)
  start.sh           # Phase 14: NEW - Daily startup script
  deploy.sh          # Production deployment (existing)
  backup_db.sh       # Database backup (existing)
```

### Pattern 1: Docker Daemon Guard
**What:** Check if Docker daemon is running before attempting compose commands. Start it if needed.
**When to use:** Always -- WSL2 may not have Docker running if systemd failed or WSL was cold-booted.
**Why:** `docker compose up -d` fails with a cryptic socket error if the daemon isn't running. Starting it proactively gives a clean user experience.

```bash
# Source: Adapted from scripts/install.sh lines 132-142
ensure_docker_running() {
    if docker info &>/dev/null; then
        return 0
    fi

    info "Starting Docker..."
    if sudo service docker start &>/dev/null; then
        # Wait briefly for daemon to be ready
        local attempts=0
        while ! docker info &>/dev/null && [ "$attempts" -lt 10 ]; do
            sleep 1
            attempts=$((attempts + 1))
        done
        if docker info &>/dev/null; then
            success "Docker started"
            return 0
        fi
    fi

    error "Could not start Docker."
    echo ""
    echo "  Try manually: sudo service docker start"
    echo "  If that fails, restart WSL: (in PowerShell) wsl --shutdown"
    return 1
}
```

### Pattern 2: Idempotent Compose Up
**What:** `docker compose up -d` without `--build` for daily starts. Rebuilds images only during install.
**When to use:** Every daily startup. The `--build` flag is intentionally omitted -- daily startup should not rebuild images (that's what install.sh does).
**Behavior when already running:** Docker Compose checks each container. Running containers are left as-is (prints "Container xyz Running"). Stopped containers are restarted. Missing containers are created. Init containers (osrm-init, db-init) that already completed successfully are skipped.

```bash
# docker compose up -d is idempotent:
# - Running containers: left untouched ("Container lpg-api Running")
# - Stopped containers: restarted
# - Missing containers: created
# - Init containers: re-run only if condition (service_completed_successfully) not met
docker compose up -d
```

### Pattern 3: Health Poll with 60-Second Timeout
**What:** Poll the API health endpoint at regular intervals, printing a spinner/progress indicator.
**When to use:** After `docker compose up -d` completes.
**Critical detail:** The success criteria specify 60 seconds, not the 300 seconds used in install.sh. Daily startup is different from first-time install -- services should come up within seconds if images are cached and OSRM data exists.

```bash
# Source: Adapted from scripts/install.sh lines 265-287
HEALTH_URL="http://localhost:8000/health"
MAX_WAIT=60
POLL_INTERVAL=3

poll_health() {
    local elapsed=0
    while [ "$elapsed" -lt "$MAX_WAIT" ]; do
        if curl -sf "$HEALTH_URL" >/dev/null 2>&1; then
            return 0
        fi
        sleep "$POLL_INTERVAL"
        elapsed=$((elapsed + POLL_INTERVAL))
        printf "\r  Waiting for services... (%ds / %ds)  " "$elapsed" "$MAX_WAIT"
    done
    printf "\n"
    return 1
}
```

### Pattern 4: Service Failure Diagnosis
**What:** When health check times out, inspect `docker compose ps` to identify which service is unhealthy/exited, and print a human-readable message with a suggested next step.
**When to use:** Only when the 60-second health check fails.
**Why:** The success criteria explicitly require "prints which service failed and a suggested next step (not a raw Docker error)."

```bash
diagnose_failure() {
    echo ""
    error "System did not become healthy within ${MAX_WAIT} seconds."
    echo ""

    # Check each critical service
    local failed=false

    # Database
    local db_status
    db_status=$(docker inspect --format='{{.State.Health.Status}}' lpg-db 2>/dev/null || echo "not found")
    if [ "$db_status" != "healthy" ]; then
        failed=true
        error "Database (lpg-db): $db_status"
        echo "  Try: docker compose logs db --tail=20"
    fi

    # OSRM
    local osrm_status
    osrm_status=$(docker inspect --format='{{.State.Status}}' osrm-kerala 2>/dev/null || echo "not found")
    if [ "$osrm_status" != "running" ]; then
        failed=true
        error "OSRM routing engine (osrm-kerala): $osrm_status"
        echo "  Try: docker compose logs osrm --tail=20"
    fi

    # API
    local api_status
    api_status=$(docker inspect --format='{{.State.Status}}' lpg-api 2>/dev/null || echo "not found")
    if [ "$api_status" != "running" ]; then
        failed=true
        error "API server (lpg-api): $api_status"
        echo "  Try: docker compose logs api --tail=20"
    fi

    if [ "$failed" = false ]; then
        warn "All containers appear running but API is not responding."
        echo "  The API may still be starting up. Wait a minute and try:"
        echo "  curl http://localhost:8000/health"
    fi
}
```

### Anti-Patterns to Avoid
- **Using `--build` on daily startup:** Rebuilds images every morning, adding minutes of unnecessary delay. `--build` belongs in install.sh and deploy.sh, not start.sh.
- **Using `docker compose down && docker compose up -d`:** Unnecessary. Destroys running containers and recreates them, causing downtime and losing init-container completion state.
- **Raw Docker error output:** The success criteria explicitly forbid "raw Docker error" on failure. Always translate to plain English with a suggested next step.
- **Running install.sh as daily startup:** install.sh runs `--build` and prompts for .env values. It is a first-time setup script, not a daily startup script.
- **Checking individual services before compose up:** `docker compose up -d` handles all orchestration. Don't pre-check services -- just run compose up and check health afterwards.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Container orchestration | Custom start/stop per service | `docker compose up -d` | Compose handles dependency ordering, init containers, idempotency |
| Health checking | Custom per-service health probes | Curl to `/health` endpoint | The API health endpoint implicitly proves DB + OSRM + VROOM connectivity |
| Service failure detection | Parse docker logs for errors | `docker inspect --format` | Gives structured status (running/exited/unhealthy) without log parsing |
| Docker daemon startup | Direct systemd commands | `sudo service docker start` | Works on both systemd and sysvinit, same pattern as install.sh |
| Color output | New ANSI helpers | Copy from bootstrap.sh | Consistency with existing scripts |

**Key insight:** The API's `/health` endpoint returns `{"status":"ok"}` only when it can reach the database (Alembic migrations complete), which means the whole stack is functional. One curl check replaces checking every service individually.

## Common Pitfalls

### Pitfall 1: Docker Daemon Not Running After WSL Boot
**What goes wrong:** `docker compose up -d` fails with "Cannot connect to the Docker daemon at unix:///var/run/docker.sock" because WSL2 doesn't always start Docker automatically.
**Why it happens:** Even with `systemd=true` in wsl.conf and Docker service enabled, WSL2 sometimes fails to start systemd services on cold boot (especially if WSL was terminated via `wsl --shutdown` or Windows restart).
**How to avoid:** Always check `docker info` first and start Docker if needed. This is the first thing start.sh should do.
**Warning signs:** Script fails immediately with a socket connection error.

### Pitfall 2: Init Containers Re-Running Unnecessarily
**What goes wrong:** `docker compose up -d` may re-run osrm-init or db-init, adding 10+ minutes to daily startup.
**Why it happens:** If the init container's exit status was lost (e.g., `docker compose down` was used, or container was removed), Compose doesn't know it completed successfully and re-runs it.
**How to avoid:** In normal daily use, containers are not removed. `docker compose up -d` checks the condition (`service_completed_successfully`) which is satisfied if the init container exited with code 0 and still exists. Daily `start.sh` should NOT run `docker compose down` first.
**Warning signs:** OSRM preprocessing starts again (takes 10-15 minutes) during what should be a 30-second daily startup.

### Pitfall 3: Port Already in Use
**What goes wrong:** `docker compose up -d` fails because port 8000 (or 5432, 5000, 3000) is already bound by a non-Docker process.
**How to avoid:** This is unlikely in the WSL2 office environment (no other services running). If it happens, the error is clear from Docker. The start script can provide a helpful message.
**Warning signs:** Docker error "port is already allocated" or "address already in use".

### Pitfall 4: OSRM Showing "Unhealthy" Despite Working
**What goes wrong:** OSRM container shows "unhealthy" in `docker compose ps` even though routing works.
**Why it happens:** The OSRM healthcheck (`curl -f http://localhost:5000/health`) may not have the expected endpoint or curl may not be installed in the OSRM container. Current live system shows osrm-kerala as "unhealthy" yet the API works fine.
**How to avoid:** Don't rely on OSRM's individual healthcheck for the start script. Use the API's `/health` endpoint as the single source of truth. If the API responds 200, the whole stack is working.
**Warning signs:** `docker compose ps` shows OSRM as unhealthy but system works fine.

### Pitfall 5: set -e Exits on Docker Daemon Check
**What goes wrong:** `docker info` returns non-zero when daemon is not running, causing `set -e` to terminate the script before the "start Docker" logic runs.
**Why it happens:** `set -e` exits on any command with non-zero exit code.
**How to avoid:** Use `docker info &>/dev/null` in an `if` statement or with `||` to suppress the exit-on-error behavior.
**Warning signs:** Script exits silently before printing any meaningful output.

## Code Examples

Verified patterns from the existing codebase:

### Health Endpoint Response (Verified on Live System)
```bash
# Source: curl http://localhost:8000/health on running system
# Returns: {"status":"ok","service":"kerala-lpg-optimizer","version":"0.2.0"}
# HTTP 200 on success
# Connection refused or timeout when API is not ready

curl -sf http://localhost:8000/health
# -s = silent (no progress bar)
# -f = fail silently on HTTP errors (returns non-zero exit code on 4xx/5xx)
```

### Docker Compose Idempotent Behavior (Verified)
```bash
# Running `docker compose up -d` when all services are already running:
# Output shows each container as "Running" -- no restart, no errors:
#
#  Container lpg-db          Running
#  Container osrm-init       Exited     <-- init container, already completed
#  Container lpg-db-init     Exited     <-- init container, already completed
#  Container osrm-kerala     Running
#  Container vroom-solver    Running
#  Container lpg-api         Running
#
# Exit code: 0
# No duplicate containers are created.
```

### Container State Inspection
```bash
# Source: Docker CLI documentation
# Get container health/run status:
docker inspect --format='{{.State.Status}}' lpg-api
# Returns: "running", "exited", "restarting", "paused", "dead", "created"

docker inspect --format='{{.State.Health.Status}}' lpg-db
# Returns: "healthy", "unhealthy", "starting" (only for containers with healthcheck)

# Get exit code (useful for init containers):
docker inspect --format='{{.State.ExitCode}}' lpg-db-init
# Returns: 0 (success), non-zero (failure)
```

### Success Banner (Matches Existing install.sh Style)
```bash
# Source: Adapted from scripts/install.sh lines 292-309
echo ""
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  System is running!                                          ${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BOLD}Dashboard:${NC}   http://localhost:8000/dashboard/"
echo -e "  ${BOLD}Driver App:${NC}  http://localhost:8000/driver/"
echo ""
```

### Docker Service Container Names (from docker-compose.yml)
```
# Service → Container name mapping (for docker inspect):
db          → lpg-db
osrm-init   → osrm-init       (init container, exits after completion)
osrm        → osrm-kerala
vroom       → vroom-solver
db-init     → lpg-db-init     (init container, exits after completion)
api         → lpg-api
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `docker-compose up -d` (v1 standalone) | `docker compose up -d` (v2 plugin) | Docker Compose v2 (2022+) | Already using v2 throughout the project |
| Individual service start scripts | Single `docker compose up -d` | Always for Compose projects | Compose handles all orchestration |
| `docker ps` for status | `docker compose ps` for project-scoped view | Docker Compose v2 | Shows only project containers, cleaner output |

**Deprecated/outdated:**
- `docker-compose` (hyphenated, v1 standalone): Use `docker compose` (space, v2 plugin). Already correct in this project.

## Open Questions

1. **Script location: `start.sh` at project root vs `scripts/start.sh`**
   - What we know: The success criteria say "Running `start.sh`" which implies project root. Bootstrap.sh is at `scripts/bootstrap.sh` but the user is told to run `./bootstrap.sh` from project root (it's actually a symlink scenario -- bootstrap.sh lives in scripts/ and `cd`s to project root).
   - What's unclear: Whether the user expectation is `./start.sh` from project root or `./scripts/start.sh`.
   - Recommendation: Place at `scripts/start.sh` for consistency with other scripts. The user runs `./scripts/start.sh` or the bootstrap success message tells them the daily command. Alternatively, a root-level symlink or wrapper. Planner should decide based on the "zero thought" user experience.

2. **Should start.sh run `--build`?**
   - What we know: install.sh uses `--build`. Daily startup should not rebuild images (wastes time, no code changes expected).
   - Recommendation: Omit `--build`. Daily startup is not a deploy. If images need rebuilding, use install.sh or deploy.sh.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | bash + manual verification |
| Config file | none -- shell scripts tested via execution |
| Quick run command | `bash -n scripts/start.sh` (syntax check) |
| Full suite command | Manual: run `start.sh` on WSL2 with services in various states |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DAILY-01 (cold start) | start.sh brings up services, polls health, prints URL | smoke | `./scripts/start.sh` on stopped services | Wave 0 |
| DAILY-01 (warm start) | start.sh completes gracefully when already running | smoke | `./scripts/start.sh` on running services | Wave 0 |
| DAILY-01 (timeout) | start.sh prints which service failed + next step | manual-only | Requires a broken service state to trigger | N/A |

**Justification for manual-only:** The timeout/failure path requires deliberately breaking a service (e.g., stopping only the API) and running start.sh. This can be tested manually but not easily automated as a repeatable test.

### Sampling Rate
- **Per task commit:** `bash -n scripts/start.sh` (syntax validation)
- **Per wave merge:** Run start.sh with services running (warm start idempotency check)
- **Phase gate:** Cold start + warm start + simulated failure

### Wave 0 Gaps
None -- no test infrastructure needed beyond bash syntax checking and manual execution.

## Sources

### Primary (HIGH confidence)
- `docker-compose.yml` (project file) -- Service definitions, container names, healthcheck configurations, dependency chain
- `scripts/install.sh` (project file) -- Existing health polling pattern (lines 265-287), color helpers, Docker daemon start logic
- `scripts/bootstrap.sh` (project file) -- Color helpers, project root detection, Docker daemon guard pattern
- `apps/kerala_delivery/api/main.py` -- Health endpoint implementation: `GET /health` returns `{"status":"ok","service":"kerala-lpg-optimizer","version":"0.2.0"}`
- Live system verification: `curl http://localhost:8000/health` returns 200 with expected JSON
- Live system verification: `docker compose ps` shows current container states, confirms idempotent behavior

### Secondary (MEDIUM confidence)
- Docker Compose documentation -- `up -d` idempotency, `--build` flag behavior, init container lifecycle
- Docker inspect documentation -- `--format` template syntax for container state inspection

### Tertiary (LOW confidence)
- None -- all findings verified against the live system and project source code

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all tools already present in project, verified on live system
- Architecture: HIGH -- patterns directly adapted from existing install.sh and bootstrap.sh
- Pitfalls: HIGH -- identified from actual live system state (e.g., OSRM showing unhealthy) and existing script patterns
- Health polling: HIGH -- exact endpoint and response format verified via live curl

**Research date:** 2026-03-05
**Valid until:** 2026-06-05 (90 days -- Docker Compose CLI and bash scripting are stable domains)
