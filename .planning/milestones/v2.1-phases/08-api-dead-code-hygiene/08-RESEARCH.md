# Phase 8: Runtime Protection - Research

**Researched:** 2026-03-10
**Domain:** Python module-level state management, ASGI middleware periodic checks, license enforcement
**Confidence:** HIGH

## Summary

Phase 8 adds periodic re-validation of license and file integrity during runtime, not just at startup. The implementation is well-scoped: add a request counter (`_request_counter`) and `maybe_revalidate()` function to `license_manager.py` (compiled to `.so`), add a state transition guard to `set_license_state()`, and wire a single `maybe_revalidate()` call into the existing middleware in `enforcement.py`.

The existing codebase already has all the building blocks: `verify_integrity()` for file hash checking, `_license_state` with `expires_at` for expiry re-checking, `get_license_status()`/`set_license_state()` for state management, and the middleware that runs on every request. The new code is purely additive -- no existing function signatures change, no existing behavior changes.

**Primary recommendation:** Implement as two additions: (1) `maybe_revalidate()` + counter + state guard in `license_manager.py`, (2) one-line middleware call in `enforcement.py`. Keep it synchronous, simple, and fully tested.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Request counter: exact integer increment, re-validate every 500 requests
- Counter resets to zero after each re-validation (simple modulo: `counter % 500 == 0`)
- Counter and re-validation logic live in compiled `license_manager.py` -> `.so` (not in enforcement.py)
- Middleware calls `maybe_revalidate()` -- a sync function in the compiled module
- No time-based fallback -- purely request-driven
- Both integrity AND license re-checked on every re-validation cycle
- Integrity: full `verify_integrity()` call (reads 3 files, computes SHA256 -- sub-millisecond)
- License: expiry-only re-check using already-decoded `_license_state.expires_at` vs `datetime.now()` -- no file I/O, no HMAC re-computation
- Synchronous execution -- no async offloading needed for 3 tiny file reads
- Skip in dev mode (consistent with startup: `_INTEGRITY_MANIFEST` is empty anyway)
- Integrity failure -> graceful shutdown: `logger.error()` with descriptive message, then `raise SystemExit`. Uvicorn finishes in-flight requests. Docker restart policy brings container back -- startup check catches tampered file again.
- License expiry -> state transition: Update `_license_state` to GRACE or INVALID. Middleware already handles these (GRACE adds X-License-Warning header, INVALID returns 503). No shutdown for license expiry.
- Logging: use existing `logger.error()` / `logger.warning()` -- no new ErrorCode enum values needed
- Allow transitions during operation: VALID -> GRACE -> INVALID (natural expiry progression)
- One-way only: once degraded, state never improves. Recovery requires restart (renewal mechanism is Phase 9)
- `set_license_state()` gets a guard: only accepts same-severity or worse transitions (VALID -> GRACE -> INVALID), rejects upgrades (INVALID -> VALID)
- Log state transitions: `logger.warning()` when state degrades

### Claude's Discretion
- Exact function signature of `maybe_revalidate()` (whether it takes `base_path` parameter or reads from module state)
- Whether the counter is a plain int or part of a small state struct
- Exact log message wording for re-validation events
- How to handle the edge case where maybe_revalidate() is called but verify_integrity() fails due to file permission issues (vs actual tampering)

### Deferred Ideas (OUT OF SCOPE)
- License renewal mechanism (hot file drop) -- Phase 9 (LIC-01)
- X-License-Expires-In response header -- Phase 9 (LIC-02)
- License status in /health endpoint -- Phase 9 (LIC-03)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| RTP-02 | Integrity checked at startup and during periodic re-validation | Startup check already exists in `enforce()`. Add `maybe_revalidate()` that calls existing `verify_integrity()` every 500 requests. Counter lives in module-level `_request_counter`. |
| RTP-03 | License + integrity re-validated every 500 requests (fully offline, no internet required) | `maybe_revalidate()` combines: (1) `verify_integrity()` for file hashes (reuses existing function, sub-ms), (2) `_license_state.expires_at` vs `datetime.now()` for license expiry (no file I/O, no network). Both are fully offline. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib (`hashlib`, `datetime`) | 3.12+ | SHA256 hashing, time comparison | Already used throughout license_manager.py; no external deps needed |
| FastAPI middleware | 0.100+ | Request interception for counter + revalidation | Already in place in enforcement.py |
| pytest | 9.0.2 | Test framework | Already configured in pytest.ini |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `unittest.mock` | stdlib | Mocking `_INTEGRITY_MANIFEST`, `_license_state`, file system | All tests for this phase |
| FastAPI `TestClient` | (bundled) | HTTP-level middleware testing | Testing middleware calls `maybe_revalidate()` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Plain int counter | `threading.Lock`-protected counter | Unnecessary -- Python GIL makes int increment atomic for single-process uvicorn; ASGI is single-threaded event loop |
| Synchronous `verify_integrity()` | `asyncio.to_thread()` | Unnecessary for 3 tiny file reads (sub-ms); adds complexity for no measurable gain |
| Time-based fallback | `asyncio.create_task()` periodic timer | User decision: purely request-driven, no time-based fallback |

**Installation:**
No new dependencies required. Everything uses Python stdlib + already-installed FastAPI/pytest.

## Architecture Patterns

### Recommended Project Structure
```
core/licensing/
    license_manager.py   # ADD: _request_counter, maybe_revalidate(), guard in set_license_state()
    enforcement.py       # ADD: maybe_revalidate() call in middleware
tests/core/licensing/
    test_license_manager.py  # ADD: tests for maybe_revalidate(), counter, state guard
    test_enforcement.py      # ADD: tests for middleware calling maybe_revalidate()
```

### Pattern 1: Module-Level Counter with Modulo Reset
**What:** A plain integer `_request_counter` at module scope, incremented in `maybe_revalidate()`, checked with `% 500 == 0`.
**When to use:** When counting events in a single-process ASGI server (Uvicorn default).
**Why safe:** Python's GIL guarantees that `_request_counter += 1` is atomic in CPython. The ASGI event loop is single-threaded, so there are no race conditions between concurrent middleware calls -- each `await call_next(request)` yields, but the counter increment and check happen synchronously before `call_next`.

```python
# In license_manager.py (compiled to .so)
_request_counter: int = 0

def maybe_revalidate(base_path: str = "/app") -> None:
    """Increment counter, re-validate every 500 requests.
    Called synchronously from middleware on every request."""
    global _request_counter
    _request_counter += 1

    if _request_counter % 500 != 0:
        return

    _request_counter = 0  # Reset after re-validation

    # ... re-validation logic
```

### Pattern 2: One-Way State Transition Guard
**What:** `set_license_state()` gains a severity check: only allows transitions to equal or worse states.
**When to use:** When operational state should only degrade, never improve without restart.

```python
# Severity ordering for guard logic
_STATUS_SEVERITY = {
    LicenseStatus.VALID: 0,
    LicenseStatus.GRACE: 1,
    LicenseStatus.INVALID: 2,
}

def set_license_state(info: LicenseInfo) -> None:
    """Store license state. Only allows same-severity or worse transitions."""
    global _license_state
    if _license_state is not None:
        current_sev = _STATUS_SEVERITY[_license_state.status]
        new_sev = _STATUS_SEVERITY[info.status]
        if new_sev < current_sev:
            # Reject upgrade (e.g., INVALID -> VALID)
            logger.warning(
                "Rejected license state upgrade from %s to %s (restart required)",
                _license_state.status.value, info.status.value,
            )
            return
        if new_sev > current_sev:
            logger.warning(
                "License state degraded from %s to %s",
                _license_state.status.value, info.status.value,
            )
    _license_state = info
```

### Pattern 3: SystemExit for Integrity Failure (Graceful Shutdown)
**What:** `raise SystemExit(msg)` from synchronous code called within async middleware.
**When to use:** When a fatal integrity violation is detected at runtime.
**Why it works:**
- `SystemExit` inherits from `BaseException`, not `Exception` -- generic `except Exception:` blocks won't catch it
- In CPython/Uvicorn, `SystemExit` propagates up the call stack and causes the process to exit
- Docker's `restart: unless-stopped` policy on the API service will restart the container
- On restart, `enforce()` runs the startup integrity check again, catching the tampered file before any requests are served

```python
# In maybe_revalidate(), after verify_integrity() fails:
if not ok:
    for f in failures:
        logger.error("Runtime integrity check failed: %s", f)
    raise SystemExit("Runtime integrity check failed. Protected files modified.")
```

### Pattern 4: License Expiry Re-check (No I/O)
**What:** Compare `_license_state.expires_at` against `datetime.now(timezone.utc)` to detect natural expiry progression.
**When to use:** During periodic re-validation to detect VALID -> GRACE -> INVALID transitions over time.
**Key detail:** Uses already-decoded state -- no file reads, no HMAC re-computation. This is a pure datetime comparison.

```python
# Expiry re-check logic in maybe_revalidate():
now = datetime.now(timezone.utc)
days_remaining = (_license_state.expires_at - now).days

if days_remaining >= 0:
    new_status = LicenseStatus.VALID
elif abs(days_remaining) <= GRACE_PERIOD_DAYS + 1:
    new_status = LicenseStatus.GRACE
else:
    new_status = LicenseStatus.INVALID

if new_status != _license_state.status:
    # Create updated LicenseInfo and call set_license_state()
    # Guard in set_license_state() handles one-way enforcement
    ...
```

### Anti-Patterns to Avoid
- **Async re-validation:** Don't use `asyncio.to_thread()` or `await` for `maybe_revalidate()`. The 3-file SHA256 check takes sub-millisecond. Making it async adds complexity and makes the code harder to test with no measurable benefit.
- **Counter in enforcement.py:** Don't put the counter in the uncompiled `.py` file. It must live in `license_manager.py` so it's inside the compiled `.so` -- making it harder to disable.
- **Catching SystemExit in middleware:** Don't add `try/except BaseException` around `maybe_revalidate()`. Let `SystemExit` propagate naturally for graceful shutdown.
- **Re-validating HMAC on every cycle:** Don't re-decode the license key. The key was validated at startup; periodic checks only need to compare expiry timestamps.
- **Thread-safe counter:** Don't use `threading.Lock()`. Uvicorn's default is a single-worker process with a single-threaded event loop. The counter increment is synchronous and non-preemptible.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| File integrity checking | Custom hash comparison | Existing `verify_integrity()` | Already handles missing files, hash mismatches, empty manifest (dev mode) |
| License status determination | Custom expiry logic | Same logic from `decode_license_key()` | Grace period boundary, days_remaining calculation already correct |
| Request counting | Custom middleware counter class | Plain module-level int | GIL-atomic in CPython single-process; simpler is better for compiled .so |

**Key insight:** Every piece of logic needed already exists in `license_manager.py`. The phase is about *wiring* existing functions into a periodic call pattern, not building new capabilities.

## Common Pitfalls

### Pitfall 1: Forgetting to Skip Re-validation in Dev Mode
**What goes wrong:** `verify_integrity()` would always return `(True, [])` in dev mode (empty manifest), but the log messages about "re-validation passed" would be confusing noise in development.
**Why it happens:** `_INTEGRITY_MANIFEST` is empty in dev, so `verify_integrity()` succeeds -- but it still runs unnecessarily.
**How to avoid:** Check `_is_dev_mode` (or check `not _INTEGRITY_MANIFEST`) before running re-validation in `maybe_revalidate()`. Match the startup pattern in `enforce()`.
**Warning signs:** Log spam with "re-validation passed" every 500 requests during local development.

### Pitfall 2: Breaking Existing set_license_state() at Startup
**What goes wrong:** The new guard in `set_license_state()` rejects the initial state set during `enforce()` because `_license_state` is `None` and the guard logic doesn't handle `None` -> anything.
**Why it happens:** Guard logic checks `_license_state.status` before verifying `_license_state is not None`.
**How to avoid:** Guard only applies when `_license_state is not None`. The `None` check at the top of the existing function already handles the first-time case.
**Warning signs:** `AttributeError: 'NoneType' object has no attribute 'status'` on startup.

### Pitfall 3: Counter Not Resetting After Re-validation
**What goes wrong:** If the counter uses `% 500 == 0` but doesn't reset, it would re-validate again at 1000, 1500, etc. This is actually the desired behavior with modulo. But if using explicit reset (`_request_counter = 0`), ensure the reset happens *after* re-validation completes, not before.
**Why it happens:** Misunderstanding the counter semantics -- modulo vs explicit reset.
**How to avoid:** Use modulo check AND explicit reset to zero for clarity. Reset after all re-validation logic completes (including potential SystemExit).
**Warning signs:** Re-validation never fires after the first cycle, or fires too frequently.

### Pitfall 4: SystemExit Caught by Middleware Exception Handling
**What goes wrong:** If enforcement.py has a `try/except Exception:` around the middleware body, `SystemExit` would still propagate (it's `BaseException`). But if someone adds `except BaseException:`, re-validation failures would be silently swallowed.
**Why it happens:** Defensive coding that catches too broadly.
**How to avoid:** Never add `except BaseException:` in the middleware. Verify existing code doesn't have it (confirmed: current middleware has no try/except at all).
**Warning signs:** Integrity failures logged but API keeps serving requests.

### Pitfall 5: License State Transition Creates New LicenseInfo with Wrong Fields
**What goes wrong:** When creating a new `LicenseInfo` for a degraded state, forgetting to copy `customer_id`, `fingerprint`, `expires_at` from the existing `_license_state`.
**Why it happens:** `LicenseInfo` is a dataclass with 6 fields; easy to miss one.
**How to avoid:** Use `dataclasses.replace()` to create a copy with only the changed fields:
```python
from dataclasses import replace
new_info = replace(_license_state, status=new_status, days_remaining=days_remaining, message=new_message)
```
**Warning signs:** `customer_id=""` or `fingerprint=""` in log messages after state transition.

## Code Examples

Verified patterns from the existing codebase:

### Existing Middleware Pattern (from enforcement.py)
```python
# Source: core/licensing/enforcement.py lines 97-125
@app.middleware("http")
async def license_enforcement_middleware(request: Request, call_next):
    status = get_license_status()  # Calls into .so -- fast, no I/O
    # ... status checks ...
    response = await call_next(request)
    return response
```

The `maybe_revalidate()` call goes right after `get_license_status()` and before any status checks:
```python
@app.middleware("http")
async def license_enforcement_middleware(request: Request, call_next):
    status = get_license_status()

    if status is not None:
        maybe_revalidate()  # <-- NEW: periodic check, may raise SystemExit
        status = get_license_status()  # Re-read: may have changed after revalidation

    # ... rest of existing middleware unchanged ...
```

### Existing State Management Pattern (from license_manager.py)
```python
# Source: core/licensing/license_manager.py lines 454-468
_license_state: LicenseInfo | None = None

def get_license_status() -> LicenseStatus | None:
    if _license_state is None:
        return None
    return _license_state.status

def set_license_state(info: LicenseInfo) -> None:
    global _license_state
    _license_state = info
```

### Existing Dev Mode Skip Pattern (from enforcement.py)
```python
# Source: core/licensing/enforcement.py lines 84-94
if not _is_dev_mode:
    ok, failures = verify_integrity()
    if not ok:
        for f in failures:
            logger.error("Integrity check failed: %s", f)
        raise SystemExit("File integrity check failed.")
    logger.info("File integrity verification passed")
else:
    logger.info("Skipping integrity verification (dev mode)")
```

### Existing verify_integrity() Call (from license_manager.py)
```python
# Source: core/licensing/license_manager.py lines 471-493
def verify_integrity(base_path: str = "/app") -> tuple[bool, list[str]]:
    if not _INTEGRITY_MANIFEST:
        return True, []
    failures = []
    base = pathlib.Path(base_path)
    for rel_path, expected_hash in _INTEGRITY_MANIFEST.items():
        file_path = base / rel_path
        if not file_path.exists():
            failures.append(f"{rel_path}: file not found")
            continue
        with open(file_path, "rb") as f:
            actual_hash = hashlib.file_digest(f, "sha256").hexdigest()
        if actual_hash != expected_hash:
            failures.append(f"{rel_path} has been modified")
    return len(failures) == 0, failures
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| License check only at startup | Periodic re-validation every N requests | Phase 8 (now) | Closes audit finding #5: "License checked only at startup" |
| `set_license_state()` allows any transition | One-way guard: only same/worse severity | Phase 8 (now) | Prevents accidental state upgrades without restart |

**Nothing deprecated:** All existing functions (`verify_integrity`, `get_license_status`, `set_license_state`, the middleware) remain as-is. Phase 8 is purely additive.

## Open Questions

1. **`base_path` parameter for `maybe_revalidate()`**
   - What we know: `verify_integrity()` takes `base_path="/app"` and the startup call in `enforce()` uses the default
   - What's unclear: Should `maybe_revalidate()` accept `base_path` as a parameter for testability, or always use the default?
   - Recommendation: Accept `base_path` parameter (default `"/app"`) and pass through to `verify_integrity()`. This makes testing easier (can use `tmp_path`).

2. **Permission errors vs tampering in `verify_integrity()`**
   - What we know: `verify_integrity()` catches `FileNotFoundError` (file missing) and hash mismatches, but doesn't explicitly catch `PermissionError`
   - What's unclear: If a file exists but is unreadable (permission denied), `open(file_path, "rb")` will raise `PermissionError`, which is not caught, causing an unhandled exception
   - Recommendation: Treat permission errors the same as integrity failures -- if we can't read a protected file, that's a failure. The current code already does this implicitly (uncaught exception triggers SystemExit). No change needed; the behavior is correct.

3. **Re-reading `get_license_status()` after `maybe_revalidate()`**
   - What we know: `maybe_revalidate()` may call `set_license_state()` to degrade the status
   - What's unclear: Should the middleware re-read `get_license_status()` after calling `maybe_revalidate()`?
   - Recommendation: Yes, re-read status after `maybe_revalidate()` so the response to request #500 reflects the degraded state immediately.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 |
| Config file | `pytest.ini` (asyncio_mode = auto) |
| Quick run command | `pytest tests/core/licensing/ -x -q` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RTP-02 | `maybe_revalidate()` calls `verify_integrity()` every 500 requests | unit | `pytest tests/core/licensing/test_license_manager.py::TestMaybeRevalidate -x` | Needs new test class |
| RTP-02 | Integrity failure at runtime triggers SystemExit | unit | `pytest tests/core/licensing/test_license_manager.py::TestMaybeRevalidate::test_integrity_failure_raises_system_exit -x` | Needs new test |
| RTP-02 | Re-validation skipped when `_INTEGRITY_MANIFEST` is empty (dev mode) | unit | `pytest tests/core/licensing/test_license_manager.py::TestMaybeRevalidate::test_skips_in_dev_mode -x` | Needs new test |
| RTP-03 | Counter increments and triggers at 500 | unit | `pytest tests/core/licensing/test_license_manager.py::TestMaybeRevalidate::test_triggers_at_500 -x` | Needs new test |
| RTP-03 | Counter resets after re-validation | unit | `pytest tests/core/licensing/test_license_manager.py::TestMaybeRevalidate::test_counter_resets -x` | Needs new test |
| RTP-03 | License expiry re-check detects VALID->GRACE transition | unit | `pytest tests/core/licensing/test_license_manager.py::TestMaybeRevalidate::test_license_expiry_transition -x` | Needs new test |
| RTP-03 | `set_license_state()` guard rejects upgrades | unit | `pytest tests/core/licensing/test_license_manager.py::TestStateGuard -x` | Needs new test class |
| RTP-03 | `set_license_state()` guard allows degradations | unit | `pytest tests/core/licensing/test_license_manager.py::TestStateGuard::test_allows_degradation -x` | Needs new test |
| RTP-03 | Middleware calls `maybe_revalidate()` | unit | `pytest tests/core/licensing/test_enforcement.py::TestRuntimeRevalidation -x` | Needs new test class |
| RTP-03 | Middleware re-reads status after `maybe_revalidate()` | integration | `pytest tests/core/licensing/test_enforcement.py::TestRuntimeRevalidation::test_status_reread -x` | Needs new test |

### Sampling Rate
- **Per task commit:** `pytest tests/core/licensing/ -x -q`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/core/licensing/test_license_manager.py::TestMaybeRevalidate` -- new test class for maybe_revalidate()
- [ ] `tests/core/licensing/test_license_manager.py::TestStateGuard` -- new test class for set_license_state() guard
- [ ] `tests/core/licensing/test_enforcement.py::TestRuntimeRevalidation` -- new test class for middleware integration

*(No framework install needed -- pytest 9.0.2 already configured)*

## Sources

### Primary (HIGH confidence)
- `core/licensing/license_manager.py` -- current implementation of `verify_integrity()`, `set_license_state()`, `get_license_status()`, `_license_state`, `_INTEGRITY_MANIFEST`, `LicenseStatus` enum
- `core/licensing/enforcement.py` -- current middleware implementation, `enforce()` entry point, dev mode check
- `tests/core/licensing/test_enforcement.py` -- existing test patterns for middleware, state management, integrity verification
- `tests/core/licensing/test_license_manager.py` -- existing test patterns for license validation, fingerprinting, HMAC
- `docker-compose.yml` line 233 -- API service `restart: unless-stopped` confirms Docker restart after SystemExit

### Secondary (MEDIUM confidence)
- [Uvicorn Server Behavior](https://www.uvicorn.org/server-behavior/) -- graceful shutdown: finishes in-flight requests, then exits
- [FastAPI Concurrency Docs](https://fastapi.tiangolo.com/async/) -- sync functions in async context; middleware runs on event loop
- [Python SystemExit](https://docs.python.org/3/library/exceptions.html#SystemExit) -- inherits from BaseException, not Exception

### Tertiary (LOW confidence)
- None -- all findings verified against primary sources (codebase) or official docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies; everything is existing Python stdlib + FastAPI
- Architecture: HIGH -- patterns copied directly from existing codebase (startup check pattern, middleware pattern, state management pattern)
- Pitfalls: HIGH -- identified from reading actual code and tracing execution paths
- Implementation approach: HIGH -- user decisions are precise and complete; code changes are additive with clear integration points

**Research date:** 2026-03-10
**Valid until:** 2026-04-10 (stable -- no external dependencies or version-sensitive APIs)
