# Phase 7: Enforcement Module - Research

**Researched:** 2026-03-10
**Domain:** License enforcement extraction, integrity verification, Cython async boundary, module-level state isolation
**Confidence:** HIGH

## Summary

This phase extracts all license enforcement logic from `main.py` into a dedicated `core/licensing/enforcement.py` module with a single `enforce(app)` entry point. The module handles three responsibilities at startup: license validation, SHA256 file integrity verification, and middleware registration. License state moves from `app.state.license_info` (trivially monkey-patchable) to a module-level variable inside the compiled `license_manager.so`.

The primary technical challenge is the Cython async boundary: `enforcement.py` must remain as a `.py` file because Cython cannot compile `async def` functions. It acts as a thin async wrapper calling synchronous compiled functions in `license_manager.so`. The integrity manifest (SHA256 hashes of protected files) must be injected into `license_manager.py` source code by `build-dist.sh` BEFORE Cython compilation, so the hashes are baked into the `.so` binary. The build pipeline's existing Step 4 (hash placeholder) is upgraded to compute and inject real manifest data.

A key research finding: regular Python module-level variables in a Cython `.so` remain in the module's `__dict__` and are technically accessible from outside. Only `cdef`-typed variables become truly hidden C variables, but `cdef` at module level is not available in pure Python mode (which this project uses). The mitigation is that analyzing a `.so` binary to find internal variable names requires reverse-engineering native code -- a massive difficulty increase over editing `.py` or `.pyc`. This level of protection matches the project's stated goals (deterrence, not cryptographic security).

**Primary recommendation:** Create `enforcement.py` as an async wrapper staying as `.py`, move all enforcement logic out of `main.py`, store license state as module-level variable in `license_manager.py` with only a `get_license_status()` accessor exported, and upgrade `build-dist.sh` Step 4 to inject real SHA256 manifest into source before Cython compilation.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Create `core/licensing/enforcement.py` as a thin async wrapper -- stays as .py (Cython cannot compile `async def`)
- All actual enforcement LOGIC (license checking, integrity verification, state storage) lives in `license_manager.py` which is already compiled to .so
- `enforcement.py` exports a single `enforce(app)` function -- this is what main.py calls
- `enforce(app)` does three things at startup: (1) validate license, (2) verify integrity manifest, (3) register middleware
- The middleware is defined in enforcement.py (must be async for ASGI) but delegates all decisions to synchronous functions in the compiled .so
- Protected files: `apps/kerala_delivery/api/main.py`, `core/licensing/enforcement.py`, `core/licensing/__init__.py`
- The .so itself is self-protecting (native machine code -- not practically modifiable)
- SHA256 hashes computed at build time by `build-dist.sh` and embedded as a dict literal in `license_manager.py` BEFORE Cython compilation
- At startup, enforce() reads each protected file, computes SHA256, compares against the embedded manifest
- If any hash mismatch: API refuses to start with clear error ("File integrity check failed: {filename} has been modified")
- Move license state to module-level variable inside `license_manager.py` (compiled .so) -- not directly accessible from Python
- Export accessor function: `get_license_status() -> LicenseStatus` (returns enum, not the full LicenseInfo object)
- The middleware calls `get_license_status()` on each request instead of reading `app.state`
- Dev-mode bypass: `enforce(app)` checks `_is_dev_mode` and sets internal state accordingly -- same logic, just relocated
- Per STATE.md blocker: "Cython async limitation: async def cannot be compiled by Cython (FastAPI#1921)"
- Boundary: `enforcement.py` (async wrapper, .py) calls `license_manager.so` (sync logic, compiled)
- enforcement.py is protected by the integrity manifest, so tampering is detected at startup
- Build pipeline: enforcement.py stays as .py in tarball, NOT compiled to .so
- Lines 160-202 of main.py: License validation in lifespan -> enforce(app) handles this
- Lines 370-425 of main.py: license_enforcement_middleware -> defined in enforcement.py, registered by enforce(app)
- Line 57 of main.py: Imports replaced by single `from core.licensing.enforcement import enforce`
- Line 166 of main.py: `app.state.license_info = ...` -> internal state in .so
- `build-dist.sh` hash step (currently placeholder): compute SHA256 of protected files and write manifest dict
- Manifest dict injected into `license_manager.py` BEFORE Cython compilation (so it's baked into the .so)
- `infra/cython_build.py`: no changes needed (already compiles license_manager.py only)
- `enforcement.py` added to rsync inclusion (stays as .py in tarball)

### Claude's Discretion
- Exact format of the integrity manifest dict in license_manager.py
- Error message wording for integrity failures
- Whether enforce() logs at INFO or WARNING level for various states
- How to handle the edge case where enforce() is called but files don't exist (fresh development without build)

### Deferred Ideas (OUT OF SCOPE)
- Periodic re-validation during runtime (checking every 500 requests) -- Phase 8 (RTP-02, RTP-03)
- License renewal mechanism -- Phase 9 (LIC-01)
- X-License-Expires-In header -- Phase 9 (LIC-02)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ENF-03 | Enforcement logic lives in compiled module with single `enforce(app)` entry point (main.py has no inline enforcement) | enforcement.py as async wrapper calling license_manager.so; main.py reduced to single import + enforce(app) call in lifespan |
| RTP-01 | SHA256 integrity manifest of protected files embedded in compiled .so | build-dist.sh Step 4 upgraded to compute SHA256 of 3 protected files and inject dict literal into license_manager.py before Cython compilation |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| hashlib (stdlib) | Python 3.12 | SHA256 file hashing for integrity manifest | Built-in, no dependencies, `hashlib.file_digest()` available since 3.11 |
| Cython | 3.2.4 | Compile license_manager.py to .so (already in use) | Already established in Phase 6, no version change |
| FastAPI | (existing) | ASGI app, middleware registration | Already in use, enforce() registers middleware via `@app.middleware("http")` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pathlib (stdlib) | Python 3.12 | File path handling for integrity checks | Resolving protected file paths relative to app root |
| logging (stdlib) | Python 3.12 | Enforcement startup/failure logging | All enforce() operations log at INFO/WARNING/ERROR |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| hashlib.file_digest() | Manual chunked reading | file_digest() is cleaner on Python 3.11+; this project uses 3.12 |
| Module-level variable for state | `cdef` typed variable | cdef not available in pure Python mode (.py files); module-level Python variable is acceptable security tradeoff |
| Dict literal manifest | JSON/TOML config file | Embedded dict compiled into .so is tamper-resistant; external config can be modified |

**Installation:**
```bash
# No new packages needed -- all libraries already in use or stdlib
```

## Architecture Patterns

### Recommended Project Structure
```
core/licensing/
    __init__.py          # Minimal stub (docstring + re-exports), stays as .py
    enforcement.py       # NEW: async wrapper, stays as .py, protected by integrity manifest
    license_manager.py   # MODIFIED: adds state storage + integrity verification functions, compiled to .so

apps/kerala_delivery/api/
    main.py              # MODIFIED: enforcement lines extracted, single enforce(app) call remains
```

### Pattern 1: Async/Sync Boundary (enforcement.py calls license_manager.so)

**What:** enforcement.py is a thin async wrapper that delegates all enforcement decisions to synchronous functions in the compiled license_manager.so. The async middleware function lives in enforcement.py because Cython cannot compile `async def`.

**When to use:** Any time you need ASGI middleware (requires `async def`) to call Cython-compiled synchronous logic.

**Example:**
```python
# core/licensing/enforcement.py (stays as .py, NOT compiled)
# Source: CONTEXT.md locked decision + Cython async limitation from STATE.md

import logging
import os
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.licensing.license_manager import (
    validate_license,
    LicenseStatus,
    LicenseInfo,
    GRACE_PERIOD_DAYS,
    get_license_status,       # NEW: accessor for internal state
    set_license_state,        # NEW: setter called only at startup
    verify_integrity,         # NEW: checks SHA256 manifest
)

logger = logging.getLogger(__name__)

_is_dev_mode = os.environ.get("ENVIRONMENT") == "development"


def enforce(app: FastAPI) -> None:
    """Single entry point for all license enforcement.

    Called once from main.py lifespan. Does:
    1. Validate license at startup
    2. Verify file integrity against embedded manifest
    3. Register middleware for ongoing enforcement
    """
    # Step 1: Validate license
    license_info = validate_license()

    if license_info.status == LicenseStatus.VALID:
        logger.info(
            "License valid -- customer=%s, expires=%s, %d days remaining",
            license_info.customer_id,
            license_info.expires_at.strftime("%Y-%m-%d"),
            license_info.days_remaining,
        )
    elif license_info.status == LicenseStatus.GRACE:
        logger.warning(
            "LICENSE IN GRACE PERIOD -- %s. "
            "System will stop working in %d days. Renew immediately.",
            license_info.message,
            GRACE_PERIOD_DAYS - abs(license_info.days_remaining),
        )
    else:
        if _is_dev_mode:
            logger.info(
                "License not configured (dev mode) -- running without enforcement"
            )
            license_info = LicenseInfo(
                customer_id="dev-mode",
                fingerprint="",
                expires_at=license_info.expires_at,
                status=LicenseStatus.VALID,
                days_remaining=999,
                message="Development mode -- no license required",
            )
        else:
            logger.error(
                "LICENSE INVALID: %s. All endpoints will return 503.",
                license_info.message,
            )

    # Store in compiled module's internal state (not on app.state)
    set_license_state(license_info)

    # Step 2: Verify file integrity
    if not _is_dev_mode:
        ok, failures = verify_integrity()
        if not ok:
            for f in failures:
                logger.error("Integrity check failed: %s", f)
            raise SystemExit(
                "File integrity check failed. Protected files have been modified."
            )
        logger.info("File integrity verification passed")
    else:
        logger.info("Skipping integrity verification (dev mode)")

    # Step 3: Register middleware
    @app.middleware("http")
    async def license_enforcement_middleware(request: Request, call_next):
        """Check license status on every request via compiled accessor."""
        status = get_license_status()  # Calls into .so -- fast, no I/O

        if status is None:
            return await call_next(request)

        if request.url.path == "/health":
            response = await call_next(request)
            if status != LicenseStatus.VALID:
                response.headers["X-License-Status"] = status.value
            return response

        if status == LicenseStatus.INVALID:
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "License expired or invalid. Contact support.",
                    "license_status": "invalid",
                },
            )

        response = await call_next(request)

        if status == LicenseStatus.GRACE:
            # Get message from compiled module
            response.headers["X-License-Warning"] = "License in grace period"

        return response
```

### Pattern 2: SHA256 Integrity Manifest in Compiled .so

**What:** SHA256 hashes of protected files computed at build time, injected as a dict literal into `license_manager.py`, then compiled to `.so`. At startup, `verify_integrity()` reads each file, computes SHA256, and compares.

**When to use:** Tamper detection for files that must remain unmodified in production.

**Example (in license_manager.py, new functions):**
```python
# Source: CONTEXT.md locked decision

# Placeholder that build-dist.sh replaces with real hashes before Cython compilation
# Format: relative path -> SHA256 hex digest
_INTEGRITY_MANIFEST: dict[str, str] = {}

# Internal license state -- not on app.state, inside compiled .so
_license_state: LicenseInfo | None = None


def get_license_status() -> LicenseStatus | None:
    """Return current license status. Called by middleware on every request."""
    if _license_state is None:
        return None
    return _license_state.status


def set_license_state(info: LicenseInfo) -> None:
    """Store license state internally. Called once at startup by enforce()."""
    global _license_state
    _license_state = info


def verify_integrity(base_path: str = "/app") -> tuple[bool, list[str]]:
    """Verify protected files against embedded SHA256 manifest.

    Returns (all_ok, list_of_failure_messages).
    """
    import hashlib
    import pathlib

    if not _INTEGRITY_MANIFEST:
        # No manifest embedded -- development environment (not built)
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
            failures.append(
                f"{rel_path} has been modified"
            )

    return len(failures) == 0, failures
```

### Pattern 3: Build Pipeline Manifest Injection

**What:** `build-dist.sh` Step 4 computes SHA256 hashes of protected files in the staging directory and uses `sed` to replace the placeholder dict in `license_manager.py` before Cython compilation.

**When to use:** Any time a manifest must be "baked in" to a compiled binary.

**Example (build-dist.sh upgrade):**
```bash
# Step 4: HASH -- Compute and inject integrity manifest
header "Computing integrity manifest"

# Compute hashes of protected files (AFTER dev-mode stripping, BEFORE compilation)
MAIN_HASH=$(sha256sum "$STAGE/apps/kerala_delivery/api/main.py" | cut -d' ' -f1)
ENFORCE_HASH=$(sha256sum "$STAGE/core/licensing/enforcement.py" | cut -d' ' -f1)
INIT_HASH=$(sha256sum "$STAGE/core/licensing/__init__.py" | cut -d' ' -f1)

# Inject manifest dict into license_manager.py (replacing the placeholder)
MANIFEST_DICT="{\
\"apps/kerala_delivery/api/main.py\": \"${MAIN_HASH}\", \
\"core/licensing/enforcement.py\": \"${ENFORCE_HASH}\", \
\"core/licensing/__init__.py\": \"${INIT_HASH}\"\
}"

sed -i "s|_INTEGRITY_MANIFEST: dict\[str, str\] = {}|_INTEGRITY_MANIFEST: dict[str, str] = ${MANIFEST_DICT}|" \
    "$STAGE/core/licensing/license_manager.py"

# Verify injection worked
grep -q "INTEGRITY_MANIFEST.*apps/kerala_delivery" "$STAGE/core/licensing/license_manager.py" \
    || { error "Failed to inject integrity manifest"; exit 1; }

success "Integrity manifest injected into license_manager.py"
```

### Anti-Patterns to Avoid
- **Storing integrity manifest in a separate config file:** A JSON/TOML manifest file can be trivially edited alongside the protected files. The manifest MUST be inside the compiled .so.
- **Using `app.state` for license state:** Trivially monkey-patchable from any Python code. Module-level variable in .so is orders of magnitude harder to modify.
- **Putting `async def` in Cython-compiled code:** Cython cannot compile `async def` (FastAPI#1921). The async middleware MUST live in the uncompiled `.py` wrapper.
- **Calling `validate_license()` on every request:** Expensive operation (reads files, computes HMAC). Call once at startup, store result, use `get_license_status()` (fast attribute read) per-request.
- **Skipping integrity check in development:** Use empty manifest (`{}`) as signal for dev environment -- `verify_integrity()` returns success when manifest is empty. Do NOT hardcode a skip.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SHA256 file hashing | Custom chunk-based reading | `hashlib.file_digest(f, "sha256")` | Python 3.11+ handles chunking internally, less code, same performance |
| Build-time string injection | Python script to modify AST | `sed` replacement of placeholder dict | Simple, proven, already used in build-dist.sh for dev-mode stripping |
| License status communication | Custom shared state object | Module-level variable + accessor function | Minimizes API surface, keeps state internal to .so |

**Key insight:** The complexity in this phase is in the _architecture_ (async/sync boundary, build-time injection, file protection), not in the _implementation_ of any single piece. Each piece is straightforward; getting them to compose correctly is the challenge.

## Common Pitfalls

### Pitfall 1: Manifest Injection Breaks Python Syntax
**What goes wrong:** The `sed` command to inject the manifest dict can produce invalid Python if file paths contain special characters or if the dict format is wrong.
**Why it happens:** Shell variable expansion and sed escaping interact unpredictably with Python dict syntax.
**How to avoid:** Use a simple, controlled format. File paths are known constants (no special chars). Test the injected line with `python3 -c "exec(open('...').read())"` after injection. Use double-quotes in the shell dict literal, not single-quotes.
**Warning signs:** Cython compilation fails with syntax error after hash step.

### Pitfall 2: Integrity Check Fails in Development
**What goes wrong:** Running the API locally (without build-dist.sh) triggers integrity failures because the manifest is empty `{}` and `verify_integrity()` tries to check files against it.
**Why it happens:** Developer forgot to handle the empty manifest case.
**How to avoid:** When `_INTEGRITY_MANIFEST` is empty (dict is `{}`), `verify_integrity()` returns `(True, [])` -- this is the development signal. The enforce() function also skips integrity verification in dev mode (`_is_dev_mode` check).
**Warning signs:** API refuses to start in development with "integrity check failed" errors.

### Pitfall 3: Tests Break Because Lifespan Changes
**What goes wrong:** Existing test_api.py tests fail after extracting enforcement from lifespan.
**Why it happens:** Tests use `TestClient(app)` without context manager (lifespan doesn't run), but they previously relied on `app.state.license_info` being set. After refactor, `enforce(app)` sets internal state instead.
**How to avoid:** After extracting enforcement from lifespan, the remaining lifespan code (API key check, health gates) is unchanged. Tests never executed the license validation path (they use ENVIRONMENT=development with lifespan skipped). The middleware now calls `get_license_status()` which returns `None` when `set_license_state()` was never called -- middleware passes through when status is None. Verify all 115 test_api.py tests and all 39 test_license_manager.py tests still pass.
**Warning signs:** 503 responses in tests that previously returned 200.

### Pitfall 4: Middleware Registration Order Changes
**What goes wrong:** Moving the middleware from `main.py` (where it's registered with `@app.middleware("http")` at a specific position) to `enforcement.py` changes the middleware stack order, breaking security header flow.
**Why it happens:** FastAPI/Starlette processes middleware in reverse registration order. The license middleware is currently registered at line 379, between CORS and exception handlers. If `enforce(app)` registers it at a different point in the lifespan, the order changes.
**How to avoid:** Call `enforce(app)` from within the lifespan function at exactly the position where the license validation currently runs (lines 160-202). The middleware registration inside `enforce()` will happen at the same conceptual point. However, note: the current middleware uses `@app.middleware("http")` decorator at module level (line 379), NOT inside lifespan. The decorator registration must also happen at module-load time or the equivalent. Solution: `enforce(app)` can be called at module level (after app creation) OR the middleware can be registered inside enforce() using `app.middleware("http")(the_middleware_func)` programmatically.
**Warning signs:** Security headers missing, CORS failures, request IDs not propagating.

### Pitfall 5: Module-Level Variable Not Truly Private in .so
**What goes wrong:** Someone discovers they can still do `from core.licensing.license_manager import _license_state` to read/modify the internal state.
**Why it happens:** Regular Python module-level variables remain in the module `__dict__` even after Cython compilation. Only `cdef`-typed variables become hidden C variables, and `cdef` at module level is not available in pure Python mode.
**How to avoid:** Accept this as a known limitation. The security improvement is: (1) variable name is not documented anywhere, (2) finding it requires reverse-engineering native .so code, (3) much harder than `app.state.license_info = ...`. The accessor pattern (`get_license_status()`) makes the legitimate API clear and hides the implementation detail. Do not use a leading underscore pattern that's too obvious -- use an obfuscated name if desired.
**Warning signs:** Not a runtime issue -- this is a security architecture limitation to document.

### Pitfall 6: enforce(app) Called Before App Is Fully Configured
**What goes wrong:** If enforce() is called too early (before middleware stack is set up), the license middleware may run before security headers are added.
**How to avoid:** Call enforce(app) inside the lifespan function (for the license validation + state setup) and register the middleware at module level using a separate function call or by having enforce() return the middleware function. Alternatively: separate concerns -- `enforce_startup(app)` for lifespan (validation + integrity), middleware registered at module level via `register_enforcement_middleware(app)`.
**Warning signs:** Missing security headers on 503 license error responses.

## Code Examples

### main.py After Refactor (verified pattern from CONTEXT.md)
```python
# Line 57 changes from:
# from core.licensing.license_manager import validate_license, LicenseStatus, LicenseInfo, GRACE_PERIOD_DAYS
# To:
from core.licensing.enforcement import enforce

# Lines 160-202 inside lifespan() change from 43 lines of license logic to:
    enforce(app)

# Lines 370-425 (license_enforcement_middleware) are DELETED entirely
```

### get_license_status() -- Fast Per-Request Check
```python
# In license_manager.py (compiled to .so)
# Source: CONTEXT.md design decision

_license_state: LicenseInfo | None = None

def get_license_status() -> LicenseStatus | None:
    """Return current license status enum.

    Called by middleware on every request. Returns the enum value only,
    not the full LicenseInfo object, to minimize information exposure.
    Fast: reads a module-level variable, no computation.
    """
    if _license_state is None:
        return None
    return _license_state.status
```

### build-dist.sh Manifest Validation
```bash
# After injection, validate the manifest is syntactically valid Python
docker run --rm -v "$STAGE:/app:ro" -w /app python:3.12-slim \
    python -c "
import ast
with open('core/licensing/license_manager.py') as f:
    tree = ast.parse(f.read())
print('Syntax OK after manifest injection')
" || { error "Manifest injection produced invalid Python syntax"; exit 1; }
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `app.state.license_info` | Module-level variable in .so | Phase 7 | Eliminates trivial monkey-patching |
| Inline enforcement in main.py | `enforce(app)` single call | Phase 7 | main.py has zero enforcement logic |
| Hash placeholder in build-dist.sh | Real SHA256 manifest injection | Phase 7 | Tamper detection for protected files |
| No integrity verification | SHA256 manifest check at startup | Phase 7 | API refuses to start if files modified |

**Deprecated/outdated:**
- `app.state.license_info`: Replaced by internal state in compiled module
- Inline license validation in lifespan (lines 160-202): Moved to enforce()
- Inline middleware (lines 370-425): Moved to enforcement.py

## Open Questions

1. **Middleware registration timing**
   - What we know: Currently the middleware is registered at module level (line 379, `@app.middleware("http")` decorator). enforce() is called from lifespan (async context). Middleware can also be registered programmatically via `app.middleware("http")(func)`.
   - What's unclear: Whether registering middleware inside lifespan (which runs at app startup) vs. at module load time affects the middleware stack order.
   - Recommendation: Register the middleware OUTSIDE lifespan by splitting enforce() into two calls: (1) `enforce(app)` at module level after app creation for middleware registration, (2) enforcement startup logic inside lifespan for license validation + integrity check. OR: register everything inside lifespan but verify middleware order in tests.

2. **sed vs. Python script for manifest injection**
   - What we know: sed is already used in build-dist.sh for dev-mode stripping. Python would be more robust for dict injection.
   - What's unclear: Whether sed can handle the dict replacement reliably for all edge cases (e.g., if file hashes contain sed special characters -- unlikely with hex-only SHA256).
   - Recommendation: Use sed for consistency with existing build-dist.sh patterns. SHA256 hex digests are [0-9a-f] only -- no sed special character risk.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (with pytest-asyncio, asyncio_mode=auto) |
| Config file | `pytest.ini` (exists, minimal: asyncio_mode = auto) |
| Quick run command | `python3 -m pytest tests/core/licensing/ -x -q` |
| Full suite command | `python3 -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ENF-03 | enforce(app) registers middleware + main.py has no enforcement | unit + integration | `python3 -m pytest tests/core/licensing/test_enforcement.py -x -q` | No -- Wave 0 |
| ENF-03 | main.py calls enforce(app) only (no inline enforcement) | static analysis | `grep -c "license_enforcement_middleware\|validate_license\|LicenseStatus\|LicenseInfo\|GRACE_PERIOD_DAYS" apps/kerala_delivery/api/main.py` (should be 0 except enforce import) | N/A (bash check) |
| RTP-01 | SHA256 manifest embedded in .so and verified at startup | unit | `python3 -m pytest tests/core/licensing/test_enforcement.py::test_verify_integrity -x -q` | No -- Wave 0 |
| RTP-01 | Tampered file causes startup failure | unit | `python3 -m pytest tests/core/licensing/test_enforcement.py::test_integrity_failure -x -q` | No -- Wave 0 |
| -- | Existing license_manager tests still pass after adding state functions | regression | `python3 -m pytest tests/core/licensing/test_license_manager.py -x -q` | Yes (39 tests, all passing) |
| -- | Existing API tests still pass after main.py refactor | regression | `python3 -m pytest tests/apps/kerala_delivery/api/test_api.py -x -q` | Yes (115 tests, all passing) |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/core/licensing/ tests/apps/kerala_delivery/api/test_api.py -x -q`
- **Per wave merge:** `python3 -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/core/licensing/test_enforcement.py` -- covers ENF-03, RTP-01 (enforce() behavior, integrity verification, middleware registration)
- [ ] Test for `get_license_status()` and `set_license_state()` in license_manager -- can be added to existing `test_license_manager.py`
- [ ] Test for `verify_integrity()` with mock manifest -- unit test for hash comparison logic

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `apps/kerala_delivery/api/main.py` lines 57, 160-202, 370-425 -- exact code to extract
- Codebase inspection: `core/licensing/license_manager.py` -- full source, 440 lines, all functions documented
- Codebase inspection: `scripts/build-dist.sh` -- Step 4 placeholder at lines 162-171
- Codebase inspection: `infra/cython_build.py` -- compilation setup, 28 lines
- Phase 6 research: `.planning/milestones/v2.1-phases/06-build-pipeline/06-RESEARCH.md` -- Cython async limitation, build pipeline patterns
- Architecture research: `.planning/research/ARCHITECTURE.md` -- enforcement module design, integrity manifest design
- CONTEXT.md: locked decisions from user discussion session

### Secondary (MEDIUM confidence)
- [Python hashlib docs](https://docs.python.org/3/library/hashlib.html) -- `file_digest()` available since Python 3.11, confirmed available on Python 3.12
- [Cython pure Python mode docs](https://cython.readthedocs.io/en/latest/src/tutorial/pure.html) -- module-level variable behavior
- [Cython issue #3959](https://github.com/cython/cython/issues/3959) -- cpdef module-level variables not exposed to Python (confirms regular Python vars ARE accessible)
- [Cython language basics](https://cython.readthedocs.io/en/latest/src/userguide/language_basics.html) -- type annotations at module level kept as Python objects in module dict

### Tertiary (LOW confidence)
- None -- all critical findings verified with primary or secondary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use, no new dependencies
- Architecture: HIGH -- async/sync boundary well-documented in STATE.md, CONTEXT.md decisions are specific and detailed
- Pitfalls: HIGH -- verified through codebase inspection (test patterns, middleware ordering, module-level variable accessibility confirmed via Cython docs)
- Build pipeline: HIGH -- existing build-dist.sh inspected, Step 4 placeholder identified, sed injection pattern already proven in Step 2

**Research date:** 2026-03-10
**Valid until:** 2026-04-10 (stable -- no fast-moving dependencies)
