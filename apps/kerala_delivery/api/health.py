"""Service health check functions and startup readiness gates.

Provides:
- Per-service health checks for PostgreSQL, OSRM, VROOM, Google API
- wait_for_services(): blocks startup until infrastructure is ready (60s timeout)
- Results stored in app.state.service_health for the /health endpoint

Health check sequence on startup (PostgreSQL -> OSRM -> VROOM):
PostgreSQL must be up first because it stores geocoding cache and routes.
OSRM must be up before VROOM because VROOM depends on OSRM for routing.
If any service times out, the API starts anyway in degraded mode.

See: .planning/phases/02-error-handling-infrastructure/02-CONTEXT.md
"""

import asyncio
import logging
import os

import httpx
from sqlalchemy import text

logger = logging.getLogger(__name__)


async def check_postgresql(engine) -> tuple[bool, str]:
    """Check if PostgreSQL is reachable via the async engine.

    Executes a simple SELECT 1 query to verify connectivity.
    Returns (True, 'connected') on success, (False, error_msg) on failure.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return (True, "connected")
    except Exception as e:
        return (False, str(e))


async def check_osrm(osrm_url: str) -> tuple[bool, str]:
    """Check if OSRM is reachable.

    Sends a nearest query with invalid coordinates (0,0). OSRM returns:
    - 200: service is up and has data loaded
    - 400: service is up but coords are invalid (still means OSRM is running)
    Both indicate the service is available.

    Returns (True, 'available') if reachable, (False, error_msg) if not.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{osrm_url}/nearest/v1/driving/0,0")
            if response.status_code in (200, 400):
                return (True, "available")
            return (False, f"unexpected status {response.status_code}")
    except Exception as e:
        return (False, str(e))


async def check_vroom(vroom_url: str) -> tuple[bool, str]:
    """Check if VROOM is reachable via its /health endpoint.

    Returns (True, 'available') if VROOM responds with 200,
    (False, error_msg) otherwise.
    """
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{vroom_url}/health")
            if response.status_code == 200:
                return (True, "available")
            return (False, f"unexpected status {response.status_code}")
    except Exception as e:
        return (False, str(e))


def check_google_api() -> tuple[str, str]:
    """Check if Google Maps API key is configured.

    This is a configuration check, not a connectivity check -- we don't
    want to consume a geocoding API call just for a health check.

    Returns ('configured', '') if key is set and non-empty,
    ('not_configured', '') otherwise.
    """
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "").strip()
    if api_key:
        return ("configured", "")
    return ("not_configured", "")


async def wait_for_services(
    engine,
    osrm_url: str,
    vroom_url: str,
    timeout: float = 60.0,
) -> dict[str, tuple[bool, str]]:
    """Block until PostgreSQL, OSRM, and VROOM are healthy, or timeout.

    Checks services sequentially: PostgreSQL first (needed for geocoding cache),
    then OSRM (needed by VROOM), then VROOM (needed for optimization).

    Each service is retried every 2 seconds until healthy or the per-service
    timeout expires. If a service times out, we log a warning and continue
    to the next service -- the API starts in degraded mode rather than failing.

    Args:
        engine: SQLAlchemy async engine for PostgreSQL checks.
        osrm_url: Base URL for OSRM (e.g., http://osrm:5000).
        vroom_url: Base URL for VROOM (e.g., http://vroom:3000).
        timeout: Total timeout in seconds for ALL services (split across them).

    Returns:
        Dict mapping service name to (healthy: bool, message: str).
    """
    results: dict[str, tuple[bool, str]] = {}
    deadline = asyncio.get_event_loop().time() + timeout

    # Service check definitions: (name, coroutine_factory)
    checks = [
        ("postgresql", lambda: check_postgresql(engine)),
        ("osrm", lambda: check_osrm(osrm_url)),
        ("vroom", lambda: check_vroom(vroom_url)),
    ]

    for name, check_fn in checks:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            # No time left -- mark as timed out
            results[name] = (False, f"timeout: no time remaining (total {timeout}s expired)")
            logger.warning("Service %s skipped -- total timeout expired", name)
            continue

        logger.info("Checking %s (%.1fs remaining)...", name, remaining)
        last_msg = "unknown"

        while True:
            healthy, msg = await check_fn()
            if healthy:
                results[name] = (healthy, msg)
                logger.info("Service %s is healthy: %s", name, msg)
                break

            last_msg = msg
            remaining = deadline - asyncio.get_event_loop().time()
            if remaining <= 2.0:
                # Not enough time for another retry
                results[name] = (False, f"timeout after {timeout}s: {last_msg}")
                logger.warning(
                    "Service %s timed out after %.1fs: %s", name, timeout, last_msg
                )
                break

            logger.debug("Service %s not ready (%s), retrying in 2s...", name, msg)
            await asyncio.sleep(2.0)

    return results
