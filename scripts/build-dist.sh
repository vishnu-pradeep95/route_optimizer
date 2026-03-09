#!/usr/bin/env bash
# =============================================================================
# Distribution Builder — Kerala LPG Delivery Route Optimizer
# =============================================================================
#
# What this does:
#   1. Copies the project tree to a temporary staging directory
#   2. Strips developer-only artifacts (.git, tests, .planning, etc.)
#   3. Compiles the licensing module (core/licensing/) to .pyc bytecode
#   4. Removes the .py source from the licensing module only
#   5. Validates the .pyc modules import correctly
#   6. Packages everything into a versioned tarball
#
# Usage:
#   ./scripts/build-dist.sh v1.3
#
# Output:
#   dist/kerala-delivery-v1.3.tar.gz
#
# The customer extracts the tarball and runs bootstrap.sh to install.
#
# Requirements:
#   - Python 3.12 (must match Docker image version for .pyc compatibility)
#   - rsync (for selective file copy with exclusions)
# =============================================================================

set -euo pipefail

VERSION="${1:?Usage: $0 <version>  (e.g., v1.3)}"

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

info()    { echo -e "${BLUE}→${NC} $*"; }
success() { echo -e "${GREEN}✓${NC} $*"; }
warn()    { echo -e "${YELLOW}⚠${NC} $*"; }
error()   { echo -e "${RED}✗${NC} $*" >&2; }
header()  { echo -e "\n${BOLD}$*${NC}"; echo "─────────────────────────────────────────"; }

# ═══════════════════════════════════════════════════════════════════════════
# Staging directory with trap cleanup
# ═══════════════════════════════════════════════════════════════════════════

BUILD_DIR=$(mktemp -d)
trap 'rm -rf "$BUILD_DIR"' EXIT

DIST_NAME="kerala-delivery"
STAGE="$BUILD_DIR/$DIST_NAME"

header "Building distribution: $DIST_NAME-$VERSION"

# ═══════════════════════════════════════════════════════════════════════════
# Copy project tree with exclusions
# ═══════════════════════════════════════════════════════════════════════════

info "Copying project tree to staging directory..."

# NOTE: ATTRIBUTION.md (third-party license obligations) is deliberately included
# in the distribution. It is NOT in the exclude list and will be copied automatically.
rsync -a \
  --exclude='.git/' \
  --exclude='.github/' \
  --exclude='.claude/' \
  --exclude='.planning/' \
  --exclude='.vscode/' \
  --exclude='.playwright-mcp/' \
  --exclude='.pytest_cache/' \
  --exclude='.venv/' \
  --exclude='.agents/' \
  --exclude='tests/' \
  --exclude='plan/' \
  --exclude='gsd-template/' \
  --exclude='node_modules/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='*.pyo' \
  --exclude='dist/' \
  --exclude='backups/' \
  --exclude='data/' \
  --exclude='tools/' \
  --exclude='.env' \
  --exclude='.env.production' \
  --exclude='.env.production.example' \
  --exclude='docker-compose.prod.yml' \
  --exclude='scripts/generate_license.py' \
  --exclude='CLAUDE.md' \
  --exclude='GUIDE.md' \
  --exclude='pytest.ini' \
  --exclude='.gitignore' \
  ./ "$STAGE/"

success "Project tree copied"

# ═══════════════════════════════════════════════════════════════════════════
# Include license.key if present
# ═══════════════════════════════════════════════════════════════════════════

if [ -f "license.key" ]; then
  cp license.key "$STAGE/"
  info "Included license.key in distribution"
fi

# ═══════════════════════════════════════════════════════════════════════════
# Compile licensing module to .pyc (legacy placement)
# ═══════════════════════════════════════════════════════════════════════════

header "Compiling licensing module"

# -b = legacy placement (same directory, NOT __pycache__/)
# -f = force recompile even if .pyc exists
# -q = quiet output
# CRITICAL: -b is mandatory. Without it, .pyc goes to __pycache__/ and
# will NOT import when .py is removed. See 18-RESEARCH.md Pitfall 1.
python3 -m compileall -b -f -q "$STAGE/core/licensing/"

success "Compiled core/licensing/ to .pyc (legacy placement)"

# ═══════════════════════════════════════════════════════════════════════════
# Remove .py source from licensing module ONLY
# ═══════════════════════════════════════════════════════════════════════════

rm "$STAGE/core/licensing/__init__.py"
rm "$STAGE/core/licensing/license_manager.py"
rm -rf "$STAGE/core/licensing/__pycache__/"

success "Removed .py source from licensing module"

# ═══════════════════════════════════════════════════════════════════════════
# Import validation test against STAGED directory
# ═══════════════════════════════════════════════════════════════════════════

header "Validating .pyc imports"

# Test that both .pyc files load correctly from the staged directory.
# Uses "import core.licensing; import core.licensing.license_manager"
# because __init__.py does NOT re-export validate_license.
# See 18-RESEARCH.md Pitfall 3.
PYTHONPATH="$STAGE" python3 -c "import core.licensing; import core.licensing.license_manager" \
  || { error "Import validation failed! .pyc modules do not load."; exit 1; }

success "Import validation passed (.pyc-only licensing module loads)"

# ═══════════════════════════════════════════════════════════════════════════
# Warn about placeholder API key in .env.example
# ═══════════════════════════════════════════════════════════════════════════

if [ -f "$STAGE/.env.example" ]; then
  if grep -qE 'GOOGLE_MAPS_API_KEY\s*=\s*$' "$STAGE/.env.example" || \
     grep -qE 'GOOGLE_MAPS_API_KEY\s*=\s*your' "$STAGE/.env.example"; then
    warn ".env.example has placeholder GOOGLE_MAPS_API_KEY -- update before customer delivery"
  fi
fi

# ═══════════════════════════════════════════════════════════════════════════
# Create tarball
# ═══════════════════════════════════════════════════════════════════════════

header "Creating tarball"

mkdir -p dist
tar czf "dist/$DIST_NAME-$VERSION.tar.gz" -C "$BUILD_DIR" "$DIST_NAME/"

SIZE=$(du -h "dist/$DIST_NAME-$VERSION.tar.gz" | cut -f1)
success "Built dist/$DIST_NAME-$VERSION.tar.gz ($SIZE)"
