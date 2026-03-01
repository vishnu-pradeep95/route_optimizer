# Technology Stack

**Analysis Date:** 2026-03-01

## Languages

**Primary:**
- Python 3.12.3 - Backend API, data processing, geocoding, route optimization pipelines
- TypeScript 5.9.3 - Frontend dashboard and driver PWA
- JavaScript/Node.js (npm) - Frontend build tooling

**Secondary:**
- SQL - Database schema and PostGIS queries via SQLAlchemy ORM
- Bash - Docker initialization scripts, OSRM preprocessing

## Runtime

**Environment:**
- Python 3.12 (see `requirements.txt` for exact versions)
- Node.js/npm (package manager for frontend)

**Package Managers:**
- pip - Python dependency management
- npm - JavaScript/TypeScript dependency management
- Lockfile status: `requirements.txt` pinned; `package-lock.json` for Node

## Frameworks

**Backend:**
- FastAPI 0.129.1 - REST API framework for order upload, geocoding, optimization, telemetry
  - Location: `apps/kerala_delivery/api/main.py`
  - Uses Uvicorn 0.41.0 as ASGI server
  - Lifespan management for async database engine lifecycle

**Frontend:**
- React 19.2.0 - Dashboard and driver PWA UI
- Vite 7.3.1 - Modern build tool and dev server
  - Config: `apps/kerala_delivery/dashboard/vite.config.ts`
  - Dev proxy configured to forward API calls to FastAPI backend

**Database:**
- SQLAlchemy 2.0.46 - ORM for async PostgreSQL access
  - Async driver: asyncpg 0.31.0 (fastest Python PostgreSQL driver)
  - Connection pooling: 5 base + 10 overflow connections
  - Session per request pattern with explicit commit

**Geospatial:**
- GeoAlchemy2 0.18.1 - PostGIS integration for geometry columns (Point, 4326)
- GeoPandas 1.1.2 - Geospatial data manipulation
- Shapely 2.1.2 - Geometric operations
- PyProj 3.7.2 - Coordinate transformations

**Testing:**
- pytest 9.0.2 - Test runner
- pytest-asyncio 1.3.0 - Async test support for FastAPI endpoints
- Located at `tests/` directory with integration and unit test suites

**Linting/Type Checking:**
- TypeScript compiler (tsc) - Type checking for frontend
- ESLint 9.39.1 - JavaScript/TypeScript linting (frontend)
- eslint-plugin-react-hooks 7.0.1, eslint-plugin-react-refresh 0.4.24

## Key Dependencies

**Critical:**
- asyncpg 0.31.0 - Native PostgreSQL driver, required for FastAPI async pattern
- Pydantic 2.12.5 - Data validation and serialization (API request/response models)
- Alembic 1.18.4 - Database migration management with async support
- FastAPI + Uvicorn - Required for async request handling with 13 drivers + dashboard

**Infrastructure:**
- httpx 0.28.1 - Async HTTP client for Google Maps, OSRM, VROOM APIs
- requests 2.32.5 - Fallback HTTP client
- slowapi 0.1.9 - Rate limiting middleware (protects expensive endpoints like upload, telemetry)
- python-dotenv 1.2.1 - Environment variable loading
- python-multipart 0.0.22 - CSV/Excel file upload handling

**Geospatial/Spatial:**
- numpy 2.4.2 - Numerical operations (distance calculations, data processing)
- pandas 3.0.1 - Data frame operations for CSV import and order preprocessing
- openpyxl 3.1.5 - Excel file parsing (CDCMS exports)
- PyYAML 6.0.3 - Route configuration (VROOM config in `infra/vroom-conf/config.yml`)

**Utilities:**
- qrcode 8.2 - QR code generation for routes (driver navigation links)
- Pillow 12.1.1 - Image processing for QR codes
- python-dateutil 2.9.0.post0 - Date/time utilities
- greenlet 3.3.2, wrapt 2.1.1 - SQLAlchemy async internals

## Configuration

**Environment Variables:**
- `API_KEY` - Timing-safe API key for POST endpoints (HMAC-SHA256)
- `ENVIRONMENT` - Controls security enforcement ("development", "staging", "production")
- `GOOGLE_MAPS_API_KEY` - Google Geocoding API (required, has $200/month free tier)
- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` - Database credentials
- `BACKEND_HOST`, `BACKEND_PORT` - FastAPI server binding (default: 0.0.0.0:8000)
- `OSRM_URL` - OSRM instance URL (default: http://localhost:5000)
- `VROOM_URL` - VROOM solver URL (default: http://localhost:3000)
- `CORS_ALLOWED_ORIGINS` - Comma-separated list (no wildcards in production)
- `RATE_LIMIT_ENABLED` - Enable rate limiting (default: true)
- `DATABASE_URL` - Full async PostgreSQL connection string with asyncpg dialect

**Configuration Files:**
- `.env.example` - Template for environment variables
- `apps/kerala_delivery/config.py` - Business logic constants (depot location, fleet specs, delivery zones)
  - Piaggio Ape Xtra LDX specs: 446 kg max weight, 30 cylinder capacity
  - Kerala-specific radius, monsoon multipliers, shift hours
- `infra/vroom-conf/config.yml` - VROOM solver configuration (OSRM routing backend)
- `infra/postgres/init.sql` - Initial schema with spatial indexes on coordinates

## Build & Deployment

**Backend Build:**
- Dockerfile: `infra/Dockerfile`
- Stages: base Python 3.12 image → install dependencies → run migrations → start Uvicorn
- Uses Docker Compose for local development and production orchestration

**Frontend Build:**
- Dockerfile: `infra/Dockerfile.dashboard`
- Vite build pipeline: TypeScript compilation → React JSX → optimized bundle
- Dev server: `npm run dev` runs Vite on port 5173 with API proxy to 8000

**Database Migrations:**
- Alembic ORM-based migrations in `infra/alembic/versions/`
- Auto-run by db-init container on startup: `alembic upgrade head`
- Uses sync SQLAlchemy for migration execution (Alembic doesn't support async)

**Docker Compose Services:**
- `db`: PostgreSQL 16 + PostGIS 3.5
- `osrm-init`: Idempotent init container (downloads & preprocesses Kerala OSM data)
- `osrm`: OSRM backend (port 5000) — handles routing queries
- `vroom`: VROOM solver (port 3000) — calls OSRM internally for travel times
- `db-init`: Auto-runs migrations before API starts
- `api`: FastAPI backend (port 8000) — orchestrates geocoding, optimization, driver routes

## Platform Requirements

**Development:**
- Docker Engine + Docker Compose (for OSRM, VROOM, PostgreSQL)
- Python 3.12 with pip
- Node.js (for npm/Vite)
- Internet for Google Maps API key validation, Kerala OSM data download (~150 MB)

**Production:**
- Deployment target: Docker Compose or Kubernetes
- Requires persistent volume for PostgreSQL data and OSRM preprocessed data (~1.5 GB)
- External services: Google Maps Geocoding API key (paid), optional license key for hardware binding
- Network: CORS-protected (no wildcard origins), rate-limited POST endpoints

---

*Stack analysis: 2026-03-01*
