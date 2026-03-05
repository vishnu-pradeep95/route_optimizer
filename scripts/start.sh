#!/usr/bin/env bash
# =============================================================================
# Daily Startup -- Kerala LPG Delivery Route Optimizer
# =============================================================================
#
# What this does:
#   1. Starts Docker daemon if it's not running
#   2. Runs docker compose up -d (no rebuild, instant for cached images)
#   3. Polls the health endpoint until the system is ready
#   4. Prints dashboard and driver app URLs on success
#   5. Diagnoses failures with plain-English suggestions
#
# Usage:
#   cd ~/routing_opt && ./scripts/start.sh
#
# Duration: ~10-30 seconds (services are already built)
#
# This is the daily command for office staff. Run it every morning.
# For first-time installation, use ./bootstrap.sh instead.
# =============================================================================

set -euo pipefail

# =============================================================================
# Color helpers (matches bootstrap.sh / install.sh for visual consistency)
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
# Constants
# =============================================================================

HEALTH_URL="http://localhost:8000/health"
MAX_WAIT=60
POLL_INTERVAL=3

# =============================================================================
# Ensure we're running from the project root
# =============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# =============================================================================
# Functions
# =============================================================================

ensure_docker_running() {
    if docker info &>/dev/null; then
        return 0
    fi

    info "Starting Docker..."
    sudo service docker start &>/dev/null || true

    local waited=0
    while [ "$waited" -lt 10 ]; do
        if docker info &>/dev/null; then
            success "Docker started"
            return 0
        fi
        sleep 1
        waited=$((waited + 1))
    done

    error "Could not start Docker."
    echo "  Try one of these:"
    echo "    1. sudo service docker start"
    echo "    2. Restart WSL: open PowerShell and run: wsl --shutdown"
    return 1
}

poll_health() {
    local elapsed=0
    local spinners=("⠋" "⠙" "⠹" "⠸")

    while [ "$elapsed" -lt "$MAX_WAIT" ]; do
        if curl -sf "$HEALTH_URL" >/dev/null 2>&1; then
            printf "\r%s\r" "$(printf ' %.0s' {1..60})"
            return 0
        fi

        local idx=$(( (elapsed / POLL_INTERVAL) % 4 ))
        printf "\r  %s Waiting for services... (%ds / %ds)  " "${spinners[$idx]}" "$elapsed" "$MAX_WAIT"

        sleep "$POLL_INTERVAL"
        elapsed=$((elapsed + POLL_INTERVAL))
    done

    echo ""
    return 1
}

diagnose_failure() {
    error "System did not become healthy within ${MAX_WAIT} seconds."
    echo ""

    local all_running=true

    # Check database (has Docker healthcheck)
    local db_status
    db_status=$(docker inspect --format='{{.State.Status}}' lpg-db 2>/dev/null || echo "not found")
    local db_health
    db_health=$(docker inspect --format='{{.State.Health.Status}}' lpg-db 2>/dev/null || echo "unknown")
    if [ "$db_status" != "running" ] || [ "$db_health" != "healthy" ]; then
        error "Database (lpg-db): status=$db_status health=$db_health"
        echo "  Try: docker compose logs db --tail=20"
        all_running=false
    fi

    # Check OSRM (no reliable healthcheck per research)
    local osrm_status
    osrm_status=$(docker inspect --format='{{.State.Status}}' osrm-kerala 2>/dev/null || echo "not found")
    if [ "$osrm_status" != "running" ]; then
        error "OSRM routing engine (osrm-kerala): status=$osrm_status"
        echo "  Try: docker compose logs osrm --tail=20"
        all_running=false
    fi

    # Check API server
    local api_status
    api_status=$(docker inspect --format='{{.State.Status}}' lpg-api 2>/dev/null || echo "not found")
    if [ "$api_status" != "running" ]; then
        error "API server (lpg-api): status=$api_status"
        echo "  Try: docker compose logs api --tail=20"
        all_running=false
    fi

    if [ "$all_running" = true ]; then
        echo ""
        warn "All containers appear running but API is not responding."
        echo "  The API may still be starting up. Wait a minute and try:"
        echo "    curl http://localhost:8000/health"
    fi

    echo ""
    echo "  If the problem persists, try: docker compose down && ./scripts/install.sh"
}

# =============================================================================
# Main flow
# =============================================================================

header "Kerala LPG Delivery Route Optimizer"
info "Starting daily services..."

ensure_docker_running || exit 1

info "Starting containers..."
docker compose up -d

echo ""
poll_health

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✓ System is running!                                        ${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${BOLD}Dashboard:${NC}   http://localhost:8000/dashboard/"
    echo -e "  ${BOLD}Driver App:${NC}  http://localhost:8000/driver/"
    echo ""
    exit 0
else
    diagnose_failure
    exit 1
fi
