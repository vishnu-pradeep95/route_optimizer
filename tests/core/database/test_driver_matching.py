"""Tests for driver name normalization, fuzzy matching, and repository CRUD.

Phase 16: Driver Database Foundation.

Tests:
1. normalize_driver_name: whitespace collapse, uppercasing, trimming
2. find_similar_drivers: fuzzy matching with RapidFuzz fuzz.ratio
3. Driver CRUD: create, read, update, deactivate, reactivate
4. get_driver_route_counts: route count aggregation per driver

All repository tests use mocked AsyncSession -- no real database needed.
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.database.models import DriverDB


# =============================================================================
# normalize_driver_name Tests
# =============================================================================


class TestNormalizeDriverName:
    """Test the name normalization function for driver matching."""

    def test_basic_uppercase(self):
        """Converts lowercase to uppercase."""
        from core.database.repository import normalize_driver_name

        assert normalize_driver_name("suresh kumar") == "SURESH KUMAR"

    def test_strips_whitespace(self):
        """Strips leading and trailing whitespace."""
        from core.database.repository import normalize_driver_name

        assert normalize_driver_name("  suresh kumar  ") == "SURESH KUMAR"

    def test_collapses_multiple_spaces(self):
        """Collapses multiple internal spaces to single space."""
        from core.database.repository import normalize_driver_name

        assert normalize_driver_name("  suresh   kumar  ") == "SURESH KUMAR"

    def test_already_normalized(self):
        """Already-normalized names pass through unchanged."""
        from core.database.repository import normalize_driver_name

        assert normalize_driver_name("SURESH KUMAR") == "SURESH KUMAR"

    def test_single_name(self):
        """Single name without spaces."""
        from core.database.repository import normalize_driver_name

        assert normalize_driver_name("rajesh") == "RAJESH"

    def test_tabs_and_newlines(self):
        """Tabs and newlines are treated as whitespace."""
        from core.database.repository import normalize_driver_name

        assert normalize_driver_name("suresh\tkumar\n") == "SURESH KUMAR"

    def test_empty_string(self):
        """Empty string normalizes to empty string."""
        from core.database.repository import normalize_driver_name

        assert normalize_driver_name("") == ""

    def test_single_character(self):
        """Single character normalizes correctly."""
        from core.database.repository import normalize_driver_name

        assert normalize_driver_name("a") == "A"


# =============================================================================
# find_similar_drivers Tests (mocked session)
# =============================================================================


def _make_driver(name: str, name_normalized: str, is_active: bool = True, driver_id: uuid.UUID | None = None) -> DriverDB:
    """Create a mock DriverDB instance for testing."""
    driver = MagicMock(spec=DriverDB)
    driver.id = driver_id or uuid.uuid4()
    driver.name = name
    driver.name_normalized = name_normalized
    driver.is_active = is_active
    driver.created_at = datetime.now(timezone.utc)
    driver.updated_at = datetime.now(timezone.utc)
    return driver


class TestFindSimilarDrivers:
    """Test fuzzy name matching using RapidFuzz."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession with preset drivers."""
        session = AsyncMock()
        return session

    def _setup_drivers(self, session: AsyncMock, drivers: list[DriverDB]):
        """Configure the mock session to return the given drivers."""
        # Mock the result of session.execute(select(DriverDB))
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = drivers
        mock_result.scalars.return_value = mock_scalars
        session.execute.return_value = mock_result

    @pytest.mark.asyncio
    async def test_finds_similar_name(self, mock_session):
        """find_similar_drivers matches 'MOHAN L' to 'Mohan Lal' (score ~87.5)."""
        from core.database.repository import find_similar_drivers

        drivers = [
            _make_driver("Mohan Lal", "MOHAN LAL"),
            _make_driver("Rajesh P", "RAJESH P"),
        ]
        self._setup_drivers(mock_session, drivers)

        matches = await find_similar_drivers(mock_session, "MOHAN L")
        # Should find Mohan Lal as a match (ratio ~87.5, above 85 threshold)
        matched_names = [d.name for d, score in matches]
        assert "Mohan Lal" in matched_names

    @pytest.mark.asyncio
    async def test_borderline_below_threshold(self, mock_session):
        """find_similar_drivers('SURESH K') does NOT match 'SURESH KUMAR' (score 80 < 85)."""
        from core.database.repository import find_similar_drivers

        drivers = [
            _make_driver("Suresh Kumar", "SURESH KUMAR"),
        ]
        self._setup_drivers(mock_session, drivers)

        matches = await find_similar_drivers(mock_session, "SURESH K")
        # fuzz.ratio("SURESH K", "SURESH KUMAR") = 80.0, below 85 threshold
        assert len(matches) == 0

    @pytest.mark.asyncio
    async def test_does_not_match_different_names(self, mock_session):
        """find_similar_drivers('RAJESH') does NOT match 'SURESH'."""
        from core.database.repository import find_similar_drivers

        drivers = [
            _make_driver("Suresh Kumar", "SURESH KUMAR"),
        ]
        self._setup_drivers(mock_session, drivers)

        matches = await find_similar_drivers(mock_session, "RAJESH")
        # RAJESH vs SURESH KUMAR should be below threshold
        assert len(matches) == 0

    @pytest.mark.asyncio
    async def test_exclude_id_filters_driver(self, mock_session):
        """find_similar_drivers excludes driver with exclude_id."""
        from core.database.repository import find_similar_drivers

        driver_id = uuid.uuid4()
        drivers = [
            _make_driver("Suresh Kumar", "SURESH KUMAR", driver_id=driver_id),
        ]
        self._setup_drivers(mock_session, drivers)

        matches = await find_similar_drivers(mock_session, "SURESH KUMAR", exclude_id=driver_id)
        assert len(matches) == 0

    @pytest.mark.asyncio
    async def test_includes_deactivated_drivers(self, mock_session):
        """find_similar_drivers includes deactivated drivers (per locked decision)."""
        from core.database.repository import find_similar_drivers

        drivers = [
            _make_driver("Suresh Kumar", "SURESH KUMAR", is_active=False),
        ]
        self._setup_drivers(mock_session, drivers)

        matches = await find_similar_drivers(mock_session, "SURESH KUMAR")
        assert len(matches) == 1

    @pytest.mark.asyncio
    async def test_exact_match_scores_100(self, mock_session):
        """Exact name match scores 100."""
        from core.database.repository import find_similar_drivers

        drivers = [
            _make_driver("Suresh Kumar", "SURESH KUMAR"),
        ]
        self._setup_drivers(mock_session, drivers)

        matches = await find_similar_drivers(mock_session, "SURESH KUMAR")
        assert len(matches) == 1
        _, score = matches[0]
        assert score == 100.0

    @pytest.mark.asyncio
    async def test_results_sorted_by_score_descending(self, mock_session):
        """Matches are sorted by score (highest first)."""
        from core.database.repository import find_similar_drivers

        drivers = [
            _make_driver("Suresh K", "SURESH K"),
            _make_driver("Suresh Kumar", "SURESH KUMAR"),
            _make_driver("Suresh Kumar K", "SURESH KUMAR K"),
        ]
        self._setup_drivers(mock_session, drivers)

        matches = await find_similar_drivers(mock_session, "SURESH KUMAR")
        if len(matches) > 1:
            scores = [score for _, score in matches]
            assert scores == sorted(scores, reverse=True)


# =============================================================================
# Driver CRUD Tests (mocked session)
# =============================================================================


class TestDriverCRUD:
    """Test driver create/read/update/deactivate/reactivate."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        session = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_create_driver_title_cases_name(self, mock_session):
        """create_driver stores title-cased name."""
        from core.database.repository import create_driver

        driver = await create_driver(mock_session, "suresh kumar")
        assert driver.name == "Suresh Kumar"

    @pytest.mark.asyncio
    async def test_create_driver_normalizes_name(self, mock_session):
        """create_driver stores uppercase name_normalized."""
        from core.database.repository import create_driver

        driver = await create_driver(mock_session, "suresh kumar")
        assert driver.name_normalized == "SURESH KUMAR"

    @pytest.mark.asyncio
    async def test_create_driver_is_active_by_default(self, mock_session):
        """create_driver creates active driver."""
        from core.database.repository import create_driver

        driver = await create_driver(mock_session, "Test Driver")
        assert driver.is_active is True

    @pytest.mark.asyncio
    async def test_create_driver_calls_session_add(self, mock_session):
        """create_driver adds driver to session and flushes."""
        from core.database.repository import create_driver

        await create_driver(mock_session, "Test Driver")
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_drivers_default(self, mock_session):
        """get_all_drivers returns all drivers by default."""
        from core.database.repository import get_all_drivers

        drivers = [
            _make_driver("Active", "ACTIVE", is_active=True),
            _make_driver("Inactive", "INACTIVE", is_active=False),
        ]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = drivers
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await get_all_drivers(mock_session)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_all_drivers_active_only(self, mock_session):
        """get_all_drivers with active_only=True filters inactive."""
        from core.database.repository import get_all_drivers

        active_drivers = [_make_driver("Active", "ACTIVE", is_active=True)]
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = active_drivers
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        result = await get_all_drivers(mock_session, active_only=True)
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_get_driver_by_id_found(self, mock_session):
        """get_driver_by_id returns driver when found."""
        from core.database.repository import get_driver_by_id

        driver_id = uuid.uuid4()
        driver = _make_driver("Test", "TEST", driver_id=driver_id)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = driver
        mock_session.execute.return_value = mock_result

        result = await get_driver_by_id(mock_session, driver_id)
        assert result is not None
        assert result.name == "Test"

    @pytest.mark.asyncio
    async def test_get_driver_by_id_not_found(self, mock_session):
        """get_driver_by_id returns None when not found."""
        from core.database.repository import get_driver_by_id

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await get_driver_by_id(mock_session, uuid.uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_update_driver_name_changes_both(self, mock_session):
        """update_driver_name changes both name and name_normalized."""
        from core.database.repository import update_driver_name

        # Mock finding the driver
        driver = _make_driver("Old Name", "OLD NAME")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = driver
        mock_session.execute.return_value = mock_result

        result = await update_driver_name(mock_session, driver.id, "New Name")
        assert result is True

    @pytest.mark.asyncio
    async def test_update_driver_name_not_found(self, mock_session):
        """update_driver_name returns False for non-existent driver."""
        from core.database.repository import update_driver_name

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await update_driver_name(mock_session, uuid.uuid4(), "New Name")
        assert result is False

    @pytest.mark.asyncio
    async def test_deactivate_driver_success(self, mock_session):
        """deactivate_driver sets is_active=False, returns True."""
        from core.database.repository import deactivate_driver

        driver = _make_driver("Test", "TEST")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = driver
        mock_session.execute.return_value = mock_result

        result = await deactivate_driver(mock_session, driver.id)
        assert result is True

    @pytest.mark.asyncio
    async def test_deactivate_driver_not_found(self, mock_session):
        """deactivate_driver returns False for non-existent driver."""
        from core.database.repository import deactivate_driver

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await deactivate_driver(mock_session, uuid.uuid4())
        assert result is False

    @pytest.mark.asyncio
    async def test_reactivate_driver_success(self, mock_session):
        """reactivate_driver sets is_active=True, returns True."""
        from core.database.repository import reactivate_driver

        driver = _make_driver("Test", "TEST", is_active=False)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = driver
        mock_session.execute.return_value = mock_result

        result = await reactivate_driver(mock_session, driver.id)
        assert result is True

    @pytest.mark.asyncio
    async def test_reactivate_driver_not_found(self, mock_session):
        """reactivate_driver returns False for non-existent driver."""
        from core.database.repository import reactivate_driver

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        result = await reactivate_driver(mock_session, uuid.uuid4())
        assert result is False


# =============================================================================
# get_driver_route_counts Tests
# =============================================================================


class TestDriverRouteCounts:
    """Test route count aggregation per driver."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession."""
        session = AsyncMock()
        return session

    @pytest.mark.asyncio
    async def test_returns_counts_dict(self, mock_session):
        """get_driver_route_counts returns dict of driver_id -> count."""
        from core.database.repository import get_driver_route_counts

        driver_id_1 = uuid.uuid4()
        driver_id_2 = uuid.uuid4()

        # Mock the query result
        mock_result = MagicMock()
        mock_result.all.return_value = [
            (driver_id_1, 5),
            (driver_id_2, 3),
        ]
        mock_session.execute.return_value = mock_result

        counts = await get_driver_route_counts(mock_session)
        assert counts[driver_id_1] == 5
        assert counts[driver_id_2] == 3

    @pytest.mark.asyncio
    async def test_empty_result(self, mock_session):
        """get_driver_route_counts returns empty dict when no routes."""
        from core.database.repository import get_driver_route_counts

        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute.return_value = mock_result

        counts = await get_driver_route_counts(mock_session)
        assert counts == {}
