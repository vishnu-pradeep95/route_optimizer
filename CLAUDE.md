# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

### Docker Stack (full system)
```bash
# Start all services (PostgreSQL, OSRM, VROOM, API + dashboard)
docker compose up -d

# Start with dashboard hot-reload for development
docker compose --profile dev up -d
# → Vite dev server at http://localhost:5173/

# Rebuild API after Python code changes
docker compose build api && docker compose up -d --no-deps api

# Rebuild dashboard after React/TS changes (production build)
docker compose build dashboard-build && docker compose up -d --no-deps dashboard-build

# View API logs
docker compose logs -f api

# WSL note: start Docker daemon first
sudo service docker start
```

### Python Tests
```bash
source .venv/bin/activate
pytest tests/ -v                          # All 736 tests
pytest tests/core/routing/ -v             # Single module
pytest tests/apps/ -v                     # API endpoint tests
pytest -k "test_upload" -v                # By name pattern
pytest -m integration -v                  # Integration-only (needs real DB)
```
All external services (OSRM, VROOM, Google Maps, PostgreSQL) are mocked — no Docker needed for `pytest`.

### Playwright E2E Tests (requires Docker stack running)
```bash
npx playwright test                         # All E2E tests
npx playwright test --project=api           # API endpoints only
npx playwright test --project=driver-pwa    # Driver PWA only
npx playwright test --project=dashboard     # Dashboard only
```
Set `API_KEY` env var for authenticated endpoint tests.

### Dashboard (React)
```bash
cd apps/kerala_delivery/dashboard
npm install
npm run dev      # Vite dev server (localhost:5173)
npm run build    # Production build
npm run lint     # ESLint
```

### Database Migrations
```bash
source .venv/bin/activate
# Migrations run automatically via db-init container on docker compose up
# Manual migration (if needed):
DATABASE_URL="postgresql+asyncpg://routing:password@localhost:5432/routing_opt" alembic upgrade head
# Create new migration:
alembic revision --autogenerate -m "description"
```
Migration scripts: `infra/alembic/versions/`. Config: `alembic.ini` (script_location = `infra/alembic`).

## Architecture

### Core vs Apps Separation
```
core/   → Generic, reusable modules. NEVER imports from apps/.
          Configured via dependency injection.
apps/   → Business-specific consumers. Kerala LPG is the first app.
```

### Service Architecture
- **PostgreSQL + PostGIS** (port 5432) — orders, routes, vehicles, drivers, settings, route_validations, GPS telemetry, geocode cache
- **OSRM** (port 5000) — travel time/distance matrices from Kerala OpenStreetMap data
- **VROOM** (port 3000) — CVRP solver, connects to OSRM for travel times
- **FastAPI API** (port 8000) — orchestrates upload → geocode → optimize → persist → serve
- **Dashboard** — React 19 + Vite 7 + MapLibre GL JS, served at `/dashboard/`
- **Driver PWA** — vanilla JS single `index.html`, served at `/driver/`

### Data Pipeline
```
CDCMS Export → cdcms_preprocessor.py → Geocode (Google Maps, PostGIS cache) → VROOM optimize → PostgreSQL → Driver PWA
```
**Two-step upload flow:** The API uses a parse-upload → driver preview → upload-orders sequence. First, `POST /api/parse-upload` parses and geocodes the CSV without persisting. The dashboard then shows a driver assignment preview. Finally, `POST /api/upload-orders` commits the optimized routes to the database.

### Core Module Interfaces
Every core module defines a `Protocol` (structural typing) before implementation. This allows swapping backends (e.g., OSRM → Valhalla, VROOM → OR-Tools) without changing calling code. Key protocols:
- `core/routing/interfaces.py` — `RoutingEngine`
- `core/optimizer/interfaces.py` — `RouteOptimizer`
- `core/geocoding/interfaces.py` — `Geocoder`, `AsyncGeocoder`
- `core/data_import/interfaces.py` — `DataImporter`

### Database Layer
- ORM models: `core/database/models.py` (SQLAlchemy 2.0 + GeoAlchemy2)
- Async sessions: `core/database/connection.py` (asyncpg driver)
- Repository pattern: `core/database/repository.py` (all CRUD)
- Schema managed by Alembic (async migrations)

## Coding Conventions

- **Tailwind v4 prefix**: `tw:` (colon, NOT hyphen). Examples: `tw:flex`, `tw:btn`, `tw:card-body`
- **CSS selectors**: escaped colon `.tw\:flex`, `.tw\:card-body`
- **Responsive variants**: `lg:tw:stats-horizontal`
- **DaisyUI components** also get `tw:` prefix: `tw:btn`, `tw:badge`, `tw:table`
- **Driver PWA**: single `index.html`, no build step, vanilla JS
- **Dashboard**: React/TypeScript/Vite with Tailwind v4 + DaisyUI v5
- **Python**: type hints everywhere, docstrings on every function, `asyncio_mode = auto` in pytest
- **API auth**: write endpoints require `X-API-Key` header; non-sensitive reads are open for driver app access

## Non-Negotiable Safety Constraints

These are Kerala MVD and business rules enforced in code — never remove or bypass:
- No countdown timers in any UI
- Minimum 30-minute delivery windows
- Speed alerts at 40 km/h
- 1.3× safety multiplier on all travel time estimates
- No PII in the optimizer (names/phones stay in source CSV)

## Testing Requirements — Driver PWA

**After every feature change or bug fix to the Driver PWA (`apps/kerala_delivery/driver_app/`):**

Run comprehensive end-to-end Playwright MCP testing. Do NOT rely on human verification for functional checks. Human verification is only for subjective visual/UX feedback.

### E2E Test Checklist — Driver PWA

Start API server, navigate to `http://localhost:8000/driver/`, and systematically verify:

**1. Upload Screen (initial state)**
- [ ] Page loads without console errors
- [ ] Upload icon (🛺) renders in container
- [ ] "Today's Deliveries" heading visible
- [ ] "Upload Delivery List" button visible and clickable
- [ ] File input triggers on button click
- [ ] Upload status area present

**2. Tabs & Navigation**
- [ ] "Delivery List" tab visible with list icon
- [ ] "Map View" tab visible with map icon
- [ ] Tab switching works (list ↔ map)

**3. Route View (after CSV upload + driver selection)**
- [ ] Header shows route info and stats
- [ ] Progress bar renders with correct segments
- [ ] "Last updated" timestamp + Refresh button visible
- [ ] Hero card shows for first pending stop
- [ ] Compact cards show for remaining stops
- [ ] Navigate button (full-width, 66px)
- [ ] Done + Fail buttons (60px each)

**4. Interactions**
- [ ] "Done" marks stop delivered, toast appears, auto-advance works
- [ ] "Fail" opens dark dialog modal (NOT browser confirm)
- [ ] Fail modal: reason dropdown, "Yes, Failed" + "Cancel" buttons
- [ ] Cancel closes modal without action
- [ ] "Yes, Failed" marks stop, red toast, auto-advance
- [ ] Call Office FAB visible (bottom-right, phone icon)
- [ ] All-done banner appears when all stops complete

**5. Responsiveness**
- [ ] Mobile viewport (393x851) — no overflow, no clipping
- [ ] Elements scale correctly on small screens

**6. Navigation Flow**
- [ ] Upload → Driver Selector → Route View → full cycle
- [ ] ⇄ (reset) button returns to driver selector
- [ ] "Upload New List" returns to upload screen
- [ ] Navigate button opens Google Maps in new tab

**7. All-Done State**
- [ ] Select a 1-stop driver (e.g., "Rajesh"), mark Done
- [ ] Green "Route complete!" banner appears
- [ ] Progress bar fully green
- [ ] Banner dismiss (x) button works

**8. API Endpoints**
- [ ] `GET /health` — 200
- [ ] `GET /driver/` — serves PWA index.html
- [ ] `POST /api/upload-orders` — accepts CSV/Excel files
- [ ] `GET /api/routes` — returns all routes
- [ ] `GET /api/routes/{vehicle_id}` — returns route data
- [ ] `POST /api/routes/{vehicle_id}/stops/{order_id}/status` — updates delivery status
- [ ] `GET /api/vehicles` — returns vehicle list
- [ ] `GET /api/runs` — returns optimization runs
- [ ] `POST /api/telemetry` — accepts telemetry data

### How to Test

**Docker rebuild required for API changes:** The API runs in Docker. After modifying `api/main.py` or any Python code:
```bash
docker compose build api && docker compose up -d --no-deps api
```

Use Playwright MCP tools:
1. `browser_navigate` to the driver app URL
2. `browser_snapshot` to get accessibility tree
3. `browser_click` / `browser_type` to interact
4. `browser_console_messages` to check for errors
5. `browser_take_screenshot` for visual verification

Traverse every button, link, and interactive element. Check console for errors after each action.

## Environment

- **Python**: 3.12, venv at `.venv/`
- **Node.js**: v24
- **OS**: Ubuntu 24.04 LTS on WSL2
- **Env vars**: Copy `.env.example` → `.env`. Key vars: `POSTGRES_PASSWORD`, `GOOGLE_MAPS_API_KEY`, `API_KEY`, `CORS_ALLOWED_ORIGINS` (must include `http://localhost:5173` for dashboard dev)
