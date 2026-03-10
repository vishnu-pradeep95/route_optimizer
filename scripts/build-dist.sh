#!/usr/bin/env bash
# =============================================================================
# Distribution Builder -- Kerala LPG Delivery Route Optimizer
# =============================================================================
#
# What this does:
#   1. Copies the project tree to a temporary staging directory (STAGE)
#   2. Strips developer-only artifacts (.git, tests, .planning, etc.)
#   3. Strips dev-mode ENVIRONMENT gate from staged main.py (production-only)
#   4. Validates zero ENVIRONMENT references remain in staged .py files
#   5. Computes SHA256 integrity manifest and injects into license_manager.py
#   6. Compiles licensing module to native .so via Cython inside Docker
#   7. Validates .so imports inside Docker (platform compatibility check)
#   8. Removes .py source from compiled modules (keeps __init__.py stub + enforcement.py)
#   9. Packages everything into a versioned tarball
#
# Pipeline ordering:
#   stage -> strip-devmode -> strip-validate -> hash -> compile -> validate-import -> clean -> package
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
#   - Docker (for Cython compilation inside python:3.12-slim container)
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
# Step 1: STAGE -- Copy project tree with exclusions
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
# Step 2: STRIP DEV-MODE -- Remove ENVIRONMENT gate from staged main.py
# ═══════════════════════════════════════════════════════════════════════════
# Distribution is production-only. The staged main.py has:
#   _is_dev_mode = os.environ.get("ENVIRONMENT") == "development"
#   _lifespan_is_dev = os.environ.get("ENVIRONMENT") == "development"
# Replace with hardcoded False so all dev branches are dead code.
# This removes the os.environ.get("ENVIRONMENT") references entirely.

header "Stripping dev-mode gate from staged main.py"

STAGED_MAIN="$STAGE/apps/kerala_delivery/api/main.py"

# Replace the _is_dev_mode check with hardcoded False
sed -i 's|_is_dev_mode = os.environ.get("ENVIRONMENT") == "development"|_is_dev_mode = False|' "$STAGED_MAIN"

# Replace the lifespan dev check with hardcoded False
sed -i 's|_lifespan_is_dev = os.environ.get("ENVIRONMENT") == "development"|_lifespan_is_dev = False|' "$STAGED_MAIN"

# Also strip comments that mention ENVIRONMENT (they leak implementation details)
sed -i '/ENVIRONMENT/d' "$STAGED_MAIN"

# Verify the replacements worked (should find _is_dev_mode = False)
grep -n "_is_dev_mode = False" "$STAGED_MAIN" || { error "Failed to strip _is_dev_mode gate"; exit 1; }
grep -n "_lifespan_is_dev = False" "$STAGED_MAIN" || { error "Failed to strip _lifespan_is_dev gate"; exit 1; }

success "Dev-mode gates hardcoded to False in staged main.py"

# ═══════════════════════════════════════════════════════════════════════════
# Step 3: STRIP VALIDATION -- Zero ENVIRONMENT references in staged .py files
# ═══════════════════════════════════════════════════════════════════════════

header "Validating dev-mode stripping"

ENV_MATCHES=$(grep -rn "ENVIRONMENT" --include="*.py" "$STAGE/" 2>/dev/null | wc -l || true)
if [ "$ENV_MATCHES" -gt 0 ]; then
    error "Found $ENV_MATCHES ENVIRONMENT references in staged .py files:"
    grep -rn "ENVIRONMENT" --include="*.py" "$STAGE/"
    error "Dev-mode code must be stripped before distribution. Aborting."
    exit 1
fi

success "No ENVIRONMENT references found in staged Python files"

# ═══════════════════════════════════════════════════════════════════════════
# Step 4: HASH -- Compute and inject integrity manifest
# ═══════════════════════════════════════════════════════════════════════════

header "Computing and injecting integrity manifest"

# Compute SHA256 of protected files (AFTER dev-mode stripping, BEFORE compilation)
MAIN_HASH=$(sha256sum "$STAGE/apps/kerala_delivery/api/main.py" | cut -d' ' -f1)
ENFORCE_HASH=$(sha256sum "$STAGE/core/licensing/enforcement.py" | cut -d' ' -f1)
INIT_HASH=$(sha256sum "$STAGE/core/licensing/__init__.py" | cut -d' ' -f1)

info "  main.py:        ${MAIN_HASH:0:16}..."
info "  enforcement.py: ${ENFORCE_HASH:0:16}..."
info "  __init__.py:    ${INIT_HASH:0:16}..."

# Build the manifest dict string
# SHA256 hex digests are [0-9a-f] only -- no sed special character risk
MANIFEST_DICT="{\"apps/kerala_delivery/api/main.py\": \"${MAIN_HASH}\", \"core/licensing/enforcement.py\": \"${ENFORCE_HASH}\", \"core/licensing/__init__.py\": \"${INIT_HASH}\"}"

# Inject into license_manager.py, replacing the empty placeholder dict
sed -i "s|_INTEGRITY_MANIFEST: dict\[str, str\] = {}|_INTEGRITY_MANIFEST: dict[str, str] = ${MANIFEST_DICT}|" \
    "$STAGE/core/licensing/license_manager.py"

# Verify injection worked
grep -q "INTEGRITY_MANIFEST.*apps/kerala_delivery" "$STAGE/core/licensing/license_manager.py" \
    || { error "Failed to inject integrity manifest"; exit 1; }

success "Integrity manifest injected into license_manager.py (3 protected files)"

# ═══════════════════════════════════════════════════════════════════════════
# Step 5: COMPILE -- Cython compilation via Docker (replaces .pyc)
# ═══════════════════════════════════════════════════════════════════════════

header "Compiling licensing module (Cython .so via Docker)"

# Build the Cython compilation image
docker build -f infra/Dockerfile.build -t kerala-cython-build . \
    || { error "Cython Docker build failed"; exit 1; }

# Extract the compiled .so using a bind-mount pattern (simpler than docker create/cp/rm)
SO_EXTRACT_DIR=$(mktemp -d)
docker run --rm -v "$SO_EXTRACT_DIR:/out" kerala-cython-build \
    sh -c 'cp /build/core/licensing/*.so /out/' \
    || { error "Failed to extract .so from container"; rm -rf "$SO_EXTRACT_DIR"; exit 1; }

# Move the .so to the staging directory
SO_BASENAME=$(ls "$SO_EXTRACT_DIR"/*.so | head -1 | xargs basename)
cp "$SO_EXTRACT_DIR/$SO_BASENAME" "$STAGE/core/licensing/$SO_BASENAME"
rm -rf "$SO_EXTRACT_DIR"

success "Compiled core/licensing/license_manager to $SO_BASENAME"

# ═══════════════════════════════════════════════════════════════════════════
# Step 6: VALIDATE -- .so imports inside Docker (BLD-02 platform check)
# ═══════════════════════════════════════════════════════════════════════════

header "Validating .so imports (Docker)"

# Mount the staged directory and test imports inside the same base image
docker run --rm -v "$STAGE:/app:ro" -w /app -e PYTHONPATH=/app python:3.12-slim \
    python -c "from core.licensing.license_manager import get_machine_fingerprint, validate_license, encode_license_key, get_license_status, set_license_state, verify_integrity; print('All imports OK')" \
    || { error ".so import validation failed inside Docker! Platform mismatch?"; exit 1; }

success "Import validation passed (.so licensing module loads in Docker)"

# ═══════════════════════════════════════════════════════════════════════════
# Step 7: CLEAN -- Remove .py source from compiled modules (keep __init__.py)
# ═══════════════════════════════════════════════════════════════════════════

rm "$STAGE/core/licensing/license_manager.py"
rm -f "$STAGE/core/licensing/license_manager.c"  # Cython intermediate, if extracted
rm -rf "$STAGE/core/licensing/__pycache__/"

# Verify enforcement.py stays as .py (Cython cannot compile async def)
[ -f "$STAGE/core/licensing/enforcement.py" ] \
    || { error "enforcement.py missing from staging -- must stay as .py"; exit 1; }

success "Removed .py source from licensing module (kept __init__.py stub and enforcement.py wrapper)"

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
# Step 8: PACKAGE -- Create tarball
# ═══════════════════════════════════════════════════════════════════════════

header "Creating tarball"

mkdir -p dist
tar czf "dist/$DIST_NAME-$VERSION.tar.gz" -C "$BUILD_DIR" "$DIST_NAME/"

SIZE=$(du -h "dist/$DIST_NAME-$VERSION.tar.gz" | cut -f1)
success "Built dist/$DIST_NAME-$VERSION.tar.gz ($SIZE)"
