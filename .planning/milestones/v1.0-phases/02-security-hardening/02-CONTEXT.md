# Phase 2: Security Hardening - Context

**Gathered:** 2026-03-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Lock down the FastAPI API for production: emit correct security headers on all responses, restrict CORS to whitelisted origins, gate API docs in production, validate file uploads before processing, replace deprecated auth libraries if present, and isolate rate limiter state in tests. The full 351-test suite must pass with no cross-test rate limiter bleed.

</domain>

<decisions>
## Implementation Decisions

### Rate Limit Policy
- Claude's discretion on specific per-endpoint numbers, guided by fleet scale (13 vehicles, ~1 office user)
- Upload endpoint (`POST /api/upload-orders`): strict limit — expensive operation triggering geocoding API calls
- Telemetry endpoint (`POST /api/telemetry`): generous limit per API key — 13 vehicles sending GPS pings, must not throttle legitimate driver updates
- Read endpoints (`GET /api/routes`, `GET /api/vehicles`): light limits to prevent runaway polling while allowing normal dashboard 10-second refresh cycles
- Rate limit exceeded response: HTTP 429 with `Retry-After` header (standard behavior, slowapi supports this)
- Rate limiting disabled in tests via `RATE_LIMIT_ENABLED=false` in pytest conftest to prevent cross-test bleed (SEC-06)

### CSP & Security Headers
- Content Security Policy: strict with explicit allowlist — `default-src 'self'` plus known sources only (tile.openstreetmap.org, unpkg.com for Leaflet, Google Maps APIs)
- CSP must be tested against running app to ensure Leaflet tiles and Google Maps navigation links still work
- HSTS: Claude's discretion based on deployment setup (enable if behind TLS)
- Permissions-Policy: restrict all browser features except geolocation (driver PWA needs it for GPS pings); disable camera, microphone, payment, etc.
- X-Frame-Options: DENY (API should never be iframed)
- X-Content-Type-Options: nosniff
- Referrer-Policy: strict-origin-when-cross-origin
- CSP violation reporting: Claude's discretion on report-only vs enforcing rollout strategy
- Security headers applied in ALL environments (dev, staging, production) — catches CSP breakage early during development

### File Upload Guardrails
- Max file size: Claude's discretion (guided by typical CDCMS exports being <50 KB for 200 rows)
- Allowed file types: CSV and Excel only (.csv, .xlsx, .xls) — matches the two formats the importer supports (CsvImporter + openpyxl)
- Row count limit: Claude's discretion (fleet is 13 vehicles, typical batch is 50-100 orders)
- Rejection errors: specific messages showing what failed and what the limits are (e.g., "File too large (15 MB). Maximum: 10 MB." or "Unsupported file type (.pdf). Accepted: .csv, .xlsx, .xls")
- Validation must happen BEFORE any processing (parse, geocode, optimize) begins

### Environment Gating
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
- Whether python-jose/passlib replacement is needed (currently neither is installed — SEC-05 may be a verification-only step)

</decisions>

<specifics>
## Specific Ideas

- Security headers scan should achieve A-grade on securityheaders.com (per success criteria)
- CSP must explicitly allow Leaflet tile servers and unpkg.com — a misconfigured CSP silently breaks maps with no visible error
- Rate limiter isolation in tests is critical — the 351-test suite currently has potential cross-test bleed from shared slowapi state

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `slowapi.Limiter` already initialized in `main.py` with `RATE_LIMIT_ENABLED` env var support — just needs `@limiter.limit()` decorators on endpoints
- `CORSMiddleware` already configured with `CORS_ALLOWED_ORIGINS` env var parsing — needs tightening, not rewriting
- `verify_api_key()` and `verify_read_key()` dependency injection pattern — rate limits can key off these for per-key limits
- `ENVIRONMENT` env var pattern already in use — extend for docs gating

### Established Patterns
- Middleware added in `main.py` lifespan/startup — Secweb fits this pattern
- Environment variables loaded via `os.environ.get()` with sensible defaults
- HTTP errors use `HTTPException(status_code, detail)` — upload validation errors should follow this
- Pydantic validation on request bodies — file validation is a new pattern (pre-Pydantic)

### Integration Points
- `main.py` middleware stack: Secweb headers should be outermost middleware (before CORS, before rate limiter)
- `POST /api/upload-orders`: add file validation before CSV parsing begins
- `conftest.py`: add rate limiter reset fixture for test isolation
- `requirements.txt`: add Secweb 1.11.0; potentially add PyJWT 2.11.0 and pwdlib 0.3.0 (verify if needed first)

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-security-hardening*
*Context gathered: 2026-03-01*
