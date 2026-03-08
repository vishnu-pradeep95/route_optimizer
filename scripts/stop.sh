#!/usr/bin/env bash
# =============================================================================
# Daily Shutdown -- Kerala LPG Delivery Route Optimizer
# =============================================================================
#
# What this does:
#   1. Stops all Docker Compose services gracefully (containers preserved)
#   2. Optionally cleans up disk space with --gc flag
#
# Usage:
#   cd ~/routing_opt && ./scripts/stop.sh          # stop services
#   cd ~/routing_opt && ./scripts/stop.sh --gc     # stop + garbage collect
#
# Duration: ~5-15 seconds
#
# GC mode (--gc) additionally:
#   - Removes orphan containers and unused networks
#   - Prunes dangling Docker images
#   - Truncates container log files (requires sudo)
#
# Safe: Never removes named volumes (pgdata, dashboard_assets) or
# non-dangling images. Your data and built images are always preserved.
# =============================================================================

set -euo pipefail

# =============================================================================
# Color helpers (matches start.sh / bootstrap.sh for visual consistency)
# =============================================================================

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

# =============================================================================
# Ensure we're running from the project root
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# =============================================================================
# Parse arguments
# =============================================================================

GC_MODE=false
if [[ "${1:-}" == "--gc" ]]; then
    GC_MODE=true
fi

# =============================================================================
# Main flow
# =============================================================================

header "Kerala LPG Delivery Route Optimizer"

# ── Step 1: Discover running services ────────────────────────────────────────

RUNNING_CONTAINERS=$(docker compose ps --format '{{.Name}}' 2>/dev/null || true)

if [[ -z "$RUNNING_CONTAINERS" ]]; then
    info "Services already stopped"
    if [[ "$GC_MODE" == true ]]; then
        # Even if no services are running, GC can still clean up
        info "Continuing with garbage collection..."
    else
        exit 0
    fi
fi

# Count and store container names
CONTAINER_COUNT=0
CONTAINER_NAMES=()
while IFS= read -r name; do
    if [[ -n "$name" ]]; then
        CONTAINER_NAMES+=("$name")
        CONTAINER_COUNT=$((CONTAINER_COUNT + 1))
    fi
done <<< "$RUNNING_CONTAINERS"

# ── Step 2 (GC only): Capture log paths before containers are removed ────────

LOG_PATHS=()
if [[ "$GC_MODE" == true ]]; then
    # Get ALL container IDs (running + stopped) from this compose project
    ALL_CONTAINER_IDS=$(docker compose ps -a --format '{{.ID}}' 2>/dev/null || true)
    if [[ -n "$ALL_CONTAINER_IDS" ]]; then
        while IFS= read -r cid; do
            if [[ -n "$cid" ]]; then
                log_path=$(docker inspect --format='{{.LogPath}}' "$cid" 2>/dev/null || true)
                if [[ -n "$log_path" ]]; then
                    LOG_PATHS+=("$log_path")
                fi
            fi
        done <<< "$ALL_CONTAINER_IDS"
    fi
fi

# ── Step 3: Stop services ───────────────────────────────────────────────────

if [[ "$CONTAINER_COUNT" -gt 0 ]]; then
    info "Stopping services..."
    docker compose stop

    for name in "${CONTAINER_NAMES[@]}"; do
        success "$name stopped"
    done

    success "Stopped $CONTAINER_COUNT service(s)"
fi

# ── Step 4 (GC only): Garbage collection ────────────────────────────────────

if [[ "$GC_MODE" == true ]]; then
    header "Garbage collection"

    # ── 4a: Truncate container logs (BEFORE down removes containers) ─────
    # Containers are stopped but still exist, so their log files are intact.
    # Must truncate now because `docker compose down` deletes containers
    # and Docker cleans up their log files.
    if [[ ${#LOG_PATHS[@]} -gt 0 ]]; then
        # Check if sudo is available
        if command -v sudo &>/dev/null; then
            TOTAL_FREED=0
            TRUNCATED=0
            for log_path in "${LOG_PATHS[@]}"; do
                # Log files are root-owned; use sudo for all access
                if sudo test -f "$log_path" 2>/dev/null; then
                    LOG_SIZE=$(sudo stat -c%s "$log_path" 2>/dev/null || echo "0")
                    if [[ "$LOG_SIZE" -gt 0 ]]; then
                        sudo truncate -s 0 "$log_path"
                        TOTAL_FREED=$((TOTAL_FREED + LOG_SIZE))
                        TRUNCATED=$((TRUNCATED + 1))
                    fi
                fi
            done

            if [[ "$TOTAL_FREED" -gt 0 ]]; then
                FREED_HUMAN=$(numfmt --to=iec "$TOTAL_FREED" 2>/dev/null || echo "${TOTAL_FREED} bytes")
                success "Truncated $TRUNCATED container log(s) ($FREED_HUMAN freed)"
            else
                info "Container logs already empty"
            fi
        else
            warn "Log truncation requires sudo -- skipping"
        fi
    else
        info "No container logs found to truncate"
    fi

    # ── 4b: Orphan container and network cleanup ─────────────────────────
    info "Removing orphan containers and unused networks..."
    docker compose down --remove-orphans
    success "Orphan containers and networks cleaned"

    # ── 4c: Dangling image prune ─────────────────────────────────────────
    info "Pruning dangling images..."
    PRUNE_OUTPUT=$(docker image prune -f 2>&1)

    # Parse results
    RECLAIMED=$(echo "$PRUNE_OUTPUT" | grep -oP "Total reclaimed space: \K.*" 2>/dev/null || echo "")

    if [[ -n "$RECLAIMED" && "$RECLAIMED" != "0B" ]]; then
        success "Removed dangling image(s) ($RECLAIMED reclaimed)"
    else
        info "No dangling images to remove"
    fi

    echo ""
    success "Garbage collection complete"
fi
