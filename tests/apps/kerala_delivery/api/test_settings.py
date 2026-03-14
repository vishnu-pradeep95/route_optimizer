"""Tests for Settings and Geocode Cache Management API endpoints.

Phase 21: Settings backend — SettingsDB model, repository CRUD,
geocode cache stats/export/import/clear, and API endpoints.

Tests are organized in two groups:
1. Repository-level tests (unit tests for get/set_setting, cache operations)
2. API endpoint tests (HTTP-level tests for all 7 new endpoints)

Uses the same mock session pattern as test_api.py — no real database needed.
"""

import io
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
# Mock DB Session Setup (same pattern as test_api.py)
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
# Repository-Level Tests: Settings CRUD
# =============================================================================


class TestSettingsRepository:
    """Test get_setting and set_setting repository functions."""

    @pytest.mark.asyncio
    async def test_get_setting_returns_none_when_not_exists(self):
        """get_setting returns None when no setting exists for the key."""
        from core.database.repository import get_setting

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)

        result = await get_setting(session, "google_maps_api_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get_setting_roundtrip(self):
        """set_setting stores value, get_setting retrieves it."""
        from core.database.repository import get_setting, set_setting
        from core.database.models import SettingsDB

        session = AsyncMock()

        # Mock set_setting: merge upserts
        session.merge = MagicMock(return_value=SettingsDB(key="google_maps_api_key", value="AIzaTestKey123"))
        session.flush = AsyncMock()

        await set_setting(session, "google_maps_api_key", "AIzaTestKey123")
        session.merge.assert_called_once()

        # Verify the merged object has correct key and value
        merged_obj = session.merge.call_args[0][0]
        assert merged_obj.key == "google_maps_api_key"
        assert merged_obj.value == "AIzaTestKey123"

    @pytest.mark.asyncio
    async def test_set_setting_upsert_overwrites(self):
        """set_setting with existing key overwrites the value (upsert)."""
        from core.database.repository import set_setting
        from core.database.models import SettingsDB

        session = AsyncMock()
        session.merge = MagicMock(return_value=SettingsDB(key="google_maps_api_key", value="new-value"))
        session.flush = AsyncMock()

        await set_setting(session, "google_maps_api_key", "new-value")

        merged_obj = session.merge.call_args[0][0]
        assert merged_obj.value == "new-value"


# =============================================================================
# Repository-Level Tests: Geocode Cache Operations
# =============================================================================


class TestGeocideCacheRepository:
    """Test geocode cache stats, export, import, and clear operations."""

    @pytest.mark.asyncio
    async def test_get_geocode_cache_stats_empty(self):
        """get_geocode_cache_stats returns zeros for empty table."""
        from core.database.repository import get_geocode_cache_stats

        session = AsyncMock()
        mock_result = MagicMock()
        # COUNT returns 0, SUM returns None for empty table
        mock_result.one.return_value = (0, None)
        session.execute = AsyncMock(return_value=mock_result)

        stats = await get_geocode_cache_stats(session)
        assert stats["total_entries"] == 0
        assert stats["total_hits"] == 0
        assert stats["api_calls_saved"] == 0
        assert stats["estimated_savings_usd"] == 0.0

    @pytest.mark.asyncio
    async def test_get_geocode_cache_stats_with_data(self):
        """get_geocode_cache_stats returns correct aggregation."""
        from core.database.repository import get_geocode_cache_stats

        session = AsyncMock()
        mock_result = MagicMock()
        # 50 entries, 200 total hits
        mock_result.one.return_value = (50, 200)
        session.execute = AsyncMock(return_value=mock_result)

        stats = await get_geocode_cache_stats(session)
        assert stats["total_entries"] == 50
        assert stats["total_hits"] == 200
        assert stats["api_calls_saved"] == 200
        assert stats["estimated_savings_usd"] == 200 * 0.005  # $1.00

    @pytest.mark.asyncio
    async def test_export_geocode_cache_serialization(self):
        """export_geocode_cache returns list of dicts with lat/lng from geometry."""
        from core.database.repository import export_geocode_cache

        session = AsyncMock()

        # Mock a GeocodeCacheDB row with a PostGIS geometry
        mock_row = MagicMock()
        mock_row.address_raw = "Vatakara Bus Stand"
        mock_row.address_norm = "vatakara bus stand"
        mock_row.source = "google"
        mock_row.confidence = 0.9
        mock_row.hit_count = 5
        mock_row.created_at = datetime(2026, 3, 1, tzinfo=timezone.utc)

        # Mock the geometry → shapely Point conversion
        mock_point = MagicMock()
        mock_point.y = 11.595  # latitude
        mock_point.x = 75.570  # longitude

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_row]
        session.execute = AsyncMock(return_value=mock_result)

        with patch("core.database.repository.to_shape", return_value=mock_point):
            entries = await export_geocode_cache(session)

        assert len(entries) == 1
        entry = entries[0]
        assert entry["address_raw"] == "Vatakara Bus Stand"
        assert entry["address_norm"] == "vatakara bus stand"
        assert entry["latitude"] == 11.595
        assert entry["longitude"] == 75.570
        assert entry["source"] == "google"
        assert entry["confidence"] == 0.9
        assert entry["hit_count"] == 5

    @pytest.mark.asyncio
    async def test_import_geocode_cache_adds_new_entries(self):
        """import_geocode_cache adds new entries and counts them."""
        from core.database.repository import import_geocode_cache

        session = AsyncMock()

        # Mock: no existing entries (all new)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)
        session.add = MagicMock()
        session.flush = AsyncMock()

        entries = [
            {
                "address_raw": "Vatakara Bus Stand",
                "latitude": 11.595,
                "longitude": 75.570,
                "source": "google",
                "confidence": 0.9,
            },
        ]

        result = await import_geocode_cache(session, entries)
        assert result["added"] == 1
        assert result["skipped"] == 0

    @pytest.mark.asyncio
    async def test_import_geocode_cache_skips_duplicates(self):
        """import_geocode_cache skips entries with duplicate address_norm+source."""
        from core.database.repository import import_geocode_cache

        session = AsyncMock()

        # Mock: existing entry found (duplicate)
        mock_existing = MagicMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_existing
        session.execute = AsyncMock(return_value=mock_result)
        session.flush = AsyncMock()

        entries = [
            {
                "address_raw": "Vatakara Bus Stand",
                "latitude": 11.595,
                "longitude": 75.570,
                "source": "google",
                "confidence": 0.9,
            },
        ]

        result = await import_geocode_cache(session, entries)
        assert result["added"] == 0
        assert result["skipped"] == 1

    @pytest.mark.asyncio
    async def test_clear_geocode_cache_returns_count(self):
        """clear_geocode_cache deletes all entries and returns count."""
        from core.database.repository import clear_geocode_cache

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 25
        session.execute = AsyncMock(return_value=mock_result)
        session.flush = AsyncMock()

        count = await clear_geocode_cache(session)
        assert count == 25


# =============================================================================
# API Endpoint Tests: Settings
# =============================================================================


class TestSettingsEndpoints:
    """Test GET /api/settings and PUT /api/settings/api-key endpoints."""

    def test_get_settings_returns_null_when_no_key(self, client, api_key):
        """GET /api/settings returns null api key when none is set."""
        with patch.dict(os.environ, {"API_KEY": api_key}):
            with patch("apps.kerala_delivery.api.main.repo.get_setting", new_callable=AsyncMock, return_value=None):
                resp = client.get("/api/settings", headers={"X-API-Key": api_key})

        assert resp.status_code == 200
        data = resp.json()
        assert data["google_maps_api_key"] is None
        assert data["has_api_key"] is False

    def test_get_settings_returns_masked_key(self, client, api_key):
        """GET /api/settings returns masked API key after one is stored."""
        with patch.dict(os.environ, {"API_KEY": api_key}):
            with patch("apps.kerala_delivery.api.main.repo.get_setting", new_callable=AsyncMock, return_value="AIzaSyD1234567890abcdefghijklmnop"):
                resp = client.get("/api/settings", headers={"X-API-Key": api_key})

        assert resp.status_code == 200
        data = resp.json()
        assert data["has_api_key"] is True
        masked = data["google_maps_api_key"]
        # Should show first 4 + stars + last 4
        assert masked.startswith("AIza")
        assert masked.endswith("mnop")
        assert "****" in masked

    def test_put_api_key_saves_and_returns_masked(self, client, api_key):
        """PUT /api/settings/api-key validates, saves, and returns masked key."""
        with patch.dict(os.environ, {"API_KEY": api_key}):
            with patch("apps.kerala_delivery.api.main._validate_google_api_key", new_callable=AsyncMock, return_value=(True, "API key is valid")):
                with patch("apps.kerala_delivery.api.main.repo.set_setting", new_callable=AsyncMock):
                    resp = client.put(
                        "/api/settings/api-key",
                        json={"api_key": "AIzaSyD1234567890abcdefghijklmnop"},
                        headers={"X-API-Key": api_key},
                    )

        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True
        assert data["masked_key"].startswith("AIza")

    def test_put_api_key_rejects_invalid(self, client, api_key):
        """PUT /api/settings/api-key returns 400 for invalid key."""
        with patch.dict(os.environ, {"API_KEY": api_key}):
            with patch("apps.kerala_delivery.api.main._validate_google_api_key", new_callable=AsyncMock, return_value=(False, "Google API returned: REQUEST_DENIED")):
                resp = client.put(
                    "/api/settings/api-key",
                    json={"api_key": "invalid-key"},
                    headers={"X-API-Key": api_key},
                )

        assert resp.status_code == 400

    def test_validate_api_key_endpoint(self, client, api_key):
        """POST /api/settings/api-key/validate tests key without saving."""
        with patch.dict(os.environ, {"API_KEY": api_key}):
            with patch("apps.kerala_delivery.api.main._validate_google_api_key", new_callable=AsyncMock, return_value=(True, "API key is valid")):
                resp = client.post(
                    "/api/settings/api-key/validate",
                    json={"api_key": "AIzaSyD1234567890abcdefghijklmnop"},
                    headers={"X-API-Key": api_key},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["valid"] is True


# =============================================================================
# API Endpoint Tests: Geocode Cache
# =============================================================================


class TestCacheEndpoints:
    """Test geocode cache stats, export, import, and clear endpoints."""

    def test_get_cache_stats(self, client, api_key):
        """GET /api/geocode-cache/stats returns correct structure."""
        stats = {
            "total_entries": 50,
            "total_hits": 200,
            "api_calls_saved": 200,
            "estimated_savings_usd": 1.0,
        }
        with patch.dict(os.environ, {"API_KEY": api_key}):
            with patch("apps.kerala_delivery.api.main.repo.get_geocode_cache_stats", new_callable=AsyncMock, return_value=stats):
                resp = client.get("/api/geocode-cache/stats", headers={"X-API-Key": api_key})

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_entries"] == 50
        assert data["estimated_savings_usd"] == 1.0

    def test_export_cache_returns_json_download(self, client, api_key):
        """GET /api/geocode-cache/export returns JSON with Content-Disposition."""
        entries = [
            {
                "address_raw": "Vatakara",
                "address_norm": "vatakara",
                "latitude": 11.595,
                "longitude": 75.570,
                "source": "google",
                "confidence": 0.9,
                "hit_count": 5,
                "created_at": "2026-03-01T00:00:00+00:00",
            }
        ]
        with patch.dict(os.environ, {"API_KEY": api_key}):
            with patch("apps.kerala_delivery.api.main.repo.export_geocode_cache", new_callable=AsyncMock, return_value=entries):
                resp = client.get("/api/geocode-cache/export", headers={"X-API-Key": api_key})

        assert resp.status_code == 200
        assert "content-disposition" in resp.headers
        assert "geocode_cache_export.json" in resp.headers["content-disposition"]
        data = resp.json()
        assert len(data) == 1

    def test_import_cache_with_valid_file(self, client, api_key):
        """POST /api/geocode-cache/import adds entries from uploaded JSON."""
        import_data = [
            {
                "address_raw": "Vatakara Bus Stand",
                "latitude": 11.595,
                "longitude": 75.570,
                "source": "google",
                "confidence": 0.9,
            }
        ]
        file_content = json.dumps(import_data).encode("utf-8")

        with patch.dict(os.environ, {"API_KEY": api_key}):
            with patch("apps.kerala_delivery.api.main.repo.import_geocode_cache", new_callable=AsyncMock, return_value={"added": 1, "skipped": 0}):
                resp = client.post(
                    "/api/geocode-cache/import",
                    files={"file": ("cache.json", io.BytesIO(file_content), "application/json")},
                    headers={"X-API-Key": api_key},
                )

        assert resp.status_code == 200
        data = resp.json()
        assert data["added"] == 1
        assert data["skipped"] == 0

    def test_delete_cache(self, client, api_key):
        """DELETE /api/geocode-cache returns deleted count."""
        with patch.dict(os.environ, {"API_KEY": api_key}):
            with patch("apps.kerala_delivery.api.main.repo.clear_geocode_cache", new_callable=AsyncMock, return_value=25):
                resp = client.delete("/api/geocode-cache", headers={"X-API-Key": api_key})

        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] == 25


# =============================================================================
# Mask API Key Helper Tests
# =============================================================================


class TestMaskApiKey:
    """Test the mask_api_key helper function."""

    def test_mask_long_key(self):
        """Keys longer than 8 chars show first 4 + stars + last 4."""
        from apps.kerala_delivery.api.main import mask_api_key

        result = mask_api_key("AIzaSyD1234567890abcdefghijklmnop")
        assert result.startswith("AIza")
        assert result.endswith("mnop")
        assert "****" in result

    def test_mask_short_key(self):
        """Keys 8 chars or fewer return all stars."""
        from apps.kerala_delivery.api.main import mask_api_key

        result = mask_api_key("12345678")
        assert result == "****"

    def test_mask_empty_key(self):
        """Empty key returns stars."""
        from apps.kerala_delivery.api.main import mask_api_key

        result = mask_api_key("")
        assert result == "****"
