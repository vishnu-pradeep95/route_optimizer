# External Integrations

**Analysis Date:** 2026-03-01

## APIs & External Services

**Google Maps Geocoding:**
- Service: Google Geocoding API v1
- What it's used for: Address geocoding (converting "MG Road, Kochi" to GPS coordinates)
- SDK/Client: httpx 0.28.1 (async HTTP client)
- Auth: `GOOGLE_MAPS_API_KEY` environment variable
- Implementation: `core/geocoding/google_adapter.py`
  - Endpoint: `https://maps.googleapis.com/maps/api/geocode/json`
  - Region bias: India (fallback for ambiguous addresses)
  - Caching: Local JSON file cache in `data/geocode_cache/` (moves to PostGIS in Phase 2)
  - Cost: $5 per 1000 requests; $200/month free credit covers ~40,000 requests
  - Accuracy: ~63% for Indian addresses; used for CDCMS orders without GPS coordinates

**OpenStreetMap (via OSRM):**
- Service: Open Source Routing Machine
- What it's used for: Travel time/distance matrix for route optimization
- Docker container: `osrm/osrm-backend:latest` (port 5000)
- Implementation: `core/routing/osrm_adapter.py`
- Connection: HTTP API (`OSRM_URL` env var, default: http://localhost:5000)
- Data source: Kerala OpenStreetMap extract (~150 MB PBF file)
  - Auto-downloaded by osrm-init container on first startup
  - Preprocessed using Multi-Level Dijkstra for fast queries
  - Updated quarterly as OSM data refreshes
- Usage: Called internally by VROOM solver for travel times; also available for direct queries

**VROOM Route Optimizer:**
- Service: Vehicle Routing Open-source Optimization Machine
- What it's used for: Assigns orders to drivers, sequences stops, generates optimized routes
- Docker container: `vroomvrp/vroom-docker:v1.14.0-rc.2` (port 3000)
- Implementation: `core/optimizer/vroom_adapter.py`
- Connection: HTTP API (`VROOM_URL` env var, default: http://localhost:3000)
- Dependencies: Uses OSRM internally for travel times (configured in `infra/vroom-conf/config.yml`)
- Algorithm: High-performance meta-heuristics for CVRP/VRPTW
  - Solves 300+ orders in milliseconds
  - Supports capacity constraints, time windows, multiple vehicles
- Configuration: `infra/vroom-conf/config.yml` sets OSRM backend routing

## Data Storage

**Databases:**
- PostgreSQL 16 + PostGIS 3.5 (primary persistence layer)
  - Container: `postgis/postgis:16-3.5` (port 5432)
  - Connection: Async via asyncpg + SQLAlchemy 2.0
  - URL: `postgresql+asyncpg://routing:{password}@{host}:5432/routing_opt`
  - Authentication: Username (`POSTGRES_USER`), password (`POSTGRES_PASSWORD`) from env vars
  - ORM models: `core/database/models.py`
    - VehicleDB - fleet vehicles (max weight, capacity, depot location as geometry Point)
    - Routes, RouteAssignments, RouteStops - optimized routes and telemetry
    - GPS telemetry and historical data (Phase 2)
  - Spatial features:
    - Geometry column type via GeoAlchemy2 for GPS coordinates (SRID 4326/WGS84)
    - GiST spatial indexes for fast proximity queries ("find drivers within 500m")
    - ST_Distance, ST_DWithin for distance calculations

**File Storage:**
- Local filesystem only (no S3/cloud storage at this time)
  - Location: `data/` directory
  - Uploaded CDCMS CSV/Excel files: `data/uploads/`
  - Geocoding cache: `data/geocode_cache/` (JSON format)
  - OSRM preprocessed data: `data/osrm/` (1.5 GB, downloaded on init)
  - Persisted in Docker via named volume `pgdata` and bind mounts

**Caching:**
- Redis: Not used
- Local JSON cache: `core/geocoding/cache.py` - addresses to coordinates
- Database query cache: Implicit via SQLAlchemy session
- Rate limiting: slowapi (in-memory with sliding window counters)

## Authentication & Identity

**API Security:**
- Custom API Key (timing-safe HMAC-SHA256 comparison)
  - Header: `X-API-Key`
  - Env var: `API_KEY`
  - Enforcement: All POST endpoints + sensitive GET endpoints require key
  - Fallback: Empty key allowed in "development" mode only
  - Implementation: `apps/kerala_delivery/api/main.py` (lines 14, 24, 77-90)

**License Management:**
- Hardware-bound license validation on startup
  - Module: `core/licensing/license_manager.py`
  - Behavior: Invalid license returns 503 in production, optional in development
  - Checked at app startup via lifespan hook

**CORS Security:**
- Allowed origins: Configured via `CORS_ALLOWED_ORIGINS` env var
- Format: Comma-separated list (no wildcards in production)
- Default: http://localhost:8000, http://localhost:5173 (dev only)
- Middleware: `fastapi.middleware.cors.CORSMiddleware`

**No external auth provider** (Auth0, Okta, etc.) — uses internal API key scheme

## Monitoring & Observability

**Error Tracking:**
- Not detected - no Sentry, DataDog, or similar integration

**Logging:**
- Python logging module (standard library)
- Logger setup: `logging.getLogger(__name__)` in each module
- Key log points:
  - API key validation warnings on startup (lines 83-90 in main.py)
  - License status on startup (valid/grace/expired)
  - Rate limit enforcement (via slowapi)
  - Database migration status (alembic upgrade head)
  - OSRM/VROOM API failures

**Health Checks:**
- FastAPI health endpoint: `GET /health` (served by main API)
- Docker healthchecks:
  - PostgreSQL: `pg_isready -U routing -d routing_opt` (every 10s)
  - OSRM: `curl -f http://localhost:5000/health` (every 30s)
  - VROOM: No explicit health check (depends_on osrm)

## CI/CD & Deployment

**Hosting:**
- Docker Compose (development and production)
- Scalable to Kubernetes (no K8s-specific code; Compose generates images)
- Reverse proxy option: Caddy (config in `infra/caddy/`)

**CI Pipeline:**
- Not detected - no GitHub Actions, GitLab CI, Jenkins, etc. workflows found
- Manual deployment: `docker compose up -d`

**Environment:**
- Docker Image Registry: Default Docker Hub (osrm/osrm-backend, vroomvrp/vroom-docker, postgis/postgis)

## Environment Configuration

**Required env vars (production):**
- `GOOGLE_MAPS_API_KEY` - Google Geocoding API key (must be valid)
- `API_KEY` - Secrets for POST endpoint protection
- `POSTGRES_PASSWORD` - Database password (change from default)
- `ENVIRONMENT` - Set to "staging" or "production" (enables security warnings)

**Optional env vars:**
- `OSRM_URL` - Override OSRM endpoint (default: http://localhost:5000)
- `VROOM_URL` - Override VROOM endpoint (default: http://localhost:3000)
- `CORS_ALLOWED_ORIGINS` - Override CORS allowlist
- `RATE_LIMIT_ENABLED` - Disable rate limiting in tests (default: true)
- `DATABASE_URL` - Override PostgreSQL connection string
- `BACKEND_HOST`, `BACKEND_PORT` - Override Uvicorn binding

**Secrets location:**
- `.env` file (not committed, use `.env.example` as template)
- Docker Compose: Environment variables passed from host `.env`
- Never commit `.env` or actual API keys

## Webhooks & Callbacks

**Incoming:**
- None detected - API is request-response only

**Outgoing:**
- None detected - no integration with third-party webhook endpoints

## Data Import/Export

**Import:**
- CSV/Excel upload via `POST /api/upload`
- Format: CDCMS export (HPCL delivery orders)
- Processing: `core/data_import/csv_importer.py` + `core/data_import/cdcms_preprocessor.py`
- Validation: Column mapping, address parsing, GPS bounds checking (India-wide sanity check)

**Export:**
- JSON routes: `GET /api/vehicle/{vehicle_id}/route`
- QR codes: Generate navigation links from route segments
- Response format: Optimized route with stops, time windows, waypoint URLs

## Third-Party Integrations Summary

**Active:**
- Google Maps Geocoding (paid API)
- OpenStreetMap (open data, self-hosted OSRM)
- VROOM Solver (open source, self-hosted Docker)
- PostgreSQL + PostGIS (open source, self-hosted Docker)

**Not Used:**
- Other geocoders (Nominatim, Mapbox)
- Cloud databases (AWS RDS, Google Cloud SQL)
- Message queues (Redis, RabbitMQ)
- External storage (AWS S3, Google Cloud Storage)
- Telemetry/APM services (New Relic, DataDog, Sentry)
- Authentication services (Auth0, Okta, Firebase Auth)
- SMS/email providers (Twilio, SendGrid)

---

*Integration audit: 2026-03-01*
