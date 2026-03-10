"""Tests for the retry decorator module.

Verifies:
- geocoding_retry retries on transient exceptions (ConnectError, TimeoutException)
- optimizer_retry retries on transient exceptions
- Neither retries on permanent errors (ValueError, HTTP 4xx)
- Both re-raise after exhausting retries
- Successful retry on second attempt returns the result

Uses real tenacity decorators applied to test functions to verify
retry behavior without mocking the retry machinery itself.
"""

import httpx
import pytest

from apps.kerala_delivery.api.retry import (
    TRANSIENT_EXCEPTIONS,
    geocoding_retry,
    optimizer_retry,
)


class TestGeocodingRetry:
    """Tests for the geocoding_retry decorator."""

    def test_geocoding_retry_retries_on_connect_error(self):
        """Function raising ConnectError is called 3 times then re-raises."""
        call_count = 0

        @geocoding_retry
        def failing_geocode():
            nonlocal call_count
            call_count += 1
            raise httpx.ConnectError("Connection refused")

        with pytest.raises(httpx.ConnectError):
            failing_geocode()

        assert call_count == 3  # stop_after_attempt(3)

    def test_geocoding_retry_no_retry_on_value_error(self):
        """ValueError is raised immediately with no retry."""
        call_count = 0

        @geocoding_retry
        def bad_input():
            nonlocal call_count
            call_count += 1
            raise ValueError("Bad input address")

        with pytest.raises(ValueError):
            bad_input()

        assert call_count == 1  # No retry

    def test_geocoding_retry_retries_on_timeout(self):
        """TimeoutException triggers retry."""
        call_count = 0

        @geocoding_retry
        def slow_geocode():
            nonlocal call_count
            call_count += 1
            raise httpx.TimeoutException("Request timed out")

        with pytest.raises(httpx.TimeoutException):
            slow_geocode()

        assert call_count == 3  # stop_after_attempt(3)


class TestOptimizerRetry:
    """Tests for the optimizer_retry decorator."""

    def test_optimizer_retry_retries_on_timeout(self):
        """Function raising TimeoutException is called 2 times then re-raises."""
        call_count = 0

        @optimizer_retry
        def slow_optimizer():
            nonlocal call_count
            call_count += 1
            raise httpx.TimeoutException("VROOM timed out")

        with pytest.raises(httpx.TimeoutException):
            slow_optimizer()

        assert call_count == 2  # stop_after_attempt(2)

    def test_optimizer_retry_succeeds_on_second_try(self):
        """First call raises ConnectError, second succeeds -- returns result."""
        call_count = 0

        @optimizer_retry
        def flaky_optimizer():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.ConnectError("Connection refused")
            return {"routes": [1, 2, 3]}

        result = flaky_optimizer()
        assert call_count == 2
        assert result == {"routes": [1, 2, 3]}

    def test_optimizer_retry_no_retry_on_http_status_error(self):
        """HTTP 400 (permanent error) is raised immediately."""
        call_count = 0

        @optimizer_retry
        def bad_request():
            nonlocal call_count
            call_count += 1
            request = httpx.Request("POST", "http://vroom:3000")
            response = httpx.Response(400, request=request)
            raise httpx.HTTPStatusError("Bad Request", request=request, response=response)

        with pytest.raises(httpx.HTTPStatusError):
            bad_request()

        assert call_count == 1  # No retry on 4xx


class TestTransientExceptions:
    """Tests for the TRANSIENT_EXCEPTIONS tuple."""

    def test_transient_exceptions_includes_connect_error(self):
        """ConnectError is in the transient list."""
        assert httpx.ConnectError in TRANSIENT_EXCEPTIONS

    def test_transient_exceptions_includes_timeout(self):
        """TimeoutException is in the transient list."""
        assert httpx.TimeoutException in TRANSIENT_EXCEPTIONS

    def test_transient_exceptions_does_not_include_http_status(self):
        """HTTPStatusError is NOT in the transient list (permanent error)."""
        assert httpx.HTTPStatusError not in TRANSIENT_EXCEPTIONS
