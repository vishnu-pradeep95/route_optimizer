"""Tests for Google Routes validation endpoint and repository functions.

Phase 22: Google Routes API validation — RouteValidationDB model,
repository CRUD, validation endpoint, and cost tracking.

Tests are organized in groups:
1. confidence_level() unit tests
2. Repository-level tests (save/get validation, stats)
3. API endpoint tests (POST validate, GET stats, GET recent)

Uses the same mock session pattern as test_settings.py — no real database needed.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from apps.kerala_delivery.api.main import app
from core.database.connection import get_session


# =============================================================================
# Mock DB Session Setup (same pattern as test_settings.py)
# =============================================================================


@pytest.fixture
def mock_session():
    """Create a mock AsyncSession for dependency override."""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def client(mock_session):
    """FastAPI TestClient with DB session overridden to a mock."""
    async def override_get_session():
        yield mock_session

    mock_service_health = {
        "postgresql": (True, "connected"),
        "osrm": (True, "available"),
        "vroom": (True, "available"),
    }

    with patch.dict(os.environ, {"RATE_LIMIT_ENABLED": "false"}), \
         patch("apps.kerala_delivery.api.main.wait_for_services", new_callable=AsyncMock, return_value=mock_service_health):
        from apps.kerala_delivery.api.main import limiter
        limiter.enabled = False

        app.dependency_overrides[get_session] = override_get_session

        app.state.service_health = mock_service_health
        app.state.started_at = datetime.now(timezone.utc)

        yield TestClient(app)
        app.dependency_overrides.clear()

        limiter.enabled = True


@pytest.fixture
def api_key():
    """API key for authenticated endpoints."""
    return "test-api-key-12345"


@pytest.fixture
def auth_headers(api_key):
    """Headers with API key for authenticated requests."""
    return {"X-API-Key": api_key}


# =============================================================================
# Unit Tests: confidence_level()
# =============================================================================


class TestConfidenceLevel:
    """Test the confidence_level helper function for boundary values."""

    def test_zero_delta_is_green(self):
        """0% delta should return green."""
        from core.database.repository import confidence_level
        assert confidence_level(0.0) == "green"

    def test_ten_percent_is_green(self):
        """10% delta (boundary) should return green."""
        from core.database.repository import confidence_level
        assert confidence_level(10.0) == "green"

    def test_just_over_ten_is_amber(self):
        """10.1% delta should return amber."""
        from core.database.repository import confidence_level
        assert confidence_level(10.1) == "amber"

    def test_twenty_five_percent_is_amber(self):
        """25% delta (boundary) should return amber."""
        from core.database.repository import confidence_level
        assert confidence_level(25.0) == "amber"

    def test_just_over_twenty_five_is_red(self):
        """25.1% delta should return red."""
        from core.database.repository import confidence_level
        assert confidence_level(25.1) == "red"

    def test_fifty_percent_is_red(self):
        """50% delta should return red."""
        from core.database.repository import confidence_level
        assert confidence_level(50.0) == "red"


# =============================================================================
# Repository Tests: save/get validation, stats
# =============================================================================


class TestValidationRepository:
    """Test save_route_validation, get_route_validation, get_validation_stats."""

    @pytest.mark.asyncio
    async def test_save_route_validation_computes_deltas(self):
        """save_route_validation computes correct delta percentages."""
        from core.database.repository import save_route_validation

        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        route_id = uuid.uuid4()

        result = await save_route_validation(
            session,
            route_id=route_id,
            osrm_distance_km=50.0,
            osrm_duration_minutes=60.0,
            google_distance_km=55.0,
            google_duration_minutes=54.0,
            google_waypoint_order="[2, 0, 1, 3]",
            estimated_cost_usd=0.01,
        )

        # distance delta: abs(55 - 50) / 50 * 100 = 10.0%
        assert result.distance_delta_pct == 10.0
        # duration delta: abs(54 - 60) / 60 * 100 = 10.0%
        assert result.duration_delta_pct == 10.0
        assert result.route_id == route_id
        assert result.osrm_distance_km == 50.0
        assert result.google_distance_km == 55.0
        session.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_route_validation_returns_existing(self):
        """get_route_validation returns existing validation for route_id."""
        from core.database.repository import get_route_validation

        session = AsyncMock()
        mock_validation = MagicMock()
        mock_validation.route_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_validation
        session.execute = AsyncMock(return_value=mock_result)

        result = await get_route_validation(session, mock_validation.route_id)
        assert result is mock_validation

    @pytest.mark.asyncio
    async def test_get_route_validation_returns_none_when_missing(self):
        """get_route_validation returns None when no validation exists."""
        from core.database.repository import get_route_validation

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await get_route_validation(session, uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_validation_stats_defaults_when_no_settings(self):
        """get_validation_stats returns count=0, total_cost=0 when no settings."""
        from core.database.repository import get_validation_stats

        session = AsyncMock()
        # Mock get_setting to return None for both keys
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        with patch("core.database.repository.get_setting", new_callable=AsyncMock, return_value=None):
            stats = await get_validation_stats(session)

        assert stats["count"] == 0
        assert stats["total_cost_usd"] == 0.0

    @pytest.mark.asyncio
    async def test_get_validation_stats_returns_correct_values(self):
        """get_validation_stats returns correct count and cost from SettingsDB."""
        from core.database.repository import get_validation_stats

        session = AsyncMock()

        async def mock_get_setting(sess, key):
            if key == "validation_count":
                return "12"
            elif key == "validation_total_cost_usd":
                return "0.12"
            return None

        with patch("core.database.repository.get_setting", side_effect=mock_get_setting):
            stats = await get_validation_stats(session)

        assert stats["count"] == 12
        assert stats["total_cost_usd"] == 0.12


# =============================================================================
# API Endpoint Tests: POST /api/routes/{vehicle_id}/validate
# =============================================================================


class TestValidateRouteEndpoint:
    """Test POST /api/routes/{vehicle_id}/validate endpoint."""

    def test_validate_returns_400_when_no_api_key_configured(self, client, api_key):
        """Returns 400 with helpful message when no Google API key is set."""
        with patch.dict(os.environ, {"API_KEY": api_key}):
            with patch("apps.kerala_delivery.api.main._cached_api_key", None):
                with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": ""}, clear=False):
                    resp = client.post(
                        "/api/routes/DRIVER-01/validate",
                        headers={"X-API-Key": api_key},
                    )

        assert resp.status_code == 400
        data = resp.json()
        assert data["error"] == "google_api_key_required"

    def test_validate_returns_404_when_route_not_found(self, client, api_key):
        """Returns 404 when route or run not found."""
        with patch.dict(os.environ, {"API_KEY": api_key}):
            with patch("apps.kerala_delivery.api.main._cached_api_key", "fake-key"):
                with patch("apps.kerala_delivery.api.main.repo.get_latest_run",
                           new_callable=AsyncMock, return_value=None):
                    resp = client.post(
                        "/api/routes/NONEXISTENT/validate",
                        headers={"X-API-Key": api_key},
                    )

        assert resp.status_code == 404

    def test_validate_returns_cached_result(self, client, api_key):
        """Returns cached validation result when route was previously validated."""
        mock_run = MagicMock()
        mock_run.id = uuid.uuid4()

        mock_route = MagicMock()
        mock_route.id = uuid.uuid4()
        mock_route.vehicle_id = "DRIVER-01"
        mock_route.total_distance_km = 45.2
        mock_route.total_duration_minutes = 67.5

        mock_validation = MagicMock()
        mock_validation.route_id = mock_route.id
        mock_validation.osrm_distance_km = 45.2
        mock_validation.osrm_duration_minutes = 67.5
        mock_validation.google_distance_km = 48.1
        mock_validation.google_duration_minutes = 62.0
        mock_validation.distance_delta_pct = 6.4
        mock_validation.duration_delta_pct = 8.1
        mock_validation.google_waypoint_order = "[2, 0, 1, 3]"
        mock_validation.estimated_cost_usd = 0.01
        mock_validation.validated_at = datetime(2026, 3, 14, 12, 0, 0, tzinfo=timezone.utc)

        with patch.dict(os.environ, {"API_KEY": api_key}):
            with patch("apps.kerala_delivery.api.main._cached_api_key", "fake-key"):
                with patch("apps.kerala_delivery.api.main.repo.get_latest_run",
                           new_callable=AsyncMock, return_value=mock_run):
                    with patch("apps.kerala_delivery.api.main.repo.get_route_for_vehicle",
                               new_callable=AsyncMock, return_value=mock_route):
                        with patch("apps.kerala_delivery.api.main.repo.get_route_validation",
                                   new_callable=AsyncMock, return_value=mock_validation):
                            resp = client.post(
                                "/api/routes/DRIVER-01/validate",
                                headers={"X-API-Key": api_key},
                            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["cached"] is True
        assert data["confidence"] == "green"
        assert data["distance_delta_pct"] == 6.4

    def test_validate_calls_google_api_and_returns_comparison(self, client, api_key):
        """Calls Google Routes API and returns OSRM vs Google comparison."""
        mock_run = MagicMock()
        mock_run.id = uuid.uuid4()

        mock_route = MagicMock()
        mock_route.id = uuid.uuid4()
        mock_route.vehicle_id = "DRIVER-01"
        mock_route.total_distance_km = 50.0
        mock_route.total_duration_minutes = 60.0

        # Mock stops with locations
        mock_stop1 = MagicMock()
        mock_stop1.location = MagicMock()
        mock_stop2 = MagicMock()
        mock_stop2.location = MagicMock()
        mock_route.stops = [mock_stop1, mock_stop2]

        # Mock shapely point conversion
        mock_point1 = MagicMock()
        mock_point1.y = 11.60  # lat
        mock_point1.x = 75.58  # lng
        mock_point2 = MagicMock()
        mock_point2.y = 11.65
        mock_point2.x = 75.62

        # Mock Google Routes API response
        google_response = MagicMock()
        google_response.status_code = 200
        google_response.raise_for_status = MagicMock()
        google_response.json.return_value = {
            "routes": [{
                "distanceMeters": 55000,  # 55 km
                "duration": "3300s",  # 55 minutes
                "optimizedIntermediateWaypointIndex": [1, 0],
            }]
        }

        # Mock saved validation result
        mock_saved = MagicMock()
        mock_saved.route_id = mock_route.id
        mock_saved.osrm_distance_km = 50.0
        mock_saved.osrm_duration_minutes = 60.0
        mock_saved.google_distance_km = 55.0
        mock_saved.google_duration_minutes = 55.0
        mock_saved.distance_delta_pct = 10.0
        mock_saved.duration_delta_pct = 8.3
        mock_saved.google_waypoint_order = "[1, 0]"
        mock_saved.estimated_cost_usd = 0.01
        mock_saved.validated_at = datetime(2026, 3, 14, 12, 0, 0, tzinfo=timezone.utc)

        with patch.dict(os.environ, {"API_KEY": api_key}):
            with patch("apps.kerala_delivery.api.main._cached_api_key", "fake-key"):
                with patch("apps.kerala_delivery.api.main.repo.get_latest_run",
                           new_callable=AsyncMock, return_value=mock_run):
                    with patch("apps.kerala_delivery.api.main.repo.get_route_for_vehicle",
                               new_callable=AsyncMock, return_value=mock_route):
                        with patch("apps.kerala_delivery.api.main.repo.get_route_validation",
                                   new_callable=AsyncMock, return_value=None):
                            with patch("apps.kerala_delivery.api.main.to_shape",
                                       side_effect=[mock_point1, mock_point2]):
                                with patch("apps.kerala_delivery.api.main.httpx.AsyncClient") as mock_client_cls:
                                    mock_client = AsyncMock()
                                    mock_client.post = AsyncMock(return_value=google_response)
                                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                                    mock_client.__aexit__ = AsyncMock(return_value=False)
                                    mock_client_cls.return_value = mock_client

                                    with patch("apps.kerala_delivery.api.main.repo.save_route_validation",
                                               new_callable=AsyncMock, return_value=mock_saved):
                                        with patch("apps.kerala_delivery.api.main.repo.increment_validation_stats",
                                                   new_callable=AsyncMock):
                                            resp = client.post(
                                                "/api/routes/DRIVER-01/validate",
                                                headers={"X-API-Key": api_key},
                                            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["cached"] is False
        assert data["vehicle_id"] == "DRIVER-01"
        assert "confidence" in data
        assert "distance_delta_pct" in data

    def test_validate_handles_google_api_timeout(self, client, api_key):
        """Returns 502 when Google API request times out."""
        import httpx

        mock_run = MagicMock()
        mock_run.id = uuid.uuid4()

        mock_route = MagicMock()
        mock_route.id = uuid.uuid4()
        mock_route.vehicle_id = "DRIVER-01"
        mock_route.total_distance_km = 50.0
        mock_route.total_duration_minutes = 60.0

        mock_stop = MagicMock()
        mock_stop.location = MagicMock()
        mock_route.stops = [mock_stop]

        mock_point = MagicMock()
        mock_point.y = 11.60
        mock_point.x = 75.58

        with patch.dict(os.environ, {"API_KEY": api_key}):
            with patch("apps.kerala_delivery.api.main._cached_api_key", "fake-key"):
                with patch("apps.kerala_delivery.api.main.repo.get_latest_run",
                           new_callable=AsyncMock, return_value=mock_run):
                    with patch("apps.kerala_delivery.api.main.repo.get_route_for_vehicle",
                               new_callable=AsyncMock, return_value=mock_route):
                        with patch("apps.kerala_delivery.api.main.repo.get_route_validation",
                                   new_callable=AsyncMock, return_value=None):
                            with patch("apps.kerala_delivery.api.main.to_shape",
                                       return_value=mock_point):
                                with patch("apps.kerala_delivery.api.main.httpx.AsyncClient") as mock_client_cls:
                                    mock_client = AsyncMock()
                                    mock_client.post = AsyncMock(
                                        side_effect=httpx.TimeoutException("Connection timed out")
                                    )
                                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                                    mock_client.__aexit__ = AsyncMock(return_value=False)
                                    mock_client_cls.return_value = mock_client

                                    resp = client.post(
                                        "/api/routes/DRIVER-01/validate",
                                        headers={"X-API-Key": api_key},
                                    )

        assert resp.status_code == 502
        data = resp.json()
        assert "timed out" in data["message"].lower()

    def test_validate_handles_google_api_http_error(self, client, api_key):
        """Returns 502 when Google API returns HTTP error."""
        import httpx

        mock_run = MagicMock()
        mock_run.id = uuid.uuid4()

        mock_route = MagicMock()
        mock_route.id = uuid.uuid4()
        mock_route.vehicle_id = "DRIVER-01"
        mock_route.total_distance_km = 50.0
        mock_route.total_duration_minutes = 60.0

        mock_stop = MagicMock()
        mock_stop.location = MagicMock()
        mock_route.stops = [mock_stop]

        mock_point = MagicMock()
        mock_point.y = 11.60
        mock_point.x = 75.58

        # Build a real httpx.Response for HTTPStatusError
        mock_request = httpx.Request("POST", "https://routes.googleapis.com/directions/v2:computeRoutes")
        error_response = httpx.Response(
            status_code=403,
            json={"error": {"message": "The caller does not have permission"}},
            request=mock_request,
        )

        with patch.dict(os.environ, {"API_KEY": api_key}):
            with patch("apps.kerala_delivery.api.main._cached_api_key", "fake-key"):
                with patch("apps.kerala_delivery.api.main.repo.get_latest_run",
                           new_callable=AsyncMock, return_value=mock_run):
                    with patch("apps.kerala_delivery.api.main.repo.get_route_for_vehicle",
                               new_callable=AsyncMock, return_value=mock_route):
                        with patch("apps.kerala_delivery.api.main.repo.get_route_validation",
                                   new_callable=AsyncMock, return_value=None):
                            with patch("apps.kerala_delivery.api.main.to_shape",
                                       return_value=mock_point):
                                with patch("apps.kerala_delivery.api.main.httpx.AsyncClient") as mock_client_cls:
                                    mock_client = AsyncMock()
                                    mock_client.post = AsyncMock(
                                        side_effect=httpx.HTTPStatusError(
                                            "403 Forbidden",
                                            request=mock_request,
                                            response=error_response,
                                        )
                                    )
                                    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                                    mock_client.__aexit__ = AsyncMock(return_value=False)
                                    mock_client_cls.return_value = mock_client

                                    resp = client.post(
                                        "/api/routes/DRIVER-01/validate",
                                        headers={"X-API-Key": api_key},
                                    )

        assert resp.status_code == 502

    def test_validate_handles_too_many_stops(self, client, api_key):
        """Returns 400 when route has more than 98 stops."""
        mock_run = MagicMock()
        mock_run.id = uuid.uuid4()

        mock_route = MagicMock()
        mock_route.id = uuid.uuid4()
        mock_route.vehicle_id = "DRIVER-01"
        mock_route.total_distance_km = 50.0
        mock_route.total_duration_minutes = 60.0

        # Create 99 stops (exceeds 98 limit)
        mock_route.stops = [MagicMock() for _ in range(99)]

        with patch.dict(os.environ, {"API_KEY": api_key}):
            with patch("apps.kerala_delivery.api.main._cached_api_key", "fake-key"):
                with patch("apps.kerala_delivery.api.main.repo.get_latest_run",
                           new_callable=AsyncMock, return_value=mock_run):
                    with patch("apps.kerala_delivery.api.main.repo.get_route_for_vehicle",
                               new_callable=AsyncMock, return_value=mock_route):
                        with patch("apps.kerala_delivery.api.main.repo.get_route_validation",
                                   new_callable=AsyncMock, return_value=None):
                            resp = client.post(
                                "/api/routes/DRIVER-01/validate",
                                headers={"X-API-Key": api_key},
                            )

        assert resp.status_code == 400
        data = resp.json()
        assert "too many stops" in data["message"].lower()


# =============================================================================
# API Endpoint Tests: GET /api/validation-stats
# =============================================================================


class TestValidationStatsEndpoint:
    """Test GET /api/validation-stats and GET /api/validation-stats/recent."""

    def test_get_validation_stats(self, client, api_key):
        """GET /api/validation-stats returns count and cost."""
        stats = {"count": 12, "total_cost_usd": 0.12}

        with patch.dict(os.environ, {"API_KEY": api_key}):
            with patch("apps.kerala_delivery.api.main.repo.get_validation_stats",
                       new_callable=AsyncMock, return_value=stats):
                resp = client.get(
                    "/api/validation-stats",
                    headers={"X-API-Key": api_key},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 12
        assert data["total_cost_usd"] == 0.12
        assert "estimated_cost_inr" in data

    def test_get_recent_validations(self, client, api_key):
        """GET /api/validation-stats/recent returns recent validation list."""
        mock_validation = MagicMock()
        mock_validation.id = uuid.uuid4()
        mock_validation.route_id = uuid.uuid4()
        mock_validation.osrm_distance_km = 45.2
        mock_validation.osrm_duration_minutes = 67.5
        mock_validation.google_distance_km = 48.1
        mock_validation.google_duration_minutes = 62.0
        mock_validation.distance_delta_pct = 6.4
        mock_validation.duration_delta_pct = 8.1
        mock_validation.estimated_cost_usd = 0.01
        mock_validation.validated_at = datetime(2026, 3, 14, 12, 0, 0, tzinfo=timezone.utc)
        mock_validation.route = MagicMock()
        mock_validation.route.vehicle_id = "DRIVER-01"

        with patch.dict(os.environ, {"API_KEY": api_key}):
            with patch("apps.kerala_delivery.api.main.repo.get_recent_validations",
                       new_callable=AsyncMock, return_value=[mock_validation]):
                resp = client.get(
                    "/api/validation-stats/recent",
                    headers={"X-API-Key": api_key},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["validations"]) == 1
        assert data["validations"][0]["vehicle_id"] == "DRIVER-01"
        assert data["validations"][0]["distance_delta_pct"] == 6.4
