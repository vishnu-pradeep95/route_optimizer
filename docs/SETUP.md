# Development Environment Setup

> **Audience:** Developer

> Follow these steps on a fresh Ubuntu machine (or WSL2 on Windows) to get a
> working development environment for the Routing Optimization project.
> Estimated time: 15–20 minutes.
>
> **Not a developer?** See [DEPLOY.md](DEPLOY.md) for the employee deployment guide instead.

---

## Prerequisites

- **OS:** Ubuntu 22.04+ (tested on 24.04 LTS under WSL2)
- **RAM:** 4 GB minimum, 8+ GB recommended
- **Disk:** 5 GB free minimum
- **Permissions:** `sudo` access for installing packages

If on Windows, you should already have WSL2 enabled with an Ubuntu distro.

---

## Step 1: System Packages

```bash
sudo apt-get update
sudo apt-get install -y \
  git \
  curl \
  python3 \
  python3-pip \
  python3-venv \
  python3-dev \
  build-essential \
  ca-certificates \
  gnupg
```

Verify:
```bash
python3 --version   # Should show 3.12+
git --version        # Should show 2.x
```

---

## Step 2: Clone the Repository

```bash
git clone <REPO_URL> routing_opt
# ^^^ Replace <REPO_URL> with the actual repository URL before customer delivery
cd routing_opt
```

Or if you already have it:
```bash
cd routing_opt
git pull origin main
```

---

## Step 3: Python Virtual Environment

```bash
# Create the virtual environment
python3 -m venv .venv

# Activate it (you'll need to do this every time you open a new terminal)
source .venv/bin/activate

# Install all Python dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

Verify:
```bash
python -c "import fastapi, httpx, psycopg, shapely, sqlalchemy, asyncpg, geoalchemy2; print('All packages OK')"
```

> **Tip:** If you're using VS Code, it will auto-detect `.venv/` and activate it
> in new terminals. Look for `(.venv)` in your terminal prompt.

---

## Step 4: Docker + Docker Compose

Docker runs our database (PostgreSQL + PostGIS), routing engine (OSRM), and
optimizer (VROOM) — all containerized so you don't install them natively.

### Install Docker

```bash
# Add Docker's official GPG key
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add the Docker apt repository
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine + Compose plugin
sudo apt-get update
sudo apt-get install -y \
  docker-ce \
  docker-ce-cli \
  containerd.io \
  docker-buildx-plugin \
  docker-compose-plugin
```

### Allow running Docker without sudo

```bash
sudo usermod -aG docker $USER
# IMPORTANT: log out and back in (or run: newgrp docker) for this to take effect
```

### Start Docker (WSL2 only — Docker doesn't auto-start on WSL)

```bash
sudo service docker start
```

> **WSL users:** You need to run this every time you restart WSL.
> Add it to your `~/.bashrc` if you want it automatic:
> ```bash
> echo 'sudo service docker start 2>/dev/null' >> ~/.bashrc
> ```

### Verify Docker

```bash
docker --version           # Should show 29.x
docker compose version     # Should show 5.x
docker run --rm hello-world  # Should print "Hello from Docker!"
```

---

## Step 5: Node.js (for Dashboard / PWA — needed later)

```bash
# Using NodeSource for latest LTS
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt-get install -y nodejs
```

Verify:
```bash
node --version    # Should show v22.x or v24.x
npm --version     # Should show 10.x+
```

> Node.js is only needed for Phase 2+ (dashboard and PWA). You can skip this
> step if you're only working on the Python backend.

---

## Step 6: Environment Variables

```bash
# Copy the template
cp .env.example .env

# Edit with your values
nano .env   # or: code .env
```

**What to fill in:**

| Variable | Where to Get It | Required? |
|---|---|---|
| `GOOGLE_MAPS_API_KEY` | [Google Cloud Console](https://console.cloud.google.com/apis/credentials) → enable "Geocoding API" | Phase 0+ |
| `POSTGRES_PASSWORD` | Choose any strong password | **Yes** — used by Docker Compose for the PostgreSQL container |
| `POSTGRES_USER` | Defaults to `routing` | No |
| `POSTGRES_DB` | Defaults to `routing_opt` | No |
| Other values | Defaults work for local development | — |

---

## Step 7: VS Code Setup (Recommended)

If you're using VS Code (recommended):

1. Open the project: `code .` from the project root
2. VS Code will auto-detect `.venv/` Python environment
3. Install recommended extensions when prompted (or manually):
   - **Python** (ms-python.python)
   - **Docker** (ms-azuretools.vscode-docker)
   - **GitLens** (eamodio.gitlens)

---

## Step 8: Verify Everything Works

Run this quick check script:

```bash
source .venv/bin/activate

echo "=== Python ==="
python --version
python -c "import fastapi; print(f'FastAPI {fastapi.__version__}')"
python -c "import sqlalchemy; print(f'SQLAlchemy {sqlalchemy.__version__}')"
python -c "import asyncpg; print('asyncpg OK')"

echo "=== Docker ==="
docker --version
docker compose version

echo "=== Services ==="
docker compose ps 2>/dev/null || echo "Services not started (run: docker compose up -d)"

echo "=== Node ==="
node --version 2>/dev/null || echo "Node.js not installed (optional for now)"

echo "=== Git ==="
git --version
git log --oneline -3

echo "=== Tests ==="
pytest tests/ -q 2>/dev/null || echo "Run 'pytest tests/ -v' for full output"

echo "=== All good! ==="
```

You should see version numbers for Python, Docker, and Git with no errors.

---

## Quick Reference

| What | Command |
|---|---|
| Activate Python venv | `source .venv/bin/activate` |
| Install a new Python package | `pip install <package> && pip freeze > requirements.txt` |
| Start Docker (WSL) | `sudo service docker start` |
| Start all services | `docker compose up -d` |
| Start only database | `docker compose up -d db` |
| Stop all services | `docker compose down` |
| Reset database (delete data) | `docker compose down -v` then `docker compose up -d db` |
| View service logs | `docker compose logs -f api` |
| Run backend server | `uvicorn apps.kerala_delivery.api.main:app --reload` |
| Run tests | `pytest tests/ -v` |
| Run tests (quick) | `pytest tests/ -q` |
| **Alembic: apply migrations** | `alembic upgrade head` |
| **Alembic: current revision** | `alembic current` |
| **Alembic: migration history** | `alembic history` |
| **Alembic: autogenerate migration** | `alembic revision --autogenerate -m "description"` |
| **Dashboard: install deps** | `cd apps/kerala_delivery/dashboard && npm install` |
| **Dashboard: dev server** | `cd apps/kerala_delivery/dashboard && npm run dev` → http://localhost:5173 |
| **Dashboard: production build** | `cd apps/kerala_delivery/dashboard && npm run build` |
| **Dashboard: type check** | `cd apps/kerala_delivery/dashboard && npx tsc --noEmit` |
| **Batch: import orders** | `python scripts/import_orders.py data/sample_orders.csv --dry-run` |
| **Batch: geocode addresses** | `python scripts/geocode_batch.py --from-csv data/sample_orders.csv --dry-run` |

---

## Troubleshooting

### Docker permission denied
```
Got permission denied while trying to connect to the Docker daemon socket
```
**Fix:** Run `sudo usermod -aG docker $USER` then log out and back in.

### Docker daemon not running (WSL)
```
Cannot connect to the Docker daemon at unix:///var/run/docker.sock
```
**Fix:** Run `sudo service docker start`.

### Python package import errors
```
ModuleNotFoundError: No module named 'fastapi'
```
**Fix:** Make sure venv is activated: `source .venv/bin/activate`, then `pip install -r requirements.txt`.

### Port already in use
```
OSError: [Errno 98] Address already in use
```
**Fix:** Find and kill the process: `lsof -i :8000` then `kill <PID>`.

---

## Step 9: OSRM Data Preparation

OSRM needs preprocessed Kerala map data before it can calculate routes.

```bash
# Create the OSRM data directory
mkdir -p data/osrm

# Download Kerala OpenStreetMap data (~100 MB)
wget -O data/osrm/kerala-latest.osm.pbf \
  https://download.openstreetmap.fr/extracts/asia/india/kerala.osm.pbf

# Preprocess the map data (3 steps — takes 5–10 minutes)
# 1. Extract road network
docker run --rm -v $(pwd)/data/osrm:/data \
  osrm/osrm-backend:latest \
  osrm-extract -p /opt/car.lua /data/kerala-latest.osm.pbf

# 2. Partition the graph
docker run --rm -v $(pwd)/data/osrm:/data \
  osrm/osrm-backend:latest \
  osrm-partition /data/kerala-latest.osrm

# 3. Customize the graph
docker run --rm -v $(pwd)/data/osrm:/data \
  osrm/osrm-backend:latest \
  osrm-customize /data/kerala-latest.osrm
```

After preprocessing, `data/osrm/` will contain ~15 files. You can now start OSRM:
```bash
docker compose up -d osrm
# OSRM has no /health endpoint — verify by querying nearest road to depot coordinates
curl -sf http://localhost:5000/nearest/v1/driving/76.2846,9.9716
```

---

## Step 10: Database Migrations

After starting the database:

```bash
docker compose up -d db    # Start PostgreSQL
alembic upgrade head       # Apply all migrations
```

To check migration status:
```bash
alembic current            # Shows current revision
alembic history            # Shows all migrations
```

---

## Step 11: CDCMS Data Workflow

If importing from HPCL's CDCMS system:

### Option A: Dashboard (recommended)

1. Open `http://localhost:8000/dashboard/` in Chrome
2. Go to the **Upload Routes** page
3. Drag & drop the CDCMS CSV file (auto-detected format)
4. Click **Upload & Optimize** — routes appear on the map
5. Click **Print QR Sheet** — print and hand QR codes to drivers

### Option B: CLI / API

```bash
# 1. Preprocess the CDCMS export (filter by driver, clean addresses)
python -c "
from core.data_import.cdcms_preprocessor import preprocess_cdcms
from apps.kerala_delivery.config import CDCMS_AREA_SUFFIX

df = preprocess_cdcms(
    'data/cdcms_export.csv',
    filter_delivery_man='GIREESHAN ( C )',
    area_suffix=CDCMS_AREA_SUFFIX,
)
df.to_csv('data/today_deliveries.csv', index=False)
print(f'Preprocessed {len(df)} orders')
"

# 2. Import and geocode
python scripts/import_orders.py data/today_deliveries.csv --geocode

# 3. Or upload via the API (replace YOUR_KEY with the API_KEY from .env)
curl -X POST http://localhost:8000/api/upload-orders \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@data/today_deliveries.csv"
```

---

## Deploying on a New Laptop

Quick checklist to get the system running on a fresh laptop:

1. **Install Ubuntu/WSL2** — Ubuntu 22.04+ required
2. **Run Steps 1–8** above in order (takes ~20 minutes)
3. **Run Step 9** — OSRM data prep (takes ~10 minutes, one-time only)
4. **Run Step 10** — Database migrations
5. **Start all services:** `docker compose up -d`
6. **Verify:** `curl http://localhost:8000/health`
7. **Open browser:** `http://localhost:8000/driver/`

Common new-laptop issues:
- **WSL2 memory limit:** If Docker is slow, increase WSL memory in `%UserProfile%\.wslconfig`:
  ```ini
  [wsl2]
  memory=8GB
  swap=4GB
  ```
- **Docker not starting:** On WSL2, Docker needs manual start: `sudo service docker start`
- **Git clone auth:** Use SSH key or personal access token for private repos

---

## Troubleshooting

### OSRM Not Ready

On **first startup**, OSRM needs to download and preprocess Kerala map data (~150 MB download, ~10-15 minutes processing). During this time, route optimization will fail.

**How to check OSRM init progress:**
```bash
# Watch the init container logs (will show download/preprocessing progress)
docker compose logs osrm-init -f

# Check if init is complete (should show "Exited (0)")
docker compose ps osrm-init
```

**How to verify OSRM is ready to serve routes:**
```bash
# Check Docker healthcheck status
docker inspect --format='{{.State.Health.Status}}' osrm-kerala

# Test with a real routing query (depot coordinates in Kochi)
curl -sf http://localhost:5000/nearest/v1/driving/76.2846,9.9716
```

**Common OSRM issues:**
- **Container exits with code 137:** Out of memory. OSRM preprocessing needs ~4 GB RAM. Increase WSL memory (see above).
- **"file not found" errors:** The `osrm-init` container hasn't finished. Wait for it to exit with code 0.
- **OSRM starts but returns errors:** Map data may be corrupted. Delete `data/osrm/` and restart: `rm -rf data/osrm && docker compose up -d`
