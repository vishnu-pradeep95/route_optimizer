#!/usr/bin/env bash
# Entrypoint for fresh-deploy test container.
# Starts Docker daemon, then runs install.sh as the employee user.
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

pass() { echo -e "${GREEN}PASS${NC} $*"; }
fail() { echo -e "${RED}FAIL${NC} $*"; }

echo ""
echo -e "${BOLD}=== Fresh Deploy Test ===${NC}"
echo "Simulating: new employee follows DEPLOY.md on a fresh laptop"
echo ""

# ── Start Docker daemon ──────────────────────────────────────────────
echo "--- Starting Docker daemon ---"
dockerd --host=unix:///var/run/docker.sock --storage-driver=vfs &>/tmp/dockerd.log &
DOCKERD_PID=$!

# Wait for Docker to be ready
waited=0
while ! docker info &>/dev/null; do
    sleep 1
    waited=$((waited + 1))
    if [ "$waited" -ge 30 ]; then
        fail "Docker daemon did not start within 30s"
        cat /tmp/dockerd.log
        exit 1
    fi
done
pass "Docker daemon running (${waited}s)"

# ── Pre-flight checks ────────────────────────────────────────────────
echo ""
echo "--- Pre-flight checks ---"

# Check required files exist
for f in docker-compose.yml .env.example scripts/install.sh scripts/start.sh scripts/bootstrap.sh; do
    if [ -f "$f" ]; then
        pass "File exists: $f"
    else
        fail "Missing file: $f"
        exit 1
    fi
done

# Check scripts are executable
for f in scripts/install.sh scripts/start.sh scripts/bootstrap.sh; do
    if [ -x "$f" ]; then
        pass "Executable: $f"
    else
        fail "Not executable: $f (employee would get 'Permission denied')"
        exit 1
    fi
done

# Check docker-compose.yml parses
if docker compose config --quiet 2>/dev/null; then
    pass "docker-compose.yml is valid"
else
    fail "docker-compose.yml has syntax errors"
    docker compose config 2>&1 | head -20
    exit 1
fi

# ── Pre-create .env (mimics what bootstrap.sh does) ──────────────────
# bootstrap.sh generates .env BEFORE calling install.sh, so install.sh
# sees it already exists and skips the interactive prompts.
echo ""
echo "--- Generating .env (bootstrap.sh does this before install.sh) ---"

cp .env.example .env
DB_PASS=$(head -c 256 /dev/urandom | tr -dc 'A-Za-z0-9' | head -c 32 || true)
API_KEY_VAL=$(head -c 256 /dev/urandom | tr -dc 'A-Za-z0-9' | head -c 32 || true)
sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$DB_PASS|" .env
sed -i "s|^API_KEY=.*|API_KEY=$API_KEY_VAL|" .env
# Leave GOOGLE_MAPS_API_KEY as placeholder — not needed for deploy test
pass ".env generated with random credentials"

# ── Run install.sh (what bootstrap.sh delegates to) ──────────────────
echo ""
echo "--- Running install.sh (bootstrap delegates here after Docker setup) ---"
echo ""

# install.sh will:
#   1. Check prerequisites (docker, git, curl)
#   2. See .env exists, skip prompts
#   3. docker compose up -d --build
#   4. Wait for health check
./scripts/install.sh && EXIT_CODE=0 || EXIT_CODE=$?

echo ""
if [ "$EXIT_CODE" -eq 0 ]; then
    echo "--- Post-install verification ---"

    # Verify health endpoint
    if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
        pass "GET /health returns 200"
    else
        fail "GET /health not responding"
    fi

    # Dashboard is served by Vite dev server (not the API) in dev compose — skip
    # In prod compose, Caddy serves the built dashboard

    # Verify driver app serves HTML
    if curl -sf http://localhost:8000/driver/ | grep -qi "html" 2>/dev/null; then
        pass "GET /driver/ serves HTML"
    else
        fail "GET /driver/ not serving HTML"
    fi

    # Verify API endpoints
    # /api/vehicles returns 401 when API_KEY is set (auth working correctly)
    status=$(curl -so /dev/null -w '%{http_code}' "http://localhost:8000/api/vehicles" 2>/dev/null)
    if [ "$status" = "200" ] || [ "$status" = "401" ]; then
        pass "GET /api/vehicles returns ${status} (auth enforced)"
    else
        fail "GET /api/vehicles returns ${status} (expected 200 or 401)"
    fi

    # /api/routes returns 404 when no routes exist — that's expected
    status=$(curl -so /dev/null -w '%{http_code}' "http://localhost:8000/api/routes" 2>/dev/null)
    if [ "$status" = "200" ] || [ "$status" = "404" ]; then
        pass "GET /api/routes returns ${status}"
    else
        fail "GET /api/routes returns ${status} (expected 200 or 404)"
    fi

    # /api/runs should always return 200 (empty list)
    status=$(curl -so /dev/null -w '%{http_code}' "http://localhost:8000/api/runs" 2>/dev/null)
    if [ "$status" = "200" ]; then
        pass "GET /api/runs returns ${status}"
    else
        fail "GET /api/runs returns ${status} (expected 200)"
    fi

    # Check container health
    echo ""
    echo "--- Container status ---"
    docker compose ps

    echo ""
    echo -e "${GREEN}${BOLD}=== DEPLOY TEST PASSED ===${NC}"
else
    echo ""
    fail "install.sh exited with code $EXIT_CODE"
    echo ""
    echo "--- Container logs (all services) ---"
    docker compose logs --tail=50 2>/dev/null || true
    echo ""
    echo "--- Individual container logs ---"
    for svc in osrm-init db db-init osrm vroom api; do
        echo "=== $svc ==="
        docker compose logs "$svc" --tail=20 2>/dev/null || true
    done
    echo ""
    echo -e "${RED}${BOLD}=== DEPLOY TEST FAILED ===${NC}"
fi

# Cleanup
docker compose down -v 2>/dev/null || true
kill "$DOCKERD_PID" 2>/dev/null || true

exit "$EXIT_CODE"
