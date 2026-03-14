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
