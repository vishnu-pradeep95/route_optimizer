# Codebase Concerns

**Analysis Date:** 2026-03-01

## Tech Debt

### N+1 Query Pattern in Dashboard Telemetry

**Issue:** Frontend fetches route details in a loop instead of batching.

**Files:** `apps/kerala_delivery/dashboard/src/pages/LiveMap.tsx` (line 75)

**Impact:**
- At current scale (5-13 vehicles) acceptable, but hits wall at 50+ vehicles
- Each vehicle detail fetch is a separate HTTP round-trip
- Dashboard responsiveness degrades with fleet size

**Fix approach:**
- Create batch endpoint: `GET /api/routes?include_stops=true` returning all route details in single response
- Update LiveMap to call batch endpoint instead of looping `fetchRouteDetail()`
- Reduces HTTP requests from N to 1 at scale

---

### Thread-Safety Gap in Global Singleton Geocoder

**Issue:** `_geocoder_instance` at module level (line 391 in `main.py`) uses no locking mechanism.

**Files:**
- `apps/kerala_delivery/api/main.py` (lines 391, 637)
- `core/geocoding/google_adapter.py`

**Impact:**
- If two concurrent requests trigger `_get_geocoder()` initialization simultaneously, race condition occurs
- Unlikely to manifest in single-worker dev environment, but will appear under load (multiple uvicorn workers)
- File I/O (reading cache from disk) during concurrent initialization could corrupt state

**Fix approach:**
- Wrap geocoder initialization in asyncio.Lock
- Guarantee only one thread reads cache file during startup
- Pattern: `async with _geocoder_lock: if not _geocoder_instance: ...`

---

### Hardcoded Placeholder Driver Names

**Issue:** Mock vehicle creation uses placeholder names instead of real data.

**Files:** `apps/kerala_delivery/api/main.py` (line 479)

**Impact:**
- Demo routes display `Driver 1`, `Driver 2` instead of actual names
- No production path to supply real driver data to vehicles endpoint
- When integrated with real fleet management, will need config file or DB seeding

**Fix approach:**
- Add `DRIVER_NAMES` to `config.py` or read from CSV/database
- Seed database with real driver records via Alembic migration
- Update `/api/vehicles` POST endpoint to accept driver_name parameter

---

### Missing Validation Report in CSV Import

**Issue:** Row-level import errors are logged individually but never aggregated.

**Files:** `core/data_import/csv_importer.py` (line 154)

**Impact:**
- User uploads CSV with 50 rows; 10 fail validation
- Frontend shows "No valid orders" but doesn't tell user which rows failed
- Debugging requires logs; cannot export error list

**Fix approach:**
- Collect exceptions during import loop into ValidationReport
- Return ValidationReport with HTTP 207 (Partial Content) showing:
  - Successfully imported rows
  - Failed rows with reason (ValueError, KeyError, TypeError)
  - Summary: "40 of 50 orders imported"
- Update upload response model to include report

---

## Known Bugs

### Geocoding Failure Silent Fallback

**Issue:** When Google Geocoding API returns success=False, order is silently skipped.

**Files:** `apps/kerala_delivery/api/main.py` (lines 668-674)

**Impact:**
- If address cannot be geocoded (ambiguous, outside bounds, API down), order is logged but unassigned
- No user feedback; looks like order was "lost"
- Batch import of 50 orders may lose 1-2 silently

**Trigger:** Upload CDCMS export with addresses outside India or ambiguous addresses (e.g., "Main Street, Kochi" without street number)

**Workaround:**
- Pre-validate addresses in CDCMS before export (ensure street number + area)
- Manually add coordinates to CSV if address is ambiguous

---

### Delivery Window Wrapping Midnight Edge Case

**Issue:** Window-widening logic crosses midnight boundary but doesn't validate final result.

**Files:** `apps/kerala_delivery/api/main.py` (lines 612-624)

**Impact:**
- Order with window 23:30 → 23:59 (29 mins) → widened to 23:30 → 00:30
- VROOM sees `time_window: ["23:30", "00:30"]` which may not parse correctly across midnight
- Route plan may fail silently or assign wrong delivery time

**Trigger:** Import orders with delivery windows close to midnight during night shift

**Workaround:** Manually adjust windows in CSV before upload to avoid midnight crossings

---

## Security Considerations

### Fleet Telemetry Endpoint Leaks Real-Time Location Data

**Issue:** `GET /api/telemetry/fleet` now requires API key (Phase 2 fix), but was previously public.

**Files:** `apps/kerala_delivery/api/main.py` (lines 1348-1410)

**Current mitigation:**
- API key authentication added (verify_read_key)
- Requires X-API-Key header matching environment variable
- Uses timing-safe comparison (hmac.compare_digest) to prevent timing attacks

**Remaining concern:**
- API key is a single shared secret; no per-user scoping
- If compromised, all GPS history (30 days) exposed
- No audit log of who accessed telemetry

**Recommendations:**
- Phase 3: Implement user-level scoping (e.g., only managers see fleet telemetry)
- Phase 3: Add audit logging to telemetry endpoints
- Phase 3: Rotate API keys periodically; support key versions

---

### XSS via Server-Rendered HTML

**Issue:** QR sheet HTML is built with user-supplied order data and returned as HTMLResponse.

**Files:** `apps/kerala_delivery/api/main.py` (lines 1077-1200)

**Current mitigation:**
- All user-controllable values (order_id, address, driver_name) escaped with `html_module.escape()`
- QR SVG is from qrcode library (generated server-side from coordinates, never user text)
- Pydantic models validate data types (order_id is UUID, not freetext)

**Why safe:**
- Order fields come from CSV import validation, not raw user input
- Addresses are validated against coordinate bounds (must geocode successfully)
- HTML output is escaped before template rendering

**Remaining risk:** If address field ever accepts unsanitized user text directly (not from CSV), XSS is possible. Current code is safe but fragile.

---

### API Key Stored in Environment Variable

**Issue:** Single API_KEY environment variable shared across all endpoints.

**Files:** `apps/kerala_delivery/api/main.py` (lines 78-90, 314-335)

**Current mitigation:**
- Read from `os.environ.get("API_KEY")` at startup
- Warns in logs if API_KEY unset in production
- Uses hmac.compare_digest() for constant-time comparison

**Concerns:**
- Single key = single point of failure (rotation requires code restart)
- No separation between read-only (telemetry queries) vs write (orders, routes)
- Key in environment variable is visible in `docker inspect`, process listings

**Recommendations:**
- Phase 3: Support multiple keys (admin, driver_app, dashboard)
- Phase 3: Read secrets from external vault (AWS Secrets Manager, HashiCorp Vault)
- Production: Never commit .env file; use secrets management pipeline

---

### Rate Limiting Implementation Incomplete

**Issue:** API has slowapi configured but rate limits are not enforced on all endpoints.

**Files:** `apps/kerala_delivery/api/main.py` (lines 30-32, 168-174)

**Current state:**
- slowapi Limiter is initialized
- Exception handler registered
- No @app.route calls decorated with limits

**Impact:**
- DOS vulnerability: malicious client can hammer `/api/upload-orders` with large files
- Denial of service: 10 MB upload limit exists but no per-IP request rate limit
- Public APIs (unprotected endpoints) have no throttling

**Fix approach:**
- Decorate endpoints with `@limiter.limit("10/minute")` (adjust per endpoint)
- Separate limits for public vs authenticated endpoints
- `/api/upload-orders`: 2/minute per IP (expensive operation)
- `/api/routes`: 30/minute per IP (cheap read)
- `/api/telemetry/{vehicle_id}`: 60/minute per API key (high-volume GPS pings expected)

---

## Performance Bottlenecks

### Telemetry Queries on High-Volume Table

**Issue:** TelemetryDB grows to ~25,000 rows/day. Queries without indexes will slow down.

**Files:**
- `core/database/models.py` (lines 306-349)
- `core/database/repository.py` (lines 462-503)

**Current state:**
- Composite indexes on (vehicle_id, recorded_at DESC) defined at table level
- GiST spatial index on location column
- Repository uses indexed lookups: `get_telemetry_batch()` filters by vehicle_id + time range

**Capacity:**
- At 25,000 rows/day, 30-day retention = 750,000 rows
- Query for "VEH-01 last hour" should use index → <100ms
- Bulk load of all telemetry (no filter) could timeout

**Scaling limit:**
- If retention expands to 90 days: 2.25M rows
- If fleet grows to 100 vehicles: 2.5M rows/day
- Time-series data (telemetry) should move to specialized DB (TimescaleDB, ClickHouse) at scale

**Improvement path:**
- Short term: Retention policy (archive data >30 days to cold storage)
- Medium term: Partition telemetry table by vehicle_id or date
- Long term: Migrate to TimescaleDB hypertables (PostgreSQL extension for time-series)

---

### Geocoding API Call Overhead

**Issue:** Each uncached address requires HTTP request to Google Geocoding API.

**Files:**
- `core/geocoding/google_adapter.py`
- `apps/kerala_delivery/api/main.py` (lines 640-674)

**Current state:**
- Database geocode cache checked first (free)
- Google API called only on cache miss
- Rate limiting: `GOOGLE_API_RATE_LIMIT_SECONDS` (likely 1 second per API docs)

**Cost impact:**
- Google charges $5 per 1000 successful requests
- If 50 orders/day with 50% cache miss rate: 25 API calls = $0.13/day
- Monthly: ~$4, annual: ~$45 — acceptable

**Capacity issue:**
- If batch import of 500 orders (startup load), 50% miss = 250 API calls
- At 1 req/sec rate limit: 4+ minutes to complete import
- Frontend timeout likely (typical HTTP timeout 30 seconds)

**Improvement path:**
- Add batch geocoding endpoint: `POST /api/geocode-batch` that queues jobs
- Use async task queue (Celery + Redis) for background geocoding
- Return partial result to frontend; keep polling for completion
- Cache entire address + coordinates (not just confidence) across runs

---

## Fragile Areas

### CSV Importer Format Detection

**Files:** `apps/kerala_delivery/api/main.py` (lines 558-594)

**Why fragile:**
- Format detection is heuristic: checks if file is tab-separated with CDCMS column names
- If user uploads a tab-separated file with different columns, auto-detection may fail
- No explicit format parameter; relies on column presence

**Safe modification:**
- Add `?format=cdcms|standard` query parameter to `/api/upload-orders`
- Require explicit format choice instead of auto-detection
- Log which format was chosen; warn if heuristic mismatches parameter

**Test coverage:**
- Test has cases for both CDCMS and standard CSV, but not for format mismatches
- Add test: "CDCMS file but standard format specified" → error message

---

### VROOM Adapter External Process Dependency

**Files:** `core/optimizer/vroom_adapter.py`

**Why fragile:**
- VROOM must be installed and accessible via `docker run vroom:v1` or `vroom` CLI
- No health check before calling; if VROOM is missing, entire API fails
- Timeout hardcoded to 60 seconds (line 106); no configurable retry

**Safe modification:**
- Add lifespan startup check: verify VROOM is accessible
- Log warning if VROOM not found; disable optimization gracefully
- Return error from `/api/upload-orders`: "Optimizer unavailable; contact admin"

**Production risk:**
- If VROOM container exits, next order upload hangs for 60s then fails
- Deployment without VROOM will silently break orders endpoint

---

### Database Connection Pool Lifecycle

**Files:**
- `core/database/connection.py`
- `apps/kerala_delivery/api/main.py` (lines 67-139)

**Why fragile:**
- Engine created once in lifespan startup
- If DB goes down mid-request, connection errors not gracefully handled
- No reconnection logic; requires app restart

**Safe modification:**
- Wrap repository calls in try/except for sqlalchemy.exc.OperationalError
- Return 503 Service Unavailable with helpful message
- Add health check endpoint that verifies DB connectivity
- Middleware could retry failed DB calls (3 retries with exponential backoff)

**Test coverage:**
- No tests for DB connection failure scenarios
- Add tests: "DB unavailable during upload" → 503, "DB recovers mid-request" → success

---

## Scaling Limits

### In-Memory Route Cache

**Current state:**
- Routes are persisted to PostgreSQL but not cached in-memory
- Each `/api/routes` request queries database
- No Redis or memcached

**Scaling concern:**
- At 13 vehicles, hitting `/api/routes` 100×/day = ~8 DB queries/day (acceptable)
- If dashboard refreshes route list every 10 seconds with 50+ concurrent clients: 500+ QPS to routes endpoint
- Database connection pool (default 10) exhausted; requests queue/timeout

**Capacity:**
- PostgreSQL can handle ~1000 simple queries/sec; this is not the bottleneck
- Network latency (request → DB → response) adds ~5-10ms per query
- Dashboard showing 50+ vehicles × 10-second refresh = visible lag

**Scaling path:**
- Add in-memory cache layer (decorator on `get_routes()`)
- Cache TTL: 30 seconds (acceptable staleness for driver map)
- Invalidate on `/api/routes/{vehicle_id}/stops/{order_id}/status` (stop status update)
- Monitor cache hit ratio; adjust TTL if misses spike

---

### Optimizer Timeout on Large Problems

**Issue:** VROOM timeout hardcoded to 60 seconds.

**Files:** `core/optimizer/vroom_adapter.py` (line 106)

**Current capacity:**
- 50 orders: ~100ms
- 200 orders: ~500ms
- 500+ orders: timeout risk (depends on number of vehicles, constraints)

**Scaling limit:**
- LPG delivery for major city (500+ orders, 50+ vehicles) may exceed 60 seconds
- No partial result; entire optimization fails

**Improvement path:**
- Make timeout configurable: `VROOM_TIMEOUT_SECONDS` in config
- Implement time-budgeted optimization: spend 55 seconds optimizing, return best result found
- If timeout occurs, return best partial solution (some orders assigned, some unassigned)

---

### Alembic Migration Versioning

**Issue:** Database schema managed via SQL init script, not Alembic migrations (in Phase 2).

**Files:**
- `infra/postgres/init.sql` (schema definition)
- `infra/alembic/` (empty migrations for now; only baseline stamped)

**Scaling concern:**
- If schema changes occur, must manually write migration
- Risk: developer changes ORM model but forgets migration
- Multi-environment deployment: prod may have different schema than dev

**Current state:** 3 migrations exist (all structural baseline setup), no active development migrations

**Improvement path:**
- Enable `alembic revision --autogenerate` on ORM model changes
- Add pre-deployment check: `alembic current` vs `alembic heads`
- Add CI/CD gate: migrations must exist for any model changes

---

## Dependencies at Risk

### Deprecated FastAPI Event Handlers

**Issue:** `on_event("startup")` / `on_event("shutdown")` are deprecated in FastAPI 0.95+.

**Current state:** Code uses `lifespan` context manager (correct pattern), but worth noting if old code remains.

**Impact:** None currently (using correct pattern). Document transition for future FastAPI upgrades.

---

### OSRM Dependency (External Service)

**Issue:** OSRM routing service is external HTTP service; no fallback routing.

**Files:** `core/routing/osrm_adapter.py`

**Risk:**
- If osrm.example.com is down, all routing calls fail
- No retry logic; fails immediately on timeout
- Timeout: 10 seconds (line 71); route calculation halts

**Scaling path:**
- Add retry logic with exponential backoff (3 retries, 1/5/10 sec delays)
- Fallback to haversine distance (straight-line approximation) if OSRM unavailable
- Health check endpoint to detect OSRM outage before accepting orders

---

### Python Version Compatibility

**Current:** Not specified in repo. No `.python-version` file or `pyproject.toml` `requires-python`.

**Risk:**
- Developers may use Python 3.11 locally, but production runs 3.10
- Type hints (e.g., `str | None`) require Python 3.10+; won't work on 3.9

**Fix:** Add `.python-version` with `3.11` or document minimum Python version in README

---

## Missing Critical Features

### Audit Logging

**What's missing:** No audit trail of API calls, data changes, or sensitive operations.

**Blocks:**
- Compliance audits (who changed a route?)
- Debugging (which API key was used for upload?)
- Security incident investigation

**Implementation needed:**
- Log all POST/PUT/DELETE calls with timestamp, API key hash, request body, response code
- Log telemetry downloads with vehicle_id, date range, requesting API key
- Retention: 90 days minimum (configurable)

---

### Rate Limiting (Enforcement)

**What's missing:** slowapi is wired but no actual limits on endpoints.

**Blocks:**
- DOS protection
- API cost control (Google Geocoding API calls)
- Fair use enforcement

---

### Real-Time Fleet Map (LiveMap) Batch Endpoint

**What's missing:** Dashboard fetches routes serially; needs batch endpoint for scale.

**Blocks:**
- Dashboard performance at 50+ vehicle scale
- Real-time fleet map feature completeness

---

## Test Coverage Gaps

### CSV Import Error Handling

**What's not tested:** Import with rows containing:
- All columns except one (partial row)
- Duplicate order_ids
- Invalid JSON in notes field
- Addresses outside India coordinate bounds

**Files:** `core/data_import/csv_importer.py`, `tests/core/data_import/test_csv_importer.py`

**Risk:** Edge cases cause silent skips or cryptic errors; users unsure what failed

**Test coverage:** Test file has 11 tests covering basic cases (missing columns, bad types, empty file), but not edge cases above

---

### Geocoding Cache Invalidation

**What's not tested:** Cache behavior when:
- Upstream Google API returns different result for same address (result changes)
- Cache file is corrupted or deleted mid-operation
- Two concurrent requests cache the same address simultaneously

**Files:** `core/geocoding/cache.py`, `tests/core/geocoding/test_cache.py`

**Risk:** Stale cached geocodes lead to wrong delivery locations (safety issue for drivers)

---

### Database Constraint Violations

**What's not tested:**
- Inserting route_stop with non-existent route_id (FK constraint)
- Creating vehicle with duplicate vehicle_id (unique constraint)
- Inserting telemetry with future recorded_at timestamp

**Files:** `core/database/repository.py`, `tests/` (no DB constraint tests)

**Risk:** Silent constraint violations; data inconsistency

---

### API Key Rotation

**What's not tested:** Behavior when API_KEY environment variable changes without app restart.

**Files:** `apps/kerala_delivery/api/main.py` (line 81, reads once at startup)

**Risk:** If key is rotated, app must restart; no graceful transition period

---

### Concurrent Geocoding Requests

**What's not tested:** Two simultaneous POST `/api/upload-orders` requests each triggering geocoder initialization.

**Files:** `apps/kerala_delivery/api/main.py` (line 637, `_get_geocoder()`)

**Risk:** Race condition on file I/O; geocoder cache could be partially initialized

---

## Configuration & Environment Gaps

### Missing Configuration Validation

**Issue:** Environment variables required for production are not validated at startup.

**Files:** `apps/kerala_delivery/config.py`

**Required vars for production:**
- `API_KEY` (for auth)
- `DATABASE_URL` (for persistence)
- `GOOGLE_API_KEY` (for geocoding)
- `CORS_ALLOWED_ORIGINS` (for frontend access)

**Current state:** No validation; missing vars cause runtime errors hours after deployment.

**Fix approach:**
- Validate all required vars in `lifespan` startup
- Raise explicit error with helpful message: "Missing DATABASE_URL; set before production deployment"
- Provide template .env.example with all required variables

---

### License Key Format Tight Coupling

**Issue:** License validation is tightly coupled to deployment; any scheme change requires code restart.

**Files:** `core/licensing/license_manager.py`

**Risk:** No way to test license changes without redeploying; production changes risky

---

## Summary by Priority

| Area | Severity | Effort | Blocks |
|------|----------|--------|--------|
| N+1 dashboard queries | Medium | 2h | Scale to 50+ vehicles |
| Geocoding batch endpoint | Medium | 4h | Scale to 50+ vehicles |
| Rate limiting enforcement | High | 3h | DOS protection |
| Thread-safe geocoder | Medium | 1h | Concurrent request safety |
| CSV validation report | Medium | 3h | User feedback on import errors |
| Telemetry table partitioning | Low | 8h | Scale to 2M+ rows |
| VROOM health check | Medium | 2h | Graceful failure handling |
| Audit logging | High | 6h | Compliance, security investigation |
| Configuration validation | Medium | 2h | Production safety |
| Coverage: DB constraints | Low | 4h | Data integrity |

---

*Concerns audit: 2026-03-01*
