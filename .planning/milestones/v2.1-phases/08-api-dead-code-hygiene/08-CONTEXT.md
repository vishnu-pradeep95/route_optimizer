# Phase 8: Runtime Protection - Context

**Gathered:** 2026-03-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Add periodic license and file integrity re-validation during operation, not just at startup. After 500+ requests, modified protected files or expired licenses must be detected and enforced. Re-validation runs fully offline with no event loop blocking (<100ms latency impact).

</domain>

<decisions>
## Implementation Decisions

### Re-validation trigger
- Request counter: exact integer increment, re-validate every 500 requests
- Counter resets to zero after each re-validation (simple modulo: `counter % 500 == 0`)
- Counter and re-validation logic live in compiled `license_manager.py` → `.so` (not in enforcement.py)
- Middleware calls `maybe_revalidate()` — a sync function in the compiled module
- No time-based fallback — purely request-driven

### Check scope
- Both integrity AND license re-checked on every re-validation cycle
- Integrity: full `verify_integrity()` call (reads 3 files, computes SHA256 — sub-millisecond)
- License: expiry-only re-check using already-decoded `_license_state.expires_at` vs `datetime.now()` — no file I/O, no HMAC re-computation
- Synchronous execution — no async offloading needed for 3 tiny file reads
- Skip in dev mode (consistent with startup: `_INTEGRITY_MANIFEST` is empty anyway)

### Failure behavior
- **Integrity failure → graceful shutdown**: `logger.error()` with descriptive message, then `raise SystemExit`. Uvicorn finishes in-flight requests. Docker restart policy brings container back — startup check catches tampered file again.
- **License expiry → state transition**: Update `_license_state` to GRACE or INVALID. Middleware already handles these (GRACE adds X-License-Warning header, INVALID returns 503). No shutdown for license expiry.
- Logging: use existing `logger.error()` / `logger.warning()` — no new ErrorCode enum values needed

### State transitions
- Allow transitions during operation: VALID → GRACE → INVALID (natural expiry progression)
- One-way only: once degraded, state never improves. Recovery requires restart (renewal mechanism is Phase 9)
- `set_license_state()` gets a guard: only accepts same-severity or worse transitions (VALID → GRACE → INVALID), rejects upgrades (INVALID → VALID)
- Log state transitions: `logger.warning()` when state degrades (e.g., "License transitioned from VALID to GRACE")

### Claude's Discretion
- Exact function signature of `maybe_revalidate()` (whether it takes `base_path` parameter or reads from module state)
- Whether the counter is a plain int or part of a small state struct
- Exact log message wording for re-validation events
- How to handle the edge case where maybe_revalidate() is called but verify_integrity() fails due to file permission issues (vs actual tampering)

</decisions>

<specifics>
## Specific Ideas

- Success criteria from ROADMAP.md are precise: "500+ requests → modified file detected", "500+ requests with expired license → detected", "<100ms latency"
- The architecture boundary from Phase 7 is strict: enforcement.py (async wrapper, .py) calls license_manager.so (sync logic, compiled)
- maybe_revalidate() must be sync (lives in compiled module) — the middleware calls it synchronously on the 500th request

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `verify_integrity()` in license_manager.py: Already reads 3 protected files and computes SHA256 — reuse directly for periodic checks
- `get_license_status()` / `set_license_state()`: Already manage internal `_license_state` — extend with guard logic
- `_license_state` (LicenseInfo): Already stores `expires_at` for expiry-only re-check
- Middleware in enforcement.py: Already runs on every request — add `maybe_revalidate()` call

### Established Patterns
- Module-level state in compiled .so: `_license_state`, `_INTEGRITY_MANIFEST` — add `_request_counter`
- `_is_dev_mode` check: Used to skip integrity verification — same pattern for periodic checks
- Sync function called from async middleware: `get_license_status()` pattern — `maybe_revalidate()` follows same pattern

### Integration Points
- `core/licensing/license_manager.py`: Add `maybe_revalidate()`, `_request_counter`, guard in `set_license_state()`
- `core/licensing/enforcement.py`: Add `maybe_revalidate()` call in middleware
- `tests/`: Need tests for periodic re-validation, state transition guards, counter behavior

</code_context>

<deferred>
## Deferred Ideas

- License renewal mechanism (hot file drop) — Phase 9 (LIC-01)
- X-License-Expires-In response header — Phase 9 (LIC-02)
- License status in /health endpoint — Phase 9 (LIC-03)

</deferred>

---

*Phase: 08-runtime-protection*
*Context gathered: 2026-03-10*
