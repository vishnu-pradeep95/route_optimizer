# Phase 9: License Management - Research

**Researched:** 2026-03-11
**Domain:** License renewal mechanism, HTTP response headers, health endpoint enrichment (Python/FastAPI)
**Confidence:** HIGH

## Summary

Phase 9 adds three capabilities to the existing licensing system: (1) a renewal.key file mechanism that extends license expiry without requiring a new fingerprint exchange, (2) an X-License-Expires-In response header on all API responses for monitoring, and (3) license status fields in the /health endpoint body for diagnostics.

The existing codebase provides strong foundations. `encode_license_key()` / `decode_license_key()` can be reused directly for renewal keys (same LPG-XXXX format per CONTEXT.md decision). The `enforce()` function in enforcement.py is the natural place to check for renewal.key before calling `validate_license()`. The `license_enforcement_middleware` already adds response headers (`X-License-Warning` for GRACE, `X-License-Status` for /health) and is the right place to add `X-License-Expires-In`. The `/health` endpoint already returns a nested `services` object and can be extended with a `license` object.

**Primary recommendation:** Structure implementation as three plans: (1) renewal mechanism (generate_license.py --renew + enforce() renewal.key check), (2) X-License-Expires-In header in middleware, (3) /health license status fields. Each is independent after establishing a new `get_license_info()` accessor that exposes the full `_license_state` LicenseInfo object.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Renewal key uses the **same LPG-XXXX-XXXX format** as the original license key (reuses existing encode/decode/validate infrastructure)
- `generate_license.py --renew --customer ID --fingerprint HASH --months N` generates the renewal key with guidance about dropping as `renewal.key`
- API checks for `renewal.key` at **startup only** (inside `enforce()`, before `validate_license()`). Customer restarts API after dropping the file. Matches existing `license.key` behavior.
- Header appears on **all responses** (including /health and 503 INVALID responses)
- Format: **days with 'd' suffix** (e.g., `45d`, `0d`, `-3d` for expired)
- Header is **omitted when license state is None** (dev mode, no license configured)
- INVALID 503 responses include the header showing how far past expiry (e.g., `-15d`)
- License info in a **nested `license` object** alongside `services` in /health body
- **No customer_id** in the license section (considered sensitive)
- **Omit `license` key entirely** when no license is configured (dev mode)

### Claude's Discretion
- Post-renewal file handling (leave renewal.key in place vs replace license.key and delete)
- Whether GRACE/INVALID license status degrades overall /health status or is purely informational
- Exact implementation of renewal key precedence logic (if both license.key and renewal.key exist)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| LIC-01 | License renewal extends expiry without full re-keying cycle (customer drops renewal.key file) | Renewal mechanism: reuse `encode_license_key()`/`decode_license_key()` with same LPG-XXXX format. Check for `renewal.key` in `enforce()` before `validate_license()`. generate_license.py --renew flag. |
| LIC-02 | X-License-Expires-In response header on API responses for monitoring | Add header in `license_enforcement_middleware`. Requires new `get_license_info()` accessor to get `days_remaining` from `_license_state`. Format: `{days}d`. |
| LIC-03 | License status included in /health endpoint body for diagnostics | Add `license` nested object to `/health` JSONResponse. Uses `get_license_info()` accessor. Omit when state is None. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12+ | Runtime | Already in use, hashlib.file_digest() requires 3.11+ |
| FastAPI | 0.95+ | Web framework | Already in use, lifespan pattern |
| Starlette | (bundled) | Middleware, Response | FastAPI's ASGI layer, already in use |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | existing | Testing | All unit tests for renewal logic, header, health |
| dataclasses | stdlib | LicenseInfo | Already used for license state |
| struct | stdlib | Binary packing | Already used in encode/decode |
| argparse | stdlib | CLI --renew flag | Already used in generate_license.py |

### Alternatives Considered
None -- this phase extends existing infrastructure only. No new libraries needed.

**Installation:**
No additional packages required. All work uses existing dependencies.

## Architecture Patterns

### Current Code Structure (relevant files)
```
core/licensing/
  __init__.py           # Public API exports
  license_manager.py    # Core: encode/decode, validate, state, integrity
  enforcement.py        # Async wrapper: enforce(app), middleware

scripts/
  generate_license.py   # CLI: --customer, --fingerprint, --months, --this-machine

apps/kerala_delivery/api/
  main.py               # /health endpoint, lifespan calls enforce(app)

tests/core/licensing/
  test_license_manager.py   # Unit tests for license_manager
  test_enforcement.py       # Unit tests for enforcement + middleware
```

### Pattern 1: New Accessor -- get_license_info()
**What:** Currently only `get_license_status()` exists (returns `LicenseStatus | None`). Both LIC-02 (header) and LIC-03 (health) need `days_remaining`, `expires_at`, and fingerprint match info from the full `LicenseInfo` object. Add `get_license_info() -> LicenseInfo | None` to license_manager.py.
**When to use:** Any time the middleware or health endpoint needs more than just the status enum.
**Example:**
```python
# In license_manager.py
def get_license_info() -> LicenseInfo | None:
    """Return full license info. None if no state set (dev mode)."""
    return _license_state
```
**Confidence:** HIGH -- direct pattern from existing `get_license_status()`.

### Pattern 2: Renewal Key Processing in enforce()
**What:** Check for renewal.key before calling `validate_license()`. If renewal.key exists, decode it, validate it, and if the new expiry is later than the current license, use the renewed expiry.
**When to use:** At API startup, in `enforce()` function body, before the main `validate_license()` call.
**Example:**
```python
# In enforcement.py, inside enforce()
def enforce(app: FastAPI) -> None:
    # Step 0: Check for renewal.key
    renewal_info = _try_load_renewal_key()
    if renewal_info:
        # Renewal key is valid -- use it as the primary license
        license_info = renewal_info
        logger.info("License renewed via renewal.key -- new expiry: %s", ...)
        # Post-renewal file handling here
    else:
        # Step 1: Normal validation
        license_info = validate_license()
    ...
```
**Confidence:** HIGH -- follows established `enforce()` pattern.

### Pattern 3: Middleware Header Addition
**What:** Add `X-License-Expires-In` header to all responses in the existing middleware.
**When to use:** On every response where license state is not None.
**Example:**
```python
# In the license_enforcement_middleware, after getting status
info = get_license_info()
if info is not None:
    response.headers["X-License-Expires-In"] = f"{info.days_remaining}d"
```
**Confidence:** HIGH -- extends existing `X-License-Warning` / `X-License-Status` header pattern.

### Pattern 4: Health Endpoint License Section
**What:** Add `license` nested object to /health response.
**When to use:** In the `/health` endpoint handler in main.py.
**Example:**
```python
# In main.py health_check()
from core.licensing.license_manager import get_license_info

info = get_license_info()
content = {
    "status": overall,
    "service": "kerala-lpg-optimizer",
    "version": app.version,
    "uptime_seconds": round(uptime, 1),
    "services": services,
}
if info is not None:
    content["license"] = {
        "status": info.status.value,
        "expires_at": info.expires_at.strftime("%Y-%m-%d"),
        "days_remaining": info.days_remaining,
        "fingerprint_match": True,  # If we got here with state set, fingerprint matched at startup
    }
```
**Confidence:** HIGH -- direct extension of existing /health structure.

### Anti-Patterns to Avoid
- **Importing `_license_state` directly:** External modules should NOT access the private `_license_state` variable. Use the public `get_license_info()` accessor. This preserves encapsulation and matches the existing `get_license_status()` pattern.
- **Renewal at runtime (not startup):** The CONTEXT.md decision is clear: renewal happens at startup only. Do NOT add hot-reload or file-watching for renewal.key.
- **Separate renewal key format:** CONTEXT.md locks the decision to use the same LPG-XXXX format. Do NOT invent a new RNW-XXXX format.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| License key encoding | New renewal-specific encoding | Existing `encode_license_key()` | Same LPG-XXXX format per CONTEXT.md decision. The renewal key IS a license key with a new expiry date. |
| HMAC signing for renewal | New signature scheme | Existing HMAC infrastructure in license_manager.py | Reuse the same `_HMAC_KEY` and signing logic. |
| Response header middleware | New middleware function | Extend existing `license_enforcement_middleware` | Adding one more header to an existing middleware is cleaner than registering a second middleware. |
| Date calculation for header | Manual datetime math | Existing `LicenseInfo.days_remaining` | Already computed correctly during `decode_license_key()` and preserved through `dataclasses.replace()`. |

**Key insight:** This phase is purely additive -- it extends existing, well-tested infrastructure. No new cryptographic primitives, no new middleware, no new data structures. Every feature maps cleanly onto existing code patterns.

## Common Pitfalls

### Pitfall 1: One-Way State Guard Blocks Renewal Upgrades
**What goes wrong:** The `set_license_state()` one-way guard (Phase 8) blocks state upgrades (e.g., INVALID->VALID). If renewal.key processing happens AFTER `set_license_state()` is called with the old (expired) license, the renewal cannot upgrade the state.
**Why it happens:** The guard is designed to prevent runtime bypasses. But at startup, we WANT to upgrade via renewal.
**How to avoid:** Process renewal.key BEFORE calling `validate_license()` or `set_license_state()`. The renewal key becomes the primary license input, and `set_license_state()` is called only once with the already-renewed state.
**Warning signs:** Renewal.key is present but license stays INVALID after restart.

### Pitfall 2: Header on 503 Responses Created by Middleware
**What goes wrong:** When license is INVALID, the middleware returns a `JSONResponse(status_code=503)` directly, bypassing `call_next`. Headers added AFTER `call_next()` are never reached.
**Why it happens:** The 503 response is constructed inline in the middleware, not by the endpoint handler.
**How to avoid:** Add the `X-License-Expires-In` header to the 503 JSONResponse object BEFORE returning it, not after `call_next()`. Must handle all three response paths: (1) INVALID 503, (2) /health pass-through, (3) normal pass-through.
**Warning signs:** 503 responses missing the X-License-Expires-In header.

### Pitfall 3: `days_remaining` Stale After Long Uptime
**What goes wrong:** `_license_state.days_remaining` is computed at startup (or last revalidation). Between revalidations (every 500 requests), the `days_remaining` value could be stale by up to many hours.
**Why it happens:** `days_remaining` is stored as an integer in LicenseInfo, not recalculated on access.
**How to avoid:** For the X-License-Expires-In header, recalculate days_remaining from `expires_at` and `datetime.now(utc)` at response time rather than using the stored value. This gives accurate results regardless of when the last revalidation occurred.
**Warning signs:** Header shows wrong day count after API has been running for a long time without revalidation.

### Pitfall 4: Renewal Key Fingerprint Must Match Current Machine
**What goes wrong:** A renewal key generated for one machine is dropped onto a different machine.
**Why it happens:** The `--renew` command takes `--fingerprint` as input. If the operator provides the wrong fingerprint, the renewal key won't match.
**How to avoid:** The renewal key passes through `validate_license()` (or equivalent decode + fingerprint check). The fingerprint check in `validate_license()` already handles this. The renewal key must contain the same fingerprint as the current machine.
**Warning signs:** "License key is not valid for this machine" error after dropping renewal.key.

### Pitfall 5: Docker Volume Mount for renewal.key
**What goes wrong:** In production Docker, `renewal.key` at `/app/renewal.key` doesn't exist because docker-compose.prod.yml only mounts `license.key`.
**Why it happens:** The `validate_license()` function checks `["license.key", "/app/license.key"]`. A new `renewal.key` path needs the same treatment.
**How to avoid:** Check both `renewal.key` and `/app/renewal.key` paths. Update docker-compose.prod.yml to optionally mount `./renewal.key:/app/renewal.key:ro`. Document that the customer needs to place renewal.key in the same directory as license.key and restart.
**Warning signs:** Renewal works in development but not in Docker production deployment.

### Pitfall 6: Fingerprint Match Field in /health is Always True
**What goes wrong:** The `fingerprint_match` field in /health is misleading. If the license is INVALID due to fingerprint mismatch, `_license_state` still stores the result with `status=INVALID` but doesn't have an explicit `fingerprint_matched` boolean.
**Why it happens:** The current `LicenseInfo` dataclass doesn't store why the license is invalid (expired vs fingerprint mismatch vs missing key).
**How to avoid:** At startup in `enforce()`, the result of `validate_license()` already sets the status. If `_license_state` is set (i.e., not None and not dev mode), we know enforce() ran. If the status is INVALID due to fingerprint mismatch, the message contains "not valid for this machine". The `fingerprint_match` field can be derived: check if `_license_state.message` does NOT contain "not valid for this machine". Alternatively, compare the stored fingerprint prefix with the current machine's fingerprint prefix.
**Warning signs:** /health shows `fingerprint_match: true` when the actual cause of INVALID is a fingerprint mismatch.

## Code Examples

### Renewal Key Generation (generate_license.py --renew)
```python
# In scripts/generate_license.py, add to argparse:
parser.add_argument(
    "--renew",
    action="store_true",
    help="Generate a renewal key (same format, customer drops as renewal.key)",
)

# In main(), after key generation:
if args.renew:
    print(f"  Save as: renewal.key")
    print(f"  Customer drops this file alongside license.key and restarts the API.")
    print(f"  The API will pick up the new expiry automatically on restart.")
```
**Source:** Extension of existing generate_license.py patterns.

### Renewal Key Processing in enforce()
```python
# In enforcement.py, inside enforce(), before validate_license():
def _try_load_renewal_key() -> Optional[LicenseInfo]:
    """Try to load and validate renewal.key. Returns LicenseInfo or None."""
    for path in ["renewal.key", "/app/renewal.key"]:
        try:
            with open(path, "r") as f:
                key = f.read().strip()
            if key:
                info = validate_license(key)
                if info.status in (LicenseStatus.VALID, LicenseStatus.GRACE):
                    return info
                else:
                    logger.warning("renewal.key present but invalid: %s", info.message)
        except FileNotFoundError:
            continue
    return None
```
**Source:** Modeled on `validate_license()` file-reading pattern (license_manager.py lines 393-400).

### X-License-Expires-In Header in Middleware
```python
# In the license_enforcement_middleware, add header to all response paths:
from core.licensing.license_manager import get_license_info
from datetime import datetime, timezone

def _compute_expires_header() -> str | None:
    """Compute X-License-Expires-In value. Returns None if no license state."""
    info = get_license_info()
    if info is None:
        return None
    # Recalculate from expires_at for accuracy (not stale days_remaining)
    days = (info.expires_at - datetime.now(timezone.utc)).days
    return f"{days}d"
```
**Source:** Pattern from existing header logic in enforcement.py middleware.

### Health Endpoint License Section
```python
# In main.py health_check(), after building services dict:
from core.licensing.license_manager import get_license_info, get_machine_fingerprint

info = get_license_info()
if info is not None:
    # Derive fingerprint_match: compare stored prefix with current machine
    current_fp = get_machine_fingerprint()[:16]
    content["license"] = {
        "status": info.status.value,
        "expires_at": info.expires_at.strftime("%Y-%m-%d"),
        "days_remaining": (info.expires_at - datetime.now(timezone.utc)).days,
        "fingerprint_match": current_fp == info.fingerprint[:16],
    }
```
**Source:** Extension of existing /health endpoint pattern (main.py lines 666-721).

## Discretion Recommendations

### Post-Renewal File Handling
**Recommendation:** Replace license.key with the renewal key content, then delete renewal.key.

**Rationale:**
- Leaving both files creates confusion about which key is active
- If the API restarts again with both files present, it needs precedence logic
- Replacing license.key means the renewal.key mechanism is "consumed" -- cleaner mental model
- The renewal key IS a valid license key (same LPG-XXXX format), so license.key always contains the active key
- Atomic write pattern: write to license.key.tmp, rename to license.key, delete renewal.key

**Alternative considered:** Leave renewal.key in place and always check it first. Rejected because it accumulates stale files and complicates the precedence chain.

### License Status Impact on /health
**Recommendation:** License status is purely informational -- does NOT degrade the overall /health status.

**Rationale:**
- /health is used for service monitoring (is the API running? are databases connected?)
- License status is a business concern, not an infrastructure concern
- The middleware already returns 503 on all endpoints when INVALID -- monitoring tools will detect this via endpoint probes
- If /health itself returned 503 due to license issues, it would confuse infrastructure monitoring (Docker health checks, load balancers) with business-logic issues
- The `license` section in /health provides all the diagnostic info needed without polluting the overall status

### Renewal Key Precedence Logic
**Recommendation:** If renewal.key exists, validate it first. If valid (VALID or GRACE), use it and replace license.key. If invalid, fall through to normal license.key validation.

**Rationale:**
- Simple, predictable behavior: renewal.key always takes precedence
- If renewal.key is invalid/expired/wrong-fingerprint, the customer still gets their existing license
- Log clearly: "renewal.key found but invalid: {reason}. Falling back to license.key."
- After successful renewal, delete renewal.key to prevent re-processing on next restart

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `get_license_status()` returns enum only | Add `get_license_info()` returning full LicenseInfo | Phase 9 | Enables header and health endpoint access to days_remaining, expires_at |
| No renewal mechanism | renewal.key file drop + restart | Phase 9 | Customers can renew without re-running get_machine_id.py |
| No expiry visibility in API | X-License-Expires-In header | Phase 9 | Monitoring tools can alert before expiry |
| /health shows infrastructure only | /health includes license section | Phase 9 | Diagnostics include license state without needing logs |

**Deprecated/outdated:**
- The early research (FEATURES.md) suggested a separate `RNW-XXXX` format and a `renew_license.py` script. CONTEXT.md overrides this: same LPG-XXXX format, same `generate_license.py` script with `--renew` flag.

## Open Questions

1. **Docker volume mount for renewal.key**
   - What we know: docker-compose.prod.yml mounts `./license.key:/app/license.key:ro`. renewal.key needs a similar mount.
   - What's unclear: Should the mount be read-write so enforce() can delete it after processing? Or should it stay read-only and the customer deletes it manually?
   - Recommendation: Mount as read-only (`:ro`) for consistency with license.key. The file-replacement logic (replace license.key, delete renewal.key) should only operate on the host-side paths. In Docker, the customer manually cleans up renewal.key after restart. Document this in the CLI output when generating renewal keys. The alternative (read-write mount) would break the security principle of the current setup.

2. **Should the `--renew` flag require `--customer` and `--fingerprint`?**
   - What we know: CONTEXT.md specifies `generate_license.py --renew --customer ID --fingerprint HASH --months N`. This means the operator must know the customer ID and fingerprint.
   - What's unclear: Could `--renew` read an existing license.key file to auto-extract customer_id and fingerprint?
   - Recommendation: Follow CONTEXT.md exactly -- require all flags explicitly. This is an operator-side tool, and requiring explicit values prevents accidental mistakes. The generate_license.py output already shows customer and fingerprint on generation, so the operator has these values from the original issuance.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (asyncio_mode = auto) |
| Config file | `pytest.ini` |
| Quick run command | `python -m pytest tests/core/licensing/ -x -q` |
| Full suite command | `python -m pytest tests/core/licensing/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| LIC-01 | Renewal key generation via --renew flag | unit | `python -m pytest tests/core/licensing/test_license_manager.py::TestRenewalKey -x` | No -- Wave 0 |
| LIC-01 | enforce() loads renewal.key and uses it | unit | `python -m pytest tests/core/licensing/test_enforcement.py::TestRenewalEnforcement -x` | No -- Wave 0 |
| LIC-01 | Post-renewal file handling (replace license.key, delete renewal.key) | unit | `python -m pytest tests/core/licensing/test_enforcement.py::TestRenewalFileHandling -x` | No -- Wave 0 |
| LIC-02 | X-License-Expires-In header on normal responses | unit | `python -m pytest tests/core/licensing/test_enforcement.py::TestExpiresInHeader -x` | No -- Wave 0 |
| LIC-02 | X-License-Expires-In header on 503 INVALID responses | unit | `python -m pytest tests/core/licensing/test_enforcement.py::TestExpiresInHeader -x` | No -- Wave 0 |
| LIC-02 | Header omitted in dev mode (state is None) | unit | `python -m pytest tests/core/licensing/test_enforcement.py::TestExpiresInHeader -x` | No -- Wave 0 |
| LIC-03 | /health includes license section when licensed | integration | `python -m pytest tests/core/licensing/test_enforcement.py::TestHealthLicenseSection -x` | No -- Wave 0 |
| LIC-03 | /health omits license section in dev mode | integration | `python -m pytest tests/core/licensing/test_enforcement.py::TestHealthLicenseSection -x` | No -- Wave 0 |
| LIC-03 | /health license section has correct fields | integration | `python -m pytest tests/core/licensing/test_enforcement.py::TestHealthLicenseSection -x` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/core/licensing/ -x -q`
- **Per wave merge:** `python -m pytest tests/core/licensing/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/core/licensing/test_license_manager.py::TestRenewalKey` -- covers LIC-01 (renewal key generation)
- [ ] `tests/core/licensing/test_enforcement.py::TestRenewalEnforcement` -- covers LIC-01 (enforce() renewal loading)
- [ ] `tests/core/licensing/test_enforcement.py::TestRenewalFileHandling` -- covers LIC-01 (file replacement)
- [ ] `tests/core/licensing/test_enforcement.py::TestExpiresInHeader` -- covers LIC-02 (all header scenarios)
- [ ] `tests/core/licensing/test_enforcement.py::TestHealthLicenseSection` -- covers LIC-03 (health endpoint)
- [ ] New accessor `get_license_info()` tests in test_license_manager.py

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `core/licensing/license_manager.py`, `core/licensing/enforcement.py`, `core/licensing/__init__.py`, `scripts/generate_license.py`, `apps/kerala_delivery/api/main.py`
- Existing test files: `tests/core/licensing/test_license_manager.py`, `tests/core/licensing/test_enforcement.py`
- Phase CONTEXT.md: `.planning/milestones/v2.1-phases/09-license-management/09-CONTEXT.md`
- Docker production config: `docker-compose.prod.yml` (license.key mount pattern)

### Secondary (MEDIUM confidence)
- Previous research: `.planning/research/FEATURES.md` (renewal feature design, superseded by CONTEXT.md decisions)
- Phase 8 state guard decisions: `.planning/STATE.md` (one-way guard implications for renewal)

### Tertiary (LOW confidence)
None -- all findings verified against codebase.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, extending existing code only
- Architecture: HIGH -- all integration points identified and verified in source code
- Pitfalls: HIGH -- derived from detailed analysis of actual code paths (state guard, middleware response flow, stale days_remaining, Docker mounts)

**Research date:** 2026-03-11
**Valid until:** 2026-04-11 (stable -- internal codebase, no external dependency drift)
