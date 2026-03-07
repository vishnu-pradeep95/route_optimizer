#!/usr/bin/env bash
# =============================================================================
# Test Fresh Deploy — simulates a new employee following DEPLOY.md
# =============================================================================
#
# Builds an Ubuntu container with Docker installed, copies the project in,
# and runs install.sh exactly as a new employee would after bootstrap.sh
# installs Docker.
#
# Usage:
#   ./tests/deploy/test-fresh-deploy.sh
#
# Requirements:
#   - Docker with BuildKit
#   - ~10-20 minutes (first run downloads OSRM data inside container)
#   - ~6 GB RAM available for OSRM preprocessing
#
# What this tests:
#   - All required files exist and are executable
#   - docker-compose.yml parses correctly
#   - .env generation from .env.example works
#   - All services start (DB, OSRM, VROOM, API)
#   - Health endpoint responds
#   - Dashboard and driver app are served
#   - API endpoints return 200
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
IMAGE_NAME="route-opt-deploy-test"

cd "$PROJECT_ROOT"

echo ""
echo "Building fresh-deploy test image..."
echo "This copies the project into a clean Ubuntu container with Docker."
echo ""

docker build \
    -f tests/deploy/Dockerfile.fresh-deploy \
    -t "$IMAGE_NAME" \
    .

echo ""
echo "Running deploy test (privileged — needed for Docker-in-Docker)..."
echo ""

docker rm -f deploy-test-run 2>/dev/null || true

docker run \
    --name deploy-test-run \
    --privileged \
    "$IMAGE_NAME"

EXIT_CODE=$?

if [ "$EXIT_CODE" -ne 0 ]; then
    echo ""
    echo "Container exited with code $EXIT_CODE"
    echo "Inspect with: docker logs deploy-test-run"
fi

# Cleanup
echo ""
echo "Cleaning up..."
docker rm -f deploy-test-run 2>/dev/null || true
docker rmi "$IMAGE_NAME" 2>/dev/null || true
docker builder prune -f --filter "label=com.docker.compose.project=route-opt-deploy-test" 2>/dev/null || true

exit "$EXIT_CODE"
