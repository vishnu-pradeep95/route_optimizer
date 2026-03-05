# Stack Research

**Domain:** WSL bootstrap, Docker auto-install, daily-use scripts, user-facing documentation
**Researched:** 2026-03-04
**Confidence:** HIGH
**Scope:** v1.3 milestone only — "Office-Ready Deployment". Existing Python/FastAPI/React/Docker stack is locked. This document covers ONLY what is new: one-command WSL install with Docker auto-provisioning, a daily start script, and CSV documentation format.

---

## Context: What Is Already in Place (Locked — Do Not Change)

| Component | Status |
|-----------|--------|
| `scripts/install.sh` | Validates Docker exists, fails if missing — needs Docker auto-install prepended |
| `scripts/deploy.sh` | Production deploy — correct, leave unchanged |
| `docker-compose.yml` | Container names: `lpg-db`, `osrm-init`, `osrm-kerala`, `vroom-solver`, `lpg-db-init`, `lpg-api` |
| `DEPLOY.md` | Employee-facing guide — incomplete: stale container names, placeholder `<REPO_URL>`, missing Docker install steps |
| `README.md` | Developer guide — stale container names in Docker Services table (`routing-db`, `osrm-kerala`, `vroom-solver`) |

The container names in README.md (`routing-db`) do not match `docker-compose.yml` (`lpg-db`). This is a documentation bug to fix, not a code change.

---

## Recommended Stack

### Core Technologies (All Already Installed — No New Dependencies)

This milestone adds zero new runtime dependencies. Every tool is either:
- Already in the system (bash, curl, apt)
- Already in `docker-compose.yml`
- Plain Markdown (no static site generator needed)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| Bash | 5.x (Ubuntu 22.04+) | Bootstrap and daily-start scripts | Already present on every Ubuntu/WSL install. No Python/Node dependency for scripts that run before Docker is up. `#!/usr/bin/env bash` with `set -euo pipefail` is the correct shebang for reliable scripts. |
| `apt` + Docker official repo | docker-ce 27.x+ | Docker Engine auto-install | Official Docker apt repository (`download.docker.com/linux/ubuntu`) is the only supported install method. The `get.docker.com` convenience script works but adds a network hop for a script the user should inspect. Official apt method is auditable and idempotent. |
| `docker compose` plugin | 2.x (ships with docker-ce) | Container orchestration | Already used. Installed automatically as `docker-compose-plugin` alongside `docker-ce`. No separate install needed. |
| `/etc/wsl.conf` `[boot]` section | WSL 0.67.6+ | Auto-start Docker on WSL launch | The `[boot] command` key in `/etc/wsl.conf` runs a command as root when WSL starts. No systemd needed. Simpler than `.bashrc` because it fires once at boot, not per terminal. |
| Markdown | GFM (GitHub Flavored) | CSV format documentation | No tooling required. Render natively in GitHub, VS Code Preview, and any browser with a Markdown extension. Editors the office employee already has. Tables, code blocks, and headers cover all CSV spec needs. |

### Supporting Libraries

| Library | Purpose | When to Use |
|---------|---------|-------------|
| `curl` | Health checks, Docker repo GPG key download | Already in `scripts/install.sh`. Required by the Docker install process itself. |
| `sudo` | Privilege escalation for Docker install | Non-negotiable for apt operations and `/etc/wsl.conf` writes. Script must check for sudo access early and fail with a clear message. |
| `service docker start` | Start Docker daemon on WSL (sysvinit path) | Fallback when systemd is not enabled. Works on all Ubuntu/WSL versions since Docker 19+. Used in boot command and daily start script. |
| `systemctl` (optional) | Start Docker when systemd is enabled | Preferred when `[boot] systemd=true` is set in wsl.conf. Script should detect which init system is active and use the right command. |

### Development Tools (For Script Quality — Do Not Install on End-User Machine)

| Tool | Purpose | Notes |
|------|---------|-------|
| ShellCheck | Static analysis for bash scripts | `sudo apt install shellcheck` on dev machine. Catches quoting bugs, unbound variables, bad substitutions before users hit them. Run against all new `.sh` files before commit. Not needed on end-user machine. |

---

## Installation

No new packages to install on the target machine beyond Docker itself. The bootstrap script is self-contained and installs what it needs.

```bash
# Developer quality check — run locally before committing new scripts
sudo apt install shellcheck
shellcheck scripts/bootstrap-wsl.sh
shellcheck scripts/start.sh
```

---

## Docker Auto-Install: Exact Approach

### Why Official apt Repo, Not `get.docker.com`

The `curl https://get.docker.com | sudo sh` convenience script works but has two downsides for a non-technical user script:

1. It fetches and executes an external script blindly — a security smell to embed in a repo script
2. It does not allow version pinning

Use the official apt repository directly. It is auditable, idempotent, and what Docker's own documentation recommends for Ubuntu.

### Exact Install Sequence (HIGH confidence — verified against official docs 2026-03-04)

```bash
# 1. Install apt prerequisites
sudo apt-get update
sudo apt-get install -y ca-certificates curl

# 2. Add Docker's GPG key (the .asc format, not the old .gpg dearmor method)
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# 3. Add the Docker apt repository
# The new deb822 .sources format (preferred over the legacy one-liner)
sudo tee /etc/apt/sources.list.d/docker.sources > /dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF

# 4. Install Docker Engine + Compose plugin
sudo apt-get update
sudo apt-get install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin

# 5. Add user to docker group (avoids sudo for docker commands)
sudo usermod -aG docker "$USER"

# 6. Start Docker daemon immediately (WSL does not auto-start services)
sudo service docker start
```

Note: After `usermod -aG docker "$USER"`, the group change does not take effect in the current shell. The bootstrap script should instruct the user to close and reopen the WSL terminal (or run `newgrp docker`) before running `install.sh`. Do not try to use `newgrp docker` inside the bootstrap script itself — `newgrp` spawns a subshell and effectively pauses script execution at that line, which breaks the script flow for non-interactive use.

### Docker Group: Handling the Subshell Problem

The `newgrp docker` workaround does NOT work inside a non-interactive script because it opens a new shell. The correct approach for the bootstrap script:

```bash
# After usermod, check if current session already has docker group
if ! id -nG "$USER" | grep -q '\bdocker\b'; then
    warn "You have been added to the docker group."
    warn "IMPORTANT: Close this terminal, reopen WSL, and run this script again."
    warn "The next run will complete the setup."
    exit 0  # Clean exit — user reruns after terminal restart
fi
```

This is the pattern used by Ubuntu's own post-install scripts. It is honest about the restart requirement rather than hiding it.

---

## WSL Docker Auto-Start: Exact Approach

### The Problem

WSL does not keep services running between terminal sessions. Every time a user opens a new WSL terminal, Docker is stopped. Currently `install.sh` handles this with `sudo service docker start`, but the daily-use script also needs it.

### Recommended: `/etc/wsl.conf` Boot Command

Write to `/etc/wsl.conf` once during bootstrap. Requires WSL 0.67.6+ (available since Windows 10 21H2 with WSL Store update, effectively universal in 2026).

```ini
# /etc/wsl.conf
[boot]
command = "service docker start"
```

This runs as root when WSL starts — before any user terminal opens. No sudo prompt. No .bashrc pollution. No per-terminal overhead.

The bootstrap script writes this idempotently:

```bash
configure_wsl_docker_autostart() {
    local WSL_CONF="/etc/wsl.conf"

    # Check if already configured
    if grep -q "service docker start" "$WSL_CONF" 2>/dev/null; then
        success "Docker auto-start already configured in $WSL_CONF"
        return 0
    fi

    info "Configuring Docker to start automatically when WSL launches..."

    # Append [boot] section if not present
    if ! grep -q '^\[boot\]' "$WSL_CONF" 2>/dev/null; then
        sudo tee -a "$WSL_CONF" > /dev/null <<'EOF'

[boot]
command = "service docker start"
EOF
    else
        # [boot] section exists — add command under it
        # Use sed to insert after [boot] line
        sudo sed -i '/^\[boot\]/a command = "service docker start"' "$WSL_CONF"
    fi

    success "Docker will now start automatically when you open WSL"
    info "Note: Takes effect after next 'wsl --shutdown' in PowerShell"
}
```

### Fallback: `.bashrc` Check (for older WSL or if wsl.conf write fails)

```bash
# Minimal Docker start check — add to ~/.bashrc if wsl.conf approach fails
if ! docker info &>/dev/null 2>&1; then
    sudo service docker start &>/dev/null
fi
```

This is the `~/.bashrc` approach documented in the existing SETUP.md. It works but adds ~1-2s to every new terminal. The wsl.conf method is strictly better for user experience.

---

## Daily Start Script Design

### What It Should Do

A `scripts/start.sh` that a non-technical user can double-click or run without arguments:

1. Check Docker is running (start it if not — handles missed wsl.conf)
2. `cd` to the project root (so it works regardless of where the user runs it from)
3. `docker compose up -d` (idempotent — safe to run when already running)
4. Wait for health check at `http://localhost:8000/health`
5. Print the dashboard URL in a box the user cannot miss
6. Optionally open Chrome to the dashboard URL

### What It Must NOT Do

- Rebuild Docker images (that is slow; only `install.sh` does this)
- Prompt for any input
- Require any arguments
- Do anything if services are already healthy (early exit)

### Chrome Open Pattern (WSL-Specific)

Opening a browser from WSL uses the Windows `cmd.exe /c start` pathway:

```bash
open_browser() {
    local url="$1"
    # WSL: use cmd.exe to open in Windows default browser
    if command -v cmd.exe &>/dev/null; then
        cmd.exe /c start "" "$url" 2>/dev/null || true
    # Native Linux: try xdg-open
    elif command -v xdg-open &>/dev/null; then
        xdg-open "$url" 2>/dev/null || true
    fi
    # Silently skip if neither works — URL is printed to terminal anyway
}
```

The `|| true` prevents script failure if the browser launch fails (e.g., no display server on pure headless WSL).

---

## Documentation Format: CSV Specification

### Format: Plain Markdown in DEPLOY.md

No documentation tooling is needed. The existing `DEPLOY.md` is the correct home for CSV format documentation — it is the employee-facing guide. The format should be:

1. **What the file looks like** — a short example of the actual CSV content (a code block with 2-3 example rows)
2. **Required columns table** — name, what it means in plain language, example value
3. **What gets rejected and why** — a table of common errors with the exact rejection message shown in the UI
4. **Address cleaning rules** — what the system does automatically (abbreviations, phone number removal)

### CSV Documentation Template Structure

```markdown
## 4. The CDCMS Export File

### What to Export from CDCMS

In CDCMS: go to **Order Management → Export → Today's Orders**.
Save as a `.csv` file. The file will look like this:

```
OrderNo,OrderStatus,ConsumerAddress,OrderQuantity,AreaName,DeliveryMan,...
ON-001,Allocated-Printed,"House Near School, Vatakara",2,VALLIKKADU,GIREESHAN ( C ),...
ON-002,Allocated-Printed,"4/146 Aminas Residency, MG Road",1,RAYARANGOTH,GIREESHAN ( C ),...
```

### Which Columns the System Uses

| Column | What It Is | Example |
|--------|-----------|---------|
| `OrderNo` | Unique order number | `ON-12345` |
| `OrderStatus` | Only `Allocated-Printed` orders are loaded | `Allocated-Printed` |
| `ConsumerAddress` | Delivery address — cleaned automatically | `House Near School, Vatakara` |
| `OrderQuantity` | Number of cylinders | `2` |
| `AreaName` | Delivery area | `VALLIKKADU` |
| `DeliveryMan` | Driver name as it appears in CDCMS | `GIREESHAN ( C )` |

All other columns are ignored.

### Why Some Orders Are Rejected

| Rejection Reason | What It Means | What to Do |
|-----------------|---------------|-----------|
| `OrderStatus is not Allocated-Printed` | Order is still Pending or already Delivered | Only export Allocated-Printed orders |
| `Address could not be geocoded` | Google Maps could not find the address | See Section 5: Fixing Bad Addresses |
| `Quantity is zero or missing` | OrderQuantity column is blank or 0 | Check the CDCMS export — re-export if needed |
| `Duplicate address (within 15m of another order)` | Two orders have nearly identical GPS location | Check whether it is the same customer uploaded twice |
```

This structure answers the actual questions a non-technical user has. No tooling beyond a text editor to maintain.

### What NOT to Add for Documentation

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| MkDocs / Docusaurus | Requires Node.js/Python build step. Creates a separate site to maintain. Overkill for a 1-2 page user guide. | Plain Markdown in DEPLOY.md |
| Swagger/OpenAPI UI for user docs | API docs are for developers. Office employees interact via the dashboard, not the API. | Section in DEPLOY.md with screenshots |
| A separate `docs/` folder | Splits attention. The employee already has DEPLOY.md bookmarked. | Expand existing DEPLOY.md sections |
| Excel/PDF spec | Not version-controlled. Hard to update. | Markdown table in DEPLOY.md |
| AsciiDoc | No tooling advantage over Markdown for GitHub rendering. | GFM Markdown |

---

## What NOT to Add (Broader Scope)

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Docker Desktop (Windows) | Requires Windows Pro/Enterprise, license for business use, more RAM overhead. WSL2 + Docker Engine is free, faster, and works on Windows Home. | Docker Engine directly in WSL2 Ubuntu |
| Ansible / Chef / Puppet | Overkill for single-machine office setup. Adds a new tool the user must learn. | Pure bash scripts |
| Snap docker package | Docker from Snap has known networking issues in WSL. The official apt repository is the right path. | Official Docker apt repo |
| pyenv / nvm for bootstrap | Bootstrap script does not need Python or Node. Installs Docker + starts services. No runtime environment needed. | Direct apt installs only |
| `sudo visudo` NOPASSWD for Docker | Removes the sudo prompt for `docker` specifically. Tempting for UX, but creates a security hole. | Accept the one-time sudo prompt during install |
| Interactive `read` prompts in `start.sh` | Daily start script must be zero-input. Non-technical users should be able to run it without reading output carefully. | Silent flags, auto-detect, clear success output only |
| Health check timeouts over 300s | Already tuned in `install.sh`. OSRM data is cached after first run — subsequent starts are fast. | Keep existing 300s MAX_WAIT, 5s POLL_INTERVAL |
| WSL2 memory configuration automation | Modifying `%UserProfile%\.wslconfig` requires writing a file on the Windows side from within WSL — fragile, requires Windows path discovery. | Document the `.wslconfig` change in DEPLOY.md as a manual step if needed |

---

## Integration with Existing `install.sh`

The existing `install.sh` is well-structured and should not be rewritten. The v1.3 changes are:

1. **Prepend a Step 0** before "Step 1: Check prerequisites" — detect if Docker is missing, and if so, run the Docker auto-install sequence. After install, the script continues normally to its existing Step 1 check.

2. **Add Docker auto-start configuration** at the end of Step 1 (after Docker is confirmed working) — write the wsl.conf boot command idempotently.

3. **Do not change Steps 2-5** — they are correct and complete.

Pattern for Step 0 integration:

```bash
# ═══════════════════════════════════════════════════════════════════════════
# Step 0: Auto-install Docker if missing
# ═══════════════════════════════════════════════════════════════════════════

if ! command -v docker &>/dev/null; then
    header "Step 0/5: Docker not found — installing automatically"
    install_docker  # function containing the apt sequence above
    configure_wsl_docker_autostart
    info "Docker installed. Please close this terminal, reopen WSL, and run this script again."
    info "This is required once so Docker group permissions take effect."
    exit 0
elif ! docker info &>/dev/null 2>&1; then
    info "Starting Docker daemon..."
    sudo service docker start
fi
# Now continue to existing Step 1...
```

The two-run pattern (install → restart terminal → rerun) is the correct UX for the docker group problem. It is honest, safe, and the same experience Docker's own post-install docs describe.

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| docker-ce (latest stable) | Ubuntu 22.04 (jammy), 24.04 (noble) | Both UBUNTU_CODENAME values work with the official apt repo. Script detects codename via `/etc/os-release`. |
| docker-compose-plugin | docker-ce (any recent) | Installed together. `docker compose version` (no hyphen) is the v2 plugin syntax. install.sh already tests for this. |
| `/etc/wsl.conf` `[boot] command` | WSL 0.67.6+ | Effectively universal in 2026. Script should check WSL version and fall back to `.bashrc` method gracefully. |
| `service docker start` | Ubuntu 22.04+, WSL2 | Uses sysvinit init.d. Works even when systemd is not the init system (default WSL2 without systemd enabled). |
| `systemctl enable docker` | Ubuntu 22.04+ with `[boot] systemd=true` | Only relevant if user has enabled systemd. Script should detect and prefer systemctl when available. |

---

## Sources

- [Docker Engine install on Ubuntu — official docs](https://docs.docker.com/engine/install/ubuntu/) — GPG key setup, apt repo, package names. HIGH confidence.
- [Docker post-install steps — official docs](https://docs.docker.com/engine/install/linux-postinstall/) — docker group, systemd enable. HIGH confidence.
- [WSL systemd support — Microsoft Learn](https://learn.microsoft.com/en-us/windows/wsl/systemd) — wsl.conf `[boot]` section, WSL version requirements, systemd default for Ubuntu. HIGH confidence.
- [codestudy.net — WSL2 docker auto-start options](https://www.codestudy.net/blog/sudo-systemctl-enable-docker-not-available-automatically-run-docker-at-boot-on-wsl2-using-a-sysvinit-init-command-or-a-workaround/) — sysvinit vs systemd comparison, wsl.conf boot command pattern. MEDIUM confidence (single non-official source, consistent with Microsoft docs).
- [ShellCheck — static analysis for shell scripts](https://www.shellcheck.net/) — tool for script quality. HIGH confidence.
- `scripts/install.sh` in this repo — reviewed directly. Existing structure and Docker detection logic. HIGH confidence (source of truth).
- `docker-compose.yml` in this repo — reviewed directly. Actual container names (`lpg-db`, `lpg-api`, etc.). HIGH confidence.

---

*Stack research for: Kerala LPG Delivery Route Optimizer v1.3 — Office-Ready Deployment*
*Researched: 2026-03-04*
