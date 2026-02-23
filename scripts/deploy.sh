#!/usr/bin/env bash
# =============================================================================
# Deploy Script — Kerala Delivery Route Optimizer
# =============================================================================
# One-command production deployment. Handles:
#   1. Pre-flight checks (env file, Docker, disk space)
#   2. Database backup (before any changes)
#   3. Build Docker images (API + dashboard)
#   4. Run Alembic migrations (schema updates)
#   5. Start/restart all services
#   6. Health check (wait for the stack to be ready)
#   7. Print deployment summary
#
# Usage:
#   ./scripts/deploy.sh              # Full deploy
#   ./scripts/deploy.sh --skip-backup # Skip pre-deploy backup (faster, riskier)
#   ./scripts/deploy.sh --build-only  # Build images without starting services
#
# Prerequisites:
#   - .env.production exists (copied from .env.production.example)
#   - Docker + Compose installed and running
#   - OSRM data preprocessed (data/osrm/kerala-latest.osrm exists)
#   - DNS pointing to this server (for Let's Encrypt TLS)
#
# Rollback:
#   If something goes wrong, restore from the pre-deploy backup:
#   ./scripts/backup_db.sh  # info on restore commands is printed by the script
#   docker compose -f docker-compose.prod.yml --env-file .env.production down
#   # Fix the issue, then re-deploy
# =============================================================================
set -euo pipefail

# ── Parse flags ──────────────────────────────────────────────────────────────
SKIP_BACKUP=false
BUILD_ONLY=false

for arg in "$@"; do
    case $arg in
        --skip-backup) SKIP_BACKUP=true ;;
        --build-only) BUILD_ONLY=true ;;
        --help|-h)
            echo "Usage: $0 [--skip-backup] [--build-only]"
            echo ""
            echo "  --skip-backup  Skip pre-deploy database backup (faster, riskier)"
            echo "  --build-only   Build Docker images without starting services"
            exit 0
            ;;
        *)
            echo "Unknown flag: $arg. Use --help for usage."
            exit 1
            ;;
    esac
done

# ── Configuration ────────────────────────────────────────────────────────────
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.production"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

cd "$PROJECT_DIR"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Deploy — Kerala Delivery Route Optimizer                   ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ── Pre-flight checks ────────────────────────────────────────────────────────

# 1. Check .env.production exists
if [[ ! -f "$ENV_FILE" ]]; then
    echo "❌ Missing $ENV_FILE"
    echo "   Copy the template and fill in values:"
    echo "   cp .env.production.example .env.production"
    echo "   nano .env.production"
    exit 1
fi
echo "✅ Environment file: $ENV_FILE"

# 2. Check Docker is running
if ! docker info &>/dev/null; then
    echo "❌ Docker is not running."
    echo "   WSL: sudo service docker start"
    echo "   Linux: sudo systemctl start docker"
    exit 1
fi
echo "✅ Docker is running"

# 3. Check compose file exists
if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "❌ Missing $COMPOSE_FILE"
    exit 1
fi
echo "✅ Compose file: $COMPOSE_FILE"

# 4. Check OSRM data exists
if [[ ! -f "data/osrm/kerala-latest.osrm" ]]; then
    echo "❌ OSRM data not found at data/osrm/kerala-latest.osrm"
    echo "   Run the OSRM preprocessing first. See SETUP.md."
    exit 1
fi
echo "✅ OSRM data present"

# 5. Check disk space (warn if < 5 GB free)
FREE_KB=$(df --output=avail "$PROJECT_DIR" | tail -1)
FREE_GB=$((FREE_KB / 1024 / 1024))
if [[ "$FREE_GB" -lt 5 ]]; then
    echo "⚠️  Low disk space: ${FREE_GB} GB free. Recommend ≥5 GB."
    read -rp "   Continue anyway? (y/N) " proceed
    [[ "$proceed" == "y" || "$proceed" == "Y" ]] || exit 1
fi
echo "✅ Disk space: ${FREE_GB} GB free"

# 6. Validate required env vars are set (not default values)
# shellcheck disable=SC1090
source "$ENV_FILE" 2>/dev/null || true
if [[ "${API_KEY:-}" == "CHANGE-ME"* || -z "${API_KEY:-}" ]]; then
    echo "❌ API_KEY is not set in $ENV_FILE"
    echo "   Generate one: openssl rand -hex 32"
    exit 1
fi
if [[ "${POSTGRES_PASSWORD:-}" == "CHANGE-ME"* || -z "${POSTGRES_PASSWORD:-}" ]]; then
    echo "❌ POSTGRES_PASSWORD is not set in $ENV_FILE"
    echo "   Generate one: openssl rand -base64 24"
    exit 1
fi
echo "✅ Required secrets are configured"
echo ""

# ── Pre-deploy backup ───────────────────────────────────────────────────────
# Why backup before deploy?
# Alembic migrations modify the database schema. If a migration fails halfway,
# you need a clean backup to restore from. This is the safety net.
if [[ "$SKIP_BACKUP" == "false" ]]; then
    # Only backup if the database container is already running (not first deploy)
    DB_CONTAINER="lpg-db-prod"
    if docker ps --format '{{.Names}}' | grep -q "^${DB_CONTAINER}$"; then
        echo "📦 Creating pre-deploy backup..."
        COMPOSE_FILE="$COMPOSE_FILE" ENV_FILE="$ENV_FILE" ./scripts/backup_db.sh
        echo ""
    else
        echo "ℹ️  Database not running (first deploy?) — skipping backup"
        echo ""
    fi
else
    echo "⏭️  Skipping pre-deploy backup (--skip-backup)"
    echo ""
fi

# ── Build Docker images ─────────────────────────────────────────────────────
echo "🔨 Building Docker images..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" build --pull
echo ""
echo "✅ Images built"
echo ""

if [[ "$BUILD_ONLY" == "true" ]]; then
    echo "🏁 Build complete (--build-only). Exiting."
    exit 0
fi

# ── Start infrastructure services first ──────────────────────────────────────
# Why start db+osrm+vroom before the API?
# The API needs a healthy database to run migrations. OSRM and VROOM need
# time to load data. Starting them first and waiting for health checks
# prevents migration failures from connection timeouts.
echo "🚀 Starting infrastructure services (db, osrm, vroom)..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d db osrm vroom

# Wait for the database to be healthy
echo "⏳ Waiting for database to be healthy..."
TIMEOUT=60
ELAPSED=0
while ! docker exec lpg-db-prod pg_isready -U "${POSTGRES_USER:-routing}" -d "${POSTGRES_DB:-routing_opt}" &>/dev/null; do
    sleep 2
    ELAPSED=$((ELAPSED + 2))
    if [[ "$ELAPSED" -ge "$TIMEOUT" ]]; then
        echo "❌ Database did not become healthy within ${TIMEOUT}s"
        echo "   Check logs: docker compose -f $COMPOSE_FILE logs db"
        exit 1
    fi
done
echo "✅ Database is healthy"

# ── Run Alembic migrations ──────────────────────────────────────────────────
# Why run migrations in a one-shot container instead of on API startup?
# - Migrations should run ONCE, not once-per-worker (uvicorn spawns 2 workers)
# - If a migration fails, the API shouldn't start with an incompatible schema
# - Separating migration from startup follows 12-factor app principles
# See: https://12factor.net/admin-processes
echo "📐 Running database migrations..."
# Why run migrations as a separate one-shot container?
# - Alembic should run ONCE, not once-per-worker (uvicorn spawns 2 workers)
# - If a migration fails, the API shouldn't start with an incompatible schema
# - Separating migration from startup follows 12-factor app principles
# DATABASE_URL is already in the API container's environment from compose,
# so we don't need to pass it again here.
# See: https://12factor.net/admin-processes
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" run --rm \
    api \
    alembic upgrade head

echo "✅ Migrations complete"
echo ""

# ── Start all services ──────────────────────────────────────────────────────
echo "🚀 Starting all services..."
docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d
echo ""

# ── Health check ─────────────────────────────────────────────────────────────
# Wait for the API and Caddy to be fully ready before declaring success.
echo "⏳ Waiting for services to be ready..."
TIMEOUT=90
ELAPSED=0

# Determine health check URL.
# Why different schemes? Caddy with "localhost" auto-issues a local TLS cert
# and redirects HTTP → HTTPS. With a real domain, Let's Encrypt provides the
# cert. We use -k (insecure) for localhost to accept the self-signed cert.
DOMAIN="${DOMAIN:-localhost}"
CURL_FLAGS="--max-time 5"
if [[ "$DOMAIN" == "localhost" ]]; then
    HEALTH_URL="https://localhost/health"
    CURL_FLAGS="$CURL_FLAGS -k"  # Accept self-signed cert for local testing
else
    HEALTH_URL="https://${DOMAIN}/health"
fi

while true; do
    # Try to hit the health endpoint through Caddy
    HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" $CURL_FLAGS "$HEALTH_URL" 2>/dev/null || echo "000")
    if [[ "$HTTP_STATUS" == "200" ]]; then
        break
    fi
    sleep 3
    ELAPSED=$((ELAPSED + 3))
    if [[ "$ELAPSED" -ge "$TIMEOUT" ]]; then
        echo "⚠️  Health check at $HEALTH_URL did not return 200 within ${TIMEOUT}s"
        echo "   Status: $HTTP_STATUS"
        echo "   The services may still be starting. Check logs:"
        echo "   docker compose -f $COMPOSE_FILE logs --tail=50"
        break
    fi
done

if [[ "$HTTP_STATUS" == "200" ]]; then
    echo "✅ Health check passed: $HEALTH_URL → 200 OK"
fi

# ── Deployment summary ──────────────────────────────────────────────────────
SCHEME="https"
[[ "$DOMAIN" == "localhost" ]] && SCHEME="http"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  🎉 Deployment complete!"
echo ""
echo "  Dashboard:  ${SCHEME}://${DOMAIN}/"
echo "  Driver App: ${SCHEME}://${DOMAIN}/driver/"
echo "  API Docs:   ${SCHEME}://${DOMAIN}/docs  (disabled in production)"
echo "  Health:     ${SCHEME}://${DOMAIN}/health"
echo ""
echo "  Useful commands:"
echo "    Logs:     docker compose -f $COMPOSE_FILE logs -f --tail=50"
echo "    Status:   docker compose -f $COMPOSE_FILE ps"
echo "    Stop:     docker compose -f $COMPOSE_FILE --env-file $ENV_FILE down"
echo "    Backup:   ./scripts/backup_db.sh"
echo "    Restart:  docker compose -f $COMPOSE_FILE --env-file $ENV_FILE restart"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
