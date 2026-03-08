#!/usr/bin/env bash
# =============================================================================
# Distribution Verifier -- Kerala LPG Delivery Route Optimizer
# =============================================================================
#
# What this does:
#   1. Extracts a distribution tarball to a temp directory
#   2. Generates a dummy .env with random credentials (no prompts)
#   3. Creates a Docker Compose port override for isolated testing
#   4. Builds and starts essential services (skips OSRM/VROOM for speed)
#   5. Verifies /health, /driver/, and /dashboard/ endpoints
#   6. Cleans up all containers, volumes, and temp files on exit
#
# Usage:
#   ./scripts/verify-dist.sh dist/kerala-delivery-v1.4.tar.gz
#
# Output:
#   PASS/FAIL for each endpoint check, exit 0 on success, exit 1 on failure.
#
# Isolation:
#   Uses COMPOSE_PROJECT_NAME=verify-dist and port 8002 to avoid
#   conflicting with any running primary stack on port 8000.
#
# Requirements:
#   - Docker and Docker Compose v2 (plugin)
#   - curl (for health checks)
# =============================================================================

set -euo pipefail

TARBALL="${1:?Usage: $0 <tarball>  (e.g., dist/kerala-delivery-v1.4.tar.gz)}"

# =============================================================================
# Color helpers (matches start.sh / build-dist.sh for visual consistency)
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

VERIFY_PORT=8002
VERIFY_PROJECT="verify-dist"
MAX_WAIT=120   # 2 minutes (longer than start.sh because dashboard must build)
POLL_INTERVAL=3

# =============================================================================
# Validate input
# =============================================================================

if [ ! -f "$TARBALL" ]; then
    error "File not found: $TARBALL"
    exit 1
fi

case "$TARBALL" in
    *.tar.gz|*.tgz) ;;
    *)
        error "Expected a .tar.gz file, got: $TARBALL"
        exit 1
        ;;
esac

# =============================================================================
# Temp directory + trap cleanup
# =============================================================================

VERIFY_DIR=$(mktemp -d)
EXTRACT_DIR=""  # Set after extraction

cleanup() {
    info "Cleaning up verification environment..."
    if [ -n "$EXTRACT_DIR" ] && [ -d "$EXTRACT_DIR" ]; then
        cd "$EXTRACT_DIR" 2>/dev/null || true
        docker compose --project-name "$VERIFY_PROJECT" \
            -f docker-compose.verify.yml \
            down --volumes --remove-orphans 2>/dev/null || true
    fi
    rm -rf "$VERIFY_DIR"
    success "Cleanup complete"
}

trap 'cleanup' EXIT

header "Verifying distribution: $(basename "$TARBALL")"

# =============================================================================
# Step 1/5: Extract tarball
# =============================================================================

header "Step 1/5: Extracting tarball"

info "Extracting to $VERIFY_DIR ..."
tar xzf "$TARBALL" -C "$VERIFY_DIR"

if [ ! -f "$VERIFY_DIR/kerala-delivery/docker-compose.yml" ]; then
    error "Invalid tarball: docker-compose.yml not found in kerala-delivery/"
    exit 1
fi

EXTRACT_DIR="$VERIFY_DIR/kerala-delivery"
cd "$EXTRACT_DIR"

success "Extracted tarball ($(du -sh "$EXTRACT_DIR" | cut -f1))"

# =============================================================================
# Step 2/5: Generate .env
# =============================================================================

header "Step 2/5: Generating .env"

if [ ! -f ".env.example" ]; then
    error ".env.example not found in tarball"
    exit 1
fi

cp .env.example .env

# Generate random credentials (openssl avoids SIGPIPE from /dev/urandom+head with pipefail)
DB_PASS=$(openssl rand -hex 16)
API_KEY=$(openssl rand -hex 16)

sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$DB_PASS|" .env
sed -i "s|^API_KEY=.*|API_KEY=$API_KEY|" .env
sed -i "s|^ENVIRONMENT=.*|ENVIRONMENT=development|" .env
sed -i "s|^GOOGLE_MAPS_API_KEY=.*|GOOGLE_MAPS_API_KEY=|" .env

success ".env generated with dummy credentials"

# =============================================================================
# Step 3/5: Generate compose port override
# =============================================================================

header "Step 3/5: Generating verification compose file"

# Generate a standalone compose file with ONLY the 4 services needed for
# verification (db, db-init, dashboard-build, api). This avoids pulling in
# OSRM/VROOM which download 300+ MB of map data and are not needed for
# endpoint verification. Uses isolated ports to avoid conflicts.

# Read DB password and API key from the .env we just generated
VERIFY_DB_PASS=$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2)
VERIFY_API_KEY=$(grep '^API_KEY=' .env | cut -d= -f2)

cat > docker-compose.verify.yml << OVERRIDE_EOF
services:
  db:
    image: postgis/postgis:16-3.5
    ports:
      - "5433:5432"
    environment:
      POSTGRES_DB: routing_opt
      POSTGRES_USER: routing
      POSTGRES_PASSWORD: ${VERIFY_DB_PASS}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./infra/postgres/init.sql:/docker-entrypoint-initdb.d/01-init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U routing -d routing_opt"]
      interval: 10s
      timeout: 5s
      retries: 5

  db-init:
    build:
      context: .
      dockerfile: infra/Dockerfile
    environment:
      - DATABASE_URL=postgresql+asyncpg://routing:${VERIFY_DB_PASS}@db:5432/routing_opt
    command: >
      sh -c "
        echo 'Running database migrations...' &&
        alembic upgrade head &&
        echo 'Database schema up to date'
      "
    depends_on:
      db:
        condition: service_healthy
    restart: "no"

  dashboard-build:
    build:
      context: .
      dockerfile: infra/Dockerfile.dashboard
      args:
        VITE_BASE_PATH: "/dashboard/"
        VITE_API_KEY: "${VERIFY_API_KEY}"
    volumes:
      - dashboard_assets:/srv/dashboard
    restart: "no"

  api:
    build:
      context: .
      dockerfile: infra/Dockerfile
    ports:
      - "${VERIFY_PORT}:8000"
    environment:
      - GOOGLE_MAPS_API_KEY=
      - API_KEY=${VERIFY_API_KEY}
      - ENVIRONMENT=development
      - OSRM_URL=http://localhost:5000
      - VROOM_URL=http://localhost:3000
      - DATABASE_URL=postgresql+asyncpg://routing:${VERIFY_DB_PASS}@db:5432/routing_opt
    volumes:
      - ./data:/app/data
      - dashboard_assets:/srv/dashboard:ro
    depends_on:
      db-init:
        condition: service_completed_successfully
      dashboard-build:
        condition: service_completed_successfully

volumes:
  pgdata:
  dashboard_assets:
OVERRIDE_EOF

success "Verification compose file generated (API on :$VERIFY_PORT)"

# =============================================================================
# Step 4/5: Build and start services
# =============================================================================

header "Step 4/5: Building and starting services"

# Create data directories that services expect
mkdir -p data/osrm data/geocode_cache

info "Building and starting db, db-init, dashboard-build, api..."
info "(Skipping OSRM/VROOM -- not needed for endpoint verification)"

docker compose \
    --project-name "$VERIFY_PROJECT" \
    -f docker-compose.verify.yml \
    up -d --build

echo ""
info "Polling health endpoint (http://localhost:$VERIFY_PORT/health)..."

# Health polling with spinner (matches start.sh pattern)
ELAPSED=0
HEALTHY=false
SPINNERS=("*" "o" "O" "@")

while [ "$ELAPSED" -lt "$MAX_WAIT" ]; do
    if curl -sf "http://localhost:$VERIFY_PORT/health" >/dev/null 2>&1; then
        printf "\r%s\r" "$(printf ' %.0s' {1..60})"
        HEALTHY=true
        break
    fi

    IDX=$(( (ELAPSED / POLL_INTERVAL) % 4 ))
    printf "\r  %s Waiting for services... (%ds / %ds)  " "${SPINNERS[$IDX]}" "$ELAPSED" "$MAX_WAIT"

    sleep "$POLL_INTERVAL"
    ELAPSED=$((ELAPSED + POLL_INTERVAL))
done

echo ""

if [ "$HEALTHY" = false ]; then
    error "Services did not become healthy within ${MAX_WAIT} seconds."
    echo ""
    info "Diagnostic logs (last 30 lines):"
    echo ""
    docker compose --project-name "$VERIFY_PROJECT" -f docker-compose.verify.yml logs --tail=30 2>/dev/null || true
    exit 1
fi

success "Services healthy after ${ELAPSED}s"

# Brief pause to ensure all routes are initialized (StaticFiles mounts may
# take a moment after the health endpoint becomes available)
sleep 2

# =============================================================================
# Step 5/5: Verify endpoints
# =============================================================================

header "Step 5/5: Verifying endpoints"

PASS_COUNT=0
FAIL_COUNT=0
TOTAL_CHECKS=3
FAILED_CHECKS=""

# Check 1: /health returns 200
info "Checking GET /health ..."
HTTP_CODE=$(curl -sf -o /dev/null -w "%{http_code}" "http://localhost:$VERIFY_PORT/health" 2>/dev/null || echo "000")
if [ "$HTTP_CODE" = "200" ]; then
    success "/health -> 200 OK"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    error "/health -> $HTTP_CODE (expected 200)"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    FAILED_CHECKS="$FAILED_CHECKS /health"
fi

# Check 2: /driver/ returns HTML
info "Checking GET /driver/ ..."
DRIVER_CODE=$(curl -s -o /tmp/verify-driver.html -w "%{http_code}" "http://localhost:$VERIFY_PORT/driver/" 2>/dev/null || echo "000")
if [ "$DRIVER_CODE" = "200" ] && grep -qi "html" /tmp/verify-driver.html 2>/dev/null; then
    success "/driver/ -> 200 OK, HTML content served"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    error "/driver/ -> HTTP $DRIVER_CODE (expected 200 with HTML)"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    FAILED_CHECKS="$FAILED_CHECKS /driver/"
fi
rm -f /tmp/verify-driver.html

# Check 3: /dashboard/ returns HTML
info "Checking GET /dashboard/ ..."
DASH_CODE=$(curl -s -o /tmp/verify-dashboard.html -w "%{http_code}" "http://localhost:$VERIFY_PORT/dashboard/" 2>/dev/null || echo "000")
if [ "$DASH_CODE" = "200" ] && grep -qi "html" /tmp/verify-dashboard.html 2>/dev/null; then
    success "/dashboard/ -> 200 OK, HTML content served"
    PASS_COUNT=$((PASS_COUNT + 1))
else
    error "/dashboard/ -> HTTP $DASH_CODE (expected 200 with HTML)"
    FAIL_COUNT=$((FAIL_COUNT + 1))
    FAILED_CHECKS="$FAILED_CHECKS /dashboard/"
fi
rm -f /tmp/verify-dashboard.html

# =============================================================================
# Results
# =============================================================================

echo ""

if [ "$FAIL_COUNT" -eq 0 ]; then
    echo -e "${GREEN}===============================================================${NC}"
    echo -e "${GREEN}  ✓ Distribution verified! All $TOTAL_CHECKS checks passed.               ${NC}"
    echo -e "${GREEN}===============================================================${NC}"
    echo ""
    echo -e "  Tarball: ${BOLD}$(basename "$TARBALL")${NC}"
    echo -e "  Checks:  /health (200), /driver/ (HTML), /dashboard/ (HTML)"
    echo ""
    exit 0
else
    echo -e "${RED}===============================================================${NC}"
    echo -e "${RED}  ✗ Verification FAILED: $PASS_COUNT/$TOTAL_CHECKS passed, $FAIL_COUNT failed    ${NC}"
    echo -e "${RED}===============================================================${NC}"
    echo ""
    echo -e "  Failed checks:${FAILED_CHECKS}"
    echo ""
    info "Diagnostic logs:"
    echo ""
    docker compose --project-name "$VERIFY_PROJECT" -f docker-compose.verify.yml logs --tail=30 2>/dev/null || true
    exit 1
fi
