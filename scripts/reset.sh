#!/usr/bin/env bash
# =============================================================================
# Reset Script — Kerala LPG Delivery Route Optimizer
# =============================================================================
#
# What this does:
#   Cleans up the project for a fresh deployment test. Removes build artifacts,
#   Docker containers/volumes/images, environment files, and caches.
#
# Usage:
#   ./scripts/reset.sh              # Interactive — prompts before each step
#   ./scripts/reset.sh --all        # Nuclear — removes everything (still prompts once)
#   ./scripts/reset.sh --dry-run    # Show what would be removed without doing it
#
# After reset, redeploy with:
#   ./scripts/install.sh            # Development
#   ./scripts/deploy.sh             # Production
#
# What is NEVER touched:
#   - .git/                         (version history)
#   - scripts/                      (this script and others)
#   - source code                   (apps/, core/, infra/, etc.)
# =============================================================================

set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════════
# Color helpers (matches install.sh / bootstrap.sh)
# ═══════════════════════════════════════════════════════════════════════════

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
skip()    { echo -e "  ${YELLOW}skip${NC} $*"; }
dry()     { echo -e "  ${BLUE}would${NC} $*"; }

# ═══════════════════════════════════════════════════════════════════════════
# Parse arguments
# ═══════════════════════════════════════════════════════════════════════════

MODE="interactive"  # interactive | all | dry-run

for arg in "$@"; do
    case "$arg" in
        --all)     MODE="all" ;;
        --dry-run) MODE="dry-run" ;;
        --help|-h)
            echo "Usage: ./scripts/reset.sh [--all | --dry-run]"
            echo ""
            echo "  (no flags)   Interactive — prompts before each step"
            echo "  --all        Remove everything (prompts once for confirmation)"
            echo "  --dry-run    Show what would be removed without doing it"
            exit 0
            ;;
        *)
            error "Unknown option: $arg"
            echo "Run with --help for usage."
            exit 1
            ;;
    esac
done

# ═══════════════════════════════════════════════════════════════════════════
# Ensure we're in the project root
# ═══════════════════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

if [ ! -f "docker-compose.yml" ]; then
    error "Not in project root. Run from: $PROJECT_ROOT"
    exit 1
fi

# ═══════════════════════════════════════════════════════════════════════════
# Confirmation helper
# ═══════════════════════════════════════════════════════════════════════════

# ask PROMPT — returns 0 (yes) or 1 (no)
# In --all mode: always yes. In --dry-run mode: always no.
ask() {
    if [ "$MODE" = "dry-run" ]; then
        return 1
    fi
    if [ "$MODE" = "all" ]; then
        return 0
    fi
    local response
    read -rp "  $1 [y/N] " response
    [[ "$response" =~ ^[Yy] ]]
}

# ═══════════════════════════════════════════════════════════════════════════
# Nuclear mode: single upfront confirmation
# ═══════════════════════════════════════════════════════════════════════════

if [ "$MODE" = "all" ]; then
    echo ""
    echo -e "${RED}${BOLD}  WARNING: This will remove EVERYTHING except source code and git history.${NC}"
    echo ""
    echo "  This includes:"
    echo "    - All Docker containers, volumes, and images"
    echo "    - Database (all orders, routes, delivery history)"
    echo "    - OSRM map data (~1.2 GB, takes 15+ min to rebuild)"
    echo "    - Geocode cache, backups, .env files"
    echo "    - Python venv, node_modules, build artifacts"
    echo ""
    read -rp "  Type 'RESET' to confirm: " confirm
    if [ "$confirm" != "RESET" ]; then
        info "Aborted."
        exit 0
    fi
    echo ""
fi

if [ "$MODE" = "dry-run" ]; then
    echo ""
    info "Dry run — showing what would be removed (no changes will be made)"
fi

# ═══════════════════════════════════════════════════════════════════════════
# Track what was cleaned
# ═══════════════════════════════════════════════════════════════════════════

CLEANED=()

# ═══════════════════════════════════════════════════════════════════════════
# Step 1: Docker containers + volumes
# ═══════════════════════════════════════════════════════════════════════════

header "Step 1/6: Docker containers & volumes"

COMPOSE_FILES=(-f docker-compose.yml)
# Use prod compose only if its env file exists (avoids interpolation errors)
if [ -f "docker-compose.prod.yml" ] && [ -f ".env.production" ]; then
    COMPOSE_FILES=(-f docker-compose.prod.yml --env-file .env.production)
fi

if docker info &>/dev/null 2>&1; then
    # Check if any project containers are running
    RUNNING=$(docker compose "${COMPOSE_FILES[@]}" ps -q 2>/dev/null | wc -l || echo "0")
    RUNNING="${RUNNING// /}"  # trim whitespace

    if [ "$RUNNING" -gt 0 ] || [ "$MODE" = "all" ]; then
        info "Stop containers and remove volumes (database, certs, dashboard assets)?"
        if [ "$MODE" = "dry-run" ]; then
            dry "docker compose down -v (removes containers + named volumes)"
        elif ask "Remove containers + volumes? (destroys database)"; then
            docker compose "${COMPOSE_FILES[@]}" down -v 2>/dev/null || true
            success "Containers stopped, volumes removed"
            CLEANED+=("docker-containers" "docker-volumes")
        else
            # Still stop containers, just keep volumes
            if ask "Stop containers but KEEP volumes (preserve database)?"; then
                docker compose "${COMPOSE_FILES[@]}" down 2>/dev/null || true
                success "Containers stopped, volumes preserved"
                CLEANED+=("docker-containers")
            else
                skip "Docker containers"
            fi
        fi
    else
        success "No running containers"
    fi
else
    warn "Docker not running — skipping container cleanup"
fi

# ═══════════════════════════════════════════════════════════════════════════
# Step 2: Docker images + build cache
# ═══════════════════════════════════════════════════════════════════════════

header "Step 2/6: Docker images & build cache"

if docker info &>/dev/null 2>&1; then
    IMAGE_COUNT=$(docker images --filter "reference=routing_opt*" -q 2>/dev/null | wc -l || echo "0")
    CACHE_SIZE=$(docker system df --format '{{.Size}}' 2>/dev/null | tail -1 || echo "unknown")

    info "Project images: $IMAGE_COUNT, Build cache: $CACHE_SIZE"

    if [ "$MODE" = "dry-run" ]; then
        dry "remove project Docker images"
        dry "prune Docker build cache"
    elif ask "Remove Docker images and build cache?"; then
        docker images --filter "reference=routing_opt*" -q 2>/dev/null | xargs -r docker rmi -f 2>/dev/null || true
        docker builder prune -af 2>/dev/null || true
        docker image prune -f 2>/dev/null || true
        success "Docker images and build cache removed"
        CLEANED+=("docker-images")
    else
        skip "Docker images"
    fi
else
    warn "Docker not running — skipping image cleanup"
fi

# ═══════════════════════════════════════════════════════════════════════════
# Step 3: OSRM data (biggest item, optional)
# ═══════════════════════════════════════════════════════════════════════════

header "Step 3/6: OSRM map data"

if [ -d "data/osrm" ]; then
    OSRM_SIZE=$(du -sh data/osrm 2>/dev/null | cut -f1 || echo "unknown")
    warn "data/osrm/ is $OSRM_SIZE — takes 15+ minutes to rebuild"

    if [ "$MODE" = "dry-run" ]; then
        dry "remove data/osrm/ ($OSRM_SIZE)"
    elif ask "Remove OSRM data? ($OSRM_SIZE, slow to rebuild)"; then
        rm -rf data/osrm
        success "OSRM data removed"
        CLEANED+=("osrm-data")
    else
        skip "OSRM data (preserved)"
    fi
else
    success "No OSRM data found"
fi

# ═══════════════════════════════════════════════════════════════════════════
# Step 4: Application data (geocode cache, backups)
# ═══════════════════════════════════════════════════════════════════════════

header "Step 4/6: Application data"

# Geocode cache
if [ -d "data/geocode_cache" ] && [ "$(ls -A data/geocode_cache 2>/dev/null)" ]; then
    CACHE_FILES=$(find data/geocode_cache -type f 2>/dev/null | wc -l)
    info "Geocode cache: $CACHE_FILES file(s)"
    if [ "$MODE" = "dry-run" ]; then
        dry "remove data/geocode_cache/"
    elif ask "Remove geocode cache? (accumulated address lookups)"; then
        rm -rf data/geocode_cache
        success "Geocode cache removed"
        CLEANED+=("geocode-cache")
    else
        skip "Geocode cache (preserved)"
    fi
else
    success "No geocode cache"
fi

# Backups
if [ -d "backups" ] && [ "$(find backups -name '*.sql.gz' 2>/dev/null)" ]; then
    BACKUP_COUNT=$(find backups -name '*.sql.gz' 2>/dev/null | wc -l)
    BACKUP_SIZE=$(du -sh backups 2>/dev/null | cut -f1 || echo "unknown")
    warn "Found $BACKUP_COUNT database backup(s) ($BACKUP_SIZE)"
    if [ "$MODE" = "dry-run" ]; then
        dry "remove backups/*.sql.gz"
    elif ask "Remove database backups? (cannot be recovered)"; then
        find backups -name '*.sql.gz' -delete 2>/dev/null
        success "Backups removed"
        CLEANED+=("backups")
    else
        skip "Backups (preserved)"
    fi
else
    success "No backups found"
fi

# ═══════════════════════════════════════════════════════════════════════════
# Step 5: Environment files
# ═══════════════════════════════════════════════════════════════════════════

header "Step 5/6: Environment files"

ENV_FILES=()
[ -f ".env" ] && ENV_FILES+=(".env")
[ -f ".env.production" ] && ENV_FILES+=(".env.production")

if [ ${#ENV_FILES[@]} -gt 0 ]; then
    info "Found: ${ENV_FILES[*]}"
    if [ "$MODE" = "dry-run" ]; then
        dry "remove ${ENV_FILES[*]}"
    elif ask "Remove environment files? (credentials will need to be regenerated)"; then
        rm -f "${ENV_FILES[@]}"
        success "Environment files removed"
        CLEANED+=("env-files")
    else
        skip "Environment files (preserved)"
    fi
else
    success "No environment files"
fi

# Bootstrap resume marker
rm -f .bootstrap_resume 2>/dev/null

# ═══════════════════════════════════════════════════════════════════════════
# Step 6: Build artifacts & caches
# ═══════════════════════════════════════════════════════════════════════════

header "Step 6/6: Build artifacts & caches"

# These are always safe to remove — no prompt needed (except in dry-run)
ARTIFACTS=()

# Python venv
if [ -d ".venv" ]; then
    VENV_SIZE=$(du -sh .venv 2>/dev/null | cut -f1 || echo "unknown")
    ARTIFACTS+=(".venv ($VENV_SIZE)")
fi

# node_modules
NODE_MODULES="apps/kerala_delivery/dashboard/node_modules"
if [ -d "$NODE_MODULES" ]; then
    NM_SIZE=$(du -sh "$NODE_MODULES" 2>/dev/null | cut -f1 || echo "unknown")
    ARTIFACTS+=("node_modules ($NM_SIZE)")
fi

# Dashboard dist
DIST_DIR="apps/kerala_delivery/dashboard/dist"
[ -d "$DIST_DIR" ] && ARTIFACTS+=("dashboard/dist")

# __pycache__
PYCACHE_COUNT=$(find . -type d -name __pycache__ -not -path './.git/*' 2>/dev/null | wc -l)
[ "$PYCACHE_COUNT" -gt 0 ] && ARTIFACTS+=("$PYCACHE_COUNT __pycache__ dirs")

# .pytest_cache
[ -d ".pytest_cache" ] && ARTIFACTS+=(".pytest_cache")

if [ ${#ARTIFACTS[@]} -gt 0 ]; then
    for a in "${ARTIFACTS[@]}"; do
        info "$a"
    done

    if [ "$MODE" = "dry-run" ]; then
        for a in "${ARTIFACTS[@]}"; do
            dry "remove $a"
        done
    else
        # Build artifacts are always safe — remove without individual prompts
        if ask "Remove build artifacts and caches?"; then
            [ -d ".venv" ] && rm -rf .venv && success "Removed .venv"
            [ -d "$NODE_MODULES" ] && rm -rf "$NODE_MODULES" && success "Removed node_modules"
            [ -d "$DIST_DIR" ] && rm -rf "$DIST_DIR" && success "Removed dashboard/dist"
            find . -type d -name __pycache__ -not -path './.git/*' -exec rm -rf {} + 2>/dev/null && success "Removed __pycache__ dirs"
            [ -d ".pytest_cache" ] && rm -rf .pytest_cache && success "Removed .pytest_cache"
            CLEANED+=("build-artifacts")
        else
            skip "Build artifacts"
        fi
    fi
else
    success "No build artifacts found"
fi

# ═══════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════

echo ""
echo "─────────────────────────────────────────"

if [ "$MODE" = "dry-run" ]; then
    echo -e "${BLUE}Dry run complete — no changes were made.${NC}"
    echo "Run without --dry-run to perform the reset."
elif [ ${#CLEANED[@]} -eq 0 ]; then
    info "Nothing was removed."
else
    echo -e "${GREEN}${BOLD}Reset complete.${NC} Cleaned: ${CLEANED[*]}"
    echo ""
    echo -e "  ${BOLD}To redeploy from scratch:${NC}"
    echo "    ./scripts/install.sh            # Development"
    echo "    ./scripts/deploy.sh             # Production"
fi
echo ""
