# Codebase Structure

**Analysis Date:** 2026-03-01

## Directory Layout

```
routing_opt/
├── apps/                          # Application-specific implementations
│   ├── kerala_delivery/           # Kerala LPG delivery (first customer)
│   │   ├── api/                   # FastAPI application
│   │   ├── config.py              # Business config (depot, fleet, cylinders)
│   │   ├── dashboard/             # React/TypeScript ops dashboard
│   │   └── driver_app/            # PWA for drivers (mobile)
│   └── __init__.py
│
├── core/                          # Reusable delivery optimization core (business-agnostic)
│   ├── models/                    # Pydantic domain models
│   ├── database/                  # SQLAlchemy ORM + persistence layer
│   ├── optimizer/                 # Route optimization adapters
│   ├── routing/                   # Distance/routing service adapters
│   ├── geocoding/                 # Address → GPS conversion + caching
│   ├── data_import/               # CSV/Excel parsing + validation
│   ├── licensing/                 # License key management
│   └── __init__.py
│
├── tests/                         # Test suite
│   ├── core/                      # Tests for core/ modules
│   ├── apps/                      # Tests for apps/ modules
│   ├── integration/               # Integration tests (OSRM+VROOM+DB)
│   ├── scripts/                   # Tests for helper scripts
│   ├── conftest.py                # Shared pytest fixtures
│   └── test_e2e_pipeline.py       # End-to-end workflow tests
│
├── scripts/                       # Utility scripts for operations
│   ├── import_orders.py           # Bulk import orders from CSV
│   ├── geocode_batch.py           # Pre-geocode addresses (builds cache)
│   ├── compare_routes.py          # Debug/validate route differences
│   ├── generate_license.py        # Create license.dat files
│   └── get_machine_id.py          # Get machine ID for licensing
│
├── infra/                         # Infrastructure as code & config
│   ├── alembic/                   # Database migration scripts
│   ├── postgres/                  # PostgreSQL initialization (init.sql)
│   ├── caddy/                     # Reverse proxy config (production)
│   └── vroom-conf/                # VROOM solver configuration files
│
├── data/                          # Persistent data directories
│   ├── geocode_cache/             # SQLite cache of geocoding results
│   └── osrm/                      # OSRM map data (Kerala PBF file)
│
├── plan/                          # Planning & design documents
│   ├── kerala_delivery_route_system_design.md  # System design doc
│   └── session-journal.md         # Development session notes
│
├── docker-compose.yml             # Local dev: FastAPI, PostgreSQL, OSRM, VROOM
├── docker-compose.prod.yml        # Production: Same but with Caddy, stronger config
├── alembic.ini                    # Alembic config for migrations
├── requirements.txt               # Python dependencies (FastAPI, SQLAlchemy, etc.)
├── README.md                      # Project overview & quick start
├── SETUP.md                       # Installation & environment setup
├── GUIDE.md                       # Operational guide for end users
└── DEPLOY.md                      # Deployment procedures
```

## Directory Purposes

**apps/kerala_delivery/:**
- Purpose: First delivery business implementation (Kerala LPG distributor)
- Contains: Application-specific code that would differ for other businesses (Mumbai food delivery would have different config, UI, etc.)
- Key files: `config.py` (Vatakara depot coords, vehicle specs, cylinder weights), `api/main.py` (FastAPI server)

**apps/kerala_delivery/api/:**
- Purpose: FastAPI HTTP server exposing the core optimization logic as a REST API
- Contains: 25+ route handlers for uploading orders, fetching routes, updating telemetry, managing vehicles, generating QR codes
- Key files: `main.py` (70 KB, lifespan context manager + all endpoints), `qr_helpers.py` (QR code generation for print-outs)

**apps/kerala_delivery/dashboard/:**
- Purpose: React/TypeScript single-page app for operations staff to manage routes, monitor drivers, upload orders
- Contains: React components (App, pages, components), API client wrapper, TypeScript types
- Build config: `vite.config.ts`, `tsconfig.json`, `package.json` (React 18+, TypeScript, Leaflet for maps)
- Output: Runs on dev server or bundles to `dist/` for production

**apps/kerala_delivery/driver_app/:**
- Purpose: Mobile-first PWA for drivers in the field — no build step, served as static HTML
- Contains: `index.html` (all CSS + JavaScript inline), `manifest.json` (PWA metadata), `sw.js` (service worker for offline support)
- Deployment: FastAPI mounts this directory at `/api/routes/{vehicle_id}` so drivers access via mobile browser

**core/models/:**
- Purpose: Pydantic domain models representing the business domain (Order, Vehicle, Route, Location)
- Contains: 4 models — `location.py`, `vehicle.py`, `order.py`, `route.py`
- Key characteristics: All use Pydantic BaseModel for validation + serialization, not tied to any specific database or framework

**core/database/:**
- Purpose: Persistence layer — SQLAlchemy ORM models, async engine/session, and repository pattern
- Contains:
  - `models.py`: VehicleDB, DriverDB, OrderDB, RouteDB, RouteStopDB, TelemetryDB, OptimizationRunDB, GeocodeCacheDB (ORM models mirroring PostgreSQL schema)
  - `connection.py`: Async engine creation, session factory, database URL configuration
  - `repository.py`: 1000+ lines of CRUD and conversion logic; no raw SQL (all SQLAlchemy)

**core/optimizer/:**
- Purpose: Route optimization solver abstraction
- Contains:
  - `interfaces.py`: Optimizer protocol (structural typing)
  - `vroom_adapter.py`: Implementation calling VROOM Docker on port 3000, converts our Order/Vehicle models to VROOM JSON and back

**core/routing/:**
- Purpose: Distance/travel-time service abstraction
- Contains:
  - `interfaces.py`: DistanceMatrix and TravelTime protocols
  - `osrm_adapter.py`: Implementation calling OSRM Docker on port 5000, applies safety multiplier (1.3)

**core/geocoding/:**
- Purpose: Address → GPS conversion with caching
- Contains:
  - `interfaces.py`: Geocoder protocol
  - `google_adapter.py`: Calls Google Geocoding API, returns lat/lon + confidence score
  - `cache.py`: Wraps geocoder, stores results in SQLite (or DB) to avoid repeated API calls and costs

**core/data_import/:**
- Purpose: Parse CSV/Excel files (CDCMS HPCL export or generic delivery lists) into Order objects
- Contains:
  - `csv_importer.py`: Generic CSV parser with column mapping
  - `cdcms_preprocessor.py`: CDCMS-specific preprocessing (recognizes column names, validates HPCL data)
  - `interfaces.py`: Importer protocol

**core/licensing/:**
- Purpose: License key management (prevents operation without valid license)
- Contains: `license_manager.py` — validates license.dat files (machine ID, expiry, capability flags)
- Enforcement: Middleware in FastAPI checks license before allowing uploads

**tests/:**
- Structure mirrors `core/` and `apps/` — each module has a `test_*.py` file alongside
- Organization:
  - `tests/core/models/test_models.py` — tests Pydantic validation
  - `tests/core/optimizer/test_vroom_adapter.py` — mocks VROOM HTTP, validates request format and response parsing
  - `tests/core/routing/test_osrm_adapter.py` — mocks OSRM HTTP, validates distance matrix logic
  - `tests/core/geocoding/test_*.py` — mocks Google API, tests caching
  - `tests/apps/kerala_delivery/api/test_api.py` — FastAPI TestClient, tests all endpoints
  - `tests/integration/test_osrm_vroom_pipeline.py` — requires real Docker containers (OSRM, VROOM), end-to-end test
  - `tests/test_e2e_pipeline.py` — full workflow: upload CSV → optimize → check routes match expected
  - `conftest.py` — shared fixtures (sample orders, vehicles, locations using real Kerala coordinates)

**scripts/:**
- Purpose: Operations utilities (not part of the API)
- `import_orders.py`: Read CSV, insert into database (bulk-load before API available)
- `geocode_batch.py`: Pre-geocode all addresses in database (warming the cache before operations)
- `compare_routes.py`: Compare two optimization runs (debugging, route stability analysis)
- `generate_license.py`: Generate license.dat for a machine
- `get_machine_id.py`: Display this machine's ID (needed for license generation)

**infra/:**
- Purpose: Infrastructure configuration for deployment
- `alembic/`: Database migrations (version control for schema changes)
  - `versions/`: SQL migration files (auto-generated by Alembic comparing models to DB, or manual)
- `postgres/`: `init.sql` — creates tables, indexes, PostGIS extension (initial schema, run once)
- `caddy/`: Reverse proxy config (production), HTTPS termination, rate limiting at edge
- `vroom-conf/`: VROOM solver configuration (cost matrices, algorithm parameters)

**data/:**
- `geocode_cache/`: SQLite file persisting geocoding results (keyed by address hash)
- `osrm/`: Kerala map data (PBF format, ~130 MB) used by OSRM container at runtime

**plan/:**
- `kerala_delivery_route_system_design.md`: System architecture and design decisions (comprehensive 3000+ word doc)
- `session-journal.md`: Development progress log (date, work completed, issues resolved)

## Key File Locations

**Entry Points:**
- `apps/kerala_delivery/api/main.py`: FastAPI application (uvicorn entry point)
- `apps/kerala_delivery/dashboard/src/main.tsx`: React app root
- `apps/kerala_delivery/driver_app/index.html`: Driver PWA
- `scripts/import_orders.py`: Batch import script
- `docker-compose.yml`: Local dev environment

**Configuration:**
- `apps/kerala_delivery/config.py`: Business constants (depot, fleet, vehicle specs, safety multiplier)
- `docker-compose.yml`: Service URLs (PostgreSQL, OSRM, VROOM), API key, database URL
- `.env`: Runtime environment variables (sourced by docker-compose, loaded by FastAPI)
- `infra/alembic/alembic.ini`: Migration tool config

**Core Logic:**
- `core/models/order.py`: Order domain model with lifecycle states
- `core/models/route.py`: Route output model with stops and metrics
- `core/optimizer/vroom_adapter.py`: Main optimization logic (VROOM integration)
- `core/routing/osrm_adapter.py`: Distance calculations (OSRM integration)
- `core/geocoding/google_adapter.py`: Address-to-GPS conversion (Google integration)
- `core/database/repository.py`: All persistence operations

**Testing:**
- `tests/conftest.py`: Shared fixtures (sample orders, vehicles, Kerala locations)
- `tests/test_e2e_pipeline.py`: Full workflow test
- `tests/integration/test_osrm_vroom_pipeline.py`: External service integration test
- `tests/apps/kerala_delivery/api/test_api.py`: API endpoint tests

## Naming Conventions

**Files:**
- `snake_case.py` for all Python files
- `test_*.py` for test files (pytest discovery pattern)
- `_private.py` for internal utilities not exported
- `*_adapter.py` for external service integrations (vroom_adapter, osrm_adapter, google_adapter)
- `*_db.py` suffix for ORM models (VehicleDB, OrderDB not just Vehicle, Order)

**Directories:**
- `core/` — reusable, business-agnostic code
- `apps/{business}/` — business-specific implementations
- `tests/` — test suite (mirrors source structure)
- `infra/` — infrastructure/deployment config
- `scripts/` — one-off utilities

**Python Classes:**
- PascalCase for all classes (BaseModel, VehicleDB, Order, VroomAdapter)
- Protocol classes for interfaces (Geocoder, Optimizer, Router — no leading I)
- Suffix `DB` for ORM models to distinguish from Pydantic models (VehicleDB vs Vehicle)

**Python Functions:**
- snake_case for public functions (optimize_routes, save_optimization_run)
- _snake_case (leading underscore) for internal/private functions (_make_point, _check_api_key)
- async def for I/O-bound functions (database, HTTP, file)

**Variables:**
- snake_case for all variables
- SCREAMING_SNAKE_CASE for module-level constants (VEHICLE_MAX_WEIGHT_KG, SAFETY_MULTIPLIER)

**API Routes:**
- Kebab-case in URLs (`/api/upload-orders`, `/api/google-maps`, `/api/qr-sheet`)
- RESTful: GET for read, POST for create, PUT for update, DELETE for remove
- Grouped by resource: `/api/routes/*`, `/api/vehicles/*`, `/api/telemetry/*`

**Database:**
- Table names: snake_case, plural (vehicles, orders, routes, route_stops, optimization_runs)
- Column names: snake_case (vehicle_id, max_weight_kg, depot_location)
- Foreign keys: {table_singular}_id (vehicle_id, route_id)
- Indexes on frequently filtered columns (vehicle_id, status, created_at)

## Where to Add New Code

**New Feature (e.g., "Realtime traffic-aware optimization"):**
- Core logic: Add new adapter in `core/optimizer/` (e.g., `vroom_adapter_traffic.py`) implementing Optimizer protocol
- API endpoint: Add route in `apps/kerala_delivery/api/main.py`
- Config: Add constants to `apps/kerala_delivery/config.py` if business-specific
- Tests: Add `tests/core/optimizer/test_vroom_traffic.py` + integration test in `tests/integration/`

**New Component/Module:**
- If reusable: Place in `core/` (e.g., `core/ml_model/` for ML-based demand forecast)
  - Structure: `__init__.py`, `interfaces.py` (protocol), `{service}_adapter.py` (implementation)
- If business-specific: Place in `apps/kerala_delivery/` (e.g., `apps/kerala_delivery/hpcl_integration.py`)
- Add tests in `tests/core/ml_model/` or `tests/apps/kerala_delivery/`

**Utility Functions:**
- Shared helpers: `core/utils.py` (coordinate helpers, validators)
- Business-specific: `apps/kerala_delivery/utils.py`
- Import style: `from core.utils import format_location` (not internal detail imports)

**New Database Table:**
- Add ORM model to `core/database/models.py` (inherit from Base, add __tablename__)
- Add SQL to `infra/postgres/init.sql` (initial creation)
- Create Alembic migration: `alembic revision --autogenerate -m "Add foo table"`
- Add repository methods to `core/database/repository.py` (save_foo, get_foo_by_id, list_foo)

**Frontend Components:**
- React: New component in `apps/kerala_delivery/dashboard/src/components/` or `pages/`
  - File: `ComponentName.tsx` (PascalCase)
  - Style: Colocated `ComponentName.css` or inline styles
  - Exports: Default export the component, named exports for types/interfaces
- Driver PWA: Edit `apps/kerala_delivery/driver_app/index.html` (all-in-one file)
  - No build step — changes visible immediately after refresh

## Special Directories

**Excluded from version control (.gitignore):**
- `node_modules/` — npm dependencies (generated, huge)
- `dist/` — built assets (generated)
- `.env` — secrets (local override only, `.env.example` is committed)
- `.venv/` — Python virtual environment (generated)
- `__pycache__/` — Python bytecode (generated)
- `data/osrm/*.pbf` — large map data files (downloaded at runtime)
- `.pytest_cache/`, `.coverage` — test artifacts (generated)

**Generated, NOT committed:**
- `alembic/versions/*.py` — auto-generated by `alembic revision --autogenerate`
- `apps/kerala_delivery/dashboard/dist/` — built app bundle

**Committed (not generated):**
- `infra/postgres/init.sql` — source of truth for initial schema
- `core/database/models.py` — ORM models (Alembic compares these to DB)
- `.env.example` — template for environment variables (no secrets)
- `requirements.txt` — Python dependency versions (for reproducible builds)

---

*Structure analysis: 2026-03-01*
