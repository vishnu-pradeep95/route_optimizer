# Phase 13: Bootstrap Installation - Context

**Gathered:** 2026-03-04
**Status:** Ready for planning

<domain>
## Phase Boundary

A non-technical office employee installs the entire system from a fresh WSL2 Ubuntu terminal with a single command (`bootstrap.sh`). The script auto-installs Docker CE, configures auto-start, validates the WSL environment, generates credentials, and delegates to the existing `install.sh` for Docker Compose orchestration. Environment guards catch WSL1, Windows filesystem paths, and low memory before proceeding.

</domain>

<decisions>
## Implementation Decisions

### Session restart flow
- Two-phase with auto-resume: bootstrap installs Docker CE, adds user to docker group, writes a marker file, then instructs user to close/reopen WSL
- On re-run, bootstrap detects the marker and resumes from install.sh automatically
- If Docker is already installed and user is in docker group, skip Docker install silently — jump straight to install.sh
- Restart message uses numbered steps with context: "Step 1: Close this Ubuntu window. Step 2: Open Ubuntu again from Start menu. Step 3: cd routing_opt && ./bootstrap.sh"

### Interactive prompts
- Fully automatic — zero prompts during bootstrap
- Bootstrap generates .env itself (PostgreSQL password + API key auto-generated) before calling install.sh
- install.sh already skips .env creation if .env exists — no changes to install.sh needed
- Credentials printed once in the final success banner for IT reference, no separate credentials file
- Both entry points work: bootstrap.sh for fresh installs, install.sh standalone for developers

### Google Maps API key
- Pre-baked by developer before customer delivery — employee never sees it
- Key lives in `.env.example` with the real value filled in before delivery
- Bootstrap copies `.env.example` to `.env` (with auto-generated DB password + API key overriding template values)
- `.env.example` committed in private repo — no gitignore needed for customer-specific deliveries

### Output & messaging
- Step-by-step with progress: "Step 1/4: Installing Docker... done", "Step 2/4: Downloading Kerala map data (this takes ~10 min)...", spinner during waits
- RAM warning: yellow warning with .wslconfig instructions, continues automatically (does not block install)
- Final success banner: Dashboard URL, Driver App URL, daily workflow steps (upload CSV, print QR, hand to drivers)
- WSL1 and /mnt/c/ errors: plain English with numbered fix steps, hand-holding for non-technical audience

### Claude's Discretion
- Resume marker file location (project root vs home directory)
- Exact Docker CE installation commands (apt repository setup)
- WSL1 vs WSL2 detection method
- RAM detection approach and threshold display
- wsl.conf configuration for Docker auto-start
- Spinner/progress indicator implementation

</decisions>

<specifics>
## Specific Ideas

- install.sh already has colored output helpers (info/success/warn/error/header) — bootstrap should use the same style for visual consistency
- install.sh health polling loop with spinner is a good pattern to reuse
- The .env.example approach means bootstrap's .env generation must: (1) copy .env.example, (2) override POSTGRES_PASSWORD and API_KEY with auto-generated values, (3) preserve GOOGLE_MAPS_API_KEY from the template

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/install.sh`: Full install pipeline (prereq check, .env, docker compose up, health poll) — bootstrap delegates to this after Docker is ready
- `scripts/install.sh` color helpers: GREEN/YELLOW/RED/BLUE/BOLD/NC with info()/success()/warn()/error()/header() functions
- `scripts/install.sh` health polling: spinner loop with HEALTH_URL, MAX_WAIT, POLL_INTERVAL pattern
- `scripts/install.sh` .env skip logic: "if [ -f .env ]; success '.env already exists'" — bootstrap pre-creates .env to leverage this

### Established Patterns
- Shell scripts use `set -euo pipefail` for safety
- Docker Compose health checks on db (pg_isready) and osrm (curl /health)
- Init containers (osrm-init, db-init) handle first-run setup idempotently
- Scripts live in `scripts/` directory

### Integration Points
- bootstrap.sh creates .env → install.sh reads it and skips creation
- bootstrap.sh installs Docker CE → install.sh checks `docker --version` (prereq passes)
- bootstrap.sh configures wsl.conf → Docker daemon auto-starts on subsequent WSL sessions
- docker-compose.yml depends_on chain: db → db-init → api, osrm-init → osrm → vroom → api

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 13-bootstrap-installation*
*Context gathered: 2026-03-04*
