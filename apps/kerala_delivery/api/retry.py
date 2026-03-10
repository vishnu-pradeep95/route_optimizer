"""Tenacity retry decorators for transient external service failures.

Provides pre-configured retry decorators for:
- geocoding_retry: Google Geocoding API calls (3 attempts, 1-10s backoff)
- optimizer_retry: VROOM optimizer calls (2 attempts, 2-15s backoff)

Both decorators only retry on transient network errors (connection refused,
timeouts). Permanent errors like HTTP 400/401/403 are NOT retried -- they
indicate bad input or auth issues that retrying won't fix.

Usage:
    @geocoding_retry
    def call_geocoding_api(address):
        return httpx.get(...)

    # Or applied at call site:
    geocoder._call_api = geocoding_retry(geocoder._call_api)

See: .planning/phases/02-error-handling-infrastructure/02-CONTEXT.md
"""

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

# Transient exceptions that indicate network/connectivity issues.
# These are worth retrying because they're typically temporary:
# - ConnectError: service not yet ready, DNS resolution failed, connection refused
# - TimeoutException: service overloaded, network latency spike
# - ConnectTimeout: specifically connection establishment timed out
#
# NOT included (permanent errors, no retry):
# - HTTPStatusError: 4xx = bad request, 5xx = server bug (retrying won't help)
# - DecodingError: response body is corrupt
TRANSIENT_EXCEPTIONS = (
    httpx.ConnectError,
    httpx.TimeoutException,
    httpx.ConnectTimeout,
)

# Geocoding retry: 3 attempts with exponential backoff (1s, 2s, 4s... capped at 10s).
# Google Geocoding API is generally reliable, so 3 attempts covers transient blips.
# The 10s max avoids excessive delay -- if Google is down for 10s, it's likely a
# sustained outage and we should fail fast with a clear error message.
geocoding_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type(TRANSIENT_EXCEPTIONS),
    reraise=True,
)

# Optimizer retry: 2 attempts with exponential backoff (2s, 4s... capped at 15s).
# VROOM calls are heavier (POST with full problem payload), so we retry fewer
# times. If VROOM is unreachable after 2 attempts, it's likely a configuration
# issue or the container is down -- retrying more won't help.
optimizer_retry = retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=2, min=2, max=15),
    retry=retry_if_exception_type(TRANSIENT_EXCEPTIONS),
    reraise=True,
)
