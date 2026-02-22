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
