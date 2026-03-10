"""Request ID middleware and logging filter for the Kerala LPG API.

Provides:
- RequestIDMiddleware: generates a unique 8-char hex ID per request,
  stores it in a ContextVar, sets it on request.state, and adds
  X-Request-ID response header.
- RequestIDFilter: logging.Filter that injects request_id into every
  log record so all log lines include [request_id] prefix.
- request_id_var: ContextVar accessible from any module for reading
  the current request's ID.
- LOG_FORMAT: standard log format string with [request_id] prefix.

See: .planning/phases/02-error-handling-infrastructure/02-CONTEXT.md
"""

import logging
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


# ContextVar for request-scoped ID propagation.
# Default "--------" is used for startup/shutdown logs (no active request).
request_id_var: ContextVar[str] = ContextVar("request_id", default="--------")


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generate a unique request ID for every HTTP request.

    Must be registered LAST in middleware chain so it runs FIRST
    (Starlette processes middleware in reverse registration order).
    This ensures even auth/license error responses include request_id.

    The ID is:
    - Set in request_id_var ContextVar (accessible across async calls)
    - Set on request.state.request_id (accessible in endpoint handlers)
    - Added as X-Request-ID response header (visible to clients)
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = uuid.uuid4().hex[:8]
        request_id_var.set(req_id)
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        return response


class RequestIDFilter(logging.Filter):
    """Inject request_id into every log record from the ContextVar.

    Add this filter to any logger or handler to include the current
    request's ID in log output. Outside of a request context, the
    default "--------" is used.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("--------")  # type: ignore[attr-defined]
        return True


# Standard log format with [request_id] prefix for grep-based correlation.
# Example output: [abc12def] INFO  apps.kerala_delivery.api.main: Upload started
LOG_FORMAT = "[%(request_id)s] %(levelname)-5s %(name)s: %(message)s"
