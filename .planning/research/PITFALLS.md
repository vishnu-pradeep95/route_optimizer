# Pitfalls Research

**Domain:** Deployment automation and user-facing documentation for Docker Compose app — non-technical office users on WSL2/Windows
**Researched:** 2026-03-04
**Confidence:** HIGH (WSL/Docker issues verified against official docs and community issue trackers; CSV encoding and install script patterns verified via multiple sources)

---

## Critical Pitfalls

### Pitfall 1: Docker Does Not Start Automatically After Windows Reboot

**What goes wrong:**
WSL2 does not run systemd by default. Docker's daemon (`dockerd`) is not started on WSL launch unless explicitly configured. Every time the office employee restarts their Windows laptop, WSL opens, they `cd routing_opt`, and `docker compose up -d` fails with "Cannot connect to the Docker daemon at unix:///var/run/docker.sock". The fix is `sudo service docker start` — but this requires knowing why it failed, knowing the command, and knowing that the password prompt is coming. A non-technical user will see the cryptic error and stop.

The current DEPLOY.md Quick Reference already lists `sudo service docker start` as step 2 in the daily workflow. But it requires the WSL sudo password, which the employee may have forgotten if they set it months ago during install and never typed it since.

**Why it happens:**
WSL2 uses a stripped-down init system. The `service` command works, but services do not persist across WSL restarts (which happen every Windows reboot). Docker Desktop avoids this problem by running as a Windows service, but this project installs Docker Engine directly in WSL (not Docker Desktop) to avoid the Docker Desktop license requirement and simplify networking.

**How to avoid:**
Configure `/etc/wsl.conf` during install to auto-start Docker on WSL launch:
```ini
[boot]
command="service docker start"
```
This eliminates the manual `sudo service docker start` step entirely. The `install.sh` script should write this config. After writing it, the startup script becomes just `docker compose up -d` — one command, no password.

Alternative: add `sudo service docker start 2>/dev/null` to the user's `~/.bashrc` (already mentioned in SETUP.md but not yet in `install.sh`).

**Warning signs:**
- DEPLOY.md daily workflow requires 3 separate commands to start (service start, compose up, activate venv)
- The install script does not write `/etc/wsl.conf`
- Testing install on fresh WSL without rebooting Windows — the Docker auto-start issue only appears after a reboot

**Phase to address:** Install script phase — add `/etc/wsl.conf` boot command during installation. The daily startup script must work with zero prerequisite knowledge after reboot.

---

### Pitfall 2: OSRM Init Container Silently OOM-Kills on 8 GB Laptops

**What goes wrong:**
OSRM `osrm-extract` preprocessing of Kerala OSM data requires approximately 3-4 GB of RAM. On a Windows laptop with 8 GB total RAM, WSL2 gets roughly 4 GB by default (half of physical RAM). Docker runs inside WSL2. When `osrm-extract` runs inside `docker compose up -d`, it may exceed available memory and get killed by the Linux OOM killer — silently. The `osrm-init` container exits with code 137 (OOM kill). `docker compose ps` shows `osrm-init` as "Exited (137)", the `osrm` service never starts (waiting on `service_completed_successfully`), the API never starts, and the health check in `install.sh` times out after 300 seconds. The error shown is the generic timeout message with "check `docker compose logs -f osrm-init`" — which requires the user to know what OOM means.

The current `install.sh` has a 300-second timeout and tells users to check logs on failure. But a non-technical user cannot diagnose OOM from container exit codes.

**Why it happens:**
WSL2's default memory allocation is 50% of physical RAM or 8 GB, whichever is lower. On 8 GB machines, that is 4 GB for WSL2 total. Docker's overhead, PostgreSQL, and the running OSRM extraction all compete for this 4 GB. The OSRM backend image's `osrm-extract` is known to be memory-hungry and does not gracefully degrade when OOM.

**How to avoid:**
1. Before starting `osrm-init`, the install script must check WSL2 memory and warn if it is below 5 GB:
   ```bash
   WSL_MEM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
   WSL_MEM_GB=$((WSL_MEM_KB / 1024 / 1024))
   if [ "$WSL_MEM_GB" -lt 5 ]; then
       warn "Only ${WSL_MEM_GB}GB available — OSRM may fail. Configure .wslconfig first."
       # Print .wslconfig instructions
   fi
   ```
2. Print `.wslconfig` instructions at the start of the install (not buried in SETUP.md "Deploying on new laptop" section). The current SETUP.md mentions this but only in a "common issues" appendix.
3. If `osrm-init` exits 137, the startup script should detect this specifically and print a clear OOM message, not the generic timeout message.

**Warning signs:**
- Install tested only on 16 GB dev machine, not on the target 8 GB office laptop
- `.wslconfig` instructions appear only in SETUP.md, not surfaced during install
- `osrm-init` exit code not checked separately from health check timeout in `install.sh`

**Phase to address:** Install script phase — add memory check before OSRM init, add `.wslconfig` guidance early in the install output, and add specific OOM detection to the failure path.

---

### Pitfall 3: "One-Command Install" Breaks When Run From Windows Context

**What goes wrong:**
A non-technical user reads `git clone <URL>` in DEPLOY.md and runs it in PowerShell or Windows Command Prompt rather than the Ubuntu terminal. The clone succeeds, creating the repository in the Windows filesystem (`C:\Users\...`). Then they open Ubuntu and follow the next steps. The project files are now at `/mnt/c/Users/.../routing_opt/` — accessible from WSL, but with three major problems:
1. Shell scripts cloned via Windows git have CRLF line endings. `./scripts/install.sh` fails immediately: `/bin/bash^M: bad interpreter`.
2. File permissions are wrong. Every file is 0777 (NTFS doesn't carry Unix permissions). `chmod +x scripts/install.sh` has no effect because the permission bits are fake.
3. Performance. `docker compose up` bind-mounts `./data/osrm` — which is a Windows filesystem path. OSRM preprocessing I/O goes through the WSL-Windows translation layer, making it 10-100x slower than native ext4.

**Why it happens:**
Non-technical users do not know that "Ubuntu terminal" and "Windows PowerShell" are different environments. The DEPLOY.md section "Step 2.3" says "in the Ubuntu terminal" but this instruction is easily missed when the user is scanning for a command to copy. The git clone command looks the same in both terminals. The CRLF issue is especially subtle because the file opens fine in Windows Notepad but fails in bash.

**How to avoid:**
1. DEPLOY.md must have a prominent warning box before the git clone step: "IMPORTANT: All commands in this guide must be run in the Ubuntu window, not in PowerShell or Windows Command Prompt."
2. The install script should detect if it is running from `/mnt/c/` (Windows filesystem) and abort with a clear message:
   ```bash
   if [[ "$(pwd)" == /mnt/* ]]; then
       error "Do not run from the Windows filesystem (/mnt/c/...)."
       echo "  Clone the repository inside WSL: cd ~ && git clone ..."
       exit 1
   fi
   ```
3. The git clone instruction in DEPLOY.md should show the clone being run inside Ubuntu with the result landing in the Linux home directory (`~/routing_opt`), not an ambiguous `<anywhere>`.

**Warning signs:**
- DEPLOY.md does not visually distinguish "Ubuntu terminal" steps from "Windows" steps
- Git clone command shown without specifying which terminal to use
- `install.sh` has no check for Windows filesystem paths

**Phase to address:** Documentation phase (DEPLOY.md rewrite) and install script phase (filesystem check). Both must land together — the doc tells users where to clone, the script catches the mistake if they ignore the doc.

---

### Pitfall 4: Interactive `read` Prompts Hang When Install Script Is Piped

**What goes wrong:**
The current `install.sh` uses `read -rp` to prompt for database password and API key. If a user follows a "one-line install" pattern (common in tutorials: `curl -s URL | bash` or `bash <(curl -s URL)`), the script hangs indefinitely at the first `read` prompt. The terminal shows nothing. Stdin is not a terminal, so `read` blocks forever. The user has to Ctrl+C and start over.

Even in normal use, `read -rp` has a subtler problem: if the user pastes a command from DEPLOY.md that includes a trailing newline or space, the read may consume it and set the password to an empty string, falling back to the generated default — which was never shown to the user (it appears before the prompt, which they scrolled past).

**Why it happens:**
`read -rp` is designed for interactive shells. It has no timeout and no non-interactive fallback. Developers test install scripts interactively and never pipe them, so they never encounter the hang.

**How to avoid:**
Two changes:
1. Check `[ -t 0 ]` before using `read`. If stdin is not a terminal, skip all prompts and use generated defaults, then print "Running non-interactively — using auto-generated credentials."
2. Show the generated default at the same line as the prompt (current install.sh already does this with `[$DEFAULT_DB_PASS]`), but also print the final used value clearly after prompt resolution, so users who press Enter know what was chosen:
   ```bash
   info "Using password: ${DB_PASS:0:4}**** (auto-generated)"
   ```
3. Do NOT support `curl | bash` in docs. Direct users to clone the repo and run the script from disk — this is safer (allows script inspection) and avoids the pipe stdin issue.

**Warning signs:**
- Install script docs show a `curl | bash` pattern
- `install.sh` has no `[ -t 0 ]` stdin check
- Generated default password is not confirmed/printed after prompt

**Phase to address:** Install script phase — add stdin detection and non-interactive mode before publishing the one-command workflow.

---

### Pitfall 5: Documentation Written for Developers, Not Read by Office Staff

**What goes wrong:**
The current DEPLOY.md is well-written but structured like a developer guide: numbered steps, technical prerequisites, code blocks with explanations. Office staff who are the actual target user read the first two paragraphs and hand the laptop to IT. Specifically:
- The "Quick Start (3 Steps)" at the top requires Docker and Git to already be installed — exactly what the non-technical user does not have. It sends them to "Section 2 below" which starts with PowerShell Admin commands, WSL installation, and Linux terminal concepts.
- The troubleshooting section lists bash commands as the fix. A non-technical user who sees "Cannot connect to Docker daemon" will not know to run `sudo service docker start`. They will close the terminal and ask IT.
- The daily startup is 3 separate commands (`cd routing_opt`, `sudo service docker start`, `docker compose up -d`) that must be remembered and typed in order every morning.

**Why it happens:**
Documentation is written by developers who can read it. Non-technical users have fundamentally different mental models: they expect one button, not three commands. "Documentation pitfall: overwhelming instructions cause users to skip steps or not try at all."

**How to avoid:**
1. Create a `start.sh` daily startup script that wraps all daily operations into one command: starts Docker, brings up compose, verifies health, opens the browser URL. Users bookmark this script.
2. Provide a Windows `.bat` file that opens Ubuntu and runs `start.sh` — double-clickable from the desktop.
3. Structure DEPLOY.md in two clearly separated sections: "First-Time Setup (do once, needs IT help)" and "Daily Use (you do this yourself every morning)". The daily use section must fit on one printed page.
4. Replace troubleshooting bash commands with decision trees: "Is the error on the blue screen or the black screen?" → "Black screen: type `sudo service docker start` then press Enter." Print the decision tree and tape it next to the monitor.

**Warning signs:**
- Daily startup section requires 3+ separate commands
- No `.bat` file or desktop shortcut for Windows users
- Troubleshooting fixes require bash commands without explaining what they do

**Phase to address:** Documentation phase — the daily-use guide must be redesigned for the actual user before it is published. The install guide can remain technical (IT staff does it once). The daily guide must be non-technical.

---

### Pitfall 6: CSV Documentation Describes the System's Internal State, Not the User's Actual File

**What goes wrong:**
The current DEPLOY.md section "Understanding the CDCMS Export" documents the CDCMS columns with internal system names (`order_id`, `address`, `quantity`) rather than the actual column names in the exported file (`OrderNo`, `ConsumerAddress`, `OrderQuantity`). It shows "after preprocessing" output but not what happens when a column is missing, renamed, or has unexpected values. The "Sample CDCMS Row" shows a manually formatted example, not a copy-pasteable real row from the export.

Non-technical users hit three predictable CSV problems:
1. They export from a different CDCMS page (e.g., "all orders" instead of "allocated orders") and get a different column set. The system fails with "missing required columns" — a technical error they do not understand.
2. They save the CDCMS export as `.xlsx` (default when they open it in Excel to "check it"). The upload rejects it or silently misparses it.
3. They use the wrong delivery status filter. CDCMS has multiple status values ("Allocated", "Allocated-Printed", "Delivered", "Cancelled"). The system only processes "Allocated-Printed". If they export before printing allocation slips, zero orders come through.

**Why it happens:**
Documentation written after the system was built describes how the code processes the file. The user's actual question is "what do I export and how do I know it's right?" — a workflow question, not a schema description.

**How to avoid:**
1. CSV documentation must show the exact CDCMS export steps with screenshots, not just the file format.
2. Document the exact failure messages and what they mean: "Missing required columns: OrderNo" means you exported from the wrong page. "No orders remain after filtering" means no "Allocated-Printed" orders exist — check the Status column.
3. Explicitly warn: do NOT open the CSV in Excel before uploading. If you opened it, save it as CSV (UTF-8) not XLSX.
4. Show a minimal example using actual CDCMS column names as headers: `OrderNo\tOrderStatus\tConsumerAddress\t...` (tab-separated, as it actually exports).
5. Add a "Pre-upload checklist" to the docs: (1) Did you export from the Delivery Allocation page? (2) Is the file named `.csv` not `.xlsx`? (3) Does it have "Allocated-Printed" in the OrderStatus column?

**Warning signs:**
- Documentation shows "after preprocessing" column names without showing the original CDCMS column names
- No warning about not opening in Excel before uploading
- No mention of what "Allocated-Printed" status means or how to verify the export has it

**Phase to address:** CSV documentation phase — write documentation from the CDCMS export workflow backward to the system's expectations, not forward from the system's schema.

---

### Pitfall 7: `osrm/osrm-backend:latest` Image Tag Causes Silent Version Drift

**What goes wrong:**
The `docker-compose.yml` uses `osrm/osrm-backend:latest` for both `osrm-init` and `osrm`. When OSRM releases a new major version that changes the preprocessing pipeline or data format, `docker compose pull` (run during updates) fetches the new version. The newly pulled image may be incompatible with the already-preprocessed data in `data/osrm/`. Result: `osrm-init` skips preprocessing (data exists), but `osrm` fails to start because the `.osrm` files were preprocessed with an older version. The error is "invalid MLD graph data" or similar — incomprehensible to a non-technical user. Worse, this happens silently on the next update, weeks or months after initial install.

**Why it happens:**
`latest` means "most recently pushed tag" not "most stable release." Using `latest` is universally flagged as a bad practice in production Docker deployments. Developers use `latest` during development to avoid specifying versions, but never pin before shipping. The OSRM project regularly breaks backward compatibility in data format between major versions.

**How to avoid:**
Pin both `osrm-init` and `osrm` to a specific version tag (e.g., `osrm/osrm-backend:v5.27.1`). When upgrading OSRM, explicitly bump the version in `docker-compose.yml` AND delete the preprocessed data directory to force re-preprocessing with the new version. Document the upgrade procedure in DEPLOY.md.

Additionally, the `osrm-init` idempotency check (`if [ -f /data/kerala-latest.osrm.mldgr ]`) does not verify that the existing data is compatible with the current OSRM version. Add a version marker file during preprocessing that records the OSRM version used.

**Warning signs:**
- `docker-compose.yml` uses `:latest` for any OSRM image
- No documented OSRM version upgrade procedure
- `osrm-init` idempotency check is file-existence only, not version-verified

**Phase to address:** Install script / Docker Compose hardening phase — pin image versions before v1.3 ships. This affects long-term maintenance, not just initial install.

---

## Moderate Pitfalls

### Pitfall 8: WSL Sudo Password Required Daily — Users Forget It

**What goes wrong:**
If `/etc/wsl.conf` auto-start is not configured (see Pitfall 1), the daily workflow requires `sudo service docker start`, which prompts for the WSL sudo password. The office employee set this password during WSL installation (DEPLOY.md Step 2.1) and may not have typed it since. Forgotten sudo passwords require WSL user reset — a technical procedure. In the interim, the system is unusable.

**How to avoid:**
1. Primary fix: configure `/etc/wsl.conf` boot command so Docker starts automatically, eliminating the sudo requirement entirely.
2. Secondary fix: during install, configure passwordless sudo for `service docker start` specifically:
   ```bash
   echo "$USER ALL=(ALL) NOPASSWD: /usr/sbin/service docker start" | sudo tee /etc/sudoers.d/docker-start
   ```
   This scopes the passwordless access to exactly one command, avoiding broad passwordless sudo.
3. DEPLOY.md must include a "Forgot your password?" recovery procedure (WSL user reset instructions for non-technical users).

**Warning signs:**
- `install.sh` does not configure `/etc/wsl.conf` auto-start
- No passwordless sudo for the specific docker start command
- DEPLOY.md has no password recovery instructions

**Phase to address:** Install script phase — configure auto-start during install, with passwordless sudo as backup.

---

### Pitfall 9: Google Maps API Key Prompts Blocked by IT Security Policy

**What goes wrong:**
The install script prompts for a Google Maps API key. In a corporate environment (which this is — an HPCL-affiliated office), IT security policies may restrict who can create Google Cloud accounts and API keys, or may require billing account approval. The office employee running the install cannot create the key themselves and must escalate to IT or management — but the install script is blocked waiting for their answer.

Additionally, the DEPLOY.md documents obtaining the API key in one line: "ask technical team." There is no documentation of what the key must be authorized for (Geocoding API specifically, not Maps JavaScript API), what quota limits to set, or what a suspicious usage spike looks like (could indicate key leak or unexpected billing).

**How to avoid:**
1. The install script must handle the case where no Google Maps API key is provided at install time. The system should start and be functional without geocoding — the dashboard should show a clear "Geocoding not configured" warning rather than failing to start.
2. Provide a dedicated "Google Maps API Key Setup" section in DEPLOY.md with screenshots: Google Cloud Console → APIs & Services → Credentials → Create API Key → Restrict to Geocoding API → Set daily quota to 500 requests (well within free tier).
3. Document the API key quota: Geocoding API free tier is 40,000 requests/month ($200 credit). At ~50 new addresses per day, this system will never exceed the free tier. Document this explicitly so management understands there is no ongoing cost.
4. Warn to set a max daily quota (500 requests) in Google Cloud Console to protect against accidental runaway geocoding or key leaks.

**Warning signs:**
- Install script exits/fails if Google Maps API key is not provided
- No standalone Google Maps setup documentation separate from the install guide
- No mention of quota limits or billing protection in the docs

**Phase to address:** Documentation phase — write the Google Maps setup section as a standalone procedure. Install script phase — make the API key optional at install time.

---

### Pitfall 10: `/mnt/c/Users/.../Downloads` Path in DEPLOY.md Requires Username Substitution

**What goes wrong:**
DEPLOY.md Step 3.2 shows:
```bash
cp /mnt/c/Users/YOUR_USERNAME/Downloads/cdcms_export.csv data/cdcms_export.csv
```
Non-technical users copy this literally, including `YOUR_USERNAME`. The command fails with "No such file or directory." They do not understand what "replace with your Windows username" means — they may not know their Windows username, or may not know it differs from their Ubuntu username.

This is a predictable copy-paste failure. The documentation pattern of `YOUR_VARIABLE` substitution is understood by developers but not by non-technical users.

**How to avoid:**
1. Provide the command with automatic substitution using the Windows username from the environment:
   ```bash
   # First, find your Windows username:
   ls /mnt/c/Users/
   # Then copy the file (replace USERNAME with what you see above):
   cp /mnt/c/Users/USERNAME/Downloads/cdcms_export.csv data/cdcms_export.csv
   ```
2. Better: include a utility function in `start.sh` or a separate `import.sh` that auto-detects the Windows Downloads folder:
   ```bash
   WIN_USER=$(ls /mnt/c/Users/ | grep -v 'Public\|Default\|All Users' | head -1)
   cp "/mnt/c/Users/$WIN_USER/Downloads/cdcms_export.csv" data/cdcms_export.csv
   ```
3. Consider: document the drag-and-drop upload workflow in the dashboard as the primary method (avoids the path issue entirely). The CLI copy command should be secondary/troubleshooting.

**Warning signs:**
- DEPLOY.md uses `YOUR_USERNAME` placeholder in bash commands
- No helper script for the Windows → WSL file copy operation
- Dashboard drag-and-drop upload is not documented as the primary daily workflow

**Phase to address:** Documentation phase and daily-startup-scripts phase — the file copy helper should be in the daily startup toolkit, not just documented as a bare bash command.

---

### Pitfall 11: README.md Stale Container Names Break Copy-Paste Troubleshooting

**What goes wrong:**
The current README.md (and possibly DEPLOY.md) references container names that do not match `docker-compose.yml`. Example: if documentation says `docker logs api` but the container is named `lpg-api` (as in `container_name: lpg-api`), users trying to diagnose problems by copying from the docs get "Error: No such container: api." Stale container names are a common documentation debt that accumulates silently.

In this project specifically, the milestone goal explicitly includes "fix stale container names" — confirming this problem exists.

**How to avoid:**
1. Audit every occurrence of container names in all documentation files against `docker-compose.yml`'s `container_name:` fields.
2. Add a documentation validation step: a script that extracts container names from `docker-compose.yml` and searches for mismatches in `*.md` files.
3. In documentation, prefer `docker compose logs -f <service-name>` (compose service name, e.g., `api`) over `docker logs <container-name>` (e.g., `lpg-api`). The compose service name is stable and defined in the docs; the container name is a deployment detail.

**Warning signs:**
- `README.md` contains any `docker logs` commands using plain names (`api`, `osrm`, `db`) that differ from `container_name:` in `docker-compose.yml`
- No automated check for documentation/config alignment

**Phase to address:** Documentation phase — must be fixed before publishing v1.3 docs. Container name audit should be the first documentation task.

---

### Pitfall 12: Health Check Timeout Hides Which Service is Actually Stuck

**What goes wrong:**
`install.sh` polls `http://localhost:8000/health` for up to 300 seconds. If any upstream service fails (OSRM, VROOM, PostgreSQL, the API itself), the health endpoint never responds and the script exits with the generic timeout message:
```
System did not become healthy within 300 seconds.
Check progress with:
  docker compose logs -f osrm-init
  docker compose logs -f db-init
```
A non-technical user has no way to know which of four services is stuck, or what to look for in the logs. They will see one of: OOM kill (OSRM), PostgreSQL password mismatch, VROOM config error, or API startup crash — all producing different log output.

**Why it happens:**
The health check is a single endpoint poll. It gives no intermediate feedback about which services started successfully. The user waits 5 minutes then sees a failure message with no diagnosis.

**How to avoid:**
During the wait loop, poll individual service statuses and report progress:
```bash
# Every 30 seconds during the wait:
echo "  DB: $(docker inspect --format='{{.State.Status}}' lpg-db 2>/dev/null || echo 'not started')"
echo "  OSRM init: $(docker inspect --format='{{.State.Status}}' osrm-init 2>/dev/null || echo 'not started')"
echo "  API: $(docker inspect --format='{{.State.Status}}' lpg-api 2>/dev/null || echo 'not started')"
```
On timeout, automatically check exit codes and show targeted diagnostics:
- `osrm-init` exit 137 → "OSRM ran out of memory. Add more RAM in .wslconfig."
- `db-init` non-zero → "Database migration failed." + last 10 lines of db-init logs
- `lpg-api` not started → "API failed to start." + last 10 lines of api logs

**Warning signs:**
- `install.sh` wait loop only polls the final health endpoint
- On timeout, user is told to manually check logs with no guidance on what to look for
- No per-service status reporting during the 5-minute wait

**Phase to address:** Install script phase — add intermediate progress reporting and automatic failure diagnosis.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Using `osrm/osrm-backend:latest` image tag | No version pinning maintenance | OSRM major version breaks existing preprocessed data silently on `docker compose pull` | Never for production/office use — pin to specific version |
| Hardcoding `/mnt/c/Users/YOUR_USERNAME/` in docs | Simple to write | Every user fails the copy command; generates IT support requests | Never — provide auto-detection or use dashboard upload |
| Documenting `sudo service docker start` as daily step | Covers WSL Docker startup | Users forget the sudo password; system unusable until IT reset | Only as fallback — primary path should be auto-start |
| Interactive `read` prompts in install script | Familiar UX for developers | Breaks when piped, blocks CI, hangs on passwordless stdin | Acceptable if stdin-detection is added |
| Combining first-time setup and daily use in one DEPLOY.md | Single document to maintain | Non-technical users must re-read all the install steps to find the daily workflow | Never — split into INSTALL.md (IT, once) and DAILY.md (office, every day) |

---

## Integration Gotchas

Common mistakes when connecting to external services or subsystems.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| OSRM data + Docker image versioning | Checking data existence but not version compatibility during `osrm-init` idempotency | Write a version marker file during preprocessing; `osrm-init` checks the marker matches current image version |
| Google Geocoding API + `.env` setup | Telling users to "paste the key" without explaining which APIs to enable or how to restrict the key | Document exact Google Cloud Console steps: enable "Geocoding API" (not "Maps JavaScript API"), restrict key to Geocoding API only, set daily quota to 500 |
| WSL2 `/mnt/c/` filesystem + Docker bind mounts | Bind-mounting `./data/osrm` when the project lives in `/mnt/c/...` | Project must live in WSL Linux filesystem (`~/routing_opt`), not Windows filesystem — I/O through translation layer makes OSRM preprocessing 10x slower |
| Docker Compose `service_completed_successfully` + `--wait-timeout` | Assuming `docker compose up --wait` correctly waits for init containers | Known bug (docker/compose#12134): `--wait-timeout` hangs when `service_completed_successfully` conditions are involved — use manual health polling instead |
| CDCMS CSV + Excel | Users opening CSV in Excel before uploading | Excel resaves as XLSX or adds BOM, breaking tab-detection. Warn explicitly: do not open in Excel, upload the file directly from the Downloads folder |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| OSRM preprocessing on Windows filesystem | `osrm-extract` takes 60+ minutes instead of 10 | Ensure project is cloned inside WSL Linux filesystem (`~/routing_opt`), not `/mnt/c/...` | Always on Windows filesystem; 10x slower regardless of machine specs |
| `docker compose up -d --build` in daily startup | Rebuilds API image every morning (slow) | Daily startup script should use `docker compose up -d` without `--build`; only rebuild after git pull | Adds 2-3 minutes to daily startup if API image rebuilds every time |
| No WSL memory limit configured | `VmmemWSL` process consumes all Windows RAM, laptop slows to crawl | Add `memory=6GB` to `%USERPROFILE%\.wslconfig`; leave 2GB for Windows | On 8 GB laptops immediately; on 16 GB laptops only under heavy Docker load |
| Health check polling every 5 seconds for 300 seconds | 60 curl calls during startup; excessive noise in logs | Poll less frequently (15s intervals) with clear progress output; total wait can be 300s but polling less aggressively | Not a scaling issue — a UX issue visible immediately on every install |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Printing API key in install script terminal output ("Save this API key") | Key visible in terminal scrollback, shared screenshots, copy-paste to wrong chat | Print key once, immediately instruct user to save it, offer to write it to a `credentials.txt` file; never log it in a file automatically |
| Google Maps API key with no quota limit | If key is leaked (e.g., committed to git), unlimited billing accumulates | Always configure `500 requests/day` hard cap in Google Cloud Console during setup; document this as mandatory |
| `.env` file not in `.gitignore` | Passwords and API keys committed to git repo | Verify `.env` is in `.gitignore` before first commit; `install.sh` should check this after creating `.env` |
| Passwordless sudo for `service docker start` too broadly scoped | `NOPASSWD: ALL` for convenience gives full root access | Scope sudoers rule to `/usr/sbin/service docker start` only — one command |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Daily workflow requires 3 typed commands | User forgets one; system in bad state; blamed on "the software" | Single `./start.sh` that handles all startup steps and opens browser; Windows `.bat` shortcut |
| Success output shows localhost URLs without explaining that Chrome must be used | User opens URL in Edge or Firefox; minor layout differences cause confusion | DEPLOY.md and startup output say explicitly "Open Chrome" not just "open in a browser" |
| Troubleshooting section uses bash jargon ("check the logs", "inspect the container") | Non-technical user cannot act on this; escalates every error to IT | Decision tree format: "Does the black screen show 'error'? Yes → type X. No → try Y." |
| "Installation complete!" shown before verifying the dashboard actually loads | User thinks it worked; first actual use fails because VROOM is not ready | Health check must include a VROOM and OSRM check, not just the API `/health` endpoint |
| CSV format documentation buried in Section 4 of DEPLOY.md | User uploads wrong file, gets cryptic error, gives up | Put a "Quick CSV Check" at the top of the daily workflow section, before the upload step |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **install.sh:** Configures `/etc/wsl.conf` boot command so Docker starts automatically after Windows reboot
- [ ] **install.sh:** Checks available WSL2 memory before starting OSRM init and warns if below 5 GB
- [ ] **install.sh:** Detects if running from `/mnt/c/` and aborts with clear message
- [ ] **install.sh:** Handles `osrm-init` exit code 137 (OOM kill) with a specific, actionable error message
- [ ] **install.sh:** Checks that stdin is a terminal before using `read` prompts
- [ ] **install.sh:** Pins OSRM image tag to a specific version, not `:latest`
- [ ] **start.sh:** Exists as a single daily-startup script wrapping all required steps
- [ ] **start.sh:** Opens the dashboard URL in Chrome as its final step
- [ ] **DEPLOY.md:** Prominently warns that all commands must be run in the Ubuntu terminal, not PowerShell
- [ ] **DEPLOY.md:** Shows git clone landing in `~/routing_opt` (Linux home), not an ambiguous path
- [ ] **DEPLOY.md:** Has a "Daily Use" section that fits on one printed page
- [ ] **DEPLOY.md:** Documents exact CDCMS export steps (which page, which filters) not just the CSV column schema
- [ ] **DEPLOY.md:** Warns not to open the CSV in Excel before uploading
- [ ] **DEPLOY.md:** Includes Google Maps API key setup with screenshots/steps for each click in Google Cloud Console
- [ ] **DEPLOY.md:** All `docker logs` commands use compose service names, not container names (verified against docker-compose.yml)
- [ ] **README.md:** All container names match `container_name:` in `docker-compose.yml`
- [ ] **Troubleshooting:** Each error message has a matched entry with human-readable explanation and exact command to run

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Docker not starting after reboot | LOW | User types `sudo service docker start` then `docker compose up -d`; if password forgotten, IT resets WSL user password via `wsl --user root passwd username` |
| OSRM OOM kill during install | MEDIUM | Add `memory=6GB` to `%USERPROFILE%\.wslconfig`, run `wsl --shutdown`, re-run `./scripts/install.sh` (OSRM init is idempotent — will retry preprocessing) |
| Project cloned on Windows filesystem | MEDIUM | `cd ~ && git clone <URL> routing_opt`, then re-run `./scripts/install.sh`; the original Windows-path clone can be deleted from Windows Explorer |
| Google Maps API key not available | LOW | System runs without geocoding; new addresses fail with a visible error in the dashboard; install proceeds; key can be added to `.env` later and services restarted |
| User opened CSV in Excel and saved as XLSX | LOW | Re-export from CDCMS, upload the `.csv` directly without opening in Excel |
| Forgotten WSL sudo password | MEDIUM | From Windows: `wsl --user root` then `passwd username`; document this recovery in DEPLOY.md with step-by-step instructions |
| OSRM data format incompatible after image version drift | HIGH | Delete `data/osrm/` directory, pin the correct image version in `docker-compose.yml`, re-run `docker compose up -d` to re-preprocess (10-20 minutes) |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Docker not auto-starting after reboot | Install script | Test: install, restart Windows, open Ubuntu, run `docker compose up -d` without any prior commands — must succeed |
| OSRM OOM kill on 8 GB laptop | Install script | Test on machine with 4 GB WSL2 allocation; script must detect and warn before attempting preprocessing |
| Install run from Windows filesystem | Install script | Test: clone to `/mnt/c/Users/test/routing_opt`, run `./scripts/install.sh` — must abort with clear message |
| Interactive `read` hangs when piped | Install script | Test: `echo "" \| ./scripts/install.sh` — must not hang |
| Documentation not readable by non-technical users | Documentation phase | Hand DEPLOY.md to someone who has never used a terminal; measure how far they get unassisted |
| CSV docs describe internals not workflow | Documentation phase | Office employee uses only the CSV docs section to diagnose a "missing columns" error — can they self-recover? |
| OSRM image version drift | Docker Compose hardening | `docker-compose.yml` contains no `:latest` tags for OSRM; version pinning documented in DEPLOY.md |
| Path substitution in docs (`YOUR_USERNAME`) | Documentation + daily scripts | `import.sh` script tested by running it with zero knowledge of Windows username |
| Stale container names in docs | Documentation phase | Automated grep of all `.md` files for container names cross-checked against `docker-compose.yml` |
| Unclear which service is stuck during install | Install script | Timeout path prints per-service status and specific OOM/crash diagnosis |

---

## Sources

- [Docker Docs: WSL2 best practices](https://docs.docker.com/desktop/features/wsl/best-practices/)
- [Docker Docs: WSL2 containers tutorial (Microsoft Learn)](https://learn.microsoft.com/en-us/windows/wsl/tutorials/wsl-containers)
- [Docker service not auto-starting in WSL — microsoft/WSL#13106](https://github.com/microsoft/WSL/issues/13106)
- [Docker compose --wait-timeout bug with service_completed_successfully — docker/compose#12134](https://github.com/docker/compose/issues/12134)
- [WSL2 file permissions and /mnt/c gotchas](https://www.turek.dev/posts/fix-wsl-file-permissions/)
- [CRLF line endings breaking bash scripts cloned on Windows — desktop/desktop#10461](https://github.com/desktop/desktop/issues/10461)
- [Docker latest tag pitfalls — vsupalov.com](https://vsupalov.com/docker-latest-tag/)
- [WSL2 memory configuration — ITNEXT](https://itnext.io/wsl2-tips-limit-cpu-memory-when-using-docker-c022535faf6f)
- [Google Maps Geocoding API billing and quotas](https://developers.google.com/maps/documentation/geocoding/usage-and-billing)
- [CSV/Excel encoding pitfalls (BOM, CRLF, XLSX)](https://hilton.org.uk/blog/csv-excel)
- [Bash pitfalls — Greg's Wiki](https://mywiki.wooledge.org/BashPitfalls)
- [Documentation for non-technical users — welcometothejungle.com](https://www.welcometothejungle.com/en/articles/btc-readme-documentation-best-practices)
- Codebase inspection: `scripts/install.sh` (interactive prompts, health check, OSRM init), `docker-compose.yml` (container names, `:latest` tags, `service_completed_successfully` conditions), `DEPLOY.md` (daily workflow, CSV docs, path substitution), `SETUP.md` (WSL memory hint buried in appendix)

---
*Pitfalls research for: Kerala LPG Delivery Route Optimizer — v1.3 Office-Ready Deployment*
*Researched: 2026-03-04*
