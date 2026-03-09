# Phase 2: Security Hardening - Research

**Researched:** 2026-03-01
**Domain:** FastAPI security middleware, HTTP security headers, CORS hardening, file upload validation, rate limiter test isolation
**Confidence:** HIGH

## Summary

This phase adds production security hardening to the FastAPI API. The codebase already has partial implementations for most requirements: CORS via `CORSMiddleware` with env-var origins, rate limiting via `slowapi` with per-endpoint decorators, API docs gating via conditional `docs_url`/`openapi_url`, and basic file extension/size validation on the upload endpoint. The gaps are: (1) no HTTP security headers middleware, (2) CORS allows all headers via `allow_headers=["*"]`, (3) `/redoc` is NOT gated in production, (4) file upload validation lacks MIME type checking and descriptive error messages with limit values, (5) `python-jose` and `passlib` are not installed (SEC-05 is verification-only), and (6) rate limiter test isolation relies on toggling `limiter.enabled` but there is no state reset between rate-limit-specific tests.

Secweb 1.30.10 provides 16 security header middlewares for FastAPI/Starlette covering CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, and more. However, Secweb does NOT include a `PermissionsPolicy` middleware in its stable release (confirmed by installing 1.30.10 and inspecting available modules). A small custom ASGI middleware is needed to add the `Permissions-Policy` header. The approach is to use the `SecWeb` all-in-one class for the standard headers, plus a custom middleware for Permissions-Policy.

**Primary recommendation:** Use Secweb 1.30.10 for standard security headers (CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy), add a small custom middleware for Permissions-Policy, fix the `/redoc` gating gap, tighten CORS `allow_headers`, improve file upload validation with MIME-type checks and descriptive errors, and disable rate limiting in tests via `RATE_LIMIT_ENABLED=false` env var (already partially done).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Rate Limit Policy
- Claude's discretion on specific per-endpoint numbers, guided by fleet scale (13 vehicles, ~1 office user)
- Upload endpoint (`POST /api/upload-orders`): strict limit -- expensive operation triggering geocoding API calls
- Telemetry endpoint (`POST /api/telemetry`): generous limit per API key -- 13 vehicles sending GPS pings, must not throttle legitimate driver updates
- Read endpoints (`GET /api/routes`, `GET /api/vehicles`): light limits to prevent runaway polling while allowing normal dashboard 10-second refresh cycles
- Rate limit exceeded response: HTTP 429 with `Retry-After` header (standard behavior, slowapi supports this)
- Rate limiting disabled in tests via `RATE_LIMIT_ENABLED=false` in pytest conftest to prevent cross-test bleed (SEC-06)

#### CSP & Security Headers
- Content Security Policy: strict with explicit allowlist -- `default-src 'self'` plus known sources only (tile.openstreetmap.org, unpkg.com for Leaflet, Google Maps APIs)
- CSP must be tested against running app to ensure Leaflet tiles and Google Maps navigation links still work
- HSTS: Claude's discretion based on deployment setup (enable if behind TLS)
- Permissions-Policy: restrict all browser features except geolocation (driver PWA needs it for GPS pings); disable camera, microphone, payment, etc.
- X-Frame-Options: DENY (API should never be iframed)
- X-Content-Type-Options: nosniff
- Referrer-Policy: strict-origin-when-cross-origin
- CSP violation reporting: Claude's discretion on report-only vs enforcing rollout strategy
- Security headers applied in ALL environments (dev, staging, production) -- catches CSP breakage early during development

#### File Upload Guardrails
- Max file size: Claude's discretion (guided by typical CDCMS exports being <50 KB for 200 rows)
- Allowed file types: CSV and Excel only (.csv, .xlsx, .xls) -- matches the two formats the importer supports (CsvImporter + openpyxl)
- Row count limit: Claude's discretion (fleet is 13 vehicles, typical batch is 50-100 orders)
- Rejection errors: specific messages showing what failed and what the limits are (e.g., "File too large (15 MB). Maximum: 10 MB." or "Unsupported file type (.pdf). Accepted: .csv, .xlsx, .xls")
- Validation must happen BEFORE any processing (parse, geocode, optimize) begins

#### Environment Gating
- API docs (`/docs`, `/redoc`): return 404 when `ENV=production`; available in development and staging
- CORS: permissive in development (allow localhost origins broadly), strict in production (require explicit `CORS_ALLOWED_ORIGINS` whitelist)
- Security headers: active in all environments
- Rate limiting: enabled in dev and production; disabled only in tests/CI via env var

### Claude's Discretion
- Exact rate limit numbers per endpoint (within the tier guidance above)
- HSTS configuration (depends on TLS setup)
- CSP report-only vs enforcing rollout
- Exact file size and row count limits
- Secweb configuration details and middleware ordering
- Whether python-jose/passlib replacement is needed (currently neither is installed -- SEC-05 may be a verification-only step)

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SEC-01 | HTTP security headers via middleware -- CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy | Secweb 1.30.10 handles CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy. Custom middleware needed for Permissions-Policy (not in Secweb stable). See Standard Stack and Code Examples sections. |
| SEC-02 | CORS hardened -- no wildcard origins, explicit whitelist from env var | Existing `CORSMiddleware` already reads `CORS_ALLOWED_ORIGINS` env var. Fix: tighten `allow_headers` from `["*"]` to explicit list. See Architecture Patterns section. |
| SEC-03 | API docs (/docs, /redoc) gated behind environment check -- hidden in production | Existing: `docs_url` and `openapi_url` gated. Gap: `redoc_url` NOT set -- defaults to `/redoc` and serves ReDoc HTML in production. Fix: add `redoc_url=_redoc_url` to FastAPI constructor. See Common Pitfalls. |
| SEC-04 | Input validation audit -- all file upload endpoints check file type, size, content | Existing: extension check and size check present. Gaps: no MIME-type/content-type sniffing check, error messages don't include the limit values or actual values, no row count limit. See Architecture Patterns. |
| SEC-05 | Replace deprecated security libraries if present (python-jose -> PyJWT, passlib -> pwdlib) | **Verification-only**: Neither `python-jose` nor `passlib` is installed (`pip list` empty, no imports found in codebase). Confirm absence and document. |
| SEC-06 | Rate limiter state isolated in tests -- no cross-test bleed | Existing: `client` fixture sets `RATE_LIMIT_ENABLED=false` and toggles `limiter.enabled`. Dedicated `rate_limited_client` fixture enables it for rate limit tests. Current pattern is functional. Enhancement: ensure `limiter.reset()` is called after rate-limit tests to prevent state leaking to subsequent test modules. See Code Examples. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Secweb | 1.30.10 | Security headers middleware (CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, and 11 more) | Built for FastAPI/Starlette, ASGI middleware implementation, no external dependencies, follows MDN/OWASP recommendations |
| slowapi | 0.1.9 | Rate limiting (already installed) | Already in use, built on `limits` library, integrates with FastAPI as Starlette extension |
| starlette | 0.52.1 | CORSMiddleware (already installed via FastAPI) | Built-in FastAPI CORS support, already configured |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-multipart | 0.0.22 | File upload parsing (already installed) | Already handles UploadFile for file upload validation |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Secweb | secure.py (TypeError/secure) | secure.py has `SecureASGIMiddleware` and better defaults, but Secweb is specifically built for FastAPI/Starlette with individual middleware classes giving finer control. CONTEXT.md mentions Secweb by name. |
| Secweb | Manual middleware | No library dependency, but hand-rolling 6+ headers invites mistakes and misses updates |
| Custom Permissions-Policy middleware | Wait for Secweb dev branch | Permissions-Policy is a success criteria requirement; cannot wait for Secweb to release it |

**Installation:**
```bash
pip install Secweb==1.30.10
```

## Architecture Patterns

### Recommended Middleware Ordering in main.py

Middleware in FastAPI/Starlette wraps in reverse order of registration: the LAST middleware added processes the request FIRST (outermost). This means:

```
# Registration order in main.py:
1. SecWeb(app)          # Registered FIRST -> processes LAST (adds headers to response)
2. Permissions-Policy   # Custom middleware for the missing header
3. CORSMiddleware       # Handles CORS preflight and origin validation
4. license_enforcement  # Existing @app.middleware("http")
5. Rate limiter         # app.state.limiter + exception handler (already registered)
```

The security headers middleware should be outermost (registered first) so that every response -- including error responses from CORS rejection or rate limiting -- gets security headers. CORS middleware must come AFTER security headers so that CORS preflight responses also include security headers.

### Pattern 1: SecWeb All-in-One Configuration
**What:** Use the `SecWeb` class to configure all standard security headers in a single call
**When to use:** When you want CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, and CORS-related headers
**Example:**
```python
# Source: Secweb GitHub README + verified via installed package inspection
from Secweb import SecWeb

SecWeb(
    app=app,
    Option={
        'csp': {
            'default-src': ["'self'"],
            'script-src': ["'self'"],
            'style-src': ["'self'", "'unsafe-inline'"],
            'img-src': [
                "'self'", "data:", "blob:",
                "https://*.tile.openstreetmap.org",
                "https://unpkg.com",
            ],
            'connect-src': [
                "'self'",
                "https://maps.googleapis.com",
            ],
            'font-src': ["'self'"],
            'frame-ancestors': ["'none'"],
        },
        'hsts': {'max-age': 31536000, 'includeSubDomains': True, 'preload': True},
        'xframe': 'DENY',
        'referrer': ['strict-origin-when-cross-origin'],
        # xcto (X-Content-Type-Options: nosniff) is ON by default in SecWeb
    },
)
```

### Pattern 2: Custom Permissions-Policy Middleware
**What:** ASGI middleware to add `Permissions-Policy` header (not available in Secweb stable)
**When to use:** Required for SEC-01 success criteria (A-grade security headers scan)
**Example:**
```python
# Source: FastAPI middleware documentation pattern
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class PermissionsPolicyMiddleware(BaseHTTPMiddleware):
    """Add Permissions-Policy header to all responses.

    Restricts browser features. Only geolocation is allowed
    (driver PWA needs GPS). All other features are denied.
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["Permissions-Policy"] = (
            "geolocation=(self), "
            "camera=(), "
            "microphone=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "accelerometer=()"
        )
        return response

app.add_middleware(PermissionsPolicyMiddleware)
```

### Pattern 3: Environment-Gated CORS
**What:** Permissive CORS in development, strict whitelist in production
**When to use:** SEC-02 requires CORS hardening
**Example:**
```python
# Source: FastAPI CORS documentation + existing codebase pattern
_env = os.environ.get("ENVIRONMENT", "development")
_cors_origins_raw = os.environ.get("CORS_ALLOWED_ORIGINS", "")

if _env == "development" and not _cors_origins_raw:
    # Dev default: allow common local origins
    _allowed_origins = [
        "http://localhost:8000",
        "http://localhost:3000",
        "http://localhost:5173",
    ]
else:
    # Production/staging: explicit whitelist only
    _allowed_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    # Tighten from ["*"] to explicit list
    allow_headers=["Content-Type", "X-API-Key", "Authorization"],
    expose_headers=["X-License-Warning", "Retry-After"],
)
```

### Pattern 4: File Upload Validation Before Processing
**What:** Validate file type (extension + content-type), size, and row count before any parsing
**When to use:** SEC-04 requires validation before processing begins
**Example:**
```python
# Source: Existing codebase pattern + enhancement
ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/octet-stream",  # Some browsers send this for .csv
}
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_ROW_COUNT = 1000  # Fleet is 13 vehicles, typical batch 50-100 orders

# In the upload endpoint, BEFORE any processing:
filename = file.filename or ""
ext = pathlib.Path(filename).suffix.lower()
if ext not in ALLOWED_EXTENSIONS:
    raise HTTPException(
        status_code=400,
        detail=f"Unsupported file type ({ext or 'none'}). Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
    )

content_type = file.content_type or ""
if content_type and content_type not in ALLOWED_CONTENT_TYPES:
    raise HTTPException(
        status_code=400,
        detail=f"Unexpected content type ({content_type}). Upload a CSV or Excel file.",
    )

content = await file.read()
if len(content) > MAX_UPLOAD_SIZE_BYTES:
    size_mb = len(content) / (1024 * 1024)
    max_mb = MAX_UPLOAD_SIZE_BYTES / (1024 * 1024)
    raise HTTPException(
        status_code=413,
        detail=f"File too large ({size_mb:.1f} MB). Maximum: {max_mb:.0f} MB.",
    )
```

### Anti-Patterns to Avoid
- **Wildcard CORS in production:** `allow_origins=["*"]` allows any website to make requests. The current code reads from env var which is correct, but `allow_headers=["*"]` should be tightened.
- **Reading full file before size check:** The current code does `content = await file.read()` then checks `len(content)`. This means the entire file is in memory before rejection. For the 10 MB limit this is acceptable (not worth streaming complexity for a small fleet app), but the error message should include actual file size.
- **Applying security headers only in production:** CONTEXT.md explicitly requires headers in ALL environments to catch CSP breakage during development.
- **Using `BaseHTTPMiddleware` for high-throughput paths:** `BaseHTTPMiddleware` has a known limitation -- it reads the entire response body before returning. For security headers that just add response headers, this is fine because the header is added AFTER `call_next` returns the response object.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy | Custom middleware for each header | Secweb `SecWeb` class | Handles 16 headers, follows MDN/OWASP, tested against edge cases (nonce generation, report-only mode, route-specific headers) |
| Rate limiting | Custom counter/token bucket | slowapi (already in use) | Handles sliding windows, key extraction, in-memory/Redis storage, Retry-After headers |
| CORS handling | Manual Access-Control-* headers | Starlette CORSMiddleware (already in use) | Handles preflight OPTIONS, origin matching, credential negotiation |
| File type detection | Reading file bytes to detect magic numbers | Extension + Content-Type check | For this use case (CSV/Excel from office staff), extension + content-type is sufficient. Magic number detection adds complexity without meaningful security gain (a malicious user can set any bytes). |

**Key insight:** Security header configuration is deceptively complex. A single missing directive in CSP can break the entire frontend (e.g., missing `img-src` for map tiles). Using a library like Secweb means you get tested defaults and only override what you need, rather than building a complete header policy from scratch.

## Common Pitfalls

### Pitfall 1: CSP Breaks Map Tiles Silently
**What goes wrong:** A strict CSP `img-src 'self'` blocks Leaflet from loading OpenStreetMap tiles. The map shows a blank gray area with no visible error -- only a CSP violation in the browser console.
**Why it happens:** Map tile URLs (`https://a.tile.openstreetmap.org/...`) are cross-origin image loads. CSP blocks them unless explicitly allowed.
**How to avoid:** CSP `img-src` MUST include `https://*.tile.openstreetmap.org` (wildcard subdomain for a/b/c tile servers). Also include `https://unpkg.com` for Leaflet marker icons and `data:` for inline SVG icons.
**Warning signs:** Maps render as gray/empty rectangles. Check browser console for `Refused to load the image` CSP errors.

### Pitfall 2: /redoc Still Accessible in Production
**What goes wrong:** The current code gates `docs_url` and `openapi_url` but does NOT set `redoc_url`. FastAPI defaults `redoc_url` to `/redoc`. When `openapi_url=None`, the ReDoc page loads but cannot fetch the schema -- however, the route still returns 200 with an HTML page containing the ReDoc JavaScript.
**Why it happens:** Partial implementation -- `redoc_url` was overlooked when `docs_url` was gated.
**How to avoid:** Add `_redoc_url = "/redoc" if _env_name != "production" else None` and pass `redoc_url=_redoc_url` to the FastAPI constructor. The success criteria specifically mentions both `/docs` and `/redoc` returning 404 in production.
**Warning signs:** Visiting `/redoc` in a production deployment returns 200 instead of 404.

### Pitfall 3: CORS allow_headers=["*"] Is Overly Permissive
**What goes wrong:** The current `allow_headers=["*"]` tells the browser that ANY header is allowed in cross-origin requests. While this doesn't create a direct vulnerability (CORS controls browser behavior, not server-side auth), it makes the API surface larger than necessary and can mask issues.
**Why it happens:** Quick setup during initial development.
**How to avoid:** Replace with explicit list: `["Content-Type", "X-API-Key", "Authorization"]`. This matches the headers the app actually uses.
**Warning signs:** Security audit tools flag wildcard headers as a medium finding.

### Pitfall 4: Rate Limiter State Leaks Between Test Modules
**What goes wrong:** The `TestRateLimiting` class enables the rate limiter for its tests, but the in-memory counter state from those tests persists. If another test module happens to run after and also enables the limiter, it may encounter pre-existing counter state.
**Why it happens:** slowapi uses an in-memory storage backend by default. The counters persist for the process lifetime.
**How to avoid:** Call `limiter.reset()` in the `rate_limited_client` fixture teardown (after yield). This clears all in-memory counters. Additionally, the main `client` fixture already disables the limiter, so normal tests are unaffected.
**Warning signs:** Intermittent 429 responses in tests that don't expect them. Test order changes cause previously passing tests to fail.

### Pitfall 5: Middleware Order Matters for Security Headers on Error Responses
**What goes wrong:** If security headers middleware is registered AFTER CORS middleware, then CORS rejection responses (403/400 from preflight failures) won't have security headers. Similarly, rate-limit 429 responses might lack headers.
**Why it happens:** FastAPI/Starlette middleware wraps in reverse registration order: last added = outermost = processes first.
**How to avoid:** Register `SecWeb` FIRST (before CORS, before rate limiter). This ensures SecWeb's middleware wraps outermost and adds headers to ALL responses including error responses from inner middleware.
**Warning signs:** Security header scan shows missing headers on certain response codes (403, 429).

### Pitfall 6: HSTS with preload on Localhost Breaks Development
**What goes wrong:** If HSTS with `preload` is sent on `localhost`, browsers may cache the HSTS policy and refuse HTTP connections to localhost for the max-age duration.
**Why it happens:** HSTS is supposed to be production-only (behind TLS), but the CONTEXT.md says security headers should be active in ALL environments.
**How to avoid:** The Caddyfile already handles HSTS at the proxy level. For the FastAPI-level HSTS header, either: (a) only enable HSTS when `ENVIRONMENT != "development"`, or (b) set a very short `max-age` (e.g., 60 seconds) in development. Recommendation: conditionally enable HSTS only in production/staging since Caddy already handles it.
**Warning signs:** Developer cannot access `http://localhost:8000` after visiting the local API with HSTS headers -- browser forces HTTPS redirect.

## Code Examples

Verified patterns from official sources and codebase inspection:

### Complete Security Headers Setup in main.py
```python
# Source: Secweb README + FastAPI middleware docs + codebase inspection
# Place BEFORE CORSMiddleware registration

import os
from Secweb import SecWeb
from starlette.middleware.base import BaseHTTPMiddleware

_env = os.environ.get("ENVIRONMENT", "development")

# --- Permissions-Policy (not available in Secweb stable) ---
class PermissionsPolicyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["Permissions-Policy"] = (
            "geolocation=(self), "
            "camera=(), "
            "microphone=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "accelerometer=()"
        )
        return response

# --- SecWeb: CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy ---
# Must be registered FIRST so it wraps outermost
_secweb_options = {
    'csp': {
        'default-src': ["'self'"],
        'script-src': ["'self'"],
        'style-src': ["'self'", "'unsafe-inline'"],
        'img-src': [
            "'self'", "data:", "blob:",
            "https://*.tile.openstreetmap.org",
            "https://unpkg.com",
        ],
        'connect-src': [
            "'self'",
            "https://maps.googleapis.com",
        ],
        'font-src': ["'self'"],
        'frame-ancestors': ["'none'"],
    },
    'xframe': 'DENY',
    'referrer': ['strict-origin-when-cross-origin'],
    # xcto: on by default (nosniff)
    # hsts: conditional on environment
}

# Only add HSTS header at the app level if NOT behind Caddy,
# or for belt-and-suspenders. Caddy already sends HSTS.
if _env != "development":
    _secweb_options['hsts'] = {
        'max-age': 31536000,
        'includeSubDomains': True,
        'preload': True,
    }

SecWeb(app=app, Option=_secweb_options)
app.add_middleware(PermissionsPolicyMiddleware)
```

### Rate Limiter Test Isolation (conftest fixture)
```python
# Source: slowapi docs (Context7) + existing test_api.py pattern
# In tests/apps/kerala_delivery/api/test_api.py

@pytest.fixture
def rate_limited_client(self, mock_session):
    from apps.kerala_delivery.api.main import app, limiter
    async def override_get_session():
        yield mock_session
    limiter.enabled = True
    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)
    app.dependency_overrides.clear()
    # CRITICAL: reset counters to prevent state leaking to other test modules
    limiter.reset()
    limiter.enabled = False
```

### Gating /redoc in Production
```python
# Source: FastAPI constructor docs + existing codebase pattern
_env_name = os.environ.get("ENVIRONMENT", "development")
_docs_url = "/docs" if _env_name != "production" else None
_redoc_url = "/redoc" if _env_name != "production" else None
_openapi_url = "/openapi.json" if _env_name != "production" else None

app = FastAPI(
    title="Kerala LPG Delivery Route Optimizer",
    # ... existing params ...
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)
```

### Testing Security Headers
```python
# Source: FastAPI TestClient pattern + codebase convention
def test_security_headers_present(self, client):
    """All responses should include security headers."""
    resp = client.get("/health")
    assert resp.status_code == 200
    # Secweb headers
    assert "content-security-policy" in resp.headers
    assert "x-frame-options" in resp.headers
    assert resp.headers["x-frame-options"] == "DENY"
    assert "x-content-type-options" in resp.headers
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert "referrer-policy" in resp.headers
    # Custom middleware header
    assert "permissions-policy" in resp.headers
    assert "geolocation=(self)" in resp.headers["permissions-policy"]

def test_cors_rejects_unlisted_origin(self, client):
    """A request from an unlisted origin should not receive CORS headers."""
    resp = client.get(
        "/health",
        headers={"Origin": "https://evil.example.com"}
    )
    assert "access-control-allow-origin" not in resp.headers
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| python-jose for JWT | PyJWT 2.x | FastAPI docs updated May 2024 | python-jose last release 2021, deprecated. NOT relevant here -- neither is installed. |
| passlib for password hashing | pwdlib or direct bcrypt | passlib broken on Python 3.13+ | NOT relevant here -- neither is installed. App uses API key auth, not password hashing. |
| Secweb individual middleware classes | SecWeb all-in-one class | Secweb 1.x+ | Single call configures all headers; individual classes still available for fine-tuning |
| Manual security headers in Starlette | Secweb / secure.py libraries | 2023+ | Libraries reduce boilerplate and follow OWASP standards |
| CORS allow_origins=["*"] | Explicit origin whitelist | OWASP guidance, always | Wildcard CORS is never appropriate for APIs with authentication |

**Deprecated/outdated:**
- python-jose: abandoned since 2021, broken on Python 3.10+. **Not installed in this project.**
- passlib: broken on Python 3.13+. **Not installed in this project.**
- Secweb PermissionsPolicy: exists only in development branch, not in stable 1.30.10. Custom middleware required.

## Open Questions

1. **CSP connect-src for Google Maps Navigation Links**
   - What we know: The driver PWA generates Google Maps navigation links (`maps.google.com`). The CONTEXT.md mentions Google Maps APIs in the CSP allowlist.
   - What's unclear: Whether `connect-src` needs `https://maps.googleapis.com` or whether these are just `<a href>` navigation links (which are NOT governed by CSP `connect-src`). Regular link clicks to external URLs are NOT blocked by CSP -- only `fetch()`, `XMLHttpRequest`, and WebSocket connections are.
   - Recommendation: Add `https://maps.googleapis.com` to `connect-src` only if the app makes API calls to Google Maps from the browser. If it only generates `<a>` links for navigation, no CSP addition is needed for Google Maps. The geocoding calls happen server-side (Python), not in the browser.

2. **Secweb Default Headers That May Conflict with Caddy**
   - What we know: Caddy already sets HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, and CSP headers. Secweb will also set them at the app level.
   - What's unclear: Whether duplicate headers cause issues. HTTP spec says multiple values for the same header name are concatenated with commas, but for CSP this creates an intersection policy (most restrictive wins). For X-Frame-Options, behavior with duplicates is browser-dependent.
   - Recommendation: This is belt-and-suspenders and is fine. The app-level headers ensure correct behavior during development (no Caddy). In production, Caddy headers and app headers will both be present. For CSP specifically, both policies will be enforced (intersection), which is correct as long as both allow the same sources. Keep the CSP configuration identical in both Caddyfile and SecWeb.

3. **HSTS in Development Environment**
   - What we know: CONTEXT.md says "security headers applied in ALL environments" but HSTS in development can lock browsers into HTTPS for localhost.
   - What's unclear: Whether the user intends HSTS to be active in development too.
   - Recommendation: Enable all headers EXCEPT HSTS in development. HSTS is the one header that can actively break the development experience. Caddy handles HSTS in production. The other headers (CSP, X-Frame-Options, etc.) are safe in all environments.

## Sources

### Primary (HIGH confidence)
- `/laurents/slowapi` (Context7) - Rate limiter reset, enable/disable, initialization patterns
- `/fastapi/fastapi` (Context7) - CORS middleware configuration, docs URL gating, middleware patterns
- Secweb 1.30.10 installed and inspected locally - Confirmed available modules, confirmed PermissionsPolicy NOT in stable release
- Codebase inspection: `apps/kerala_delivery/api/main.py` (lines 143-206) - Current CORS, rate limiter, docs gating
- Codebase inspection: `tests/apps/kerala_delivery/api/test_api.py` (lines 1610-1662) - Current rate limiter test pattern
- Codebase inspection: `infra/caddy/Caddyfile` (lines 30-66) - Existing security headers at proxy level

### Secondary (MEDIUM confidence)
- [Secweb GitHub README](https://github.com/tmotagam/Secweb) - Configuration examples, middleware list, verified via local install
- [FastAPI CORS tutorial](https://fastapi.tiangolo.com/tutorial/cors/) - CORSMiddleware parameters, preflight handling
- [FastAPI discussion #9587](https://github.com/fastapi/fastapi/discussions/9587) - python-jose deprecation status
- [FastAPI discussion #11773](https://github.com/fastapi/fastapi/discussions/11773) - passlib deprecation status

### Tertiary (LOW confidence)
- None -- all findings verified via primary or secondary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Secweb installed and inspected locally, slowapi verified via Context7, all libraries confirmed compatible
- Architecture: HIGH - Middleware ordering verified against FastAPI/Starlette middleware wrapping semantics, codebase patterns inspected
- Pitfalls: HIGH - CSP tile breakage documented in CONTEXT.md, /redoc gap confirmed via code inspection, HSTS localhost issue well-documented
- Code examples: HIGH - All patterns based on verified library APIs and existing codebase conventions

**Research date:** 2026-03-01
**Valid until:** 2026-03-31 (stable domain, libraries mature)
