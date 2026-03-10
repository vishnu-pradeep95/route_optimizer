"""Tests for the health check module.

Verifies:
- Per-service health checks (PostgreSQL, OSRM, VROOM, Google API)
- Startup wait_for_services with timeout and sequential checking
- Edge cases: connection errors, timeouts, partial failures

Uses unittest.mock to simulate external service responses without
requiring real PostgreSQL, OSRM, or VROOM instances.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


class TestCheckPostgresql:
    """Tests for check_postgresql()."""

    @pytest.mark.asyncio
    async def test_check_postgresql_success(self):
        """Healthy PostgreSQL returns (True, 'connected')."""
        from apps.kerala_delivery.api.health import check_postgresql

        mock_engine = AsyncMock()
        mock_conn = AsyncMock()
        mock_engine.connect.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_engine.connect.return_value.__aexit__ = AsyncMock(return_value=False)

        healthy, msg = await check_postgresql(mock_engine)
        assert healthy is True
        assert msg == "connected"

    @pytest.mark.asyncio
    async def test_check_postgresql_failure(self):
        """Failed PostgreSQL returns (False, error_msg)."""
        from apps.kerala_delivery.api.health import check_postgresql

        mock_engine = AsyncMock()
        mock_engine.connect.side_effect = Exception("Connection refused")

        healthy, msg = await check_postgresql(mock_engine)
        assert healthy is False
        assert "Connection refused" in msg


class TestCheckOsrm:
    """Tests for check_osrm()."""

    @pytest.mark.asyncio
    async def test_check_osrm_success(self):
        """OSRM returning 200 is available."""
        from apps.kerala_delivery.api.health import check_osrm

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("apps.kerala_delivery.api.health.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            healthy, msg = await check_osrm("http://osrm:5000")
            assert healthy is True
            assert msg == "available"

    @pytest.mark.asyncio
    async def test_check_osrm_400_is_available(self):
        """OSRM returning 400 means running (bad coords, but alive)."""
        from apps.kerala_delivery.api.health import check_osrm

        mock_response = MagicMock()
        mock_response.status_code = 400

        with patch("apps.kerala_delivery.api.health.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            healthy, msg = await check_osrm("http://osrm:5000")
            assert healthy is True
            assert msg == "available"

    @pytest.mark.asyncio
    async def test_check_osrm_connection_error(self):
        """OSRM connection error returns (False, error_msg)."""
        from apps.kerala_delivery.api.health import check_osrm

        with patch("apps.kerala_delivery.api.health.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("Connection refused")
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            healthy, msg = await check_osrm("http://osrm:5000")
            assert healthy is False
            assert "Connection refused" in msg


class TestCheckVroom:
    """Tests for check_vroom()."""

    @pytest.mark.asyncio
    async def test_check_vroom_success(self):
        """VROOM /health returning 200 is available."""
        from apps.kerala_delivery.api.health import check_vroom

        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("apps.kerala_delivery.api.health.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            healthy, msg = await check_vroom("http://vroom:3000")
            assert healthy is True
            assert msg == "available"

    @pytest.mark.asyncio
    async def test_check_vroom_failure(self):
        """VROOM connection failure returns (False, error_msg)."""
        from apps.kerala_delivery.api.health import check_vroom

        with patch("apps.kerala_delivery.api.health.httpx.AsyncClient") as MockClient:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("Connection refused")
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            healthy, msg = await check_vroom("http://vroom:3000")
            assert healthy is False
            assert "Connection refused" in msg


class TestCheckGoogleApi:
    """Tests for check_google_api()."""

    def test_check_google_api_configured(self):
        """Returns ('configured', '') when GOOGLE_MAPS_API_KEY is set."""
        from apps.kerala_delivery.api.health import check_google_api

        with patch.dict("os.environ", {"GOOGLE_MAPS_API_KEY": "AIzaTestKey123"}):
            status, msg = check_google_api()
            assert status == "configured"
            assert msg == ""

    def test_check_google_api_not_configured(self):
        """Returns ('not_configured', '') when key is empty or missing."""
        from apps.kerala_delivery.api.health import check_google_api

        with patch.dict("os.environ", {"GOOGLE_MAPS_API_KEY": ""}, clear=False):
            status, msg = check_google_api()
            assert status == "not_configured"
            assert msg == ""

    def test_check_google_api_missing(self):
        """Returns ('not_configured', '') when env var is missing entirely."""
        from apps.kerala_delivery.api.health import check_google_api

        import os
        env = os.environ.copy()
        env.pop("GOOGLE_MAPS_API_KEY", None)
        with patch.dict("os.environ", env, clear=True):
            status, msg = check_google_api()
            assert status == "not_configured"


class TestWaitForServices:
    """Tests for wait_for_services()."""

    @pytest.mark.asyncio
    async def test_wait_for_services_all_healthy(self):
        """All services healthy returns all (True, msg) in results."""
        from apps.kerala_delivery.api.health import wait_for_services

        mock_engine = AsyncMock()

        with patch("apps.kerala_delivery.api.health.check_postgresql", new_callable=AsyncMock) as mock_pg, \
             patch("apps.kerala_delivery.api.health.check_osrm", new_callable=AsyncMock) as mock_osrm, \
             patch("apps.kerala_delivery.api.health.check_vroom", new_callable=AsyncMock) as mock_vroom:
            mock_pg.return_value = (True, "connected")
            mock_osrm.return_value = (True, "available")
            mock_vroom.return_value = (True, "available")

            result = await wait_for_services(mock_engine, "http://osrm:5000", "http://vroom:3000", timeout=5.0)

            assert result["postgresql"] == (True, "connected")
            assert result["osrm"] == (True, "available")
            assert result["vroom"] == (True, "available")

    @pytest.mark.asyncio
    async def test_wait_for_services_timeout(self):
        """When a service never becomes healthy, timeout is reported and remaining services still checked."""
        from apps.kerala_delivery.api.health import wait_for_services

        mock_engine = AsyncMock()

        call_count = 0

        async def pg_always_fails(engine):
            nonlocal call_count
            call_count += 1
            return (False, "Connection refused")

        with patch("apps.kerala_delivery.api.health.check_postgresql", side_effect=pg_always_fails), \
             patch("apps.kerala_delivery.api.health.check_osrm", new_callable=AsyncMock) as mock_osrm, \
             patch("apps.kerala_delivery.api.health.check_vroom", new_callable=AsyncMock) as mock_vroom:
            mock_osrm.return_value = (True, "available")
            mock_vroom.return_value = (True, "available")

            # Use a very short timeout so the test runs fast
            result = await wait_for_services(mock_engine, "http://osrm:5000", "http://vroom:3000", timeout=3.0)

            # PostgreSQL should be reported as unhealthy (timed out)
            assert result["postgresql"][0] is False
            assert "timeout" in result["postgresql"][1].lower() or "Connection refused" in result["postgresql"][1]
            # OSRM and VROOM should still be checked and healthy
            assert result["osrm"] == (True, "available")
            assert result["vroom"] == (True, "available")
            # Should have retried at least once
            assert call_count >= 1
