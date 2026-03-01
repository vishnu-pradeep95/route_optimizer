#!/usr/bin/env bash
# =============================================================================
# Smart Installer — Kerala LPG Delivery Route Optimizer
# =============================================================================
#
# What this does:
#   1. Checks for required tools (Docker, Docker Compose, git)
#   2. Clones or updates the repository
#   3. Creates .env with prompted values (or secure defaults)
#   4. Builds and starts all services (including OSRM + DB auto-init)
#   5. Waits for the system to be healthy
#
# Usage (local — run from project root):
#   chmod +x scripts/install.sh
#   ./scripts/install.sh
#
# Duration: ~10-20 minutes on first run (OSRM preprocessing is slowest)
# Subsequent runs: ~1-2 minutes (OSRM data cached, images cached)
#
# Requirements:
#   - Ubuntu 22.04+ or WSL2 with Ubuntu
#   - Internet connection (first run only — downloads images + map data)
#   - sudo access (for Docker commands if not in docker group)
#
# What happens on re-run:
#   - Existing .env is preserved (never overwritten)
#   - OSRM data reuse (init container is idempotent)
#   - Database migrations are idempotent (Alembic skips applied ones)
#   - Docker images use cache for fast rebuilds
# =============================================================================

set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════════════════

# Colors for output (disabled if not a terminal)
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    BLUE='\033[0;34m'
    BOLD='\033[1m'
    NC='\033[0m'  # No Color
else
    GREEN='' YELLOW='' RED='' BLUE='' BOLD='' NC=''
fi

# Health check settings
HEALTH_URL="http://localhost:8000/health"
MAX_WAIT=300  # 5 minutes max wait for system to come up
POLL_INTERVAL=5

# ═══════════════════════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════════════════════

info()    { echo -e "${BLUE}→${NC} $*"; }
success() { echo -e "${GREEN}✓${NC} $*"; }
warn()    { echo -e "${YELLOW}⚠${NC} $*"; }
error()   { echo -e "${RED}✗${NC} $*" >&2; }
header()  { echo -e "\n${BOLD}$*${NC}"; echo "─────────────────────────────────────────"; }

# Generate a random 32-character password (alphanumeric)
# Why /dev/urandom + tr? It's available on all Linux systems without
# requiring python or openssl. base64 ensures printable characters.
generate_password() {
    tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 32
}

# Check if a command exists
require_cmd() {
    local cmd="$1"
    local install_hint="${2:-}"
    if ! command -v "$cmd" &> /dev/null; then
        error "$cmd is not installed."
        if [ -n "$install_hint" ]; then
            echo "  Install with: $install_hint"
        fi
        return 1
    fi
    return 0
}

# ═══════════════════════════════════════════════════════════════════════════
# Step 1: Check prerequisites
# ═══════════════════════════════════════════════════════════════════════════

header "Step 1/5: Checking prerequisites"

MISSING=0

# Docker
if require_cmd docker "See https://docs.docker.com/engine/install/ubuntu/"; then
    DOCKER_VERSION=$(docker --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' || echo "unknown")
    success "Docker $DOCKER_VERSION"
else
    MISSING=1
fi

# Docker Compose (v2 plugin or standalone)
if docker compose version &> /dev/null; then
    COMPOSE_VERSION=$(docker compose version --short 2>/dev/null || echo "unknown")
    success "Docker Compose $COMPOSE_VERSION"
elif require_cmd docker-compose "sudo apt install docker-compose-plugin"; then
    success "Docker Compose (standalone)"
else
    MISSING=1
fi

# Git
if require_cmd git "sudo apt install git"; then
    success "Git $(git --version | grep -oP '\d+\.\d+\.\d+' || echo 'unknown')"
else
    MISSING=1
fi

# curl (needed for health checks)
if require_cmd curl "sudo apt install curl"; then
    success "curl"
else
    MISSING=1
fi

if [ "$MISSING" -ne 0 ]; then
    echo ""
    error "Missing prerequisites. Install the tools above and re-run this script."
    exit 1
fi

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    warn "Docker daemon is not running."
    info "Attempting to start Docker..."
    if sudo service docker start 2>/dev/null; then
        success "Docker daemon started"
    else
        error "Could not start Docker. Try: sudo service docker start"
        exit 1
    fi
fi

success "All prerequisites met"

# ═══════════════════════════════════════════════════════════════════════════
# Step 2: Determine project directory
# ═══════════════════════════════════════════════════════════════════════════

header "Step 2/5: Setting up project directory"

# If we're already in the project root (docker-compose.yml exists), use it
if [ -f "docker-compose.yml" ] && grep -q "lpg-api" docker-compose.yml 2>/dev/null; then
    PROJECT_DIR="$(pwd)"
    success "Running from project root: $PROJECT_DIR"
elif [ -f "scripts/install.sh" ]; then
    # Running from scripts/ or project root
    PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    cd "$PROJECT_DIR"
    success "Project root: $PROJECT_DIR"
else
    error "Could not find project root. Run this script from the project directory."
    echo "  cd /path/to/routing_opt && ./scripts/install.sh"
    exit 1
fi

# ═══════════════════════════════════════════════════════════════════════════
# Step 3: Create .env if it doesn't exist
# ═══════════════════════════════════════════════════════════════════════════

header "Step 3/5: Environment configuration"

if [ -f ".env" ]; then
    success ".env already exists — keeping existing configuration"
    info "To reconfigure, delete .env and re-run this script"
else
    info "Creating .env from template..."

    # Generate secure defaults
    DEFAULT_DB_PASS=$(generate_password)
    DEFAULT_API_KEY=$(generate_password)

    echo ""
    echo -e "${BOLD}Configure your installation:${NC}"
    echo "(Press Enter to accept defaults shown in brackets)"
    echo ""

    # Database password
    read -rp "PostgreSQL password [$DEFAULT_DB_PASS]: " DB_PASS
    DB_PASS="${DB_PASS:-$DEFAULT_DB_PASS}"

    # API key
    read -rp "API key for dashboard access [$DEFAULT_API_KEY]: " API_KEY_VAL
    API_KEY_VAL="${API_KEY_VAL:-$DEFAULT_API_KEY}"

    # Google Maps API key (optional)
    read -rp "Google Maps API key (optional, press Enter to skip): " GMAPS_KEY
    GMAPS_KEY="${GMAPS_KEY:-}"

    # Create .env from template with user values
    if [ -f ".env.example" ]; then
        cp .env.example .env
    else
        # Minimal .env if template is missing
        cat > .env << 'ENVEOF'
API_KEY=
ENVIRONMENT=development
GOOGLE_MAPS_API_KEY=
POSTGRES_USER=routing
POSTGRES_PASSWORD=
POSTGRES_DB=routing_opt
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
OSRM_URL=http://localhost:5000
VROOM_URL=http://localhost:3000
CORS_ALLOWED_ORIGINS=http://localhost:8000,http://localhost:3000
RATE_LIMIT_ENABLED=true
ENVEOF
    fi

    # Replace values in .env using sed
    # Why sed instead of envsubst? The .env file has other variables we want to keep as-is.
    sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$DB_PASS|" .env
    sed -i "s|^API_KEY=.*|API_KEY=$API_KEY_VAL|" .env
    if [ -n "$GMAPS_KEY" ]; then
        sed -i "s|^GOOGLE_MAPS_API_KEY=.*|GOOGLE_MAPS_API_KEY=$GMAPS_KEY|" .env
    fi

    echo ""
    success ".env created with secure credentials"
    warn "SAVE THESE CREDENTIALS — you'll need the API key for the dashboard:"
    echo -e "  API Key: ${BOLD}$API_KEY_VAL${NC}"
    echo ""
fi

# ═══════════════════════════════════════════════════════════════════════════
# Step 4: Build and start services
# ═══════════════════════════════════════════════════════════════════════════

header "Step 4/5: Building and starting services"

info "This may take 10-20 minutes on first run (downloading images + map data)"
echo ""

# Create data directories if they don't exist
mkdir -p data/osrm data/geocode_cache

# Build and start all services
# --build forces rebuild of custom images (API)
# Init containers (osrm-init, db-init) run automatically via depends_on
docker compose up -d --build

success "All containers started"

# ═══════════════════════════════════════════════════════════════════════════
# Step 5: Wait for system to be healthy
# ═══════════════════════════════════════════════════════════════════════════

header "Step 5/5: Waiting for system to become healthy"

info "Init containers are setting up OSRM data and database schema..."
info "This is a one-time process — future starts will be instant."
echo ""

ELAPSED=0
HEALTHY=false

while [ "$ELAPSED" -lt "$MAX_WAIT" ]; do
    # Show a simple progress indicator
    DOTS=$(( (ELAPSED / POLL_INTERVAL) % 4 ))
    case $DOTS in
        0) SPINNER="⠋" ;;
        1) SPINNER="⠙" ;;
        2) SPINNER="⠹" ;;
        3) SPINNER="⠸" ;;
    esac
    printf "\r  %s Waiting for services... (%ds / %ds)  " "$SPINNER" "$ELAPSED" "$MAX_WAIT"

    # Check if API is responding
    if curl -sf "$HEALTH_URL" > /dev/null 2>&1; then
        HEALTHY=true
        break
    fi

    sleep "$POLL_INTERVAL"
    ELAPSED=$((ELAPSED + POLL_INTERVAL))
done

echo ""  # Clear the progress line

if [ "$HEALTHY" = true ]; then
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  ✓ Installation complete! System is running.                 ${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo -e "  ${BOLD}Dashboard:${NC}   http://localhost:8000/dashboard/"
    echo -e "  ${BOLD}Driver App:${NC}  http://localhost:8000/driver/"
    echo -e "  ${BOLD}API Health:${NC}  http://localhost:8000/health"
    echo ""
    echo -e "  ${BOLD}Daily workflow:${NC}"
    echo "    1. Open dashboard in Chrome"
    echo "    2. Upload today's CDCMS export (drag & drop)"
    echo "    3. Print QR sheet → hand to drivers"
    echo "    4. Drivers scan QR → Google Maps → deliver"
    echo ""
    echo -e "  ${BOLD}To stop:${NC}  docker compose down"
    echo -e "  ${BOLD}To start:${NC} docker compose up -d"
    echo ""
else
    echo ""
    warn "System did not become healthy within $MAX_WAIT seconds."
    echo ""
    echo "  This usually means OSRM is still preprocessing map data."
    echo "  Check progress with:"
    echo ""
    echo "    docker compose logs -f osrm-init"
    echo "    docker compose logs -f db-init"
    echo ""
    echo "  Once init containers finish, the API will start automatically."
    echo "  Check status: docker compose ps"
    echo ""
    exit 1
fi
