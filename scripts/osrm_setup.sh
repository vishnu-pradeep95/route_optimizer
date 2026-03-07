#!/usr/bin/env bash
# =============================================================================
# OSRM Setup Script — Download Kerala OSM data & preprocess for routing
# =============================================================================
#
# What this does:
#   1. Downloads Kerala OpenStreetMap extract (~150 MB PBF file)
#   2. Runs OSRM preprocessing pipeline (extract → partition → customize)
#   3. Produces .osrm files that the OSRM Docker container can serve
#
# Prerequisites:
#   - Docker must be running: `sudo service docker start` (WSL2)
#   - ~2 GB free disk space (PBF + processed files)
#   - Internet connection for initial download
#
# Usage:
#   chmod +x scripts/osrm_setup.sh
#   ./scripts/osrm_setup.sh
#
# Duration: ~5-10 minutes depending on machine specs
#
# Why MLD algorithm?
#   Multi-Level Dijkstra (MLD) is the recommended OSRM preprocessing mode.
#   It's faster to preprocess than Contraction Hierarchies (CH) and supports
#   flexible routing profiles. Trade-off: slightly slower queries, but still
#   sub-millisecond for our use case.
#   See: https://github.com/Project-OSRM/osrm-backend/wiki/Running-OSRM
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="$PROJECT_ROOT/data/osrm"

# Kerala OSM extract — updated regularly by OpenStreetMap France
KERALA_PBF_URL="https://download.openstreetmap.fr/extracts/asia/india/kerala.osm.pbf"
PBF_FILE="$DATA_DIR/kerala-latest.osm.pbf"

# OSRM Docker image — same version as docker-compose.yml
OSRM_IMAGE="osrm/osrm-backend:v5.25.0"

# Car profile is the closest default to a three-wheeler.
# For Phase 2+, we'll create a custom Lua profile with:
#   - 40 km/h urban speed cap
#   - 50 km/h suburban cap
#   - Weight/turn restrictions for narrow Kerala roads
# For now, the generic car profile + our 1.3× safety multiplier
# in config.py compensates for the speed overestimate.
OSRM_PROFILE="car"

echo "============================================="
echo "OSRM Kerala Setup"
echo "============================================="
echo "Data directory: $DATA_DIR"
echo ""

# ─── Step 1: Download Kerala OSM extract ──────────────────────────────
if [ -f "$PBF_FILE" ]; then
    echo "✓ Kerala PBF already exists at $PBF_FILE"
    echo "  To re-download, delete the file and run again."
else
    echo "→ Downloading Kerala OSM extract (~150 MB)..."
    echo "  Source: $KERALA_PBF_URL"
    curl -L -o "$PBF_FILE" "$KERALA_PBF_URL"
    echo "✓ Download complete: $(du -h "$PBF_FILE" | cut -f1)"
fi

echo ""

# ─── Step 2: OSRM Extract ────────────────────────────────────────────
# Parses the PBF and extracts road network graph.
# Creates: .osrm, .osrm.ebg, .osrm.nbg, etc.
echo "→ Step 2/4: Extracting road network (osrm-extract)..."
docker run --rm -t \
    -v "$DATA_DIR:/data" \
    "$OSRM_IMAGE" \
    osrm-extract \
    -p /opt/car.lua \
    /data/kerala-latest.osm.pbf

echo "✓ Extract complete"
echo ""

# ─── Step 3: OSRM Partition ──────────────────────────────────────────
# Partitions the graph for MLD algorithm.
# This is what makes queries fast — precomputes multi-level structure.
echo "→ Step 3/4: Partitioning graph for MLD (osrm-partition)..."
docker run --rm -t \
    -v "$DATA_DIR:/data" \
    "$OSRM_IMAGE" \
    osrm-partition \
    /data/kerala-latest.osrm

echo "✓ Partition complete"
echo ""

# ─── Step 4: OSRM Customize ──────────────────────────────────────────
# Computes edge weights based on the speed profile.
# After this step, OSRM is ready to serve queries.
echo "→ Step 4/4: Customizing edge weights (osrm-customize)..."
docker run --rm -t \
    -v "$DATA_DIR:/data" \
    "$OSRM_IMAGE" \
    osrm-customize \
    /data/kerala-latest.osrm

echo "✓ Customize complete"
echo ""

# ─── Done ─────────────────────────────────────────────────────────────
echo "============================================="
echo "OSRM setup complete!"
echo "============================================="
echo ""
echo "Processed files in: $DATA_DIR"
ls -lh "$DATA_DIR" | head -20
echo ""
echo "Next steps:"
echo "  1. Start the stack:  docker compose up -d"
echo "  2. Test OSRM:        curl 'http://localhost:5000/route/v1/driving/76.2846,9.9716;76.2996,9.9816'"
echo "  3. Run integration tests: pytest tests/integration/ -v"
echo ""
echo "To rebuild after an OSM data update:"
echo "  rm $PBF_FILE"
echo "  ./scripts/osrm_setup.sh"
