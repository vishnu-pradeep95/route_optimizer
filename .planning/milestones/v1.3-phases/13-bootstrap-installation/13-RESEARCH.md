# Phase 13: Bootstrap Installation - Research

**Researched:** 2026-03-05
**Domain:** WSL2 environment detection, Docker CE automated installation, bash scripting
**Confidence:** HIGH

## Summary

Phase 13 creates a `bootstrap.sh` script that installs Docker CE on a fresh WSL2 Ubuntu system and delegates to the existing `install.sh`. The technical domain is well-understood: Docker CE installation via the official apt repository is stable and well-documented, WSL1/WSL2 detection has reliable kernel-string methods, and systemd-based Docker auto-start is the standard approach on modern WSL2.

The existing `install.sh` already provides color helpers, spinner patterns, health polling, and `.env` skip logic that bootstrap can reuse. The main new work is: (1) environment guards (WSL version, filesystem path, memory), (2) Docker CE apt installation with zero prompts, (3) Docker group + session restart flow with marker-file resume, (4) `.env` generation from `.env.example` with auto-generated credentials, and (5) wsl.conf configuration for Docker auto-start.

**Primary recommendation:** Build bootstrap.sh as a single self-contained script that sources install.sh's color helpers (or duplicates them for independence), implements guards first, Docker install second, `.env` generation third, then delegates to install.sh. Use a two-phase marker file approach for the required WSL session restart after Docker group changes.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- Two-phase with auto-resume: bootstrap installs Docker CE, adds user to docker group, writes a marker file, then instructs user to close/reopen WSL
- On re-run, bootstrap detects the marker and resumes from install.sh automatically
- If Docker is already installed and user is in docker group, skip Docker install silently -- jump straight to install.sh
- Restart message uses numbered steps with context: "Step 1: Close this Ubuntu window. Step 2: Open Ubuntu again from Start menu. Step 3: cd routing_opt && ./bootstrap.sh"
- Fully automatic -- zero prompts during bootstrap
- Bootstrap generates .env itself (PostgreSQL password + API key auto-generated) before calling install.sh
- install.sh already skips .env creation if .env exists -- no changes to install.sh needed
- Credentials printed once in the final success banner for IT reference, no separate credentials file
- Both entry points work: bootstrap.sh for fresh installs, install.sh standalone for developers
- Google Maps API key pre-baked by developer before customer delivery -- employee never sees it
- Key lives in `.env.example` with the real value filled in before delivery
- Bootstrap copies `.env.example` to `.env` (with auto-generated DB password + API key overriding template values)
- `.env.example` committed in private repo -- no gitignore needed for customer-specific deliveries
- Step-by-step with progress: "Step 1/4: Installing Docker... done", "Step 2/4: Downloading Kerala map data (this takes ~10 min)...", spinner during waits
- RAM warning: yellow warning with .wslconfig instructions, continues automatically (does not block install)
- Final success banner: Dashboard URL, Driver App URL, daily workflow steps
- WSL1 and /mnt/c/ errors: plain English with numbered fix steps

### Claude's Discretion
- Resume marker file location (project root vs home directory)
- Exact Docker CE installation commands (apt repository setup)
- WSL1 vs WSL2 detection method
- RAM detection approach and threshold display
- wsl.conf configuration for Docker auto-start
- Spinner/progress indicator implementation

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INST-01 | Bootstrap script auto-installs Docker CE in WSL if missing | Docker CE apt repository commands verified on Ubuntu 24.04 WSL2; official docs confirm package set: docker-ce, docker-ce-cli, containerd.io, docker-buildx-plugin, docker-compose-plugin |
| INST-02 | Bootstrap script configures wsl.conf for Docker auto-start on boot | Two approaches verified: (1) systemd=true + systemctl enable docker, (2) [boot] command=service docker start. Systemd approach confirmed working on this system. |
| INST-03 | Bootstrap script detects Windows filesystem (`/mnt/c/`) and aborts with clear redirect | Path prefix check `case "$(pwd)" in /mnt/[a-z]/*)` verified working on actual WSL2 system |
| INST-04 | Bootstrap script pre-checks available RAM and warns if OSRM may OOM | `/proc/meminfo` MemTotal field gives WSL-allocated RAM; threshold of 5 GB confirmed in success criteria |
| INST-05 | Bootstrap script detects WSL1 vs WSL2 and fails clearly on WSL1 | Kernel string detection: WSL2 has `microsoft-standard` (lowercase), WSL1 has `Microsoft` (capital M) without `standard`. Verified on live system. |

</phase_requirements>

## Standard Stack

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| bash | 5.x | Script runtime | Pre-installed on Ubuntu, `set -euo pipefail` for safety |
| apt-get | system | Package installation | Standard Ubuntu package manager, supports `-y` for non-interactive |
| curl | system | GPG key download, health checks | Pre-installed or easily installed, used by Docker official instructions |
| sed | system | .env value replacement | Available everywhere, used by existing install.sh |
| grep | system | Kernel string detection, file parsing | Standard, supports `-q` for silent checks |

### Supporting
| Tool | Purpose | When to Use |
|------|---------|-------------|
| `tr + /dev/urandom` | Password generation | Generating POSTGRES_PASSWORD and API_KEY (same pattern as install.sh) |
| `systemctl` | Docker service management | Enabling Docker auto-start after installation |
| `sudo` | Privileged operations | Docker install, wsl.conf writing, service management |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `systemctl enable docker` | `[boot] command=service docker start` in wsl.conf | Both work; systemctl is cleaner when systemd is enabled. Using both provides belt-and-suspenders. |
| `uname -r` kernel check | `WSL_INTEROP` env var check | WSL_INTEROP is WSL2-only but less documented; kernel string is the community-standard approach |
| DEB822 `.sources` format | One-line `.list` format | Both work; official Docker docs now show DEB822 but `.list` format also works and is simpler. Use what the official docs recommend. |

**Installation:** No npm/pip install needed. All tools are system-level.

## Architecture Patterns

### Recommended Script Structure
```
scripts/
  bootstrap.sh      # NEW: Environment guards + Docker install + .env gen + delegate to install.sh
  install.sh         # EXISTING: Docker Compose up + health polling (unchanged)
```

### Pattern 1: Two-Phase Resume with Marker File
**What:** Bootstrap writes a marker file after Docker install + group add, then instructs user to restart WSL. On re-run, marker file is detected and bootstrap skips to install.sh.
**When to use:** When a session restart is required (Docker group membership needs re-login).
**Recommendation:** Use marker file in project root (`.bootstrap_resume`) rather than home directory. Project root is simpler to reason about, and the user is already instructed to `cd routing_opt`.

```bash
MARKER_FILE=".bootstrap_resume"

# Phase 1: Check if resuming
if [ -f "$MARKER_FILE" ]; then
    rm "$MARKER_FILE"
    info "Resuming installation after restart..."
    # Jump to install.sh
    exec ./scripts/install.sh
fi

# ... Docker install, group add ...

# Write marker and instruct restart
touch "$MARKER_FILE"
echo "Step 1: Close this Ubuntu window."
echo "Step 2: Open Ubuntu again from Start menu."
echo "Step 3: cd routing_opt && ./bootstrap.sh"
exit 0
```

### Pattern 2: Guard-First Architecture
**What:** All environment checks run before any installation begins. Fail fast with clear messages.
**When to use:** Always -- prevents partial installations that are hard to recover from.
**Order:** (1) WSL check, (2) WSL version check, (3) Filesystem path check, (4) RAM warning, (5) Docker check, (6) Resume check.

```bash
# Guard 1: Are we on WSL at all?
if ! grep -qi microsoft /proc/version 2>/dev/null; then
    error "This script is designed for Windows Subsystem for Linux (WSL)."
    exit 1
fi

# Guard 2: WSL2 required (WSL1 has "Microsoft" without "standard")
if ! uname -r | grep -qi "microsoft.*standard"; then
    error "WSL version 1 detected. WSL version 2 is required."
    echo ""
    echo "  To upgrade to WSL2:"
    echo "  1. Open PowerShell as Administrator"
    echo "  2. Run: wsl --set-version Ubuntu 2"
    echo "  3. Wait for conversion to complete"
    echo "  4. Re-run this script"
    exit 1
fi

# Guard 3: Not running from Windows filesystem
case "$(pwd)" in
    /mnt/[a-z]/*)
        error "Running from Windows filesystem ($(pwd))"
        echo ""
        echo "  This causes severe performance problems."
        echo "  Instead, clone the project in your Linux home directory:"
        echo ""
        echo "  1. cd ~"
        echo "  2. git clone <repo-url> routing_opt"
        echo "  3. cd routing_opt"
        echo "  4. ./bootstrap.sh"
        exit 1
        ;;
esac

# Guard 4: RAM warning (non-blocking)
TOTAL_RAM_MB=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
if [ "$TOTAL_RAM_MB" -lt 5120 ]; then
    warn "Low memory detected: ${TOTAL_RAM_MB} MB available to WSL"
    echo "  OSRM requires at least 5 GB RAM for Kerala map processing."
    echo ""
    echo "  To increase WSL memory:"
    echo "  1. Create/edit C:\\Users\\YourName\\.wslconfig"
    echo "  2. Add these lines:"
    echo "     [wsl2]"
    echo "     memory=6GB"
    echo "  3. Run in PowerShell: wsl --shutdown"
    echo "  4. Re-open Ubuntu and try again"
    echo ""
fi
```

### Pattern 3: Docker CE Non-Interactive Installation
**What:** Full Docker CE install via official apt repository with zero prompts.
**When to use:** When Docker is not already installed.

```bash
install_docker() {
    info "Installing Docker CE..."

    # Remove conflicting packages silently
    for pkg in docker.io docker-doc docker-compose podman-docker containerd runc; do
        sudo apt-get remove -y "$pkg" 2>/dev/null || true
    done

    # Install prerequisites
    sudo apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        ca-certificates curl gnupg

    # Add Docker's official GPG key
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
        -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc

    # Add Docker apt repository
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu \
$(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
        sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    # Install Docker CE
    sudo apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        docker-ce docker-ce-cli containerd.io \
        docker-buildx-plugin docker-compose-plugin

    success "Docker CE installed"
}
```

### Pattern 4: Docker Auto-Start via Systemd
**What:** Enable systemd in wsl.conf and enable Docker service.
**When to use:** After Docker CE is installed. Ensures Docker starts automatically on every WSL session.

```bash
configure_docker_autostart() {
    # Ensure systemd is enabled in wsl.conf
    if ! grep -q "systemd=true" /etc/wsl.conf 2>/dev/null; then
        sudo tee -a /etc/wsl.conf > /dev/null << 'EOF'

[boot]
systemd=true
EOF
    fi

    # Enable Docker service via systemd
    sudo systemctl enable docker.service
    sudo systemctl enable containerd.service

    success "Docker configured to start automatically"
}
```

### Pattern 5: .env Generation from Template
**What:** Copy .env.example to .env, auto-generate POSTGRES_PASSWORD and API_KEY, preserve GOOGLE_MAPS_API_KEY from template.
**When to use:** Before calling install.sh, only if .env doesn't exist.

```bash
generate_env() {
    if [ -f ".env" ]; then
        success ".env already exists -- keeping existing configuration"
        return
    fi

    if [ ! -f ".env.example" ]; then
        error ".env.example not found. Installation package may be incomplete."
        exit 1
    fi

    cp .env.example .env

    # Auto-generate secure credentials
    local db_pass api_key
    db_pass=$(tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 32)
    api_key=$(tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 32)

    # Override password and API key (preserve everything else including GOOGLE_MAPS_API_KEY)
    sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$db_pass|" .env
    sed -i "s|^API_KEY=.*|API_KEY=$api_key|" .env

    success ".env created with auto-generated credentials"
}
```

### Anti-Patterns to Avoid
- **Prompting the user:** The locked decision is fully automatic, zero prompts. Never use `read` in bootstrap.sh.
- **Modifying install.sh:** Bootstrap pre-creates .env so install.sh skips its interactive .env creation. Do not modify install.sh.
- **Using `newgrp docker`:** This opens a new shell and doesn't propagate properly in scripts. The correct approach is the two-phase restart with marker file.
- **Running Docker commands before group takes effect:** After `usermod -aG docker $USER`, the current session doesn't have the new group. Must restart WSL.
- **Using `sudo docker compose` as workaround:** The success criteria require Docker to work without sudo after reboot. Don't paper over the group issue.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Docker CE installation | Custom apt commands | Docker official apt repository setup | GPG key management, repository URL construction, package dependencies are all handled by the official process |
| Password generation | Custom random functions | `tr -dc 'A-Za-z0-9' < /dev/urandom \| head -c 32` | Already proven in install.sh, works on all Linux systems |
| Service auto-start | Custom rc.local or cron hacks | `systemctl enable docker` with systemd=true in wsl.conf | systemd is the standard on modern WSL2; rc.local hacks are fragile |
| Color output | Custom ANSI codes | Copy install.sh's color helpers | Consistency with existing install.sh output |
| Spinner animation | Complex progress library | Simple spinner loop from install.sh | Already proven pattern in the codebase |

**Key insight:** The existing install.sh has battle-tested patterns for colors, spinners, health polling, and .env handling. Bootstrap should match these patterns, not invent new ones.

## Common Pitfalls

### Pitfall 1: Docker Group Requires Session Restart
**What goes wrong:** After `sudo usermod -aG docker $USER`, running `docker ps` still fails with permission denied because the current shell doesn't pick up new group membership.
**Why it happens:** Linux group membership is loaded at login time. `usermod` modifies `/etc/group` but the current session's token isn't refreshed.
**How to avoid:** Two-phase approach with marker file. After Docker install + group add, instruct user to close and reopen WSL terminal, then re-run bootstrap.sh.
**Warning signs:** `docker: permission denied` errors after install but before restart.

### Pitfall 2: WSL1 Kernel String Variation
**What goes wrong:** Detection regex too strict and misses older WSL1 kernel versions, or too loose and matches non-WSL systems.
**Why it happens:** WSL1 kernels use patterns like `4.4.0-xxxxx-Microsoft` (capital M), while WSL2 uses `x.x.x-microsoft-standard-WSL2` (lowercase m, includes "standard").
**How to avoid:** First check if running on WSL at all (`grep -qi microsoft /proc/version`). Then check for WSL2 specifically (`uname -r | grep -qi "microsoft.*standard"`). If on WSL but not WSL2, it's WSL1.
**Warning signs:** Script passing on non-WSL Linux systems or failing on valid WSL2 installs.

### Pitfall 3: /mnt/c/ Path Performance
**What goes wrong:** Running from Windows filesystem (`/mnt/c/Users/...`) causes Docker build to be 10-50x slower due to filesystem translation overhead.
**Why it happens:** WSL's DrvFs filesystem bridge between Windows NTFS and Linux ext4 has significant I/O overhead for the thousands of small file operations Docker does.
**How to avoid:** Check `$(pwd)` against `/mnt/[a-z]/*` pattern. Abort with clear instructions to clone in Linux home directory.
**Warning signs:** Docker builds taking 30+ minutes instead of 2-3 minutes.

### Pitfall 4: wsl.conf Overwrites
**What goes wrong:** Writing to `/etc/wsl.conf` clobbers existing user configurations (e.g., [user] default=...).
**Why it happens:** Using `sudo tee /etc/wsl.conf` or `echo > /etc/wsl.conf` replaces the entire file.
**How to avoid:** Check if sections/keys already exist before writing. Use `tee -a` (append) and grep to verify the setting isn't already present. Better: read existing file, merge settings, write back.
**Warning signs:** User's default username or other settings lost after running bootstrap.

### Pitfall 5: apt-get Prompts During Docker Install
**What goes wrong:** Ubuntu's package manager prompts for confirmation or shows interactive configuration dialogs, breaking the zero-prompt requirement.
**Why it happens:** Some packages trigger debconf dialogs. Without `-y` and `DEBIAN_FRONTEND=noninteractive`, apt blocks waiting for input.
**How to avoid:** Always use `sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq` for all apt operations.
**Warning signs:** Script hangs waiting for user input during Docker installation.

### Pitfall 6: Memory Reporting in WSL2
**What goes wrong:** `/proc/meminfo` shows the WSL2 VM's allocated memory, not the host's total RAM.
**Why it happens:** WSL2 runs in a lightweight VM. By default it gets 50% of host RAM (or 8 GB, whichever is less), configurable via `.wslconfig`.
**How to avoid:** This is actually the correct behavior for our use case -- we want to check what memory WSL has available, not the host total. The 5 GB threshold check against MemTotal is correct.
**Warning signs:** Users with 16 GB RAM but default WSL config showing only 8 GB.

### Pitfall 7: set -e + sudo Failures
**What goes wrong:** If the user doesn't have passwordless sudo, `sudo apt-get` might fail interactively (password prompt fails under `set -e`).
**Why it happens:** Fresh WSL Ubuntu typically has passwordless sudo for the default user, but custom configurations may require a password.
**How to avoid:** The default WSL Ubuntu configuration has passwordless sudo. Document this assumption. The user already types their password once for `sudo` in the session; subsequent sudo calls use the cached credential (default 15 min timeout).
**Warning signs:** Script exits immediately with "sudo: a terminal is required to read the password" type errors.

## Code Examples

Verified patterns from the existing codebase and official documentation:

### Color Helpers (from install.sh, line 39-63)
```bash
# Source: scripts/install.sh
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

info()    { echo -e "${BLUE}--${NC} $*"; }
success() { echo -e "${GREEN}ok${NC} $*"; }
warn()    { echo -e "${YELLOW}!!${NC} $*"; }
error()   { echo -e "${RED}xx${NC} $*" >&2; }
header()  { echo -e "\n${BOLD}$*${NC}"; echo "---"; }
```

### Spinner with Background Process (from install.sh health-poll pattern)
```bash
# Source: Adapted from scripts/install.sh spinner pattern
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
    printf "\r  %s\n" "  "
    wait "$pid"
    return $?
}

# Usage:
sudo apt-get install -y -qq docker-ce ... &>/dev/null &
spin_while $! "Installing Docker CE..."
```

### Docker CE Install Commands (Official Docker Documentation)
```bash
# Source: https://docs.docker.com/engine/install/ubuntu/
# Verified against actual system: Ubuntu 24.04 (Noble) on WSL2

# 1. Remove old versions
for pkg in docker.io docker-doc docker-compose podman-docker containerd runc; do
    sudo apt-get remove -y "$pkg" 2>/dev/null || true
done

# 2. Add Docker's official GPG key
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# 3. Add Docker apt repository (one-line format works on all Ubuntu versions)
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] \
https://download.docker.com/linux/ubuntu \
$(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
    sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 4. Install Docker CE packages
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin
```

### WSL Version Detection (Verified on Live System)
```bash
# Source: https://github.com/microsoft/WSL/issues/4555 + verified on WSL2

detect_wsl() {
    # Not on WSL at all?
    if ! grep -qi microsoft /proc/version 2>/dev/null; then
        echo "none"
        return
    fi
    # WSL2: kernel string contains "microsoft-standard" (lowercase)
    # WSL1: kernel string contains "Microsoft" (capital M) without "standard"
    if uname -r | grep -qi "microsoft.*standard"; then
        echo "wsl2"
    else
        echo "wsl1"
    fi
}
```

### Memory Check (Verified on Live System)
```bash
# Source: /proc/meminfo on WSL2 reports VM-allocated memory
# WSL2 default: 50% of host RAM or 8 GB, whichever is less

check_memory() {
    local total_mb
    total_mb=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)

    if [ "$total_mb" -lt 5120 ]; then
        warn "Low memory: ${total_mb} MB allocated to WSL (5120 MB recommended)"
        echo ""
        echo "  OSRM needs ~4 GB to process Kerala map data."
        echo "  To increase WSL memory, create this file on Windows:"
        echo ""
        echo "    File: C:\\Users\\YourName\\.wslconfig"
        echo "    Contents:"
        echo "      [wsl2]"
        echo "      memory=6GB"
        echo ""
        echo "  Then run in PowerShell: wsl --shutdown"
        echo "  Re-open Ubuntu and try again."
        echo ""
    else
        success "Memory: ${total_mb} MB available (minimum 5120 MB)"
    fi
}
```

### wsl.conf Safe Modification
```bash
# Ensure [boot] section exists with systemd=true
# Without clobbering existing settings

ensure_wsl_conf() {
    local conf="/etc/wsl.conf"

    # Check if systemd is already enabled
    if grep -q "systemd=true" "$conf" 2>/dev/null; then
        success "systemd already enabled in wsl.conf"
        return
    fi

    # Check if [boot] section exists
    if grep -q "^\[boot\]" "$conf" 2>/dev/null; then
        # Add systemd=true after [boot] section
        sudo sed -i '/^\[boot\]/a systemd=true' "$conf"
    else
        # Append [boot] section
        echo "" | sudo tee -a "$conf" > /dev/null
        echo "[boot]" | sudo tee -a "$conf" > /dev/null
        echo "systemd=true" | sudo tee -a "$conf" > /dev/null
    fi

    success "systemd enabled in wsl.conf"
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `docker.io` package from Ubuntu repos | `docker-ce` from Docker's official apt repo | Always -- Docker official repo is preferred | Gets latest Docker version, not Ubuntu's older package |
| `[boot] command=service docker start` | `systemd=true` + `systemctl enable docker` | WSL 0.67.6+ (2022) | Proper systemd integration, Docker starts as native service |
| GPG key via `apt-key add` | GPG key in `/etc/apt/keyrings/` | Docker docs 2022+ | `apt-key` is deprecated, keyrings is the modern approach |
| DEB822 `.sources` format | One-line `.list` format still works | Both supported | Official Docker docs now show `.sources` format but `.list` still works fine |

**Deprecated/outdated:**
- `apt-key add` for GPG keys -- use `/etc/apt/keyrings/` directory instead
- `docker-compose` standalone binary -- use `docker compose` (v2 plugin) which comes with `docker-compose-plugin`
- `[boot] command=service docker start` -- works but systemd approach is cleaner

## Open Questions

1. **DEB822 vs one-line apt source format**
   - What we know: Official Docker docs now show DEB822 format (`.sources`), but one-line format (`.list`) still works. The actual system uses `.list` format.
   - What's unclear: Whether to match the official docs' newest format or use the simpler `.list` format.
   - Recommendation: Use one-line `.list` format. It's simpler, works on all Ubuntu versions, and is what's currently on this system. HIGH confidence this is fine.

2. **Marker file cleanup on failure**
   - What we know: If bootstrap writes the marker file but install.sh fails after resume, the marker file is already removed.
   - What's unclear: Edge case where Docker install succeeds, marker is written, but user never restarts.
   - Recommendation: The marker file is harmless -- it just triggers the resume path which calls install.sh. If install.sh fails, user can re-run. No special cleanup needed.

3. **sudo password caching**
   - What we know: Default Ubuntu WSL has passwordless sudo. If sudo requires a password, the 15-minute cache means only one prompt.
   - What's unclear: Whether enterprise-configured WSL images disable passwordless sudo.
   - Recommendation: Accept this as a known limitation. If sudo prompts, user enters password once and the rest of the script runs with cached credentials. Document in error messages.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | bash + manual verification |
| Config file | none -- shell scripts tested via execution |
| Quick run command | `bash -n scripts/bootstrap.sh` (syntax check) |
| Full suite command | Manual: run bootstrap.sh on fresh WSL2 Ubuntu |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INST-01 | Docker CE auto-install | manual-only | Run on fresh WSL2 Ubuntu without Docker | N/A |
| INST-02 | Docker auto-start via wsl.conf/systemd | manual-only | Reboot WSL, check `systemctl is-active docker` | N/A |
| INST-03 | /mnt/c/ detection and abort | smoke | `cd /mnt/c && bash /path/to/bootstrap.sh; echo $?` | N/A |
| INST-04 | RAM check and warning | smoke | Check `/proc/meminfo` parsing in isolation | N/A |
| INST-05 | WSL1 detection and fail | manual-only | Requires WSL1 environment (or mock `/proc/version`) | N/A |

**Justification for manual-only tests:** INST-01, INST-02, and INST-05 require specific system states (no Docker installed, WSL reboot, WSL1 environment) that cannot be automated in-repo. INST-03 and INST-04 can be partially tested by running specific guard functions in isolation.

### Sampling Rate
- **Per task commit:** `bash -n scripts/bootstrap.sh` (syntax validation)
- **Per wave merge:** Syntax check + shellcheck if available
- **Phase gate:** Manual execution on test WSL2 environment

### Wave 0 Gaps
- [ ] `bash -n` syntax check is minimal -- consider adding `shellcheck` as optional linting
- Shell scripts are inherently hard to unit test; validation is primarily manual execution

## Sources

### Primary (HIGH confidence)
- [Docker official docs - Install Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/) -- Full apt repository installation commands, verified against actual system
- [Microsoft Learn - WSL Configuration](https://learn.microsoft.com/en-us/windows/wsl/wsl-config) -- wsl.conf and .wslconfig syntax, [boot] section, systemd support
- Live system verification on Ubuntu 24.04 (Noble) / WSL2 / Docker CE 29.2.1

### Secondary (MEDIUM confidence)
- [GitHub WSL Issue #4555](https://github.com/microsoft/WSL/issues/4555) -- WSL1 vs WSL2 detection methods, kernel string patterns
- [DEV.to - Docker on WSL2 without Docker Desktop](https://dev.to/felipecrs/simply-run-docker-on-wsl2-without-docker-desktop-j1m) -- systemd + Docker auto-start pattern

### Tertiary (LOW confidence)
- Bash spinner patterns from various blog posts -- generic patterns, well-established but not from authoritative source

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all tools are system-level, verified on live system
- Architecture: HIGH -- two-phase resume pattern is straightforward, all guards verified on actual WSL2
- Docker installation: HIGH -- official Docker docs + verified against actual installed system
- WSL detection: HIGH -- kernel string patterns verified on live WSL2, WSL1 pattern from official GitHub issue
- Pitfalls: HIGH -- each pitfall identified from actual system testing or documented community issues

**Research date:** 2026-03-05
**Valid until:** 2026-06-05 (90 days -- Docker apt repo URLs and WSL APIs are stable)
