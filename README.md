# Routing Optimization Platform

![CI](https://github.com/vishnu-pradeep95/route_optimizer/actions/workflows/ci.yml/badge.svg)

A modular delivery-route optimization system. First deployment: **Kerala LPG cylinder delivery** (HPCL distributor with 13 three-wheelers, 30–50 deliveries/day, 5 km radius from depot in Vatakara, Kozhikode).

The architecture is designed to be **reusable across any delivery business** — the Kerala LPG app is the first consumer, not the only one.

> **Employee?** If you're setting up this system at the office, skip to the [Employee Deployment Guide (DEPLOY.md)](docs/DEPLOY.md) — no programming knowledge required.

---

## Quick Start

```bash
# 1. Clone & setup Python
git clone <REPO_URL> routing_opt && cd routing_opt
# ^^^ Replace <REPO_URL> with the actual repository URL before customer delivery
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Environment config
cp .env.example .env
# Edit .env — minimum required changes:
#   POSTGRES_PASSWORD=any-strong-password-you-choose
#   GOOGLE_MAPS_API_KEY=your-key-here       (only needed for geocoding)
#   CORS_ALLOWED_ORIGINS=http://localhost:8000,http://localhost:5173
#   (add :5173 so the React dashboard dev server can talk to the API)

# 3. Start infrastructure (OSRM + VROOM + PostgreSQL + API)
sudo service docker start          # WSL2 only — skip on native Linux/Mac
docker compose up -d

# 4. Wait for services to be healthy, then verify
# start.sh handles health polling -- only needed if running outside Docker
sleep 5
curl http://localhost:8000/health   # should return {"status":"ok"}
docker compose ps                   # all services should show "running"

# 5. Apply database migrations
# Automated by db-init container -- only needed if running outside Docker
alembic upgrade head

# 6. Run tests (no Docker needed — all external services are mocked)
pytest tests/ -v

# 7. Open the app
# Driver PWA:   http://localhost:8000/driver/
# API docs:     http://localhost:8000/docs
#
# Ops dashboard (React dev server with hot reload):
cd apps/kerala_delivery/dashboard
npm install          # first time only
npm run dev          # → http://localhost:5173
```

> **Full setup guide** (first-time, including Docker install, OSRM data prep): see [SETUP.md](docs/SETUP.md)

### Stopping & Restarting

```bash
# Stop everything
docker compose down

# Restart after Python/config changes
docker compose restart api

# Rebuild API image after adding pip packages
docker compose up -d --build api

# Hard-refresh the dashboard after frontend changes
# Browser: Ctrl+Shift+R  (bypasses service worker cache)
```

---

## How It Works

```
CDCMS Export → Preprocess → Geocode → Optimize → Database → Driver PWA
     │            │            │           │          │           │
 HPCL tab-    Clean addr,   Google     VROOM +   PostgreSQL  Mobile-friendly
 separated    filter by     Maps API   OSRM       + PostGIS   offline-capable
 (19 cols)    driver/area   (cached)   (ms solve)    │
                                                GPS Telemetry
                                                + Delivery Status
```

1. **Export** today's delivery list from HPCL's CDCMS system (tab-separated file with 19 columns)
2. **Preprocess** the raw CDCMS data — filter by driver/area, clean messy Kerala addresses, extract needed columns
3. **Geocode** cleaned addresses to GPS coordinates (Google Maps API, results permanently cached)
4. **Optimize** routes using VROOM (CVRP with Time Windows) with OSRM travel times
5. **Persist** optimization results, routes, and stops to PostgreSQL + PostGIS
6. **Serve** optimized routes to drivers via a Progressive Web App (PWA) they open in Chrome
7. **Track** GPS telemetry and delivery status updates in real time

---

## Project Structure

```
routing_opt/
│
├── core/                          ← REUSABLE modules (business-agnostic)
│   ├── models/                    ← Pydantic data models
│   │   ├── location.py            ← GPS location with validation
│   │   ├── order.py               ← Delivery order (weight, priority, status)
│   │   ├── vehicle.py             ← Vehicle specs (capacity, speed)
│   │   └── route.py               ← Route, RouteStop, RouteAssignment
│   ├── routing/                   ← Routing engine adapters
│   │   ├── interfaces.py          ← RoutingEngine protocol
│   │   └── osrm_adapter.py        ← OSRM implementation
│   ├── optimizer/                 ← Route optimization engine adapters
│   │   ├── interfaces.py          ← RouteOptimizer protocol
│   │   └── vroom_adapter.py       ← VROOM implementation
│   ├── geocoding/                 ← Geocoding adapters
│   │   ├── interfaces.py          ← Geocoder + AsyncGeocoder protocols
│   │   ├── google_adapter.py      ← Google Maps + SHA256 file cache
│   │   └── cache.py               ← PostGIS geocode cache (CachedGeocoder)
│   ├── database/                  ← PostgreSQL + PostGIS persistence
│   │   ├── __init__.py            ← Package docs + architecture overview
│   │   ├── connection.py          ← Async engine, session factory (asyncpg)
│   │   ├── models.py              ← SQLAlchemy ORM models (orders, routes, telemetry)
│   │   └── repository.py          ← Data access layer (async CRUD operations)
│   ├── data_import/               ← Data ingestion
│   │   ├── interfaces.py          ← DataImporter protocol
│   │   ├── csv_importer.py        ← Generic CSV/Excel import
│   │   └── cdcms_preprocessor.py  ← HPCL CDCMS export converter
│   └── licensing/                 ← Software licensing
│       └── license_manager.py     ← Hardware-bound license key validation
│
├── apps/
│   └── kerala_delivery/           ← FIRST APP: Kerala LPG business logic
│       ├── config.py              ← All Kerala-specific constants
│       ├── api/
│       │   ├── main.py            ← FastAPI backend (upload, optimize, serve)
│       │   └── qr_helpers.py      ← QR code generation + Google Maps URL builder
│       ├── driver_app/            ← PWA (index.html, sw.js, manifest.json)
│       └── dashboard/             ← Ops dashboard (React + Vite + MapLibre GL JS)
│           ├── src/pages/         ← UploadRoutes, LiveMap, RunHistory, FleetManagement
│           ├── src/components/    ← RouteMap, VehicleList, StatsBar
│           └── src/lib/api.ts     ← Typed fetch client for all API endpoints
│
├── tests/                         ← Mirrors source structure (420 tests)
│   ├── conftest.py                ← Shared fixtures (Kerala coordinates)
│   ├── core/                      ← Unit tests for all core modules
│   │   ├── database/              ← 35 DB tests (models, repository, connection)
│   │   └── geocoding/             ← Geocoder + PostGIS cache tests (16 cache tests)
│   ├── scripts/                   ← Batch script tests (import_orders, geocode_batch)
│   ├── apps/                      ← API endpoint tests
│   └── integration/               ← End-to-end pipeline tests
│
├── infra/
│   ├── Dockerfile                 ← API container image
│   ├── postgres/init.sql          ← PostGIS schema + extensions + seed data
│   ├── alembic/                   ← Database migrations (async SQLAlchemy)
│   │   ├── env.py                 ← Async migration runner + PostGIS filter
│   │   └── versions/              ← Migration scripts (3 so far)
│   └── vroom-conf/                ← VROOM service configuration
├── docker-compose.yml             ← PostgreSQL + OSRM + VROOM + API stack
├── scripts/
│   ├── import_orders.py           ← Batch CSV import (parse + geocode + save to DB)
│   └── geocode_batch.py           ← Batch geocode addresses (CSV or DB → PostGIS cache)
│
├── data/
│   ├── sample_orders.csv          ← 30 example orders (generic CSV format)
│   └── sample_cdcms_export.csv    ← 27-row CDCMS tab-separated sample (Vatakara area)
│
├── docs/                          ← All documentation files
│   ├── DEPLOY.md                  ← Employee deployment guide (no coding required)
│   ├── SETUP.md                   ← Complete new-developer setup guide
│   ├── GUIDE.md                   ← Comprehensive platform guide
│   ├── CSV_FORMAT.md              ← Upload file format reference
│   ├── LICENSING.md               ← License generation & activation guide
│   ├── DISTRIBUTION.md            ← Build & deliver customer distributions
│   ├── ATTRIBUTION.md             ← Third-party licenses and attribution
│   ├── ENV-COMPARISON.md          ← Dev vs production environment differences
│   ├── GOOGLE-MAPS.md             ← API key setup and troubleshooting
│   └── ERROR-MAP.md               ← Error message traceability
│
├── .env.example                   ← Template for environment vars
├── requirements.txt               ← Pinned Python packages
├── LICENSE                        ← Proprietary software license
└── .github/
    ├── copilot-instructions.md    ← Always-on AI context
    └── agents/                    ← Copilot agent definitions
```

### Architecture Principle: Core vs Apps

```
core/  →  Generic, reusable modules. NEVER imports from apps/.
          Configured via dependency injection (pass config, don't hardcode).

apps/  →  Business-specific consumers of core modules.
          Kerala LPG is the first. A Mumbai food delivery startup would
          create apps/mumbai_food/ with their own config.py.
```

---

## API Endpoints

Base URL: `http://localhost:8000`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check — returns `{"status": "ok", "version": ...}` |
| `POST` | `/api/upload-orders` | Upload CSV → geocode → optimize → persist → return assignment |
| `GET` | `/api/routes` | List all routes (summary per vehicle) |
| `GET` | `/api/routes/{vehicle_id}` | Full route detail for a specific driver |
| `GET` | `/api/routes/{vehicle_id}/google-maps` | Google Maps URL(s) + QR code SVG(s) for a vehicle's route |
| `GET` | `/api/qr-sheet` | Printable A4 HTML page with QR codes for ALL vehicles |
| `POST` | `/api/routes/{vehicle_id}/stops/{order_id}/status` | Update delivery status (`delivered` / `failed` / `pending`) |
| `GET` | `/api/runs` | List recent optimization runs (newest first) |
| `GET` | `/api/runs/{run_id}/routes` | All routes for a specific optimization run |
| `POST` | `/api/telemetry` | Receive a single GPS telemetry ping from driver app |
| `POST` | `/api/telemetry/batch` | Receive multiple GPS pings in one request (reduces N+1 overhead) |
| `GET` | `/api/telemetry/fleet` | Latest position of every active vehicle |
| `GET` | `/api/telemetry/{vehicle_id}` | GPS history for a specific vehicle |
| `GET` | `/api/vehicles` | List all fleet vehicles |
| `GET` | `/api/vehicles/{vehicle_id}` | Get details for a specific vehicle |
| `POST` | `/api/vehicles` | Register a new vehicle |
| `PUT` | `/api/vehicles/{vehicle_id}` | Update vehicle details |
| `DELETE` | `/api/vehicles/{vehicle_id}` | Remove a vehicle from the fleet |
| `GET` | `/driver/` | Serves the driver PWA |

### Input Data: CDCMS Export Format

The primary input is the **HPCL CDCMS export** — a tab-separated file with 19 columns exported from the Cylinder Delivery & Customer Management System.

> **Authentication:** Write endpoints (`POST`, `PUT`, `DELETE`) require an API key
> in the `X-API-Key` header. Set `API_KEY` in `.env`. Sensitive read endpoints
> (telemetry, vehicles, QR sheet, Google Maps routes) also require the key.
> Non-sensitive reads (`/api/routes`, `/health`) are open for driver app access.

See [data/sample_cdcms_export.csv](data/sample_cdcms_export.csv) for a CDCMS format sample, or [data/sample_orders.csv](data/sample_orders.csv) for a generic CSV example.

#### CDCMS Columns (19 total)

| Column | Used | Purpose |
|--------|------|---------|
| `OrderNo` | ✅ | Unique order ID — becomes `order_id` |
| `OrderStatus` | ✅ | Filter: only "Allocated-Printed" orders are processed |
| `ConsumerAddress` | ✅ | Delivery address (messy — cleaned by preprocessor) |
| `OrderQuantity` | ✅ | Number of cylinders |
| `AreaName` | ✅ | CDCMS area grouping (e.g., VALLIKKADU, RAYARANGOTH) |
| `DeliveryMan` | ✅ | Used to filter for a specific driver |
| `MobileNo` | ❌ | Not imported (privacy — stays in CDCMS) |
| Other 12 columns | ❌ | Ignored (OrderDate, CashMemoNo, etc.) |

#### Address Preprocessing Pipeline

CDCMS addresses are messy — fields concatenated without separators, phone numbers mixed in, inconsistent abbreviations. The `cdcms_preprocessor.py` module applies a 10-step cleaning pipeline:

| Step | What It Does | Example |
|------|--------------|---------|
| 1 | Remove embedded phone numbers | `(H) 9847862734KURUPAL` → `(H) KURUPAL` |
| 2 | Remove CDCMS artifacts (PH:, reference numbers) | `/ PH: 2511259` → removed |
| 3 | Remove backtick/quote markers | `` ``THANAL`` `` → `THANAL` |
| 4 | Expand abbreviations (NR., PO., (H)) | `NR.` → `Near`, `(H)` → `House` |
| 5 | Handle concatenated PO names | `KUNIYILPO.` → `KUNIYIL P.O.` |
| 6 | Add spaces between stuck number+text | `4/146AMINAS` → `4/146 AMINAS` |
| 7 | Collapse multiple spaces | `KAINATTY   VATAKARA` → `KAINATTY VATAKARA` |
| 8 | Strip dangling punctuation | Leading/trailing `;:-+` removed |
| 9 | Title case + fix artifacts | `KSEB` preserved, `P.O.` preserved |
| 10 | Append area suffix | `..., Vatakara, Kozhikode, Kerala` for geocoding |

#### Preprocessing Usage

```python
from core.data_import.cdcms_preprocessor import preprocess_cdcms
from apps.kerala_delivery.config import CDCMS_AREA_SUFFIX

# Read CDCMS export, filter for one driver, clean addresses
df = preprocess_cdcms(
    "data/cdcms_export.csv",
    filter_delivery_man="GIREESHAN ( C )",
    area_suffix=CDCMS_AREA_SUFFIX,
)

# Output: DataFrame with columns: order_id, address, quantity, area_name, delivery_man
df.to_csv("data/today_deliveries.csv", index=False)
```

#### Generic CSV Upload Format

If not using CDCMS, you can upload a standard CSV directly:

**Required columns:**

| Column | Type | Example |
|--------|------|---------|
| `order_id` | string | `ORD-001` |
| `address` | string | `Edappally Junction, Kochi` |
| `customer_id` | string | `CUST-001` |

**Optional columns:**

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `cylinder_type` | string | `domestic` | `domestic` (14.2 kg), `commercial` (19 kg), `5kg` |
| `quantity` | int | `1` | Number of cylinders |
| `priority` | int | `2` | 1=high, 2=normal, 3=low |
| `notes` | string | — | Delivery instructions for driver |
| `latitude` | float | — | If provided, skips geocoding for this row |
| `longitude` | float | — | Must pair with latitude |
| `weight_kg` | float | — | Overrides cylinder_type weight calculation |

---

## Kerala Business Configuration

All business-specific values live in [`apps/kerala_delivery/config.py`](apps/kerala_delivery/config.py):

| Parameter | Value | Source |
|-----------|-------|--------|
| Depot location | 11.624°N, 75.579°E (Vatakara, Kozhikode) | Actual LPG godown location |
| Vehicles | 13 × Piaggio Ape Xtra LDX | Fleet data |
| Max payload | 446 kg (90% of 496 kg rated) | Safety margin |
| Max cylinders/load | 30 domestic | Cargo bed volume |
| Speed limit | 40 km/h (urban) | Kerala MVD |
| Safety multiplier | 1.3× on all travel times | Kerala road conditions |
| Monsoon multiplier | 1.5× extra (June–Sep) | Flooded roads + reduced visibility |
| Service time/stop | 5 minutes | Unload + signature + empty collection |
| Min delivery window | 30 minutes | Kerala MVD — no time-pressure delivery |
| Delivery radius | 5 km from depot | HPCL free-delivery policy |

---

## Safety & Regulatory Constraints (Non-Negotiable)

These are enforced by the system and cannot be bypassed:

| Rule | Reason |
|------|--------|
| **No countdown timers** in any UI | Kerala MVD directive |
| **≥ 30 min delivery windows** | No "instant delivery" pressure |
| **Speed alerts at 40 km/h** | Driver safety, three-wheeler limits |
| **1.3× safety multiplier** on all ETAs | Kerala roads ≠ ideal conditions |
| **No PII in the optimizer** | Data privacy — names/phones stay in source CSV |

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Database** | PostgreSQL 16 + PostGIS 3.5 | Persistent storage, spatial queries |
| **ORM** | SQLAlchemy 2.0 + asyncpg | Async database access, model mapping |
| **Routing engine** | OSRM (Docker, port 5000) | Travel time & distance matrices |
| **Optimizer** | VROOM (Docker, port 3000) | Vehicle routing problem solver (CVRP + Time Windows) |
| **Backend** | Python 3.12 + FastAPI | API server, orchestration |
| **Data models** | Pydantic v2 + SQLAlchemy ORM | Validation, serialization, persistence |
| **Geocoding** | Google Maps API (PostGIS cache + CachedGeocoder) | Address → GPS coordinates |
| **Driver app** | PWA (HTML/JS/Service Worker) | Mobile-friendly, offline-capable |
| **Migrations** | Alembic (async) | Database schema versioning (3 migrations applied) |
| **Ops Dashboard** | React 19 + Vite 7 + MapLibre GL JS 5 | Upload & routes, live tracking, route visualization, run history, fleet management |
| **QR Codes** | qrcode 8.2 + Pillow 12.1.1 | Google Maps navigation URLs encoded as scannable QR codes |
| **Infrastructure** | Docker Compose | Single-command deployment |

---

## Running Tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

**420 tests** covering:
- Core models (16 tests: location, order, vehicle, route validation)
- OSRM adapter (8 tests: travel time, distance matrix, safety multiplier)
- VROOM adapter (15 tests: route optimization, priority, unassigned handling)
- Google geocoder (10 tests: API calls, caching, geocode cache hits)
- PostGIS geocode cache (16 tests: CachedGeocoder -- cache-first strategy, hit/miss, confidence)
- Geocode normalization (15 tests: address normalization and deduplication)
- Duplicate detector (21 tests: geocoded location duplicate detection)
- CSV importer (22 tests: standard/custom columns, coordinate passthrough, error recovery)
- CDCMS preprocessor (33 tests: TSV reading, address cleaning, filtering, abbreviation handling)
- Database layer (35 tests: ORM models, repository CRUD, connection lifecycle, telemetry)
- Licensing (25 tests: hardware-bound license keys, offline validation, expiry, tampering)
- API endpoints (107 tests: health, routes, status updates, upload pipeline, optimization runs, telemetry, fleet CRUD, rate limiting, QR codes, XSS prevention)
- QR helpers (24 tests: Google Maps URL building, QR SVG/PNG generation, route splitting)
- Kerala config (22 tests: vehicle specs, safety constraints, routing config, depot location)
- Batch scripts (31 tests: import_orders.py, geocode_batch.py -- parsing, geocoding, dry-run, stats)
- E2E pipelines (11 tests: CSV->Order, Order->VROOM, Route->QR, full upload->optimize, QR sheet)
- Integration (9 tests: end-to-end CSV -> geocode -> optimize -> persist pipeline)

All external services (OSRM, VROOM, Google Maps, PostgreSQL) are mocked in tests — no Docker required to run the test suite.

---

## Docker Services

```bash
# Start all services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f api

# Stop all services
docker compose down

# Restart API after Python/config changes (fast — no rebuild)
docker compose restart api

# Rebuild + restart API after adding pip packages to requirements.txt
docker compose up -d --build api
```

| Service | Container | Port | Health Check |
|---------|-----------|------|-------------|
| PostgreSQL + PostGIS | `lpg-db` | 5432 | `pg_isready -U routing -d routing_opt` |
| OSRM | `osrm-kerala` | 5000 | `curl -sf http://localhost:5000/nearest/v1/driving/76.2846,9.9716` |
| VROOM | `vroom-solver` | 3000 | `curl -sf http://localhost:3000/health` |
| API | `lpg-api` | 8000 | `curl http://localhost:8000/health` |

> **Note:** OSRM has no `/health` endpoint. You verify readiness by querying a real coordinate -- the command above queries the nearest road segment to the depot location in Kochi. OSRM requires preprocessed Kerala map data in `data/osrm/`. This is downloaded automatically on first `docker compose up`. See [SETUP.md](docs/SETUP.md) for manual download steps if running OSRM outside Docker.

---

## Environment Variables

Copy `.env.example` → `.env` and configure:

| Variable | Required | Description |
|----------|----------|--------------|
| `POSTGRES_PASSWORD` | **Yes** | Database password — set any strong value |
| `GOOGLE_MAPS_API_KEY` | Yes (for geocoding) | Google Cloud API key with Geocoding API enabled |
| `API_KEY` | No (dev) / Yes (prod) | Header `X-API-Key` required for write endpoints. Leave empty in dev. |
| `CORS_ALLOWED_ORIGINS` | **Yes** | Comma-separated frontend origins. **Must include `http://localhost:5173`** when running the React dashboard via `npm run dev`. |
| `OSRM_URL` | No | Defaults to `http://localhost:5000` |
| `VROOM_URL` | No | Defaults to `http://localhost:3000` |
| `POSTGRES_USER` | No | Defaults to `routing` |
| `POSTGRES_DB` | No | Defaults to `routing_opt` |
| `DATABASE_URL` | No | Auto-built from above; override for remote DB |

> **Common issue:** Dashboard shows network errors or blank data? Check `CORS_ALLOWED_ORIGINS` includes the correct port (`:5173` for Vite dev, `:8000` for production).

---

## Development Phases

| Phase | Status | Description |
|-------|--------|-------------|
| **0: Baseline** | ✅ Complete | Core modules, data models, tests, API, driver PWA, Docker setup |
| **1: Single-Vehicle** | ✅ Complete | Real OSRM Kerala data, speed profiles, 68% route improvement validated |
| **2: Multi-Vehicle + DB** | ✅ Complete | PostgreSQL + PostGIS, time windows, GPS telemetry, optimization history, fleet management, API auth, batch scripts |
| **3: Production** | ✅ Complete | Docker Compose prod config, CDCMS preprocessor, read-scoped auth. *Note: monitoring, re-optimization, and proof-of-delivery from the design doc's original Phase 3 scope moved to Phase 4.* |
| **4A: QR Codes** | ✅ Complete | Google Maps QR codes, printable QR sheet, Upload & Routes dashboard page, route splitting for >11 stops |
| **4B: UI Redesign** | ✅ Complete | Dashboard sidebar nav, stone/amber design system, driver PWA overhaul, responsive layout |
| **4C: Licensing** | ✅ Complete | Hardware-bound license key generation, offline validation, expiry checks |
| **4D: Easy Install** | ✅ Complete | Init containers, installer script, Caddy reverse proxy, simplified deployment |

---

## Licensing

The software uses hardware-bound license keys. See [LICENSING.md](docs/LICENSING.md)
for the complete guide.

**Quick reference:**

| Task | Command |
|------|---------|
| Get machine fingerprint | `python scripts/get_machine_id.py` |
| Generate license key (developer only) | `python scripts/generate_license.py --customer "name" --fingerprint "hash" --months 12` |
| Activate license | Set `LICENSE_KEY` in `.env` or save key to `license.key` |
| Build customer distribution | `./scripts/build-dist.sh v1.3` |

### Dev vs Production

| Aspect | Development | Production (customer) |
|--------|-------------|----------------------|
| License enforcement | Optional | Required |
| Licensing source code | `.py` (readable) | `.pyc` (bytecode only) |
| `generate_license.py` | Included | Excluded |
| Tests, planning docs | Included | Excluded |
| Docker Compose | `docker-compose.yml` | `docker-compose.prod.yml` |
| Ports exposed | 8000, 5432, 5000, 3000 | 80, 443 (Caddy reverse proxy) |
| API docs (`/docs`) | Available | Disabled |

---

## How Another Business Would Use This

A different delivery company (e.g., Mumbai food delivery) would:

1. Clone this repo
2. Create `apps/mumbai_food/config.py` with their vehicles, speed limits, and constraints
3. Write their own API endpoints in `apps/mumbai_food/api/`
4. Reuse `core/routing/`, `core/optimizer/`, `core/geocoding/`, `core/data_import/` unchanged
5. All core modules accept configuration via constructor arguments — no hardcoded business values

---

## Interface-First Design

Every core module defines a **Protocol** (Python structural typing) before any implementation:

```python
# core/routing/interfaces.py
class RoutingEngine(Protocol):
    def get_travel_time(self, origin, destination) -> TravelTime: ...
    def get_distance_matrix(self, locations) -> DistanceMatrix: ...
```

This allows swapping OSRM → Valhalla, or VROOM → OR-Tools, without changing any calling code. All protocols are `@runtime_checkable` for isinstance() verification in tests.

---

## Contributing

- **Code style:** Clarity over cleverness. Every function gets a docstring. Type hints everywhere.
- **Comments:** Explain *why* (design decisions), not *what*. Link to docs/articles for non-obvious choices.
- **Tests:** Every new function in `core/` must have tests. `pytest` must pass before every commit.
- **Imports:** Keep `core/` independent — it must never import from `apps/`.
- **Setup:** New contributors follow [SETUP.md](docs/SETUP.md) (15–20 min to working environment).

---

## Documentation

| Document | Description |
|----------|-------------|
| [DEPLOY.md](docs/DEPLOY.md) | Office employee setup and daily use guide |
| [SETUP.md](docs/SETUP.md) | Developer environment setup |
| [LICENSING.md](docs/LICENSING.md) | License generation, activation, and lifecycle |
| [DISTRIBUTION.md](docs/DISTRIBUTION.md) | Build, deliver, and verify customer distributions |
| [ENV-COMPARISON.md](docs/ENV-COMPARISON.md) | Development vs production environment differences |
| [GOOGLE-MAPS.md](docs/GOOGLE-MAPS.md) | Google Maps API key setup and troubleshooting |
| [ATTRIBUTION.md](docs/ATTRIBUTION.md) | Third-party licenses and required attribution |
| [CSV_FORMAT.md](docs/CSV_FORMAT.md) | Upload file format reference |
| [GUIDE.md](docs/GUIDE.md) | Comprehensive platform guide |
| [ERROR-MAP.md](docs/ERROR-MAP.md) | Error message traceability map |

---

## Key References

| Resource | URL |
|----------|-----|
| VROOM API | https://github.com/VROOM-Project/vroom/blob/master/docs/API.md |
| OSRM HTTP API | https://project-osrm.org/docs/v5.24.0/api/ |
| Kerala OSM Data | https://download.openstreetmap.fr/extracts/asia/india/kerala.osm.pbf |
| Google Geocoding API | https://developers.google.com/maps/documentation/geocoding |
