# Phase 7: Enforcement Module - Context

**Gathered:** 2026-03-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Extract all license enforcement logic from main.py into a compiled enforcement module with a single `enforce(app)` entry point. Embed a SHA256 integrity manifest of protected files in the compiled .so, verified at startup. After this phase, main.py contains one enforce() call and zero lines of license validation, middleware registration, or enforcement logic. License state is stored internally (not on app.state).

</domain>

<decisions>
## Implementation Decisions

### Module architecture
- Create `core/licensing/enforcement.py` as a thin async wrapper — stays as .py (Cython cannot compile `async def`)
- All actual enforcement LOGIC (license checking, integrity verification, state storage) lives in `license_manager.py` which is already compiled to .so
- `enforcement.py` exports a single `enforce(app)` function — this is what main.py calls
- `enforce(app)` does three things at startup: (1) validate license, (2) verify integrity manifest, (3) register middleware
- The middleware is defined in enforcement.py (must be async for ASGI) but delegates all decisions to synchronous functions in the compiled .so

### Integrity manifest scope
- Protected files: `apps/kerala_delivery/api/main.py`, `core/licensing/enforcement.py`, `core/licensing/__init__.py`
- The .so itself is self-protecting (native machine code — not practically modifiable)
- SHA256 hashes computed at build time by `build-dist.sh` and embedded as a dict literal in `license_manager.py` BEFORE Cython compilation
- At startup, enforce() reads each protected file, computes SHA256, compares against the embedded manifest
- If any hash mismatch: API refuses to start with clear error ("File integrity check failed: {filename} has been modified")

### License state storage
- Currently on `app.state.license_info` — trivially monkey-patchable (`app.state.license_info = LicenseInfo(status=VALID)`)
- Move to module-level variable inside `license_manager.py` (compiled .so) — not directly accessible from Python
- Export accessor function: `get_license_status() -> LicenseStatus` (returns enum, not the full LicenseInfo object)
- The middleware calls `get_license_status()` on each request instead of reading `app.state`
- Dev-mode bypass: `enforce(app)` checks `_is_dev_mode` and sets internal state accordingly — same logic, just relocated

### Async/compiled boundary
- Per STATE.md blocker: "Cython async limitation: async def cannot be compiled by Cython (FastAPI#1921)"
- Boundary: `enforcement.py` (async wrapper, .py) calls `license_manager.so` (sync logic, compiled)
- The middleware function (`async def`) lives in enforcement.py — it's just plumbing that calls compiled sync functions
- enforcement.py is protected by the integrity manifest, so tampering is detected at startup
- Build pipeline: enforcement.py stays as .py in tarball, NOT compiled to .so

### What moves out of main.py
- Lines 160-202: License validation in lifespan → enforce(app) handles this
- Lines 370-425: license_enforcement_middleware → defined in enforcement.py, registered by enforce(app)
- Line 57: Imports (validate_license, LicenseStatus, LicenseInfo, GRACE_PERIOD_DAYS) → replaced by single `from core.licensing.enforcement import enforce`
- Line 166: `app.state.license_info = ...` → internal state in .so
- Line 293 comment: License enforcement reference → removed

### Build pipeline updates
- `build-dist.sh` hash step (currently placeholder): compute SHA256 of protected files and write manifest dict
- Manifest dict injected into `license_manager.py` BEFORE Cython compilation (so it's baked into the .so)
- `infra/cython_build.py`: no changes needed (already compiles license_manager.py only)
- `enforcement.py` added to rsync inclusion (stays as .py in tarball)

### Claude's Discretion
- Exact format of the integrity manifest dict in license_manager.py
- Error message wording for integrity failures
- Whether enforce() logs at INFO or WARNING level for various states
- How to handle the edge case where enforce() is called but files don't exist (fresh development without build)

</decisions>

<specifics>
## Specific Ideas

- The Phase 6 CONTEXT.md noted: "Enforcement module compilation (main.py enforcement logic) — Phase 7" and "Integrity manifest embedding in .so — Phase 7 (RTP-01)" — these are the deferred items now being executed
- User previously emphasized "absolutely positively make sure everything works" during Phase 6 main.py refactor — same caution applies here since we're moving enforcement logic out of main.py
- Existing tests (test_api.py) test the license enforcement middleware behavior — these tests must continue to pass after the refactor

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/licensing/license_manager.py` (.so): Already compiled, contains `validate_license()`, `LicenseStatus`, `LicenseInfo`, `GRACE_PERIOD_DAYS`, `get_machine_fingerprint()`
- `scripts/build-dist.sh`: Already has a "hash protected files" placeholder step (Phase 6, Task 2) — ready to be upgraded with real manifest generation
- `infra/Dockerfile.build` + `infra/cython_build.py`: Cython compilation infrastructure — already working

### Established Patterns
- Production-default: `_is_dev_mode = os.environ.get("ENVIRONMENT") == "development"` — same pattern for enforce() dev bypass
- Middleware pattern: `@app.middleware("http")` with async def, checks state, returns JSONResponse on failure
- Build pipeline: stage → strip → hash → compile → validate → clean → package (8-step sequence from Phase 6)

### Integration Points
- `apps/kerala_delivery/api/main.py` lines 57, 160-202, 370-425: Enforcement code to extract
- `tests/apps/kerala_delivery/api/test_api.py`: License enforcement tests that must keep passing
- `scripts/build-dist.sh`: Hash step needs manifest generation before Cython compilation
- `core/licensing/__init__.py`: May need to re-export enforce() for clean import path

</code_context>

<deferred>
## Deferred Ideas

- Periodic re-validation during runtime (checking every 500 requests) — Phase 8 (RTP-02, RTP-03)
- License renewal mechanism — Phase 9 (LIC-01)
- X-License-Expires-In header — Phase 9 (LIC-02)

</deferred>

---

*Phase: 07-enforcement-module*
*Context gathered: 2026-03-10*
