# Routing Optimization Platform

A modular delivery-route optimization system. First deployment: **Kerala LPG cylinder delivery** (HPCL distributor with 13 three-wheelers, 30–50 deliveries/day, 5 km radius from depot in Kochi).

The architecture is designed to be **reusable across any delivery business** — the Kerala LPG app is the first consumer, not the only one.

---

## Quick Start

```bash
# 1. Clone & setup Python
git clone <REPO_URL> routing_opt && cd routing_opt
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Environment config
cp .env.example .env
# Edit .env → add your GOOGLE_MAPS_API_KEY

# 3. Start infrastructure (OSRM + VROOM + API)
sudo service docker start          # WSL2 only
docker compose up -d

# 4. Run tests
pytest tests/ -v

# 5. Open the driver app
# http://localhost:8000/driver/
```

> **Full setup guide** (first-time, including Docker install, OSRM data prep): see [SETUP.md](SETUP.md)

---

## How It Works

```
CSV Upload → Geocoding → Route Optimization → Driver PWA
     │            │              │                  │
 CDCMS export  Google Maps   VROOM + OSRM      Mobile-friendly
 (30 orders)   API (cached)  (milliseconds)    offline-capable
```

1. **Upload** a CSV of today's delivery orders (from HPCL CDCMS system or manual entry)
2. **Geocode** addresses to GPS coordinates (Google Maps API, results cached in local file store)
3. **Optimize** routes using VROOM (Capacitated Vehicle Routing Problem solver) with OSRM travel times
4. **Serve** optimized routes to drivers via a Progressive Web App (PWA) they open in Chrome

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
│   │   ├── interfaces.py          ← Geocoder protocol
│   │   └── google_adapter.py      ← Google Maps + SHA256 file cache
│   └── data_import/               ← Data ingestion
│       ├── interfaces.py          ← DataImporter protocol
│       └── csv_importer.py        ← CSV/Excel CDCMS import
│
├── apps/
│   └── kerala_delivery/           ← FIRST APP: Kerala LPG business logic
│       ├── config.py              ← All Kerala-specific constants
│       ├── api/main.py            ← FastAPI backend (upload, optimize, serve)
│       └── driver_app/            ← PWA (index.html, sw.js, manifest.json)
│
├── tests/                         ← Mirrors source structure (58 tests)
│   ├── conftest.py                ← Shared fixtures (Kerala coordinates)
│   ├── core/                      ← Unit tests for all core modules
│   └── apps/                      ← API endpoint tests
│
├── infra/
│   └── Dockerfile                 ← API container image
├── docker-compose.yml             ← OSRM + VROOM + API stack
├── data/
│   └── sample_orders.csv          ← 30 example orders around Kochi
│
├── plan/                          ← Design docs & session memory
│   ├── kerala_delivery_route_system_design.md   ← Authoritative design doc
│   └── session-journal.md         ← Cross-session development log
│
├── .env.example                   ← Template for environment vars
├── requirements.txt               ← Pinned Python packages
├── SETUP.md                       ← Complete new-developer setup guide
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
| `POST` | `/api/upload-orders` | Upload CSV → geocode → optimize → return assignment |
| `GET` | `/api/routes` | List all routes (summary per vehicle) |
| `GET` | `/api/routes/{vehicle_id}` | Full route detail for a specific driver |
| `POST` | `/api/routes/{vehicle_id}/stops/{order_id}/status` | Update delivery status (`delivered` / `failed` / `pending`) |
| `GET` | `/driver/` | Serves the driver PWA |

### Upload CSV Format

See [data/sample_orders.csv](data/sample_orders.csv) for a working example.

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
| Depot location | 9.9716°N, 76.2846°E (Kochi) | HPCL godown |
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
| **Routing engine** | OSRM (Docker, port 5000) | Travel time & distance matrices |
| **Optimizer** | VROOM (Docker, port 3000) | Vehicle routing problem solver (CVRP) |
| **Backend** | Python 3.12 + FastAPI | API server, orchestration |
| **Data models** | Pydantic v2 | Validation, serialization |
| **Geocoding** | Google Maps API (cached) | Address → GPS coordinates |
| **Driver app** | PWA (HTML/JS/Service Worker) | Mobile-friendly, offline-capable |
| **Infrastructure** | Docker Compose | Single-command deployment |

---

## Running Tests

```bash
source .venv/bin/activate
pytest tests/ -v
```

**58 tests** covering:
- Core models (location, order, vehicle, route validation)
- OSRM adapter (travel time, distance matrix, safety multiplier)
- VROOM adapter (route optimization, priority, unassigned handling)
- Google geocoder (API calls, caching, error handling)
- CSV importer (standard/custom columns, coordinate passthrough, error recovery)
- API endpoints (health, routes, status updates, upload pipeline, monsoon multiplier)

All external services (OSRM, VROOM, Google Maps) are mocked in tests — no Docker required to run the test suite.

---

## Docker Services

```bash
# Start all services
docker compose up -d

# Check status
docker compose ps

# View logs
docker compose logs -f api

# Stop
docker compose down
```

| Service | Container | Port | Health Check |
|---------|-----------|------|-------------|
| OSRM | `osrm-kerala` | 5000 | `curl http://localhost:5000/health` |
| VROOM | `vroom-solver` | 3000 | — |
| API | `lpg-api` | 8000 | `curl http://localhost:8000/health` |

> **Note:** OSRM requires preprocessed Kerala map data in `data/osrm/`. See [SETUP.md](SETUP.md) for download and preprocessing steps.

---

## Environment Variables

Copy `.env.example` → `.env` and configure:

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_MAPS_API_KEY` | Yes (for geocoding) | Google Cloud API key with Geocoding API enabled |
| `OSRM_URL` | No | Defaults to `http://localhost:5000` |
| `VROOM_URL` | No | Defaults to `http://localhost:3000` |
| `POSTGRES_USER` | No | For Phase 2+ database |
| `POSTGRES_PASSWORD` | No | For Phase 2+ database |

---

## Development Phases

| Phase | Status | Description |
|-------|--------|-------------|
| **0: Baseline** | ✅ Complete | Core modules, data models, tests, API, driver PWA, Docker setup |
| **1: Single-Vehicle** | 🔜 Next | Test with real OSRM data, calibrate speed profiles, shadow mode |
| **2: Multi-Vehicle + Dashboard** | Planned | GPS tracking, ops dashboard, time windows |
| **3: Production** | Planned | Cloud deploy, monitoring, automated daily use |
| **4: Advanced** | Planned | ML travel-time models, dynamic re-routing, notifications |

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
- **Setup:** New contributors follow [SETUP.md](SETUP.md) (15–20 min to working environment).

---

## Key References

| Resource | URL |
|----------|-----|
| Design Document | [plan/kerala_delivery_route_system_design.md](plan/kerala_delivery_route_system_design.md) |
| VROOM API | https://github.com/VROOM-Project/vroom/blob/master/docs/API.md |
| OSRM HTTP API | https://project-osrm.org/docs/v5.24.0/api/ |
| Kerala OSM Data | https://download.openstreetmap.fr/extracts/asia/india/kerala.osm.pbf |
| Google Geocoding API | https://developers.google.com/maps/documentation/geocoding |
