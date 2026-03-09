# Phase 23: Distribution Verification & Operational Scripts - Research

**Researched:** 2026-03-08
**Domain:** Bash scripting, Docker Compose operations, distribution verification
**Confidence:** HIGH

## Summary

Phase 23 creates two new shell scripts (`stop.sh` and `verify-dist.sh`) and has no library dependencies -- it is purely Bash + Docker Compose operations. The project already has four production-quality scripts (`start.sh`, `install.sh`, `build-dist.sh`, `bootstrap.sh`) that establish identical patterns: `set -euo pipefail`, color helpers with terminal detection, `SCRIPT_DIR`/`PROJECT_ROOT` resolution, and spinner-based health polling. Both new scripts must match these patterns exactly.

The key technical challenge is `verify-dist.sh`: it must extract the tarball into `/tmp`, stand up a second Docker Compose stack on different ports (to avoid conflicts with a running primary stack), verify endpoints, and clean up. Docker Compose v5 (installed on this system) supports `--project-name` for namespace isolation and compose override files for port remapping. The existing `tests/deploy/` directory already contains a Docker-in-Docker fresh deploy test -- `verify-dist.sh` takes a lighter approach by extracting alongside the host system with port overrides.

**Primary recommendation:** Follow the existing script patterns exactly. Use a compose override file (`docker-compose.verify.yml`) generated at runtime to remap all ports. Handle OSRM data by either sharing the host's `data/osrm/` directory or accepting a longer verification time on first run.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **stop.sh behavior:** Use `docker compose stop` (halt containers, don't remove) for fast restart. Pre-check if no services running, print "Services already stopped" and exit 0. List each container as it stops with checkmarks and total count. Auto-resolve project root via SCRIPT_DIR pattern.
- **GC mode (--gc flag):** Remove dangling images only (`docker image prune -f`), remove orphan containers (`docker compose down --remove-orphans` then stop remaining), truncate all container log files to zero bytes, no confirmation prompt, show what was cleaned with sizes.
- **Clean install verification:** Automated `scripts/verify-dist.sh` script, extract tarball to /tmp, use `COMPOSE_PROJECT_NAME=verify-dist` on different port (8002), auto-generate dummy .env, bypass install.sh interactive prompts, verify three endpoints (/health, /driver/, /dashboard/), trap-based cleanup.

### Claude's Discretion
- Exact port mapping strategy for isolated verification (override compose ports)
- How to handle OSRM/VROOM in verification (may need to skip or wait longer)
- Timeout values for verification health polling
- Whether to verify .pyc licensing module loads in the extracted tarball
- Error diagnosis if verification fails (which step, which service)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| OPS-01 | `scripts/stop.sh` gracefully stops all services (docker compose stop, not down -v) | Verified: `docker compose stop` halts containers without removing volumes. Container names from compose: lpg-api, lpg-db, osrm-kerala, vroom-solver, plus init containers. Color helpers and SCRIPT_DIR patterns documented from existing scripts. |
| OPS-02 | `stop.sh --gc` cleans dangling images, orphan containers, and truncates container logs | Verified: `docker image prune -f` removes dangling only (not `-a`). Log files at `/var/lib/docker/containers/<id>/<id>-json.log` require `sudo truncate -s 0`. `docker compose down --remove-orphans` handles orphan containers. |
| OPS-03 | Clean install from `build-dist.sh` tarball verified in fresh environment | Tarball structure verified (contains docker-compose.yml, .env.example, scripts/, etc.). Port override via runtime-generated docker-compose.verify.yml. OSRM data handling is the main complexity. |
</phase_requirements>

## Standard Stack

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| Bash | 5.x | Script runtime | All existing scripts use bash, `#!/usr/bin/env bash` |
| Docker Compose | v5.0.2 (v2 plugin) | Container orchestration | Already installed, `docker compose` syntax (not `docker-compose`) |
| curl | system | Health endpoint polling | Already used by start.sh and install.sh |

### Supporting
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| `truncate` | coreutils | Zero-out log files | GC mode log cleanup |
| `mktemp` | coreutils | Create temp directory | verify-dist.sh tarball extraction |
| `tar` | system | Extract tarball | verify-dist.sh |
| `du` | coreutils | Report sizes of cleaned items | GC mode size reporting |
| `sed` | system | Modify .env values | verify-dist.sh .env generation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Compose override file for ports | Environment variable substitution | Compose file has hardcoded ports, not `${VAR:-default}` syntax -- override file is cleaner than sed-modifying compose |
| `truncate -s 0` for logs | `echo "" > file` or `> file` | `truncate` is atomic and explicit, preferred for system files |
| Direct tarball extraction | Docker-in-Docker test (exists in tests/deploy/) | DinD is heavier, 10-20 min runtime. Port-isolated extraction is faster for daily verification |

## Architecture Patterns

### Recommended Project Structure
```
scripts/
├── stop.sh             # NEW -- complement to start.sh
├── verify-dist.sh      # NEW -- distribution tarball verification
├── start.sh            # Existing -- daily startup
├── install.sh          # Existing -- first-time setup
├── build-dist.sh       # Existing -- tarball builder
└── bootstrap.sh        # Existing -- WSL-specific bootstrap
```

### Pattern 1: Standard Script Boilerplate (from existing scripts)
**What:** Every script in this project follows identical structure
**When to use:** All new scripts must match
**Example:**
```bash
#!/usr/bin/env bash
# =============================================================================
# Title — Kerala LPG Delivery Route Optimizer
# =============================================================================
# ... description block ...

set -euo pipefail

# Colors (disabled if not a terminal)
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    BLUE='\033[0;34m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    GREEN='' YELLOW='' RED='' BLUE='' BOLD='' NC=''
fi

info()    { echo -e "${BLUE}→${NC} $*"; }
success() { echo -e "${GREEN}✓${NC} $*"; }
warn()    { echo -e "${YELLOW}⚠${NC} $*"; }
error()   { echo -e "${RED}✗${NC} $*" >&2; }
header()  { echo -e "\n${BOLD}$*${NC}"; echo "─────────────────────────────────────────"; }

# Project root resolution
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"
```

### Pattern 2: Trap-Based Cleanup (from build-dist.sh)
**What:** Temporary directories cleaned up on exit, even on error
**When to use:** verify-dist.sh creates temp dir and isolated compose stack
**Example:**
```bash
VERIFY_DIR=$(mktemp -d)
trap 'cleanup' EXIT

cleanup() {
    info "Cleaning up verification environment..."
    cd "$VERIFY_DIR/kerala-delivery"
    docker compose --project-name verify-dist down --volumes --remove-orphans 2>/dev/null || true
    rm -rf "$VERIFY_DIR"
}
```

### Pattern 3: Health Polling with Spinner (from start.sh)
**What:** Spinner animation while polling /health endpoint
**When to use:** verify-dist.sh waiting for API to come up
**Example:**
```bash
poll_health() {
    local url="$1"
    local max_wait="$2"
    local elapsed=0
    local spinners=("⠋" "⠙" "⠹" "⠸")
    while [ "$elapsed" -lt "$max_wait" ]; do
        if curl -sf "$url" >/dev/null 2>&1; then
            printf "\r%s\r" "$(printf ' %.0s' {1..60})"
            return 0
        fi
        local idx=$(( (elapsed / 3) % 4 ))
        printf "\r  %s Waiting for services... (%ds / %ds)  " "${spinners[$idx]}" "$elapsed" "$max_wait"
        sleep 3
        elapsed=$((elapsed + 3))
    done
    echo ""
    return 1
}
```

### Pattern 4: Port Override via Compose File (for verify-dist.sh)
**What:** Generate a docker-compose.verify.yml override file to remap all host ports
**When to use:** Running isolated verification stack alongside primary stack
**Example:**
```bash
# Generate override file to remap ports for isolation
cat > "$VERIFY_DIR/kerala-delivery/docker-compose.verify.yml" << 'EOF'
services:
  db:
    ports:
      - "5433:5432"
  osrm:
    ports:
      - "5001:5000"
  vroom:
    ports:
      - "3001:3000"
  api:
    ports:
      - "8002:8000"
EOF

# Use both compose files
docker compose \
    --project-name verify-dist \
    -f docker-compose.yml \
    -f docker-compose.verify.yml \
    up -d --build
```

### Anti-Patterns to Avoid
- **Using `docker compose down -v` in stop.sh:** This removes named volumes (pgdata, dashboard_assets), destroying database data. The decision is to use `docker compose stop` (halt only).
- **Using `docker image prune -a` in GC mode:** This removes ALL unused images (not just dangling), which would remove base images needed for fast restart. Only dangling images should be pruned.
- **Hardcoding container names:** Use `docker compose ps --format` to discover container names dynamically, in case compose configuration changes.
- **Running verify-dist.sh without trap cleanup:** If the script fails mid-way, orphan containers and volumes will litter the system. Trap is mandatory.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Port conflict detection | Custom port scanner | Compose override file with known-free ports | Compose handles port binding; if port is taken, compose fails fast with clear error |
| Container log discovery | Manual path construction | `docker inspect --format='{{.LogPath}}' <container>` | Log path format is Docker-internal, varies by storage driver |
| Random credential generation | Python/openssl | `tr -dc 'A-Za-z0-9' < /dev/urandom \| head -c 32` | Already established pattern in install.sh and bootstrap.sh |
| Service readiness | Custom TCP probing | curl to /health endpoint with polling loop | Already proven pattern in start.sh with spinner |

**Key insight:** Every operational concern in this phase has an established solution in the existing scripts. The job is composition and adaptation, not invention.

## Common Pitfalls

### Pitfall 1: `docker compose stop` vs `docker compose down`
**What goes wrong:** Using `down` removes containers and networks. Using `down -v` also removes volumes (database data loss).
**Why it happens:** Muscle memory from development workflows where `down` is common.
**How to avoid:** stop.sh must use `docker compose stop` exclusively for the default mode. Only the `--gc` flag uses `docker compose down --remove-orphans` (without `-v`) to clean orphans.
**Warning signs:** Volume listed in `docker volume ls` disappears after running stop.sh.

### Pitfall 2: Container log truncation requires sudo
**What goes wrong:** Log files under `/var/lib/docker/containers/` are owned by root. `truncate -s 0` without `sudo` silently fails or errors.
**Why it happens:** Docker daemon runs as root; container logs inherit root ownership.
**How to avoid:** Use `sudo truncate -s 0 "$logpath"` and handle the case where sudo is not available.
**Warning signs:** Log sizes don't decrease after GC, or permission denied errors.

### Pitfall 3: OSRM data not available in verify-dist.sh temp directory
**What goes wrong:** The tarball does NOT include `data/osrm/` (it's excluded by build-dist.sh). The extracted directory has no OSRM data, so osrm-init will try to download and preprocess (~10-20 minutes).
**Why it happens:** OSRM data is ~1.5 GB and generated at install time, not included in distribution.
**How to avoid:** Two options: (a) Create an empty `data/osrm/` in the temp dir and accept that OSRM won't be available (verification checks /health and /driver/ only, which don't require OSRM), or (b) symlink/copy the host's `data/osrm/` into the temp dir for faster verification.
**Warning signs:** verify-dist.sh takes 15+ minutes to complete.

### Pitfall 4: Dashboard build container needs API_KEY env var
**What goes wrong:** The `dashboard-build` service takes `VITE_API_KEY` from `.env` at build time. If `.env` has an empty API_KEY, the built dashboard won't be able to authenticate API calls.
**Why it happens:** The dashboard embeds the API key at build time via Vite's `import.meta.env`.
**How to avoid:** The auto-generated .env for verification should include a dummy API_KEY value (not empty).
**Warning signs:** Dashboard loads but API calls return 401.

### Pitfall 5: Compose project name isolation is NOT port isolation
**What goes wrong:** `COMPOSE_PROJECT_NAME=verify-dist` creates separate containers/networks/volumes, but if both stacks expose the same host ports, the second stack fails to bind.
**Why it happens:** Docker port mapping is host-level, not compose-project-level.
**How to avoid:** MUST use compose override file to remap ALL exposed ports (db:5433, osrm:5001, vroom:3001, api:8002).
**Warning signs:** "Bind for 0.0.0.0:8000 failed: port is already allocated" error.

### Pitfall 6: Init containers (osrm-init, db-init, dashboard-build) in verification
**What goes wrong:** Init containers may take long or fail if dependencies aren't met.
**Why it happens:** osrm-init downloads data, db-init runs migrations, dashboard-build needs node_modules.
**How to avoid:** For verification, the critical path is: db starts -> db-init migrates -> dashboard-build builds -> api starts. OSRM/VROOM are optional for endpoint verification. Consider using `docker compose up -d --build db db-init dashboard-build api` to skip OSRM/VROOM entirely if speed is a priority.
**Warning signs:** Verification hangs waiting for osrm-init to download 150 MB.

### Pitfall 7: stop.sh --gc log truncation needs running container IDs
**What goes wrong:** After `docker compose stop`, containers are stopped. `docker inspect --format='{{.LogPath}}'` still works on stopped containers, but only if they exist (not removed).
**Why it happens:** Log files persist as long as the container exists (stopped or running).
**How to avoid:** Collect log paths BEFORE running `docker compose down --remove-orphans`, then truncate. Or use `docker ps -a` to find all containers (including stopped ones).
**Warning signs:** "No such container" errors during log truncation.

## Code Examples

### stop.sh -- Core Stop Logic
```bash
# Source: Adapted from start.sh patterns

# Get list of running services
RUNNING=$(docker compose ps --format '{{.Name}}' 2>/dev/null)
if [ -z "$RUNNING" ]; then
    info "Services already stopped"
    exit 0
fi

# Count and stop
COUNT=$(echo "$RUNNING" | wc -l)
docker compose stop

# Report each stopped container
while IFS= read -r name; do
    success "$name stopped"
done <<< "$RUNNING"

echo ""
success "Stopped $COUNT service(s)"
```

### stop.sh --gc -- Log Truncation
```bash
# Source: Docker documentation on container logs

header "Truncating container logs"
TOTAL_FREED=0
for container_id in $(docker ps -aq); do
    LOG_PATH=$(docker inspect --format='{{.LogPath}}' "$container_id" 2>/dev/null)
    if [ -n "$LOG_PATH" ] && [ -f "$LOG_PATH" ]; then
        LOG_SIZE=$(sudo stat -c%s "$LOG_PATH" 2>/dev/null || echo 0)
        TOTAL_FREED=$((TOTAL_FREED + LOG_SIZE))
        sudo truncate -s 0 "$LOG_PATH"
    fi
done
# Convert bytes to human-readable
if [ "$TOTAL_FREED" -gt 0 ]; then
    FREED_HR=$(numfmt --to=iec "$TOTAL_FREED" 2>/dev/null || echo "${TOTAL_FREED} bytes")
    success "Truncated container logs ($FREED_HR freed)"
else
    info "Container logs already empty"
fi
```

### stop.sh --gc -- Dangling Image Prune with Size Reporting
```bash
# Capture prune output for size reporting
PRUNE_OUTPUT=$(docker image prune -f 2>/dev/null)
RECLAIMED=$(echo "$PRUNE_OUTPUT" | grep -oP 'Total reclaimed space: \K.*' || echo "0B")
REMOVED_COUNT=$(echo "$PRUNE_OUTPUT" | grep -c "^Deleted:" || echo 0)
if [ "$REMOVED_COUNT" -gt 0 ]; then
    success "Removed $REMOVED_COUNT dangling image(s) ($RECLAIMED)"
else
    info "No dangling images to remove"
fi
```

### verify-dist.sh -- Compose Override Generation
```bash
# Generate port override for isolated verification
cat > "$EXTRACT_DIR/docker-compose.verify.yml" << 'OVERRIDE'
services:
  db:
    ports:
      - "5433:5432"
  osrm:
    ports:
      - "5001:5000"
  vroom:
    ports:
      - "3001:3000"
  api:
    ports:
      - "8002:8000"
    environment:
      - OSRM_URL=http://osrm:5000
      - VROOM_URL=http://vroom:3000
OVERRIDE
```

### verify-dist.sh -- Auto-Generate .env
```bash
# Source: Adapted from bootstrap.sh pattern
cp .env.example .env
DB_PASS=$(tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 32)
API_KEY_VAL=$(tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 32)
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$DB_PASS|" .env
sed -i "s|^API_KEY=.*|API_KEY=$API_KEY_VAL|" .env
sed -i "s|^ENVIRONMENT=.*|ENVIRONMENT=development|" .env
```

### verify-dist.sh -- Endpoint Verification
```bash
# Source: Adapted from tests/deploy/entrypoint.sh
VERIFY_URL="http://localhost:8002"
PASS=0
FAIL=0

# Check /health
if curl -sf "$VERIFY_URL/health" >/dev/null 2>&1; then
    success "GET /health returns 200"
    PASS=$((PASS + 1))
else
    error "GET /health not responding"
    FAIL=$((FAIL + 1))
fi

# Check /driver/ serves HTML
if curl -sf "$VERIFY_URL/driver/" | grep -qi "html" 2>/dev/null; then
    success "GET /driver/ serves HTML"
    PASS=$((PASS + 1))
else
    error "GET /driver/ not serving HTML"
    FAIL=$((FAIL + 1))
fi

# Check /dashboard/ serves React app
if curl -sf "$VERIFY_URL/dashboard/" | grep -qi "html" 2>/dev/null; then
    success "GET /dashboard/ serves HTML"
    PASS=$((PASS + 1))
else
    error "GET /dashboard/ not serving HTML"
    FAIL=$((FAIL + 1))
fi
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `docker-compose` (standalone) | `docker compose` (v2 plugin) | Docker Compose v2 | All scripts must use `docker compose`, not `docker-compose` |
| Manual OSRM setup | osrm-init container (idempotent) | Phase 13 | verify-dist.sh gets OSRM init for free via compose |
| Manual .env creation | bootstrap.sh auto-generates | Phase 15 | verify-dist.sh follows same auto-generation pattern |
| Docker-in-Docker deploy test | Port-isolated host extraction | Phase 23 | Lighter, faster verification (~2-5 min vs ~20 min) |

**Current Docker Compose version:** v5.0.2 (confirmed on system)
- `docker compose stop` -- stops without removing
- `docker compose down --remove-orphans` -- removes orphan containers
- `docker image prune -f` -- removes dangling images only (not `-a`)

## Open Questions

1. **OSRM data in verification: skip or share?**
   - What we know: Tarball does NOT include data/osrm/. OSRM download takes ~10-20 min. The /health endpoint and /driver/ app do NOT require OSRM to be running.
   - What's unclear: Whether the API returns 200 on /health when OSRM is down, or if it reports degraded state.
   - Recommendation: Start with skipping OSRM/VROOM entirely in verification (only start db, db-init, dashboard-build, api). If /health requires OSRM, add an option to copy host OSRM data. **This is Claude's discretion per CONTEXT.md.**

2. **Timeout for verification health polling**
   - What we know: install.sh uses 300s (5 min) for full install. start.sh uses 60s for daily startup. Dashboard build takes ~30-60s.
   - Recommendation: Use 120s for verification -- longer than start.sh (dashboard needs to build) but shorter than install.sh (no OSRM preprocessing). **This is Claude's discretion per CONTEXT.md.**

3. **Whether to verify .pyc licensing module loads**
   - What we know: build-dist.sh already validates .pyc imports during build. The verification script tests the built tarball.
   - Recommendation: Skip -- the build already validates this. The endpoint checks (/health returning 200) implicitly confirm licensing loads. **This is Claude's discretion per CONTEXT.md.**

4. **Error diagnosis strategy**
   - What we know: start.sh has a `diagnose_failure()` function that checks each container individually.
   - Recommendation: On verification failure, print the logs of failed containers using `docker compose --project-name verify-dist logs --tail=30`. Show which of the 3 endpoint checks passed/failed. **This is Claude's discretion per CONTEXT.md.**

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Bash scripts (self-verifying) |
| Config file | none -- scripts are the tests |
| Quick run command | `./scripts/stop.sh && docker compose ps` |
| Full suite command | `./scripts/verify-dist.sh dist/kerala-delivery-v*.tar.gz` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OPS-01 | stop.sh stops all services | smoke | `./scripts/stop.sh && docker compose ps --format '{{.Status}}' \| grep -v Exited` | Wave 0 (stop.sh is the deliverable) |
| OPS-02 | stop.sh --gc cleans up | smoke | `./scripts/stop.sh --gc` | Wave 0 (stop.sh --gc is the deliverable) |
| OPS-03 | Clean install from tarball | integration | `./scripts/verify-dist.sh dist/kerala-delivery-*.tar.gz` | Wave 0 (verify-dist.sh is the deliverable) |

### Sampling Rate
- **Per task commit:** Manual smoke test of the script being developed
- **Per wave merge:** Run both scripts end-to-end
- **Phase gate:** `stop.sh` tested against running stack; `verify-dist.sh` run against latest tarball

### Wave 0 Gaps
- [ ] `scripts/stop.sh` -- new file, covers OPS-01 and OPS-02
- [ ] `scripts/verify-dist.sh` -- new file, covers OPS-03
- [ ] Build a fresh tarball first: `./scripts/build-dist.sh v1.4` (verify-dist.sh needs input)

## Sources

### Primary (HIGH confidence)
- Existing scripts: `scripts/start.sh`, `scripts/install.sh`, `scripts/build-dist.sh`, `scripts/bootstrap.sh` -- pattern source for all new scripts
- `docker-compose.yml` -- service names, port mappings, volume mounts, init container dependencies
- `tests/deploy/entrypoint.sh` -- endpoint verification patterns, .env auto-generation
- `dist/kerala-delivery-v0.0-uat.tar.gz` -- verified tarball contents and structure
- Docker Compose v5.0.2 CLI help -- verified `stop`, `down`, `--remove-orphans`, `--project-name` flags

### Secondary (MEDIUM confidence)
- Docker container log paths verified via `docker inspect --format='{{.LogPath}}'` on running system
- `docker image prune -f` help output confirmed: removes dangling only without `-a`

### Tertiary (LOW confidence)
- None -- all findings verified against running system and existing code

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- pure Bash + Docker Compose, verified on running system
- Architecture: HIGH -- all patterns derived from existing codebase scripts
- Pitfalls: HIGH -- each pitfall verified against actual Docker behavior on this system

**Research date:** 2026-03-08
**Valid until:** 2026-04-08 (stable -- Bash and Docker Compose APIs rarely change)
