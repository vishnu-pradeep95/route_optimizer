"""Tests for RequestIDMiddleware, RequestIDFilter, and request_id_var.

Covers ERR-02: Request ID middleware adds X-Request-ID header.
"""

import logging
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.kerala_delivery.api.middleware import (
    RequestIDMiddleware,
    RequestIDFilter,
    request_id_var,
    LOG_FORMAT,
)


@pytest.fixture
def test_app():
    """Create a minimal FastAPI app with RequestIDMiddleware for testing."""
    app = FastAPI()

    @app.get("/test")
    async def test_endpoint():
        return {"request_id": request_id_var.get("")}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    app.add_middleware(RequestIDMiddleware)
    return app


@pytest.fixture
def test_client(test_app):
    return TestClient(test_app)


class TestRequestIDMiddleware:
    """X-Request-ID header generation."""

    def test_response_has_x_request_id_header(self, test_client):
        """Every response must include X-Request-ID header."""
        resp = test_client.get("/test")
        assert "X-Request-ID" in resp.headers

    def test_request_id_is_8_char_hex(self, test_client):
        """X-Request-ID must be exactly 8 hex characters."""
        resp = test_client.get("/test")
        req_id = resp.headers["X-Request-ID"]
        assert len(req_id) == 8
        assert re.match(r"^[0-9a-f]{8}$", req_id)

    def test_request_id_unique_per_request(self, test_client):
        """Each request gets a unique ID."""
        ids = set()
        for _ in range(10):
            resp = test_client.get("/test")
            ids.add(resp.headers["X-Request-ID"])
        assert len(ids) == 10  # All unique

    def test_request_id_available_in_endpoint(self, test_client):
        """request_id_var ContextVar is accessible within endpoint."""
        resp = test_client.get("/test")
        data = resp.json()
        header_id = resp.headers["X-Request-ID"]
        assert data["request_id"] == header_id

    def test_health_endpoint_also_gets_request_id(self, test_client):
        """Even /health gets X-Request-ID."""
        resp = test_client.get("/health")
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) == 8


class TestRequestIDFilter:
    """Log record injection of request_id."""

    def test_filter_adds_request_id_to_log_record(self):
        """RequestIDFilter injects request_id into log records."""
        filt = RequestIDFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="test message", args=(), exc_info=None,
        )
        # Before filter, record may not have request_id
        result = filt.filter(record)
        assert result is True
        assert hasattr(record, "request_id")

    def test_filter_uses_contextvar_default(self):
        """When no request is active, filter uses default '--------'."""
        # Reset contextvar to default
        token = request_id_var.set("--------")
        try:
            filt = RequestIDFilter()
            record = logging.LogRecord(
                name="test", level=logging.INFO, pathname="", lineno=0,
                msg="test", args=(), exc_info=None,
            )
            filt.filter(record)
            assert record.request_id == "--------"
        finally:
            request_id_var.reset(token)


class TestLogFormat:
    """LOG_FORMAT constant."""

    def test_log_format_includes_request_id_placeholder(self):
        assert "%(request_id)s" in LOG_FORMAT

    def test_log_format_includes_level(self):
        assert "%(levelname)" in LOG_FORMAT
