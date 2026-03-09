#!/usr/bin/env bash
# =============================================================================
# Bootstrap Installer — Kerala LPG Delivery Route Optimizer
# =============================================================================
#
# What this does:
#   1. Validates WSL2 environment (version, filesystem, memory)
#   2. Installs Docker CE if not present
#   3. Configures Docker auto-start via systemd
#   4. Generates .env with secure credentials
#   5. Delegates to install.sh for Docker Compose orchestration
#
# Usage:
#   cd ~/routing_opt
#   ./bootstrap.sh
#
# For non-technical office staff: this is the ONLY command needed.
# Everything else is automatic.
#
# Two-phase flow:
#   First run:  Installs Docker, asks user to restart WSL terminal
#   Second run: Resumes automatically, sets up .env, starts services
#
# If Docker is already installed: skips to .env + install.sh immediately.
# =============================================================================

set -euo pipefail

# ═══════════════════════════════════════════════════════════════════════════
# Color helpers (matches scripts/install.sh for visual consistency)
# ═══════════════════════════════════════════════════════════════════════════

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
# Spinner helper
# ═══════════════════════════════════════════════════════════════════════════

spin_while() {
    local pid=$1
    local msg="${2:-Working...}"
    local chars='|/-\'
    local i=0
    while kill -0 "$pid" 2>/dev/null; do
        i=$(( (i + 1) % 4 ))
        printf "\r  %s %s  " "${chars:$i:1}" "$msg"
        sleep 0.2
    done
    printf "\r%s\r" "$(printf ' %.0s' {1..60})"
    wait "$pid"
    return $?
}

# ═══════════════════════════════════════════════════════════════════════════
# Ensure we're running from the project root
# ═══════════════════════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# ═══════════════════════════════════════════════════════════════════════════
# Resume check (two-phase flow)
# ═══════════════════════════════════════════════════════════════════════════

MARKER_FILE=".bootstrap_resume"
FRESH_DOCKER_INSTALL=false

if [ -f "$MARKER_FILE" ]; then
    rm "$MARKER_FILE"
    info "Resuming installation after restart..."
    echo ""

    # Verify docker group membership took effect
    if ! groups | grep -q docker; then
        error "Docker group not applied. Close ALL Ubuntu windows, then reopen and re-run."
        echo ""
        echo "  1. Type 'exit' or close this window"
        echo "  2. Open Ubuntu again from the Start menu"
        echo "  3. Run:"
        echo "     cd $(pwd)"
        echo "     ./bootstrap.sh"
        exit 1
    fi

    success "Docker group membership confirmed"

    # Fall through to .env generation and install.sh delegation
else
    # ═══════════════════════════════════════════════════════════════════════
    # Guard: WSL check
    # ═══════════════════════════════════════════════════════════════════════

    if ! grep -qi microsoft /proc/version 2>/dev/null; then
        error "This installer is designed for Windows Subsystem for Linux (WSL)."
        echo ""
        echo "  For other Linux systems, use ./scripts/install.sh directly."
        exit 1
    fi

    # ═══════════════════════════════════════════════════════════════════════
    # Guard: WSL version (INST-05)
    # ═══════════════════════════════════════════════════════════════════════

    if ! uname -r | grep -qi "microsoft.*standard"; then
        error "WSL version 1 detected. WSL version 2 is required."
        echo ""
        echo "  To upgrade to WSL2:"
        echo "  1. Open PowerShell as Administrator"
        echo "  2. Run: wsl --set-version Ubuntu 2"
        echo "  3. Wait for conversion to complete"
        echo "  4. Re-open Ubuntu and run this script again"
        exit 1
    fi

    success "WSL2 detected"

    # ═══════════════════════════════════════════════════════════════════════
    # Guard: Windows filesystem (INST-03)
    # ═══════════════════════════════════════════════════════════════════════

    case "$(pwd)" in
        /mnt/[a-z]/*)
            error "You are running from the Windows filesystem ($(pwd))"
            echo ""
            echo "  This causes severe performance problems with Docker."
            echo "  Please clone the project in your Linux home directory:"
            echo ""
            echo "  1. cd ~"
            echo "  2. Copy or clone the project folder to here"
            echo "  3. cd routing_opt"
            echo "  4. ./bootstrap.sh"
            exit 1
            ;;
    esac

    success "Running from Linux filesystem"

    # ═══════════════════════════════════════════════════════════════════════
    # Guard: RAM warning (INST-04)
    # ═══════════════════════════════════════════════════════════════════════

    TOTAL_RAM_MB=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
    if [ "$TOTAL_RAM_MB" -lt 5120 ]; then
        warn "Low memory: ${TOTAL_RAM_MB} MB allocated to WSL (5120 MB recommended)"
        echo ""
        echo "  OSRM needs about 4-5 GB RAM to process Kerala map data."
        echo "  To increase WSL memory:"
        echo ""
        echo "  1. Open Notepad on Windows"
        echo "  2. Type these two lines:"
        echo "     [wsl2]"
        echo "     memory=6GB"
        echo "  3. Save as: C:\\Users\\YourName\\.wslconfig"
        echo "     (replace YourName with your Windows username)"
        echo "  4. Open PowerShell and run: wsl --shutdown"
        echo "  5. Re-open Ubuntu and try again"
        echo ""
    else
        success "Memory: ${TOTAL_RAM_MB} MB available"
    fi

    # ═══════════════════════════════════════════════════════════════════════
    # Docker check + install (INST-01)
    # ═══════════════════════════════════════════════════════════════════════

    if command -v docker &>/dev/null && groups | grep -q docker; then
        success "Docker already installed"
        # Skip to .env generation (below)
    else
        FRESH_DOCKER_INSTALL=true

        header "Step 1/4: Installing Docker CE"

        # Remove conflicting packages silently
        info "Removing old Docker packages (if any)..."
        for pkg in docker.io docker-doc docker-compose podman-docker containerd runc; do
            sudo apt-get remove -y "$pkg" 2>/dev/null || true
        done

        # Install prerequisites
        info "Installing prerequisites..."
        sudo apt-get update -qq 2>/dev/null
        sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
            ca-certificates curl gnupg 2>/dev/null

        # Add Docker's official GPG key
        info "Adding Docker repository..."
        sudo install -m 0755 -d /etc/apt/keyrings
        sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
            -o /etc/apt/keyrings/docker.asc
        sudo chmod a+r /etc/apt/keyrings/docker.asc

        # Add Docker apt repository (one-line .list format)
        echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu \
$(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
            sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

        # Update and install Docker CE
        sudo apt-get update -qq 2>/dev/null
        info "Installing Docker CE (this may take a few minutes)..."
        sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
            docker-ce docker-ce-cli containerd.io \
            docker-buildx-plugin docker-compose-plugin 2>/dev/null &
        spin_while $! "Installing Docker CE..."

        success "Docker CE installed"

        # ═══════════════════════════════════════════════════════════════════
        # Docker auto-start (INST-02)
        # ═══════════════════════════════════════════════════════════════════

        header "Step 2/4: Configuring Docker auto-start"

        # Ensure systemd is enabled in wsl.conf
        if grep -q "systemd=true" /etc/wsl.conf 2>/dev/null; then
            success "systemd already enabled in wsl.conf"
        elif grep -q "^\[boot\]" /etc/wsl.conf 2>/dev/null; then
            # [boot] section exists, add systemd=true after it
            sudo sed -i '/^\[boot\]/a systemd=true' /etc/wsl.conf
            success "systemd enabled in wsl.conf"
        else
            # No [boot] section, append it
            echo "" | sudo tee -a /etc/wsl.conf > /dev/null
            echo "[boot]" | sudo tee -a /etc/wsl.conf > /dev/null
            echo "systemd=true" | sudo tee -a /etc/wsl.conf > /dev/null
            success "systemd enabled in wsl.conf"
        fi

        # Enable Docker service via systemd
        sudo systemctl enable docker.service 2>/dev/null || true
        sudo systemctl enable containerd.service 2>/dev/null || true
        success "Docker will start automatically on every boot"

        # ═══════════════════════════════════════════════════════════════════
        # Docker group + restart flow
        # ═══════════════════════════════════════════════════════════════════

        sudo usermod -aG docker "$USER"
        touch "$MARKER_FILE"

        header "Step 3/4: Restart required"
        echo ""
        echo "  Docker is installed! To continue, restart your terminal:"
        echo ""
        echo "  1. Close this Ubuntu window (type 'exit' or click X)"
        echo "  2. Open Ubuntu again from the Start menu"
        echo "  3. Run these commands:"
        echo "     cd $(pwd)"
        echo "     ./bootstrap.sh"
        echo ""
        echo "  The installation will resume automatically."
        echo ""

        exit 0
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════
# .env generation (reached via resume path OR skip-Docker path)
# ═══════════════════════════════════════════════════════════════════════════

header "Generating configuration..."

if [ -f ".env" ]; then
    success ".env already exists -- keeping existing configuration"
else
    if [ ! -f ".env.example" ]; then
        error ".env.example not found. Installation package may be incomplete."
        exit 1
    fi

    cp .env.example .env

    # Auto-generate secure credentials
    DB_PASS=$(tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 32)
    API_KEY_VAL=$(tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 32)

    # Override password and API key
    sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$DB_PASS|" .env
    sed -i "s|^API_KEY=.*|API_KEY=$API_KEY_VAL|" .env

    # Prompt for Google Maps API key (required for geocoding)
    echo ""
    echo -e "  ${BOLD}Google Maps API key${NC} (required for geocoding addresses)"
    echo "  Get one at: https://console.cloud.google.com/apis/credentials"
    echo "  Enable the \"Geocoding API\" — free \$200/month credit covers ~40,000 lookups."
    echo ""
    read -rp "  Google Maps API key (press Enter to skip): " GMAPS_KEY
    if [ -n "$GMAPS_KEY" ]; then
        sed -i "s|^GOOGLE_MAPS_API_KEY=.*|GOOGLE_MAPS_API_KEY=$GMAPS_KEY|" .env
        success "Google Maps API key configured"
    else
        warn "No Google Maps API key — geocoding will only work for cached addresses."
        info "Add it later: edit .env and set GOOGLE_MAPS_API_KEY=your-key"
    fi

    success ".env created with auto-generated credentials"
fi

# ═══════════════════════════════════════════════════════════════════════════
# Delegate to install.sh
# ═══════════════════════════════════════════════════════════════════════════

header "Starting system installation..."
info "This downloads Docker images and Kerala map data (~10-20 minutes first time)"

exec ./scripts/install.sh
