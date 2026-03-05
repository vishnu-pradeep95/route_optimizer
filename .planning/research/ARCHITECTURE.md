# Architecture Research

**Domain:** Office-ready deployment scripting for a Docker Compose–based logistics system
**Researched:** 2026-03-04
**Confidence:** HIGH — all findings based on direct inspection of existing codebase

---

## System Overview — Existing State

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         EXISTING SCRIPT LAYER                               │
├──────────────────┬──────────────────┬──────────────────┬────────────────────┤
│  scripts/        │  scripts/        │  scripts/        │  scripts/          │
│  install.sh      │  deploy.sh       │  backup_db.sh    │  build-pwa-css.sh  │
│  (dev setup)     │  (prod deploy)   │  (cron backup)   │  (CSS build tool)  │
│                  │                  │                  │                    │
│  Assumes Docker  │  Uses prod env   │  Auto-detects    │  Requires          │
│  already present │  file, Caddy     │  dev vs prod     │  tailwindcss-extra │
└────────┬─────────┴────────┬─────────┴────────┬─────────┴────────────────────┘
         │                  │                  │
         ▼                  ▼                  ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                     DOCKER COMPOSE LAYER (unchanged in v1.3)                 │
├─────────────┬─────────────┬──────────────┬─────────────┬────────────────────┤
│  osrm-init  │    osrm     │    vroom     │   db-init   │       api          │
│  (one-shot) │  :5000      │   :3000      │  (one-shot) │     :8000          │
│  downloads  │ (routing)   │ (optimizer)  │  alembic    │  FastAPI +         │
│  + preproc  │             │              │  upgrade    │  static files      │
│  Kerala OSM │             │              │  head       │  driver PWA        │
│  Idempotent │             │              │  Idempotent │  dashboard         │
└─────────────┴─────────────┴──────────────┴─────────────┴────────────────────┘
                                    │
                                    ▼
                         ┌──────────────────────┐
                         │  db (PostGIS 16-3.5) │
                         │  :5432 (dev only)    │
                         │  pgdata named volume │
                         └──────────────────────┘
```

**Container names (actual, from docker-compose.yml):**
- `lpg-db` (dev) / `lpg-db-prod` (prod)
- `osrm-init` / `osrm-init-prod`
- `osrm-kerala` / `osrm-kerala-prod`
- `vroom-solver` / `vroom-solver-prod`
- `lpg-db-init` / `lpg-db-init-prod`
- `lpg-api` / `lpg-api-prod`

Note: README.md shows `routing-db` in its Docker Services table — this is stale and must be corrected.

---

## System Overview — Target State (v1.3 additions)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         NEW ENTRYPOINTS (v1.3)                              │
├──────────────────────────┬──────────────────────────────────────────────────┤
│      bootstrap.sh        │               start.sh                           │
│      (ONE-TIME, WSL)     │               (DAILY, all platforms)             │
│                          │                                                  │
│  1. apt-get: git, curl,  │  1. sudo service docker start (WSL daemon)      │
│     Docker CE, Compose   │  2. docker compose up -d                        │
│  2. usermod docker group │  3. curl /health until 200 (60s timeout)        │
│  3. git clone repo       │  4. print "Dashboard: http://localhost:8000/..."│
│  4. call install.sh      │                                                  │
└──────────────┬───────────┴────────────────┬─────────────────────────────────┘
               │                            │
               ▼                            ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│               EXISTING SCRIPT LAYER (install.sh gets minor update)          │
├──────────────────┬──────────────────┬──────────────────┬────────────────────┤
│  scripts/        │  scripts/        │  scripts/        │  scripts/          │
│  install.sh      │  deploy.sh       │  backup_db.sh    │  build-pwa-css.sh  │
│  (minor update)  │  NO CHANGE       │  NO CHANGE       │  NO CHANGE         │
└──────────────────┴──────────────────┴──────────────────┴────────────────────┘
                                    │
                             DOCKER COMPOSE LAYER (NO CHANGE)
```

---

## Component Responsibilities

### New Components

| Component | File | Purpose | Calls Into |
|-----------|------|---------|------------|
| WSL bootstrap | `bootstrap.sh` (project root) | Fresh machine setup: install Docker + Git, clone repo, delegate to install.sh | `scripts/install.sh` |
| Daily startup | `start.sh` (project root) | Every-morning startup: start Docker daemon, bring compose up, verify health | `docker compose up -d`, `curl /health` |

### Modified Components

| Component | File | Change | Scope |
|-----------|------|--------|-------|
| Project setup | `scripts/install.sh` | Minor: add guard checking if `.env` is missing and bootstrap context note in header | Documentation inside file only |
| Office guide | `DEPLOY.md` Section 3.1 | Replace 4-command daily startup block with `./start.sh` | Text change, Section 3.1 only |
| Office guide | `DEPLOY.md` Section 2.3 | Reference `bootstrap.sh` instead of manual Docker install blocks | Text change, Section 2.3 only |
| Developer guide | `README.md` Docker Services table | Fix stale container name `routing-db` → `lpg-db`, fix `routeopt` → `routing` | Text change, one table |

### Unchanged Components (DO NOT TOUCH)

| Component | Why Frozen |
|-----------|------------|
| `scripts/deploy.sh` | Production deployment; any regression here breaks live system |
| `scripts/backup_db.sh` | Container name detection logic at lines 37-46 is tightly coupled to `lpg-db`/`lpg-db-prod`; works correctly |
| `docker-compose.yml` | Changing container names to match stale docs would break `backup_db.sh` and `deploy.sh` |
| `docker-compose.prod.yml` | Production config; correct and stable |
| `scripts/build-pwa-css.sh` | Build utility; no deployment relationship |
| All API Python code | Out of scope for v1.3 |
| All React dashboard code | Out of scope for v1.3 |
| Driver PWA | Out of scope for v1.3 |

---

## Recommended Project Structure

```
routing_opt/
├── bootstrap.sh              # NEW: zero-to-running for fresh WSL install
├── start.sh                  # NEW: daily morning startup script
├── scripts/
│   ├── install.sh            # MINOR UPDATE: add bootstrap context note
│   ├── deploy.sh             # unchanged (production)
│   ├── backup_db.sh          # unchanged
│   ├── build-pwa-css.sh      # unchanged
│   └── osrm_setup.sh         # unchanged (manual OSRM rebuild)
├── DEPLOY.md                 # UPDATE: reference start.sh, fix container names
└── README.md                 # UPDATE: fix container name table
```

**Why at project root, not in `scripts/`?**

`bootstrap.sh` and `start.sh` are end-user entrypoints for non-technical office employees. The DEPLOY.md already directs the user to `cd routing_opt` then run commands. A root-level file means the instruction is simply `./start.sh`. Requiring `./scripts/start.sh` adds cognitive friction and a path to mistype. Developer scripts (backup, osrm setup, CSS build) belong in `scripts/` because developers know to look there.

---

## Architectural Patterns

### Pattern 1: Bootstrap Delegates to install.sh — No Logic Duplication

**What:** `bootstrap.sh` is a thin system-provisioning wrapper. It installs OS-level prerequisites (Docker, Git via apt-get), then calls `scripts/install.sh` for all project-level setup. Zero duplication of credential prompts, health checks, or compose logic.

**Why not merge Docker install into install.sh:** `install.sh` is also used by developers who already have Docker. Adding system-level install logic creates two paths (`if ! docker; then apt-get install...`) that complicate the existing clean flow and risk breaking developer workflows.

**Example:**
```bash
# bootstrap.sh structure (simplified)
install_docker()  # apt-get steps — only if not already present
clone_or_update() # git clone $REPO_URL routing_opt, or git pull if exists
cd routing_opt
./scripts/install.sh  # delegate — no credential or health logic here
```

### Pattern 2: Idempotent Guards — Replicate Existing Convention

**What:** Every action in every script checks before acting. This is already the convention: osrm-init checks for `.osrm.mldgr`, `install.sh` checks for `.env`. New scripts must follow the same pattern without exception.

**Why:** The office employee will re-run these scripts when something seems broken. A script that fails with "already exists" errors destroys trust.

**Required guards in bootstrap.sh:**
```bash
# Docker guard
if command -v docker &>/dev/null; then
    success "Docker already installed — skipping"
else
    # [5-step Docker CE install from apt]
fi

# Clone guard
if [ -d "routing_opt/.git" ]; then
    success "routing_opt already exists — pulling latest"
    cd routing_opt && git pull origin main
else
    git clone "$REPO_URL" routing_opt && cd routing_opt
fi
```

**Required guards in start.sh:**
```bash
# .env guard (setup not complete)
if [ ! -f ".env" ]; then
    error ".env not found. Run ./scripts/install.sh first."
    exit 1
fi

# Docker daemon guard (WSL-specific)
if ! docker info &>/dev/null; then
    sudo service docker start
fi
```

### Pattern 3: start.sh as a Daily Fast-Path, Not a Rebuild

**What:** `start.sh` does exactly three things: (1) ensure Docker daemon is running, (2) run `docker compose up -d`, (3) poll `/health` until 200 or 60s timeout, then print dashboard URL.

**What it must NOT do:** prompt for input, rebuild images, run git pull, run alembic, or attempt any installation.

**Why:** `docker compose up -d` with cached images starts in under 10 seconds. `docker compose up -d --build` can take 3-5 minutes if pip or npm cache is cold. A non-technical user who sees the terminal sit at "Building..." for 3 minutes on a Tuesday morning will panic or close the terminal.

**Example:**
```bash
# start.sh — complete logic
cd "$PROJECT_DIR"

# 1. Docker daemon (WSL-specific: daemon not auto-started on boot)
if ! docker info &>/dev/null; then
    info "Starting Docker daemon..."
    sudo service docker start
    sleep 3
fi

# 2. Start compose stack (fast: images cached from install)
docker compose up -d

# 3. Health check (max 60s)
for i in $(seq 1 12); do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        echo ""
        echo "  System is running."
        echo "  Dashboard: http://localhost:8000/dashboard/"
        echo "  Driver App: http://localhost:8000/driver/"
        exit 0
    fi
    sleep 5
done
warn "Services taking longer than expected. Check: docker compose ps"
```

### Pattern 4: Fix Docs to Match Code — Never the Reverse

**What:** The README.md Docker Services table shows `routing-db` as the container name, but `docker-compose.yml` defines it as `lpg-db`. Fix the README.

**Why not rename the container:** `backup_db.sh` auto-detects container names by literal string matching (`lpg-db` / `lpg-db-prod`) at lines 37-46. Renaming in compose would silently break the backup script. Container name changes have hidden blast radius: they also appear in `deploy.sh` health checks (`lpg-db-prod`) and in deploy.sh's backup call at line 136.

**The rule:** Documentation follows code. Code does not change to match documentation.

---

## Data Flow — Install to Daily Use Lifecycle

```
═══════════════════════════════════════════════════════
FIRST TIME — fresh Windows laptop with WSL (once ever)
═══════════════════════════════════════════════════════

bootstrap.sh
 │
 ├─► apt-get: git curl ca-certificates gnupg
 ├─► [Docker CE official install — 5 apt commands]
 ├─► usermod -aG docker $USER && newgrp docker
 ├─► git clone <REPO_URL> routing_opt
 └─► cd routing_opt && ./scripts/install.sh
                              │
                              ├─► create .env (prompts for DB pass, API key, GMaps key)
                              ├─► mkdir data/osrm data/geocode_cache
                              ├─► docker compose up -d --build
                              │       ├── osrm-init: download + preprocess Kerala OSM (~150MB, ~10min)
                              │       ├── db-init: alembic upgrade head (creates schema)
                              │       └── api: start uvicorn (waits for db-init)
                              └─► poll /health until 200 (up to 5 min)
                              → print "Installation complete! Dashboard: http://localhost:8000/..."


═══════════════════════════════════════════════════════
DAILY — every morning
═══════════════════════════════════════════════════════

start.sh
 │
 ├─► [guard: .env exists, else error]
 ├─► sudo service docker start  (WSL daemon not auto-started)
 ├─► docker compose up -d       (fast: images cached, osrm data present)
 │       ├── osrm-init: detects .osrm.mldgr → exits immediately
 │       ├── db-init: alembic upgrade head (no-op if schema current)
 │       └── api: starts in ~3s
 └─► poll /health until 200 (usually <30s)
 → print "Dashboard: http://localhost:8000/dashboard/"


═══════════════════════════════════════════════════════
UPDATE — when technical team pushes code changes
═══════════════════════════════════════════════════════

(manual, not a script)
git pull origin main
docker compose up -d --build api   # rebuild API image with new Python code
# db-init runs automatically and applies any new Alembic migrations
```

---

## Integration Points

### New Components and Their Boundaries

| New Component | Invokes | Reads | Writes | Does Not Touch |
|---------------|---------|-------|--------|----------------|
| `bootstrap.sh` | `scripts/install.sh` | Nothing (fresh machine) | `routing_opt/` directory | `.env`, docker-compose.yml, any Python/JS code |
| `start.sh` | `docker compose up -d`, `curl /health` | `.env` (existence check only) | Nothing | Credentials, images, database, any source code |

### Modification Blast Radius

| Modified File | Lines Changed | Risk |
|---------------|---------------|------|
| `scripts/install.sh` | Header comment only | Zero — no logic change |
| `DEPLOY.md` Section 3.1 | ~10 lines replaced | Zero — documentation only |
| `DEPLOY.md` Section 2.3 | ~30 lines replaced | Zero — documentation only |
| `README.md` Docker Services table | 2 rows corrected | Zero — documentation only |

### Critical Boundary: backup_db.sh Container Name Detection

`backup_db.sh` uses this logic (lines 37-46) to auto-detect the database container:

```bash
if [[ "$COMPOSE_FILE" == *prod* ]]; then
    DB_CONTAINER="lpg-db-prod"
else
    DB_CONTAINER="lpg-db"
fi
```

This is hardcoded to current container names. Any change to container names in `docker-compose.yml` silently breaks database backups. This is why we fix docs to match compose, not the reverse.

---

## Scaling Considerations

This is a single-office deployment for one LPG distributor. The only meaningful "scale" for v1.3 is operational: can a non-technical person use these scripts reliably over 12 months?

| Scenario | Expected Behavior |
|----------|-------------------|
| `bootstrap.sh` re-run on same machine | Idempotent guards skip all completed steps; re-runs in under 30 seconds |
| `start.sh` when Docker already running | `docker compose up -d` is a no-op for running containers; health check passes immediately |
| `start.sh` after laptop reboot | WSL Docker daemon start + container up takes ~30-60s; stays within 60s health timeout |
| OSRM data present, `install.sh` re-run | osrm-init detects `.osrm.mldgr`, exits in 1s; total startup under 60s |
| New laptop, repo already cloned | `bootstrap.sh` skips clone, installs Docker, calls `install.sh` |
| Internet outage on daily startup | `start.sh` succeeds (all data already present locally; geocoding caches hits) |

---

## Anti-Patterns

### Anti-Pattern 1: Docker Install Logic Inside install.sh

**What people do:** Add `if ! command -v docker; then apt-get install docker-ce; fi` inside `install.sh`.

**Why it's wrong:** `install.sh` is used by developers who already have Docker. Adding system-level package installation creates two execution paths. If the apt-get steps fail (network issue, wrong Ubuntu version, GPG key error), the error lands inside a script that previously "just worked" for developers. Debugging becomes harder for both audiences.

**Do this instead:** Keep `bootstrap.sh` as the system-provisioning layer. `install.sh` documents that it assumes Docker is present ("Requirements: Ubuntu 22.04+ or WSL2 with Ubuntu"). Separation of concerns between system setup and project setup.

### Anti-Pattern 2: start.sh That Rebuilds Images

**What people do:** Use `docker compose up -d --build` in `start.sh` to "keep things current."

**Why it's wrong:** `--build` triggers Docker image rebuilds. On a warm machine after a `git pull`, rebuilding the API image reinstalls all pip packages from the layer cache — but if `requirements.txt` has changed or the Docker build cache is cold (e.g., after disk cleanup), this takes 3-5 minutes. A non-technical user who sees the terminal sit at "Building..." for 3 minutes on a weekday morning will not know if it's working or broken.

**Do this instead:** `start.sh` uses `docker compose up -d` only. Updates (after `git pull`) are a separate manual step. Daily startup never rebuilds.

### Anti-Pattern 3: Renaming Container Names to Match Stale Docs

**What people do:** Change `container_name: lpg-db` to `container_name: routing-db` in `docker-compose.yml` to match the README.

**Why it's wrong:** `backup_db.sh` has hardcoded `lpg-db`/`lpg-db-prod` strings for container auto-detection. `deploy.sh` references `lpg-db-prod` by name in its health check loop (line 173). The blast radius of a container rename spans three scripts. A rename that silently breaks backups is worse than a stale README.

**Do this instead:** Fix the README table to show `lpg-db`. Docs follow code.

### Anti-Pattern 4: Prompting for Credentials in start.sh

**What people do:** `start.sh` prompts "Enter your API key:" to confirm identity on each startup.

**Why it's wrong:** Credentials live in `.env`, which was created during `install.sh`. `start.sh` should not handle credentials at all. Prompting creates new failure modes (user types wrong key, `.env` gets overwritten accidentally) and adds 30-60 seconds to every morning startup.

**Do this instead:** `start.sh` checks that `.env` exists (existence check, no read) and errors if missing: "Run `./scripts/install.sh` first — setup is not complete."

### Anti-Pattern 5: Single Monolithic Bootstrap + Install + Daily Startup Script

**What people do:** Merge all three into one script with flags: `setup.sh --bootstrap`, `setup.sh --daily`, `setup.sh --install`.

**Why it's wrong:** The audiences and timing are different. Bootstrap is a one-time operation with system-level side effects (apt-get, usermod). Daily startup is a quick, safe operation with no side effects. Merging them means the daily-use script carries the cognitive weight and risk surface of the bootstrap. A non-technical user who runs `./setup.sh` by accident on a Tuesday morning should not end up running `apt-get install`.

**Do this instead:** Separate files for separate purposes. Use the simplest possible names: `bootstrap.sh` (self-explanatory: one-time bootstrap) and `start.sh` (self-explanatory: start the system).

---

## Suggested Build Order

Dependencies determine ordering. Build in this sequence:

**1. `start.sh`** — standalone, lowest risk. Calls only `docker compose up -d` and `curl`. Can be tested immediately on the existing running system. This also validates the script style and output format before writing the more complex `bootstrap.sh`.

**2. Fix `DEPLOY.md` Section 3** — replace the 4-command daily startup block with `./start.sh`. Requires `start.sh` to exist. Unblocks the office employee from using the new script.

**3. `bootstrap.sh`** — delegates to `install.sh`, so `install.sh` must be working as-is first. Writing this after `start.sh` establishes the color/output conventions. The Docker CE install steps are well-documented and can be adapted from the existing DEPLOY.md Section 2.2.

**4. Fix `DEPLOY.md` Section 2** — replace the multi-block manual Docker install section with `./bootstrap.sh`. Requires `bootstrap.sh` to exist and be tested.

**5. Fix `README.md`** — correct the Docker Services table container names and update Quick Start to reference `bootstrap.sh`. No code dependencies; purely documentation. Can be done at any time but naturally last since it confirms what the scripts actually do.

**Why this order matters:**

`start.sh` is the highest daily-impact change (office employee runs it every morning) and the lowest risk change (no system modification). Getting it right first, then building documentation on top of working scripts, prevents documentation from making promises the scripts cannot keep.

---

## Sources

- `scripts/install.sh` — full inspection (324 lines): prerequisite checks, `.env` creation, compose up, health wait logic
- `scripts/deploy.sh` — full inspection: prod flow with pre-deploy backup, migrations, Caddy health check
- `scripts/backup_db.sh` — full inspection: container name auto-detection at lines 27-46, pg_dump via docker exec
- `docker-compose.yml` — full inspection: 6 services, actual container names, healthcheck conditions, depends_on chain
- `docker-compose.prod.yml` — full inspection: 8 services including Caddy and dashboard-build, resource limits
- `DEPLOY.md` — full inspection: existing office guide, Section 3.1 "Daily Use" contains the 4-command block to be replaced
- `README.md` — full inspection: Docker Services table at line 403-408 shows stale container name `routing-db`
- `.env.example` — full inspection: all environment variables with comments

---

*Architecture research for: v1.3 Office-Ready Deployment — WSL bootstrap, Docker auto-install, daily startup scripts*
*Researched: 2026-03-04*
