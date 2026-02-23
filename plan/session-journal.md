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

## 2026-02-23 — Phase 2: Batch Telemetry, Rate Limiting, Fleet CRUD, Window Enforcement + Code Reviews #7–8

**Phase:** 2 (multi-vehicle + database — fleet management + hardening)
**Tests:** 164 passing (144 → 164)

**What happened:**

### Review of prior session's OPEN items
Two items listed as OPEN in the previous journal entry were already implemented:
- "Authentication not implemented" → **Already done.** `verify_api_key()` dependency with `APIKeyHeader("X-API-Key")`, 5 auth tests, `.env.example` docs.
- "Upload pipeline not fully wired" → **Already done.** `repo.save_optimization_run()` + `session.commit()` in upload endpoint, stores OrderDB/RouteDB/RouteStopDB.

### Batch telemetry endpoint
- Added `GET /api/telemetry/fleet` — returns latest GPS ping per vehicle in one query using PostgreSQL `DISTINCT ON(vehicle_id)` + `ORDER BY recorded_at DESC`. Replaces the N+1 pattern where dashboard called `/api/telemetry/{vehicle_id}?limit=1` once per vehicle. At 13 vehicles polling every 15s, this cuts 13 HTTP requests + 13 DB queries down to 1+1.
- **Route ordering fix**: `/api/telemetry/fleet` **must** be defined before `/api/telemetry/{vehicle_id}` or FastAPI captures "fleet" as a vehicle_id.
- Added `POST /api/telemetry/batch` — accepts up to 100 pings in one request via `TelemetryBatchRequest`. Validates, filters (accuracy >50m), checks speed alerts (>40 km/h), saves with `add_all()` batch insert.
- Updated dashboard: `FleetTelemetryResponse` type, `fetchFleetTelemetry()` API function, rewrote `LiveMap.tsx` to use single batch call instead of N+1.
- Repository: `get_fleet_latest_telemetry()`, `save_telemetry_batch()` with `add_all()` for batch performance.

### Rate limiting (slowapi)
- Installed `slowapi==0.1.9` with `Limiter(key_func=get_remote_address)`.
- Per-endpoint limits: upload=10/min, telemetry single=120/min, telemetry batch=20/min, status update=60/min, fleet CRUD write=20/min, fleet delete=10/min.
- `RATE_LIMIT_ENABLED` env var toggle — defaults to `true`, set `false` in tests.
- Test fixture disables limiter via `limiter.enabled = False` to avoid 429s in test suite.

### Fleet management CRUD
- 7 new endpoints: `GET/POST /api/vehicles`, `GET/PUT/DELETE /api/vehicles/{vehicle_id}`
- Repository functions: `get_all_vehicles()`, `get_vehicle_by_vehicle_id()`, `create_vehicle()` (with depot PostGIS geometry), `update_vehicle()` (field whitelist pattern), `deactivate_vehicle()` (soft-delete).
- `_vehicle_to_dict(v: "VehicleDB")` helper centralizes PostGIS→JSON conversion.
- `vehicle_type` validated via `Literal["diesel", "electric", "cng"]` on `VehicleCreate`/`VehicleUpdate`.

### MIN_DELIVERY_WINDOW enforcement
- Step 1b in upload endpoint: detects windows shorter than `MIN_DELIVERY_WINDOW_MINUTES` (30 min) and **widens** them by extending `window_end` rather than rejecting orders. Handles midnight crossing. Logs count of widened windows.
- Updated `config.py` to reference enforcement location.

### Code Review #7 (1C, 4W, 6I) — all resolved
| Finding | Fix |
|---|---|
| C1: CORS allow_methods missing PUT/DELETE | Added `["GET", "POST", "PUT", "DELETE"]` with comment |
| W1: save_telemetry_batch per-ping add() | Changed to `add_all()` batch |
| W2: TS TelemetryPing.recorded_at not nullable | Changed to `string \| null` with JSDoc |
| W3: Fleet telemetry no auth | Added TODO Phase 3 comment about read-scoped auth |
| W4: vehicle_type not validated | `Literal["diesel", "electric", "cng"]` |
| I2: _vehicle_to_dict missing type hint | Added `TYPE_CHECKING` import + `"VehicleDB"` annotation |

### Code Review #8 (re-review: 0C, 1W, 2I) — resolved
| Finding | Fix |
|---|---|
| W1: create_vehicle docstring omitted "cng" | Updated to `'diesel', 'electric', 'cng'` |
| I1: No test for invalid vehicle_type | Added `test_create_vehicle_rejects_invalid_type` (422) |
| I2: allow_headers=["*"] could tighten | Noted, low-risk — deferred |

### Tests added (20 new, 164 total)
| Class | Tests | What they verify |
|---|---|---|
| TestFleetTelemetry | 2 | Fleet dict response, empty fleet returns zero |
| TestTelemetryBatch | 4 | Multi-ping save, discard/alerts count, >100 rejection, empty batch |
| TestFleetManagement | 9 | List all, active_only, details, 404, create, duplicate 409, update, delete, **invalid type 422** |
| TestDeliveryWindowEnforcement | 2 | 10-min window widened to 30, valid 60-min unchanged |
| TestRateLimiting | 1 | Rate limit hit returns 429 |

**Files changed (8):**
| Area | Files |
|---|---|
| Backend | `apps/kerala_delivery/api/main.py` (batch telemetry, rate limiting, fleet CRUD, window enforcement, CORS fix, Literal validation, TYPE_CHECKING import) |
| Repository | `core/database/repository.py` (fleet telemetry, fleet CRUD, batch add_all) |
| Config | `apps/kerala_delivery/config.py` (TODO removed, enforcement reference) |
| Dashboard | `apps/kerala_delivery/dashboard/src/{types.ts, lib/api.ts, pages/LiveMap.tsx}` (FleetTelemetryResponse, batch fetch) |
| Tests | `tests/apps/kerala_delivery/api/test_api.py` (20 new tests, rate limiter fixture) |
| Deps | `requirements.txt` (slowapi), `.env.example` (RATE_LIMIT_ENABLED) |

**DECIDED:** Rate limiting uses slowapi + get_remote_address — simple, works behind reverse proxy with X-Forwarded-For
**DECIDED:** Rate limiter disabled in tests via `limiter.enabled = False` + env var
**DECIDED:** Fleet telemetry uses PostgreSQL DISTINCT ON — single query for all vehicles
**DECIDED:** Vehicle soft-delete (is_active=False) rather than hard delete
**DECIDED:** Vehicle update uses field whitelist pattern — prevents arbitrary column injection
**DECIDED:** Delivery window widening over rejection — more operationally friendly
**DECIDED:** vehicle_type limited to Literal["diesel", "electric", "cng"] per design doc Section 4
**DECIDED (resolves OPEN):** N+1 telemetry fetch replaced with batch endpoint
**DECIDED (resolves OPEN):** Rate limiting implemented on all write endpoints
**DECIDED (resolves OPEN):** MIN_DELIVERY_WINDOW enforcement wired into upload pipeline
**DECIDED (resolves OPEN):** Authentication was already implemented (APIKeyHeader + verify_api_key)
**DECIDED (resolves OPEN):** Upload pipeline was already wired to DB persistence

**OPEN:** Read-level auth for fleet telemetry (TODO Phase 3 — fleet-wide location data is sensitive)
**OPEN:** CORS allow_headers=["*"] could be tightened to specific headers (low priority)
**OPEN:** Drag-and-drop route adjustment not implemented (Phase 3)
**OPEN:** No dashboard tests (deferred to Phase 3)
**OPEN:** Offline-first PWA sync not implemented
**OPEN:** OSRM speed profile not yet calibrated with real GPS data
**OPEN:** No real customer data loaded — using sample_orders.csv with 30 synthetic Kochi orders

**Next steps:**
1. Dashboard E2E tests (Playwright)
2. Phase 3: production deployment (Docker Compose on VPS)
3. Read-scoped auth for fleet-wide endpoints
4. OSRM speed profile calibration with real GPS data
5. Offline-first driver PWA

---
## 2025-07-18 — Phase 2 Completion: Fleet UI + Geocoding Cache + Batch Scripts

**Phase:** Phase 2 (Multi-Vehicle + Dashboard) — near-complete
**Tests:** 180 passing (164 → 180, +16 new)
**TypeScript:** 0 errors

### What happened:
1. **Fleet Management dashboard page** (FleetManagement.tsx, 750 lines)
   - Full CRUD UI: vehicle table with inline add/edit, deactivate/reactivate
   - Validation: speed limit capped at 40 km/h (MVD rule), weight capped at 496 kg
   - Default weight corrected to 446 kg (496 × 0.9 safety factor per design doc)
   - Added `Vehicle`, `VehiclesResponse` types; `apiWrite` + fleet API functions
   - Added 🚛 Fleet nav tab in App.tsx

2. **PostGIS geocoding cache** (core/geocoding/cache.py, ~300 lines)
   - CachedGeocoder: Decorator pattern wrapping upstream Geocoder
   - Cache-first strategy: PostGIS lookup → upstream API → save to cache
   - Driver-verified saves with confidence=0.95
   - Graceful degradation: cache failures fall through to upstream
   - Stats tracking (hits/misses/errors) with summary formatting

3. **AsyncGeocoder protocol** added to core/geocoding/interfaces.py
   - Async variant for DB-backed implementations (CachedGeocoder)
   - Sync Geocoder protocol unchanged for GoogleGeocoder

4. **Batch scripts** (scripts/)
   - `import_orders.py`: CSV → DB import with optional geocoding, dry-run mode
   - `geocode_batch.py`: Batch geocoding with cache-first, cost estimation, dry-run

5. **Tests** (tests/core/geocoding/test_cache.py, 16 tests)
   - Cache hits, misses, error handling, driver-verified saves, batch, stats
   - All mocking repository layer — no real DB needed

6. **Code Review #9** — found 2 CRITICAL (speed/weight validation missing), 6 WARNING, 8 INFO
   - All issues fixed in same session, re-review confirmed 0 CRITICAL

### Files created:
- `apps/kerala_delivery/dashboard/src/pages/FleetManagement.tsx` (750 lines)
- `apps/kerala_delivery/dashboard/src/pages/FleetManagement.css` (312 lines)
- `core/geocoding/cache.py` (~300 lines)
- `scripts/import_orders.py` (~260 lines)
- `scripts/geocode_batch.py` (~345 lines)
- `tests/core/geocoding/test_cache.py` (~350 lines)

### Files modified:
- `apps/kerala_delivery/dashboard/src/types.ts` (Vehicle, VehiclesResponse)
- `apps/kerala_delivery/dashboard/src/lib/api.ts` (apiWrite, fleet functions, DEV warning)
- `apps/kerala_delivery/dashboard/src/App.tsx` (fleet page + nav)
- `core/geocoding/interfaces.py` (AsyncGeocoder protocol)
- `requirements.txt` (pytest-asyncio==1.3.0)

**DECIDED:** Fleet Management uses inline forms (not modals) — maintains spatial context
**DECIDED:** CachedGeocoder is Decorator pattern — wraps any upstream Geocoder
**DECIDED:** AsyncGeocoder is a separate Protocol from sync Geocoder
**DECIDED:** import_orders.py creates an "imported" optimization run (OrderDB requires run_id FK)
**DECIDED:** DEFAULT_MAX_WEIGHT_KG = 446 (was 500, corrected to match design doc: 496 × 0.9)
**DECIDED:** MAX_SPEED_LIMIT_KMH = 40 enforced in UI validation + HTML input attrs
**DECIDED:** MAX_RATED_PAYLOAD_KG = 496 enforced in UI validation + HTML input attrs
**DECIDED:** Single asyncio.run() in batch scripts (avoids orphaned DB connections)
**DECIDED:** apiWrite warns in DEV mode when VITE_API_KEY is missing

**OPEN:** No tests for import_orders.py or geocode_batch.py (scripts/)
**OPEN:** No React component tests for FleetManagement (Playwright E2E deferred)
**OPEN:** geocode_batch.py has no rate limiting between Google API calls (INFO)
**OPEN:** repository.get_cached_geocode() drops cached address_text (INFO)
**OPEN:** Read-level auth for fleet telemetry (Phase 3)
**OPEN:** Offline-first PWA sync not implemented
**OPEN:** OSRM speed profile not yet calibrated with real GPS data

**Next steps:**
1. Script tests (import_orders.py, geocode_batch.py)
2. Dashboard E2E tests (Playwright)
3. Phase 3: production deployment (Docker Compose on VPS)
4. Read-scoped auth for fleet-wide endpoints
5. OSRM speed profile calibration with real GPS data
6. Offline-first driver PWA

---

## Session 2025-07-19 — Bug Fixes, Script Tests, Doc Updates

**Phase:** Phase 2 near-complete, all docs updated

### Bug Fixes
- DECIDED: `repository.get_cached_geocode()` now passes `address_text=row.address_raw` to `_point_to_location()` — cache hits preserve address text
- DECIDED: Fixed `import_orders.py` — 4 occurrences of `order.address` → `order.address_raw` (Order model uses `address_raw`)
- DECIDED: Fixed `geocode_batch.py` `read_addresses_from_db()` — `OrderDB.address` → `OrderDB.address_raw`

### Rate Limiting
- DECIDED: `geocode_batch.py` uses `await asyncio.sleep(0.05)` between Google API calls (20 req/s, within 50 QPS limit)
- DECIDED: `import_orders.py` uses `time.sleep(0.05)` in geocoding loop (synchronous script context)
- Named constant `GOOGLE_API_RATE_LIMIT_SECONDS = 0.05` in both scripts

### New Tests (31 total new tests, 211 total)
- `tests/scripts/test_import_orders.py` — 16 tests: CSV parsing, dry-run, geocoding flow, failure counting, CLI args, stats display
- `tests/scripts/test_geocode_batch.py` — 15 tests: CSV reading, dedup, custom columns, cache-first strategy, dry-run, API failures, rate limiting, CLI args, DB address reading

### Documentation Updates
- README.md: test count 144→211, added 8 API endpoints, added scripts/FleetManagement/cache.py to project tree, Phase 2 "Near-Complete", auth note, ROUTEOPT_API_KEY env var
- GUIDE.md: Section 12 updated — "What works" expanded, resolved items removed from "What's left" and "Open Items"
- SETUP.md: Added batch script commands to quick reference table

### Code Reviews
- Review #10: 1 CRITICAL (OrderDB.address bug in geocode_batch.py read_from_db), 2 WARNING, 5 INFO
- Review #10 re-review: 0 CRITICAL, 0 WARNING, 1 INFO — all findings resolved

**Tests:** 211 passing (pytest, 2.4s)

**RESOLVED:** repository.get_cached_geocode() drops cached address_text
**RESOLVED:** geocode_batch.py has no rate limiting between Google API calls
**RESOLVED:** No tests for import_orders.py or geocode_batch.py

**OPEN:** No React component tests for FleetManagement (Playwright E2E deferred)
**OPEN:** Read-level auth for fleet telemetry (Phase 3)
**OPEN:** Offline-first PWA sync not implemented
**OPEN:** OSRM speed profile not yet calibrated with real GPS data
**OPEN:** scripts/ import from apps/kerala_delivery/config (W1 — Kerala-specific coupling, low urgency)

**Next steps:**
1. Dashboard E2E tests (Playwright)
2. Phase 3: production deployment (Docker Compose on VPS)
3. Read-scoped auth for fleet-wide endpoints
4. OSRM speed profile calibration with real GPS data
5. Offline-first driver PWA

---