"""Tests for DeliveryMan column validation in parse_upload endpoint.

Phase 19: The per-driver TSP pipeline requires a DeliveryMan column in
CDCMS exports. parse_upload must fail fast with a clear 400 error when
this column is missing or empty, before running driver auto-creation or
geocoding.
"""

import io
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from apps.kerala_delivery.api.main import app
from core.database.connection import get_session


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
    """FastAPI TestClient with DB session overridden and rate limiting disabled."""
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


class TestParseUploadDeliveryManColumn:
    """Tests for DeliveryMan column validation in parse_upload (Phase 19)."""

    @staticmethod
    def _make_cdcms_xlsx_without_deliveryman():
        """Create a CDCMS xlsx file WITHOUT a DeliveryMan column.

        Has the required CDCMS marker columns (OrderNo, ConsumerAddress,
        OrderStatus=Allocated-Printed) but is missing DeliveryMan entirely.
        """
        rows = []
        for i in range(3):
            rows.append({
                "OrderNo": str(517827 + i),
                "OrderStatus": "Allocated-Printed",
                "OrderDate": "14-02-2026 9:41",
                "OrderQuantity": "1",
                "AreaName": "VALLIKKADU",
                "ConsumerAddress": f"Address {517827 + i}",
            })

        df = pd.DataFrame(rows)
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        buf.seek(0)
        return buf.read(), "cdcms_no_deliveryman.xlsx"

    @staticmethod
    def _make_cdcms_xlsx_with_empty_deliveryman():
        """Create a CDCMS xlsx file with DeliveryMan column but all values empty/NaN."""
        rows = []
        for i in range(3):
            rows.append({
                "OrderNo": str(517827 + i),
                "OrderStatus": "Allocated-Printed",
                "OrderDate": "14-02-2026 9:41",
                "OrderQuantity": "1",
                "AreaName": "VALLIKKADU",
                "DeliveryMan": "",
                "ConsumerAddress": f"Address {517827 + i}",
            })

        df = pd.DataFrame(rows)
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        buf.seek(0)
        return buf.read(), "cdcms_empty_deliveryman.xlsx"

    @staticmethod
    def _make_cdcms_xlsx_with_deliveryman():
        """Create a valid CDCMS xlsx with DeliveryMan column populated."""
        rows = []
        for i in range(3):
            rows.append({
                "OrderNo": str(517827 + i),
                "OrderStatus": "Allocated-Printed",
                "OrderDate": "14-02-2026 9:41",
                "OrderQuantity": "1",
                "AreaName": "VALLIKKADU",
                "DeliveryMan": "SURESH KUMAR",
                "ConsumerAddress": f"Address {517827 + i}",
            })

        df = pd.DataFrame(rows)
        buf = io.BytesIO()
        df.to_excel(buf, index=False)
        buf.seek(0)
        return buf.read(), "cdcms_with_deliveryman.xlsx"

    def test_missing_deliveryman_column_returns_400(self, client, mock_session):
        """parse_upload returns 400 when DeliveryMan column is absent from CDCMS file."""
        xlsx_bytes, filename = self._make_cdcms_xlsx_without_deliveryman()

        resp = client.post(
            "/api/parse-upload",
            files={"file": (filename, xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )

        assert resp.status_code == 400
        data = resp.json()
        assert "DeliveryMan" in data["user_message"]
        assert "CDCMS export with driver assignments" in data["user_message"]
        assert data["error_code"] == "UPLOAD_INVALID_FORMAT"

    def test_empty_deliveryman_column_returns_400(self, client, mock_session):
        """parse_upload returns 400 when DeliveryMan column exists but all values are empty.

        When DeliveryMan values are all empty strings, the CDCMS preprocessor's
        placeholder filter removes all rows (empty string is in PLACEHOLDER_DRIVER_NAMES),
        resulting in an empty DataFrame. This triggers the "No Allocated-Printed orders"
        error before the DeliveryMan check is reached. Either error message is acceptable
        -- both tell the user to fix the file.
        """
        xlsx_bytes, filename = self._make_cdcms_xlsx_with_empty_deliveryman()

        resp = client.post(
            "/api/parse-upload",
            files={"file": (filename, xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )

        assert resp.status_code == 400
        data = resp.json()
        # Either the placeholder filter catches empty DeliveryMan (returning "No Allocated-Printed")
        # or the Phase 19 check catches missing delivery_man column content.
        assert data["error_code"] in ("UPLOAD_NO_VALID_ORDERS", "UPLOAD_INVALID_FORMAT")

    def test_valid_deliveryman_column_passes(self, client, mock_session):
        """parse_upload succeeds when DeliveryMan column has valid values."""
        xlsx_bytes, filename = self._make_cdcms_xlsx_with_deliveryman()

        with patch("apps.kerala_delivery.api.main.repo") as mock_repo:
            mock_repo.get_all_drivers = AsyncMock(return_value=[])
            mock_repo.find_similar_drivers = AsyncMock(return_value=[])

            async def mock_create_driver(session, name):
                driver = MagicMock()
                driver.id = uuid.uuid4()
                driver.name = name.strip().title()
                driver.is_active = True
                return driver

            mock_repo.create_driver = AsyncMock(side_effect=mock_create_driver)

            resp = client.post(
                "/api/parse-upload",
                files={"file": (filename, xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "upload_token" in data
        assert len(data["drivers"]) >= 1
