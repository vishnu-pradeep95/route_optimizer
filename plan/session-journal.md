# Session Journal — Kerala Delivery Route System

> **How this works:** The `Session Journal` agent appends a compact entry after each
> working session. The main `Kerala Delivery Route Architect` agent reads this file
> at session start to restore context. Keep entries short — this file is injected
> into every session's context window.
>
> **Format rules:**
> - One entry per session, newest at the bottom
> - Use `DECIDED:` prefix for final decisions (searchable)
> - Use `OPEN:` prefix for unresolved questions
> - Use `BLOCKED:` prefix for items that need external input

---

## 2025-07-15 — Project Bootstrap

**Phase:** Pre-Phase 0 (planning)
**What happened:**
- Created main architect agent at `.github/agents/kerala-delivery-route-architect.agent.md`
- Created session journal system for cross-session memory
- Created `copilot-instructions.md` for always-on context
- Reviewed and cross-referenced design document with business requirements

**Key facts gathered:**
- Solo developer (others contribute later via git) → maintainability priority
- No mobile dev experience → step-by-step guidance needed, consider PWA-first
- Budget flexible → can use managed services to reduce dev complexity
- 40–50 deliveries/day, data comes from spreadsheets
- Need to define spreadsheet format + add privacy/obfuscation layer
- 24/7 operations, co-founder is non-technical

**OPEN:** Exact spreadsheet column format not yet defined
**OPEN:** Mobile approach not finalized (PWA vs native vs Fleetbase Navigator)
**OPEN:** Driver shift structure not documented
**OPEN:** Data privacy/obfuscation approach not finalized

---

## 2026-02-21 — Second Code Review: All 13 Fixes Implemented, 58 Tests Green

**Phase:** 0 (core implementation complete, hardening)
**What happened:**
- Performed second full code review (0 CRITICAL, 5 WARNING, 8 INFO findings)
- Implemented all 13 fixes across 7 files: `core/data_import/csv_importer.py`, `core/data_import/interfaces.py`, `apps/kerala_delivery/config.py`, `apps/kerala_delivery/api/main.py`, `apps/kerala_delivery/driver_app/sw.js`, `tests/apps/kerala_delivery/api/test_api.py`, `tests/core/data_import/test_csv_importer.py`
- Added 4 new tests: upload-and-optimize (valid CSV, empty CSV), monsoon multiplier (July=1.95×, Feb=1.3×) → **58 tests passing**
- Refactored API tests: yield-based `with_assignment`/`no_assignment` fixtures replace 7× try/finally blocks

**DECIDED:** `DEFAULT_CYLINDER_WEIGHTS={}` in core (business-agnostic); Kerala app passes its own lookup via config
**DECIDED:** `StatusUpdate.status` uses `Literal["delivered","failed","pending"]` — Pydantic returns 422 for invalid values
**DECIDED:** SW install uses `Promise.allSettled` per-resource so CDN failure doesn't block activation
**DECIDED:** All 4 Protocol interfaces now have `@runtime_checkable`
**OPEN:** Thread-safety for `_current_assignment`/`_current_orders` globals — needs proper locking in Phase 2
**OPEN:** `MIN_DELIVERY_WINDOW_MINUTES` enforcement not yet wired into optimizer (Phase 2)
**Next steps:** First review cycle complete — move to Phase 1 (Docker integration testing with real OSRM/VROOM)

---

## 2026-02-21 — Phase 1 Core Complete, Code Review #3 Fixes Applied, 74 Tests

**Phase:** 1 (single-vehicle prototype — core criteria met)
**What happened:**
- Fixed VROOM distance=0 bug: VROOM requires `"options": {"g": true}` to include distance in response
- Fixed cumulative duration bug: VROOM step-level distance/duration are cumulative from route start, not per-leg — adapter now subtracts previous step
- Created OSRM setup script (`scripts/osrm_setup.sh`) — Kerala data preprocessed with MLD algorithm
- Added 9 integration tests (OSRM + VROOM end-to-end), all passing with Docker services
- Created `scripts/compare_routes.py` — 68.1% distance reduction vs naive baseline (target ≥15%)
- Code Review #3: 0 CRITICAL, 3 WARNING, 8 INFO — all findings implemented:
  - W1: Fixed `test_api.py` mock data to use cumulative VROOM step values
  - W2: Made `compare_routes.py` configurable via CLI args (no longer tightly coupled to Kerala config)
  - W3: Added `access.log` to `.gitignore`, removed from git cache
  - I1: Pinned exact priority values (70, 10) in test
  - I2: Added VROOM HTTP error propagation test
  - I3: Fixed `test_import_standard_csv` to use `cylinder_weight_lookup`
  - I4: Replaced bare `Exception` with `ValidationError` in model tests
  - I5: Added `service_time_minutes` → seconds conversion test
  - I6: Added weight/capacity verification test
  - I7: Added `int()` truncation comment in vroom_adapter
  - I8: Added `DataImporter` protocol compliance test
- Updated design doc: PWA instead of Kotlin, MLD instead of CH, VROOM implementation notes, phase status markers
- **74 tests passing** (65 unit + 9 integration)

**DECIDED:** PWA for driver app (Phase 1-2); evaluate Fleetbase Navigator or native if PWA limits hit
**DECIDED:** MLD algorithm for OSRM (faster preprocessing, supports profile changes without full rebuild)
**DECIDED:** VROOM Docker tag = `v1.14.0-rc.2` (no `latest` available)
**OPEN:** Thread-safety for `_current_assignment`/`_current_orders` globals — needs proper locking in Phase 2
**OPEN:** `MIN_DELIVERY_WINDOW_MINUTES` enforcement not yet wired into optimizer (Phase 2)
**OPEN:** OSRM speed profile not yet calibrated with real GPS data
**OPEN:** No PostgreSQL/PostGIS database yet — currently using in-memory storage + CSV files
**OPEN:** No real customer data loaded — using sample_orders.csv with 30 synthetic Kochi orders

---

## 2026-02-21 — Phase 2 DB Layer, Code Review #4, Educational Comments, Docs Update

**Phase:** 2 (multi-vehicle + database — DB layer complete, dashboard pending)
**What happened:**
- Built full PostgreSQL + PostGIS persistence layer: async SQLAlchemy ORM models (`OrderDB`, `RouteDB`, `RouteStopDB`, `OptimizationRunDB`, `TelemetryDB`, `GeocodeCacheDB`), repository with async CRUD, Docker Compose with PostGIS 16-3.5, `infra/postgres/init.sql` schema + seed data
- Fixed broken API tests (10 failing after removing in-memory globals) — rewrote `test_api.py` with `app.dependency_overrides[get_session]` DB session mocks → 103 tests passing
- Code Review #4: 0 CRITICAL, 6 WARNING, 7 INFO — all 13 fixes implemented:
  - W1: Chained `selectinload(RouteDB.stops).selectinload(RouteStopDB.order)` to prevent `MissingGreenlet` in async
  - W2: Persist `delivery_window_start`/`end` from Order → OrderDB for audit trail
  - W3: Health endpoint uses `app.version` instead of hardcoded `"0.1.0"`
  - W4: Extracted `get_recent_runs()` to repository; removed inline SQL + inline imports from endpoints
  - W5: Removed duplicate `DATABASE_URL` from `config.py` (single source of truth in `connection.py`)
  - W6: Made GPS accuracy threshold configurable (`config.GPS_ACCURACY_THRESHOLD_M = 50.0`)
  - I1–I4: Import moved out of loop, rowcount guard on `update_stop_status`, 5 new endpoint tests, geocode cache hit test
- Added educational comments to 7+ files: `core/database/__init__.py` (architecture diagram), `models.py` (GiST index teaching), `connection.py` (session lifecycle), `docker-compose.yml` (PostGIS/volumes/healthcheck), `init.sql` (UUID trade-offs, scaling projections, ST_MakePoint gotcha)
- Rewrote "Educational Code Standards" in `.github/agents/kerala-delivery-route-architect.agent.md`: WHY Rule, 5 teaching moment categories, 12-row comment depth table, good/bad examples
- Updated `README.md`: added `core/database/` to tree, new API endpoints (`/api/runs`, `/api/telemetry`), PostgreSQL in Docker services table, 109→109 test count, Phase 1 ✅, Phase 2 🔧
- Updated `SETUP.md`: verify includes `sqlalchemy, asyncpg, geoalchemy2`, `POSTGRES_PASSWORD` required, expanded quick reference with DB commands

**Files changed:** `core/database/{__init__,connection,models,repository}.py`, `apps/kerala_delivery/{config,api/main}.py`, `core/data_import/csv_importer.py`, `infra/postgres/init.sql`, `docker-compose.yml`, `tests/apps/kerala_delivery/api/test_api.py`, `.github/agents/kerala-delivery-route-architect.agent.md`, `README.md`, `SETUP.md`

**DECIDED:** Repository pattern for all DB access — endpoints never write inline SQL
**DECIDED:** GPS accuracy threshold is configurable per-deployment (not hardcoded 50m)
**DECIDED:** Geocode cache lives in PostGIS (replaces SHA256 file cache for multi-instance deploys)
**DECIDED (resolves OPEN):** PostgreSQL + PostGIS is live — no longer using in-memory storage
**DECIDED (resolves OPEN):** Thread-safety for globals is resolved — DB sessions replace `_current_assignment`/`_current_orders`
**OPEN:** Upload pipeline not yet fully wired to DB (repository exists but upload endpoint still needs final integration)
**OPEN:** Alembic migrations not yet initialized (schema managed by `init.sql` for now)
**OPEN:** Ops dashboard not started (React + MapLibre GL JS planned)
**OPEN:** Offline-first PWA sync not implemented
**OPEN:** `MIN_DELIVERY_WINDOW_MINUTES` enforcement not yet wired into optimizer
**OPEN:** OSRM speed profile not yet calibrated with real GPS data
**OPEN:** No real customer data loaded — using sample_orders.csv with 30 synthetic Kochi orders
**Next steps:** 1. Wire upload pipeline to persist via repository 2. Initialize Alembic migrations 3. Start ops dashboard (React + map)

---

## 2026-02-21 — Code Review #5: Security Hardening, Type Fixes, 9 New Tests, Agent Checklists

**Phase:** 2 (multi-vehicle + database — DB layer complete, security hardened, dashboard pending)
**Commit:** `3fddd6a` — "Phase 2 DB layer + Code Review #4 & #5 fixes + security hardening" (32 files, +3523/-313)
**Tests:** 118 passing (109 → 118), all unit tests in ~1.25s

**What happened:**
- Code Review #5 delivered 3 CRITICAL, 7 WARNING, 10 INFO findings — all implemented except C1 (authentication, deferred by design)
- Security hardening: CORS env-based whitelist, Dockerfile non-root user, input validation on query params, atomic cache writes, cache corruption recovery
- Type safety fixes: `save_telemetry` return type, `DistanceMatrix` nullable durations/distances, timezone-aware `created_at`
- Architecture fix: hardcoded India coordinate bounds removed from `core/` → injectable `coordinate_bounds` param on `CsvImporter` (reusability preserved)
- Dead code removed: `OptimizeRequest`, `DriverRouteResponse` (unused Pydantic models in main.py), `routes_to_assignment()` (unused function in repository.py)
- 9 new tests: coordinate bounds injection, cache corruption recovery, all-geocoding-failure 400, delivery location proof-of-delivery, telemetry endpoint (3 tests)
- Agent files updated: security + optimization checklists added to implementer, code-reviewer, deep-researcher, session-journal, partner-explainer agents (5 agents total)

**Files changed (17 source + 3 test + 5 agent + 4 docs/config):**
| File | Changes |
|---|---|
| `apps/kerala_delivery/api/main.py` | CORS env whitelist, filename None guard, tmp_path init, Query validation, removed 2 unused classes, CsvImporter gets coordinate_bounds |
| `apps/kerala_delivery/config.py` | Added `INDIA_COORDINATE_BOUNDS = (6.0, 37.0, 68.0, 97.5)` |
| `core/routing/interfaces.py` | `DistanceMatrix.durations`/`.distances` → `list[list[float \| None]]` |
| `core/data_import/csv_importer.py` | Injectable `coordinate_bounds` param, removed hardcoded India bounds |
| `core/geocoding/google_adapter.py` | Atomic file write (_save_cache), corruption recovery (_load_cache), added logging |
| `core/optimizer/vroom_adapter.py` | `int()` → `round()` for weight values |
| `core/models/route.py` | `_utcnow()` helper, timezone-aware `created_at` fields |
| `core/database/repository.py` | `save_telemetry` return type fixed, removed `routes_to_assignment()` |
| `infra/Dockerfile` | Non-root user `appuser` (UID 1001) |
| `.env.example` | Added `CORS_ALLOWED_ORIGINS` |
| `.github/agents/implementer.agent.md` | Security checklist (9 rules) + optimization checklist (6 rules) |
| `.github/agents/code-reviewer.agent.md` | Security section (8 checks) + performance section (8 checks) |
| `.github/agents/deep-researcher.agent.md` | Security evaluation table (7 checks) + optimization table (6 checks) |
| `.github/agents/session-journal.agent.md` | Security context capture rules |
| `.github/agents/partner-explainer.agent.md` | Security explanation translations for non-tech partner |
| `tests/apps/kerala_delivery/api/test_api.py` | 5 new tests (geocoding failure, delivery location, telemetry ×3) |
| `tests/core/data_import/test_csv_importer.py` | 2 new tests (bounds reject, no-bounds accept) |
| `tests/core/geocoding/test_google_adapter.py` | 2 new tests (corrupt cache, non-dict cache) |

**Security decisions made this session:**
- **DECIDED:** CORS origins from `CORS_ALLOWED_ORIGINS` env var (comma-separated), defaults to `http://localhost:8000,http://localhost:3000`
- **DECIDED:** Docker container runs as non-root user `appuser` (UID 1001, group `appgroup`)
- **DECIDED:** Query param validation via FastAPI `Query()` with `ge`/`le` constraints on all `limit` params
- **DECIDED:** Geocode file cache uses atomic writes (write to `.tmp` then `os.replace`) to prevent corruption
- **DECIDED:** Cache corruption recovery: bad JSON or non-dict content logged and cache reset to empty (no crash)
- **DECIDED:** Coordinate bounds are injected into `CsvImporter`, not hardcoded in core — any business can define their own bounds

**Type safety decisions:**
- **DECIDED:** `DistanceMatrix` allows `None` in durations/distances (OSRM returns null for unroutable pairs)
- **DECIDED:** `save_telemetry` returns `tuple[UUID | None, bool]` (None when accuracy below threshold)
- **DECIDED:** All `created_at` fields use `datetime.now(timezone.utc)` — no naive datetimes
- **DECIDED:** VROOM weight conversion uses `round()` not `int()` (avoids systematic undercount)

**OPEN: C1 — Authentication not implemented.** No auth on any endpoint. Needs design decision: API key (simpler, good for internal tool) vs JWT (better for future multi-tenant). Recommend API key for Phase 2, JWT for Phase 3+. This is the highest-priority security gap.
**OPEN:** Upload pipeline not fully wired to DB persistence (repository exists, upload endpoint needs final integration)
**OPEN:** Alembic migrations not initialized (schema managed by `init.sql` for now)
**OPEN:** Ops dashboard not started (React + MapLibre GL JS planned)
**OPEN:** Offline-first PWA sync not implemented
**OPEN:** `MIN_DELIVERY_WINDOW_MINUTES` enforcement not yet wired into optimizer
**OPEN:** OSRM speed profile not yet calibrated with real GPS data
**OPEN:** No real customer data loaded — using sample_orders.csv with 30 synthetic Kochi orders
**OPEN:** Rate limiting not implemented on any endpoint (noted in agent security checklists)

**Architecture notes for next session:**
- `core/` modules are clean — no business-specific hardcoding remains. Coordinate bounds, cylinder weights, speed limits all injected from `apps/kerala_delivery/config.py`
- All 5 agent files now have security + optimization awareness. New code will be checked against these rules automatically.
- Repository layer is complete and tested. The upload endpoint in `main.py` (line ~210-350) is the next integration point.
- Docker Compose runs: PostgreSQL 16 + PostGIS 3.5, OSRM (Kerala MLD), VROOM v1.14.0-rc.2, API (FastAPI)
- Test structure: `tests/` mirrors `core/` and `apps/`. Run `pytest` from project root. Integration tests need Docker services.

**Next steps:**
1. Implement authentication (API key recommended for Phase 2)
2. Wire upload pipeline to persist orders/routes via repository
3. Initialize Alembic for schema migrations
4. Start ops dashboard (React + MapLibre GL JS)
5. Push to remote: `git push origin main`

---

## 2026-02-22 — Phase 2: Alembic Migrations + Ops Dashboard + Code Review #6 Fixes

**Phase:** 2 (multi-vehicle + database — Alembic + dashboard complete)
**Tests:** 144 passing (118 → 144)

**What happened:**
- **Alembic async migrations** initialized. `env.py` uses async engine (asyncpg), imports `DATABASE_URL` from `core.database.connection` (single source of truth), and filters PostGIS system tables via `include_object()` callback.
- **3 migrations created & applied:**
  1. `215c8204dc10` — baseline stamp (represents init.sql schema)
  2. `ccbb9fc2db2c` — align REAL→Float, nullable→NOT NULL, add spatial indexes
  3. `4228dedc0975` — drop duplicate `_orm`-suffix telemetry indexes (Review #6 fix W1)
- **React + TypeScript ops dashboard** built at `apps/kerala_delivery/dashboard/`:
  - Stack: React 19 + Vite 7 + MapLibre GL JS 5 + react-map-gl 8
  - Pages: LiveMap (real-time vehicle tracking, 15s telemetry polling), RunHistory (expandable optimization run table)
  - Components: RouteMap (polylines + stop markers + live GPS dots), VehicleList (sidebar with ETA ranges), StatsBar (summary cards)
  - Typed API client (`lib/api.ts`) for all 6 backend endpoints
  - Production build: 0 TS errors, 78 modules, ~170 KB gzip
- **Code Review #6** (1 CRITICAL, 3 WARNING, 5 INFO) — **all findings implemented:**
  - C1: Removed hardcoded DB password from `alembic.ini` → placeholder + env.py imports from connection.py
  - W1: Reconciled duplicate telemetry indexes (renamed ORM indexes to match init.sql, created migration to drop `_orm` duplicates)
  - W2: Added TODO for batch endpoint to replace N+1 telemetry fetch pattern in LiveMap
  - W3: Added TODO for Phase 3 drag-and-drop route adjustment in RouteMap
  - I1: Fixed wrong icon (⏱ → ⚖️ for weight in VehicleList)
  - I3: Fixed missing Fragment key in RunHistory
  - I4: Made telemetry fields nullable (`speed_kmh`, `accuracy_m`, `heading` → `number | null`) + null guards in RouteMap
  - I5: Added educational docstring to type-alignment migration

**Files changed (25+):**
| Area | Files |
|---|---|
| Alembic | `alembic.ini`, `infra/alembic/{env.py, script.py.mako}`, `infra/alembic/versions/{215c8204dc10,ccbb9fc2db2c,4228dedc0975}*.py` |
| Dashboard | `apps/kerala_delivery/dashboard/{package.json, tsconfig*.json, vite.config.ts, index.html, src/{App,main}.tsx, types.ts, lib/api.ts, components/{RouteMap,VehicleList,StatsBar}.tsx, pages/{LiveMap,RunHistory}.tsx, vite-env.d.ts}` |
| Backend | `core/database/models.py` (index rename) |

**DECIDED:** Alembic env.py imports `DATABASE_URL` from `core.database.connection` — no credentials in alembic.ini
**DECIDED:** ORM index names match init.sql exactly (no `_orm` suffix) — prevents autogenerate duplicates
**DECIDED:** Dashboard uses MapLibre GL JS (open source) + OpenStreetMap tiles — no map API key needed
**DECIDED:** 15-second telemetry polling interval (matches driver app's GPS send interval)
**DECIDED:** Dashboard dev server proxies `/api/*` and `/health` to FastAPI on port 8000
**DECIDED (resolves OPEN):** Alembic migrations initialized — no longer managed by init.sql only
**DECIDED (resolves OPEN):** Ops dashboard exists — React + MapLibre GL JS with live tracking

**OPEN:** N+1 telemetry fetch pattern in LiveMap — needs batch endpoint (W2, Phase 3)
**OPEN:** Drag-and-drop route adjustment not implemented (W3, Phase 3)
**OPEN:** No dashboard tests (I2 — deferred to Phase 3)
**OPEN:** Authentication not implemented (C1 from Review #5 — still highest-priority security gap)
**OPEN:** Upload pipeline not fully wired to DB persistence
**OPEN:** Offline-first PWA sync not implemented
**OPEN:** `MIN_DELIVERY_WINDOW_MINUTES` enforcement not yet wired into optimizer
**OPEN:** OSRM speed profile not yet calibrated with real GPS data
**OPEN:** No real customer data loaded — using sample_orders.csv with 30 synthetic Kochi orders
**OPEN:** Rate limiting not implemented on any endpoint

**Next steps:**
1. Implement API key authentication (highest-priority security gap)
2. Wire upload pipeline to persist via repository
3. Add dashboard E2E tests (Playwright)
4. Phase 3: batch telemetry endpoint, drag-and-drop route editing, production deploy

---
