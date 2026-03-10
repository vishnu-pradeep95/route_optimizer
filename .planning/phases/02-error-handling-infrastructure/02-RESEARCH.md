# Phase 02: Error Handling Infrastructure - Research

**Researched:** 2026-03-10
**Domain:** FastAPI structured error handling, request tracing, retry logic, frontend error UI
**Confidence:** HIGH

## Summary

This phase replaces ~30 ad-hoc `HTTPException(detail="...")` calls across `apps/kerala_delivery/api/main.py` (2245 lines) with a consistent `ErrorResponse` Pydantic model, adds request ID tracing via middleware, implements startup health gates for PostgreSQL/OSRM/VROOM, adds retry logic for transient external service failures, and builds frontend error differentiation in the React/TypeScript dashboard.

The codebase already has strong foundations: DaisyUI alert components (`tw:alert-error`, `tw:alert-warning`, etc.), the "Problem -- fix action" error message pattern established in v1.3, and a `GEOCODING_REASON_MAP` dict that maps API status codes to user-friendly messages. The existing `lifespan()` context manager is the right place for startup health gates. The `apiFetch()`/`apiWrite()` helpers in `dashboard/src/lib/api.ts` are the single integration point for error response parsing.

**Primary recommendation:** Build the ErrorResponse model and request ID middleware first (API-side), then migrate HTTPExceptions endpoint by endpoint, then wire up frontend error differentiation, and finally add retry logic and startup health gates.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Tiered error responses**: Both `user_message` (plain-English "Problem -- fix action") and `technical_message`. Dashboard shows `user_message` by default, with "Show details" toggle revealing error_code, request_id, timestamp
- **Namespaced error codes**: Grouped by subsystem -- `GEOCODING_FAILED`, `UPLOAD_INVALID_FORMAT`, `OPTIMIZER_TIMEOUT`, `AUTH_KEY_MISSING`, etc. Maps to ERROR-MAP.md
- **Partial success uses HTTP 200 with warnings**: Not 207. Response includes `success: true`, `imported` count, `total` count, and `warnings[]` array
- **Help URL field**: Each error code maps to a section in docs/ files (ERROR-MAP.md, GOOGLE-MAPS.md). Dashboard renders as clickable help link
- **CSV upload errors**: Inline table showing failed rows with row number, field, and reason. Include "Download Error Report" and "Upload Fixed CSV" actions
- **Network/server errors**: Contextual banner at top of affected section. Auto-dismisses when connection restores. Includes [Retry] button
- **Color-coded by severity**: Red (failures), amber (warnings), green (success), blue (info/retry). Matches v1.1 status badge colors
- **Short UUID request ID**: First 8 chars of UUID (e.g., "abc12def"). Visible in error details only, not on success responses
- **Every log line includes request ID**: Middleware injects request_id into logging context. Format: `[abc12def] INFO message`
- **Startup health gates**: API must check PostgreSQL, OSRM, VROOM on startup. Block until healthy (60s timeout). If timeout, start anyway but return 503 with specific service name. NON-NEGOTIABLE
- **Per-service health endpoint**: `GET /health` returns per-service status (postgresql, osrm, vroom, google_api) with overall status (healthy/degraded/unhealthy) and uptime
- **Startup sequence**: PostgreSQL first, then OSRM, then VROOM
- **Scope**: API + Dashboard only -- Driver PWA out of scope
- **HARD REQUIREMENT**: Every error UI element must have Playwright E2E test coverage. All spacing and alignment must be correct

### Claude's Discretion
- Detail toggle implementation: DaisyUI collapse vs modal
- Which services get retry logic and retry counts/backoff strategy
- Exact ErrorResponse Pydantic model field names
- Compression/batching of warning arrays for large imports

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.129.1 | API framework (already installed) | Custom exception handlers, middleware support |
| Pydantic | 2.12.5 | ErrorResponse model (already installed) | Native FastAPI integration, `model_dump()` |
| tenacity | 9.1.4 | Retry with exponential backoff (NEW) | De facto Python retry library, async support, works with httpx |
| httpx | 0.28.1 | HTTP client for OSRM/VROOM/Google (already installed) | Async support, timeout handling |
| DaisyUI | 5.5.19 | Error UI components (already installed) | `tw:alert-*`, `tw:collapse`, `tw:modal` components |
| Tailwind CSS | 4.2.1 | Styling (already installed) | `tw:` prefix convention established |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| uuid (stdlib) | - | Request ID generation | `uuid.uuid4().hex[:8]` for short IDs |
| logging (stdlib) | - | Structured logging with request context | LogRecord filter for request_id injection |
| asyncio (stdlib) | - | Startup health gate timeouts | `asyncio.wait_for()` with 60s timeout |
| contextvars (stdlib) | - | Request-scoped context propagation | Thread-safe request_id storage across async calls |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tenacity | Manual retry loops | Tenacity handles jitter, backoff, async natively -- manual loops miss edge cases |
| contextvars | Starlette Request.state | contextvars works across async boundaries without passing request everywhere |
| DaisyUI collapse | DaisyUI modal for details | Collapse keeps context visible (user sees error + details together). Modal interrupts. Recommend collapse |

**Installation:**
```bash
pip install tenacity==9.1.4
```

Add `tenacity==9.1.4` to `requirements.txt` after `starlette==0.52.1`.

## Architecture Patterns

### Recommended Project Structure
```
apps/kerala_delivery/api/
  main.py                    # Existing -- endpoints migrate to use error_response()
  errors.py                  # NEW -- ErrorResponse model, error codes enum, helper functions
  middleware.py               # NEW -- RequestIDMiddleware, error handler registration
  health.py                  # NEW -- startup health gates, enhanced /health endpoint
  retry.py                   # NEW -- tenacity retry wrappers for external services

apps/kerala_delivery/dashboard/src/
  lib/api.ts                 # MODIFY -- parse ErrorResponse, extract user_message
  lib/errors.ts              # NEW -- error types, error code → help URL mapping
  components/ErrorBanner.tsx  # NEW -- contextual error banner with auto-dismiss + retry
  components/ErrorTable.tsx   # NEW -- inline error table for CSV upload failures
  components/ErrorDetail.tsx  # NEW -- "Show details" collapse with request_id, error_code
  pages/UploadRoutes.tsx     # MODIFY -- integrate ErrorTable, download/re-upload actions
```

### Pattern 1: ErrorResponse Pydantic Model
**What:** A single Pydantic model that ALL error responses conform to, replacing ad-hoc `{"detail": "..."}` dicts.
**When to use:** Every HTTPException replacement, every error JSON response.
**Example:**
```python
# apps/kerala_delivery/api/errors.py
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from enum import StrEnum

class ErrorCode(StrEnum):
    """Namespaced error codes grouped by subsystem."""
    # Upload
    UPLOAD_INVALID_FORMAT = "UPLOAD_INVALID_FORMAT"
    UPLOAD_FILE_TOO_LARGE = "UPLOAD_FILE_TOO_LARGE"
    UPLOAD_EMPTY_FILE = "UPLOAD_EMPTY_FILE"
    UPLOAD_NO_VALID_ORDERS = "UPLOAD_NO_VALID_ORDERS"
    UPLOAD_NO_ALLOCATED = "UPLOAD_NO_ALLOCATED"
    # Geocoding
    GEOCODING_FAILED = "GEOCODING_FAILED"
    GEOCODING_NOT_CONFIGURED = "GEOCODING_NOT_CONFIGURED"
    GEOCODING_QUOTA_EXCEEDED = "GEOCODING_QUOTA_EXCEEDED"
    # Optimizer
    OPTIMIZER_TIMEOUT = "OPTIMIZER_TIMEOUT"
    OPTIMIZER_UNAVAILABLE = "OPTIMIZER_UNAVAILABLE"
    OPTIMIZER_ERROR = "OPTIMIZER_ERROR"
    # Fleet
    FLEET_NO_VEHICLES = "FLEET_NO_VEHICLES"
    FLEET_VEHICLE_NOT_FOUND = "FLEET_VEHICLE_NOT_FOUND"
    FLEET_VEHICLE_EXISTS = "FLEET_VEHICLE_EXISTS"
    FLEET_NO_FIELDS = "FLEET_NO_FIELDS"
    # Route
    ROUTE_NOT_FOUND = "ROUTE_NOT_FOUND"
    ROUTE_NO_RUNS = "ROUTE_NO_RUNS"
    ROUTE_STOP_NOT_FOUND = "ROUTE_STOP_NOT_FOUND"
    # Auth
    AUTH_KEY_MISSING = "AUTH_KEY_MISSING"
    AUTH_KEY_INVALID = "AUTH_KEY_INVALID"
    # Service
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    SERVICE_DEGRADED = "SERVICE_DEGRADED"
    # General
    INTERNAL_ERROR = "INTERNAL_ERROR"
    INVALID_REQUEST = "INVALID_REQUEST"

# Error code -> docs/ URL path mapping
ERROR_HELP_URLS: dict[str, str] = {
    ErrorCode.UPLOAD_INVALID_FORMAT: "/docs/CSV_FORMAT.md#file-level-errors",
    ErrorCode.GEOCODING_NOT_CONFIGURED: "/docs/GOOGLE-MAPS.md#api-key-setup",
    ErrorCode.GEOCODING_QUOTA_EXCEEDED: "/docs/GOOGLE-MAPS.md#quota",
    ErrorCode.OPTIMIZER_UNAVAILABLE: "/docs/SETUP.md#osrm-vroom",
    # ... map all codes
}

class ErrorResponse(BaseModel):
    """Structured error response for all API errors.

    Tiered by role:
    - user_message: plain-English "Problem -- fix action" for office staff
    - technical_message: developer-level detail for debugging
    - error_code: namespaced code for frontend error handling
    - request_id: short UUID for support correlation
    """
    success: bool = Field(default=False)
    error_code: str = Field(..., description="Namespaced error code (e.g., UPLOAD_INVALID_FORMAT)")
    user_message: str = Field(..., description="Plain-English error for office staff")
    technical_message: str = Field(default="", description="Developer-level detail")
    request_id: str = Field(default="", description="8-char request ID for support")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    help_url: str = Field(default="", description="Link to relevant docs section")

def error_response(
    status_code: int,
    error_code: ErrorCode,
    user_message: str,
    technical_message: str = "",
    request_id: str = "",
) -> JSONResponse:
    """Create a structured error JSONResponse."""
    body = ErrorResponse(
        error_code=error_code,
        user_message=user_message,
        technical_message=technical_message,
        request_id=request_id,
        help_url=ERROR_HELP_URLS.get(error_code, ""),
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
    )
```

### Pattern 2: Request ID Middleware
**What:** Starlette BaseHTTPMiddleware that generates a short UUID per request, stores it in contextvars, and adds it to response headers.
**When to use:** Every single request to the API.
**Example:**
```python
# apps/kerala_delivery/api/middleware.py
import uuid
import logging
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware

request_id_var: ContextVar[str] = ContextVar("request_id", default="--------")

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        req_id = uuid.uuid4().hex[:8]
        request_id_var.set(req_id)
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response

class RequestIDFilter(logging.Filter):
    """Injects request_id into every log record."""
    def filter(self, record):
        record.request_id = request_id_var.get("--------")
        return True

# Configure logging format: [abc12def] INFO message
LOG_FORMAT = "[%(request_id)s] %(levelname)-5s %(name)s: %(message)s"
```

### Pattern 3: Startup Health Gates
**What:** In the FastAPI `lifespan()`, check PostgreSQL, OSRM, VROOM connectivity with a 60-second timeout. Block until healthy or timeout.
**When to use:** On application startup, before accepting any requests.
**Example:**
```python
# apps/kerala_delivery/api/health.py
import asyncio
import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

async def check_postgresql(engine) -> tuple[bool, str]:
    """Check PostgreSQL connectivity."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True, "connected"
    except Exception as e:
        return False, str(e)

async def check_osrm(osrm_url: str) -> tuple[bool, str]:
    """Check OSRM availability."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{osrm_url}/nearest/v1/driving/0,0")
            return resp.status_code in (200, 400), "available"
    except Exception as e:
        return False, str(e)

async def check_vroom(vroom_url: str) -> tuple[bool, str]:
    """Check VROOM availability."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{vroom_url}/health")
            return resp.status_code == 200, "available"
    except Exception as e:
        return False, str(e)

async def wait_for_services(engine, osrm_url: str, vroom_url: str, timeout: float = 60.0):
    """Block until all services healthy or timeout.

    Sequence: PostgreSQL first, then OSRM, then VROOM.
    Returns dict of service -> (healthy, message).
    """
    results = {}
    deadline = asyncio.get_event_loop().time() + timeout

    for name, check_fn in [
        ("postgresql", lambda: check_postgresql(engine)),
        ("osrm", lambda: check_osrm(osrm_url)),
        ("vroom", lambda: check_vroom(vroom_url)),
    ]:
        while asyncio.get_event_loop().time() < deadline:
            healthy, msg = await check_fn()
            if healthy:
                results[name] = (True, msg)
                break
            await asyncio.sleep(2)
        else:
            results[name] = (False, f"timeout after {timeout}s")

    return results
```

### Pattern 4: Retry with Tenacity
**What:** Wrap transient-failure-prone HTTP calls with tenacity retry decorators.
**When to use:** OSRM, VROOM, and Google Geocoding API calls that can fail transiently.
**Example:**
```python
# apps/kerala_delivery/api/retry.py
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import httpx

# Retry on connection errors and timeouts (transient), NOT on HTTP 4xx (permanent)
TRANSIENT_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.TimeoutException,
    httpx.ConnectTimeout,
)

geocoding_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(TRANSIENT_EXCEPTIONS),
    reraise=True,
)

optimizer_retry = retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=2, min=2, max=15),
    retry=retry_if_exception_type(TRANSIENT_EXCEPTIONS),
    reraise=True,
)
```

### Pattern 5: Frontend Error Differentiation
**What:** Parse the structured ErrorResponse in the API client, dispatch to appropriate UI component by error type.
**When to use:** Every API call in the dashboard.
**Example:**
```typescript
// dashboard/src/lib/errors.ts
export interface ApiError {
  success: false;
  error_code: string;
  user_message: string;
  technical_message: string;
  request_id: string;
  timestamp: string;
  help_url: string;
}

export type ErrorSeverity = "error" | "warning" | "info";

export function classifyError(error: ApiError): ErrorSeverity {
  if (error.error_code.startsWith("UPLOAD_")) return "error";
  if (error.error_code.includes("TIMEOUT")) return "warning";
  if (error.error_code.includes("UNAVAILABLE")) return "warning";
  return "error";
}

export function isApiError(obj: unknown): obj is ApiError {
  return typeof obj === "object" && obj !== null && "error_code" in obj && "user_message" in obj;
}

// Map error codes to docs URLs
export const ERROR_HELP_URLS: Record<string, string> = {
  UPLOAD_INVALID_FORMAT: "/docs/CSV_FORMAT.md#file-level-errors",
  GEOCODING_NOT_CONFIGURED: "/docs/GOOGLE-MAPS.md#api-key-setup",
  // ...
};
```

### Anti-Patterns to Avoid
- **Catching Exception broadly and returning 500:** Always catch specific exception types and map to specific error codes. The existing `except Exception as e: raise HTTPException(500, ...)` should be the LAST resort, not the pattern.
- **Returning sensitive info in error details:** Never include stack traces, database connection strings, or API keys in `technical_message`. Use `type(e).__name__` only.
- **Retry on 4xx errors:** Never retry client errors (400, 401, 404). Only retry on connection/timeout errors and 5xx from external services.
- **Mixing old and new error formats:** During migration, a global exception handler should catch any remaining `HTTPException` and wrap it in `ErrorResponse` format for consistency.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Retry logic | Custom while loops with sleep | `tenacity` decorators | Handles jitter, backoff, max attempts, exception filtering, async support |
| Request ID propagation | Thread-local variables | `contextvars.ContextVar` | Thread-safe in async context, works across await boundaries |
| Error response serialization | Manual dict construction | Pydantic `ErrorResponse.model_dump()` | Type-safe, validates fields, consistent JSON serialization |
| Health check polling | Custom asyncio loops | `asyncio.wait_for()` with deadline | Clean timeout handling, cancellation support |
| Alert UI components | Custom styled divs | DaisyUI `tw:alert-error`, `tw:alert-warning`, etc. | Consistent theming, accessible, already in the design system |
| Collapse/expand UI | Custom state + CSS | DaisyUI `tw:collapse` component | Accessible, animated, already used for ImportSummary |

**Key insight:** The codebase already uses DaisyUI extensively (collapse for import failures, alerts for warnings, badges for status). The error UI should extend these patterns, not introduce new component libraries.

## Common Pitfalls

### Pitfall 1: Middleware Ordering
**What goes wrong:** Request ID middleware runs AFTER security middleware, so error responses from auth/license checks don't include request_id.
**Why it happens:** FastAPI/Starlette processes middleware in reverse registration order (last added = outermost).
**How to avoid:** Register RequestIDMiddleware LAST (after all other middleware), so it's the outermost layer and runs first on every request.
**Warning signs:** Error responses missing `request_id` field on auth failures.

### Pitfall 2: HTTPException Handler Conflicts
**What goes wrong:** FastAPI has a built-in handler for `HTTPException` that returns `{"detail": "..."}`. Adding a custom handler can conflict or miss cases.
**Why it happens:** FastAPI registers its own `HTTPException` handler during setup. Custom handlers must explicitly override it.
**How to avoid:** Use `@app.exception_handler(HTTPException)` to wrap ALL HTTPExceptions in ErrorResponse format. This catches both new `error_response()` calls and any remaining old-style `raise HTTPException(...)`.
**Warning signs:** Some errors return `{"detail": "..."}` and others return `ErrorResponse` format.

### Pitfall 3: Auto-Dismiss Banner Race Condition
**What goes wrong:** Network error banner auto-dismisses when connection restores, but a new error arrives simultaneously, creating a flash.
**Why it happens:** The health poll and the data fetch run independently.
**How to avoid:** Use a debounce: only auto-dismiss after the connection has been stable for 5+ seconds. Don't dismiss on single successful health check.
**Warning signs:** Error banner flickers on intermittent connectivity.

### Pitfall 4: contextvars Not Set in Lifespan
**What goes wrong:** Startup logs don't have request_id because lifespan runs outside request context.
**Why it happens:** `ContextVar` is request-scoped, and lifespan is application-scoped.
**How to avoid:** Use a default value `"startup-"` for logs during lifespan, and only use the request_id in request-handling code.
**Warning signs:** Startup log lines show `[--------]` instead of a meaningful prefix.

### Pitfall 5: Retry Amplifying Failures
**What goes wrong:** Retrying geocoding API calls when the API key is invalid (REQUEST_DENIED) wastes time and may trigger rate limits.
**Why it happens:** Retry is configured on all exceptions, not just transient ones.
**How to avoid:** Only retry on `httpx.ConnectError`, `httpx.TimeoutException`, `httpx.ConnectTimeout`. Never retry on HTTP 400/401/403 responses.
**Warning signs:** Upload takes 3x longer to fail when Google API key is bad.

### Pitfall 6: Missing Tailwind tw: Prefix
**What goes wrong:** New error UI components use `alert-error` instead of `tw:alert-error`, CSS classes don't apply.
**Why it happens:** Developer muscle memory from vanilla Tailwind/DaisyUI.
**How to avoid:** ALL Tailwind/DaisyUI classes must use the `tw:` colon prefix. CSS selectors escape the colon: `.tw\:alert-error`.
**Warning signs:** Components render with no styling, especially DaisyUI components.

## Code Examples

### Example 1: Migrating an HTTPException to ErrorResponse
```python
# BEFORE (current code, line 740):
raise HTTPException(
    status_code=400,
    detail=f"Unsupported file type ({ext or 'none'}). Accepted: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
)

# AFTER:
from apps.kerala_delivery.api.errors import error_response, ErrorCode
from apps.kerala_delivery.api.middleware import request_id_var

return error_response(
    status_code=400,
    error_code=ErrorCode.UPLOAD_INVALID_FORMAT,
    user_message=f"Unsupported file type ({ext or 'none'}) -- use .csv, .xlsx, or .xls",
    technical_message=f"Expected one of {sorted(ALLOWED_EXTENSIONS)}, got '{ext}'",
    request_id=request_id_var.get(""),
)
```

### Example 2: Global HTTPException Handler (catch-all for migration period)
```python
# apps/kerala_delivery/api/middleware.py
from fastapi import Request
from fastapi.exceptions import HTTPException
from fastapi.responses import JSONResponse

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Wrap all HTTPExceptions in ErrorResponse format for consistency."""
    req_id = getattr(request.state, "request_id", "")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error_code": "INTERNAL_ERROR" if exc.status_code >= 500 else "INVALID_REQUEST",
            "user_message": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            "technical_message": "",
            "request_id": req_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "help_url": "",
        },
    )
```

### Example 3: Enhanced Health Endpoint
```python
@app.get("/health")
async def health_check():
    """Enhanced health check with per-service status."""
    service_health = getattr(app.state, "service_health", {})
    services = {
        "postgresql": service_health.get("postgresql", {"status": "unknown"}),
        "osrm": service_health.get("osrm", {"status": "unknown"}),
        "vroom": service_health.get("vroom", {"status": "unknown"}),
        "google_api": {"status": "configured" if _get_geocoder() else "not_configured"},
    }
    all_healthy = all(s.get("status") in ("connected", "available", "configured", "not_configured")
                      for s in services.values())
    any_unhealthy = any(s.get("status") in ("unavailable", "timeout", "error")
                        for s in services.values())
    overall = "healthy" if all_healthy else ("unhealthy" if any_unhealthy else "degraded")

    return {
        "status": overall,
        "service": "kerala-lpg-optimizer",
        "version": app.version,
        "uptime_seconds": (datetime.now(timezone.utc) - app.state.started_at).total_seconds(),
        "services": services,
    }
```

### Example 4: Frontend ErrorBanner Component
```tsx
// dashboard/src/components/ErrorBanner.tsx
import { useState, useEffect } from "react";
import { AlertTriangle, RefreshCw, ChevronDown, ExternalLink } from "lucide-react";
import type { ApiError } from "../lib/errors";

interface ErrorBannerProps {
  error: ApiError;
  onRetry?: () => void;
  onDismiss?: () => void;
  autoRecover?: boolean; // auto-dismiss when connection restores
}

export function ErrorBanner({ error, onRetry, onDismiss, autoRecover }: ErrorBannerProps) {
  const [showDetails, setShowDetails] = useState(false);
  const severity = error.error_code.includes("TIMEOUT") ? "warning" : "error";
  const alertClass = severity === "warning" ? "tw:alert-warning" : "tw:alert-error";

  return (
    <div role="alert" className={`tw:alert ${alertClass} tw:mb-4`}>
      <AlertTriangle size={20} className="tw:shrink-0" />
      <div className="tw:flex-1">
        <p className="tw:font-medium">{error.user_message}</p>
        {error.help_url && (
          <a href={error.help_url} target="_blank" rel="noopener noreferrer"
             className="tw:text-sm tw:underline tw:flex tw:items-center tw:gap-1 tw:mt-1">
            Help <ExternalLink size={12} />
          </a>
        )}
        {/* "Show details" toggle -- DaisyUI collapse */}
        <div className="tw:collapse tw:mt-2">
          <input type="checkbox" checked={showDetails}
                 onChange={() => setShowDetails(!showDetails)} />
          <div className="tw:collapse-title tw:text-xs tw:p-0 tw:min-h-0">
            <button onClick={() => setShowDetails(!showDetails)}
                    className="tw:text-xs tw:opacity-70 tw:flex tw:items-center tw:gap-1">
              Show details <ChevronDown size={12} />
            </button>
          </div>
          <div className="tw:collapse-content tw:text-xs tw:p-0">
            <div className="tw:mt-1 tw:space-y-1 tw:opacity-70">
              <p>Error: {error.error_code}</p>
              <p>Request ID: {error.request_id}</p>
              <p>Time: {new Date(error.timestamp).toLocaleTimeString()}</p>
              {error.technical_message && <p>Detail: {error.technical_message}</p>}
            </div>
          </div>
        </div>
      </div>
      {onRetry && (
        <button onClick={onRetry} className="tw:btn tw:btn-sm tw:btn-ghost">
          <RefreshCw size={14} /> Retry
        </button>
      )}
    </div>
  );
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `raise HTTPException(400, detail="...")` | Structured `ErrorResponse` with error codes | FastAPI 0.95+ (2023) | Frontend can programmatically handle errors by code |
| `on_event("startup")` | `lifespan()` context manager | FastAPI 0.95 (2023) | Cleaner resource management, already used in codebase |
| Thread-local for request context | `contextvars.ContextVar` | Python 3.7+ (2018) | Async-safe, works across `await` boundaries |
| Manual retry loops | `tenacity` decorators | tenacity 8.0+ (2022) | Jitter, backoff, exception filtering, async support |
| Pydantic v1 `.dict()` | Pydantic v2 `.model_dump()` | Pydantic 2.0 (2023) | Already used in codebase, faster serialization |

**Deprecated/outdated:**
- `@app.on_event("startup")` / `@app.on_event("shutdown")`: Deprecated in FastAPI 0.95+. Use `lifespan()` (already used).
- Pydantic v1 `class Config:`: Codebase already uses Pydantic v2 patterns.

## Open Questions

1. **Error code granularity for geocoding**
   - What we know: `GEOCODING_REASON_MAP` has 6 entries mapping Google API status to user messages
   - What's unclear: Should each Google status code get its own error code (GEOCODING_ZERO_RESULTS, GEOCODING_REQUEST_DENIED, etc.) or use one GEOCODING_FAILED with the reason in user_message?
   - Recommendation: Use a single `GEOCODING_FAILED` error code with the specific reason in `user_message`. The reason map already handles differentiation. Keep error codes coarse-grained for frontend routing.

2. **Warning array size for large imports**
   - What we know: A 100-row CSV with 50 warnings generates a large response payload
   - What's unclear: Should we cap warnings at some limit? Paginate?
   - Recommendation: Cap at 100 warnings with a `"... and N more"` note. Current daily volumes (40-50 orders) make this unlikely, but defensive.

3. **Health check frequency during runtime**
   - What we know: Startup checks with 60s timeout are defined. Dashboard polls `/health` every 30s.
   - What's unclear: Should the API periodically re-check service health in the background, or only check on demand?
   - Recommendation: Cache service health for 30 seconds, refresh lazily on `/health` calls. No background polling needed -- the 30s dashboard poll already provides sufficient freshness.

## Validation Architecture

> `workflow.nyquist_validation` not found in config.json -- treating as enabled.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `pytest.ini` (asyncio_mode = auto) |
| Quick run command | `pytest tests/apps/kerala_delivery/api/test_api.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ERR-01 | ErrorResponse model validates all fields | unit | `pytest tests/apps/kerala_delivery/api/test_errors.py -x` | -- Wave 0 |
| ERR-02 | Request ID middleware adds X-Request-ID header | integration | `pytest tests/apps/kerala_delivery/api/test_middleware.py -x` | -- Wave 0 |
| ERR-03 | All HTTPExceptions wrapped in ErrorResponse format | integration | `pytest tests/apps/kerala_delivery/api/test_api.py -x` | Partial (existing) |
| ERR-04 | Startup health gates check PostgreSQL, OSRM, VROOM | unit | `pytest tests/apps/kerala_delivery/api/test_health.py -x` | -- Wave 0 |
| ERR-05 | Enhanced /health returns per-service status | integration | `pytest tests/apps/kerala_delivery/api/test_api.py::test_health -x` | Partial (existing) |
| ERR-06 | Retry logic retries on transient failures only | unit | `pytest tests/apps/kerala_delivery/api/test_retry.py -x` | -- Wave 0 |
| ERR-07 | Frontend ErrorBanner renders and auto-dismisses | e2e | Playwright MCP | -- Wave 0 |
| ERR-08 | Frontend error detail toggle shows request_id | e2e | Playwright MCP | -- Wave 0 |
| ERR-09 | CSV upload error table shows failed rows | e2e | Playwright MCP | -- Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/apps/kerala_delivery/api/ -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green + Playwright MCP E2E pass before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/apps/kerala_delivery/api/test_errors.py` -- covers ERR-01 (ErrorResponse model)
- [ ] `tests/apps/kerala_delivery/api/test_middleware.py` -- covers ERR-02 (RequestIDMiddleware)
- [ ] `tests/apps/kerala_delivery/api/test_health.py` -- covers ERR-04 (startup health gates)
- [ ] `tests/apps/kerala_delivery/api/test_retry.py` -- covers ERR-06 (retry logic)

*(Existing `test_api.py` covers ERR-03 and ERR-05 partially -- will need updates)*

## Existing Code Inventory

### HTTPException Migration Targets (30 calls across main.py)
| Line | Status Code | Current Detail | Proposed Error Code |
|------|-------------|---------------|---------------------|
| 402 | 404 | "sw.js not found" | (internal, no migration needed) |
| 482 | 401 | "Invalid or missing API key..." | AUTH_KEY_INVALID |
| 740 | 400 | "Unsupported file type..." | UPLOAD_INVALID_FORMAT |
| 748 | 400 | "Unexpected content type..." | UPLOAD_INVALID_FORMAT |
| 764 | 413 | "File too large..." | UPLOAD_FILE_TOO_LARGE |
| 789 | 400 | "No 'Allocated-Printed' orders..." | UPLOAD_NO_ALLOCATED |
| 871 | 400 | "No valid orders found in file" | UPLOAD_NO_VALID_ORDERS |
| 1067 | 400 | "No active vehicles configured..." | FLEET_NO_VEHICLES |
| 1128 | 400 | ValueError pass-through | INVALID_REQUEST |
| 1132 | 503 | "Route optimizer is not ready..." | OPTIMIZER_UNAVAILABLE |
| 1142 | 503 | "Route optimizer timed out..." | OPTIMIZER_TIMEOUT |
| 1152 | 502 | "Route optimizer returned an error..." | OPTIMIZER_ERROR |
| 1161 | 500 | "An unexpected error occurred..." | INTERNAL_ERROR |
| 1196 | 404 | "No routes generated yet..." | ROUTE_NO_RUNS |
| 1269 | 404 | "No routes generated yet." | ROUTE_NO_RUNS |
| 1273 | 404 | "No route found for vehicle..." | ROUTE_NOT_FOUND |
| 1360 | 404 | "No routes generated yet." | ROUTE_NO_RUNS |
| 1365 | 404 | "Stop not found" | ROUTE_STOP_NOT_FOUND |
| 1375 | 404 | "Stop not found" | ROUTE_STOP_NOT_FOUND |
| 1392 | 404 | "Stop not found" | ROUTE_STOP_NOT_FOUND |
| 1449 | 404 | "No routes generated yet." | ROUTE_NO_RUNS |
| 1453 | 404 | "No route found for vehicle..." | ROUTE_NOT_FOUND |
| 1506 | 404 | "No routes generated yet..." | ROUTE_NO_RUNS |
| 1510 | 404 | "No routes found for the latest run." | ROUTE_NO_RUNS |
| 2074 | 404 | "Vehicle not found" | FLEET_VEHICLE_NOT_FOUND |
| 2093 | 409 | "Vehicle already exists" | FLEET_VEHICLE_EXISTS |
| 2141 | 400 | "No fields to update" | FLEET_NO_FIELDS |
| 2145 | 404 | "Vehicle not found" | FLEET_VEHICLE_NOT_FOUND |
| 2166 | 404 | "Vehicle not found" | FLEET_VEHICLE_NOT_FOUND |
| 2221 | 400 | "Invalid run_id format" | INVALID_REQUEST |
| 2225 | 404 | "Optimization run not found" | ROUTE_NO_RUNS |

### Dashboard Integration Points
| File | Current Error Handling | Needed Change |
|------|----------------------|---------------|
| `lib/api.ts` | Throws `new Error("API error N: body")` | Parse ErrorResponse JSON, throw typed `ApiError` |
| `pages/UploadRoutes.tsx` | `catch (err) { setErrorMessage(err.message) }` | Parse ApiError, show ErrorBanner with details |
| `pages/LiveMap.tsx` | `setError(string \| null)` | Replace with ApiError state, show ErrorBanner |
| `pages/FleetManagement.tsx` | Generic error handling | Contextual error banners |
| `pages/RunHistory.tsx` | Generic error handling | Contextual error banners |
| `App.tsx` | Health polling returns boolean | Enhanced health with per-service status |

### Existing DaisyUI Components Available
- `tw:alert tw:alert-error` -- red error alerts (in use)
- `tw:alert tw:alert-warning` -- amber warning alerts (in use)
- `tw:alert tw:alert-success` -- green success alerts (in use)
- `tw:alert tw:alert-info` -- blue info alerts (available, not yet used)
- `tw:collapse tw:collapse-arrow` -- expandable detail sections (in use for ImportSummary)
- `tw:badge` -- status badges (in use)
- `tw:btn tw:btn-sm` -- small buttons (in use)
- `tw:table tw:table-sm` -- compact tables (in use for failure rows)

## Sources

### Primary (HIGH confidence)
- FastAPI source code and docs: exception handling, middleware, lifespan -- [fastapi.tiangolo.com/tutorial/handling-errors](https://fastapi.tiangolo.com/tutorial/handling-errors/)
- Codebase analysis: `apps/kerala_delivery/api/main.py` (2245 lines, 30 HTTPException calls)
- Codebase analysis: `apps/kerala_delivery/dashboard/src/lib/api.ts` (345 lines)
- Codebase analysis: `apps/kerala_delivery/dashboard/src/pages/UploadRoutes.tsx` (775 lines)
- DaisyUI 5 docs: alert, collapse, badge components
- tenacity PyPI: v9.1.4, Python 3.10+ -- [pypi.org/project/tenacity](https://pypi.org/project/tenacity/)
- Python docs: contextvars -- async-safe context propagation

### Secondary (MEDIUM confidence)
- [FastAPI Error Handling Patterns | Better Stack](https://betterstack.com/community/guides/scaling-python/error-handling-fastapi/) -- structured error patterns
- [FastAPI Middleware Patterns 2026 | johal.in](https://johal.in/fastapi-middleware-patterns-custom-logging-metrics-and-error-handling-2026-2/) -- middleware ordering
- [Tenacity Retries: Exponential Backoff 2026 | johal.in](https://johal.in/tenacity-retries-exponential-backoff-decorators-2026/) -- tenacity patterns

### Tertiary (LOW confidence)
- None -- all findings verified against codebase or official docs

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in use except tenacity (well-established, PyPI verified)
- Architecture: HIGH -- patterns derived from existing codebase analysis + FastAPI official docs
- Pitfalls: HIGH -- identified from actual code patterns and common FastAPI middleware issues
- Migration scope: HIGH -- complete inventory of all 30 HTTPException calls with line numbers

**Research date:** 2026-03-10
**Valid until:** 2026-04-10 (stable -- no fast-moving dependencies)
