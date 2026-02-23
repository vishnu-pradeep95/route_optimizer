"""Tests for the scripts/geocode_batch.py batch geocoding script.

Validates that the geocode_batch script correctly:
1. Reads addresses from CSV files
2. Uses cache-first strategy (PostGIS cache before Google API)
3. Handles dry-run mode (check cache but don't call API)
4. Tracks statistics (cache hits, API calls, successes, failures)
5. Applies rate limiting between Google API calls

All database and geocoding calls are mocked — no Docker required.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.models.location import Location
from core.geocoding.interfaces import GeocodingResult


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def address_csv(tmp_path: Path) -> str:
    """Create a CSV file with an 'address' column for geocoding.

    Three addresses of varying quality — simulates real-world input:
    - Well-formed address (should geocode successfully)
    - Landmark-based address (common in Kerala)
    - Vague address (likely to fail or low confidence)
    """
    csv_content = (
        "address,customer_id\n"
        "Edappally Junction Kochi Kerala,CUST-001\n"
        "Near Temple Marine Drive Kochi,CUST-002\n"
        "Some Building Somewhere,CUST-003\n"
    )
    csv_file = tmp_path / "addresses.csv"
    csv_file.write_text(csv_content)
    return str(csv_file)


@pytest.fixture
def custom_column_csv(tmp_path: Path) -> str:
    """CSV with a non-default address column name."""
    csv_content = (
        "raw_address,name\n"
        "MG Road Kochi,Customer A\n"
        "Palarivattom Kochi,Customer B\n"
    )
    csv_file = tmp_path / "custom.csv"
    csv_file.write_text(csv_content)
    return str(csv_file)


# =============================================================================
# read_addresses_from_csv() tests
# =============================================================================

class TestReadAddressesFromCsv:
    """Test CSV address reading with deduplication and filtering."""

    def test_reads_default_address_column(self, address_csv: str):
        """Should read addresses from the 'address' column by default."""
        from scripts.geocode_batch import read_addresses_from_csv

        addresses = read_addresses_from_csv(address_csv)
        assert len(addresses) == 3

    def test_reads_custom_column_name(self, custom_column_csv: str):
        """Should accept a custom column name via --address-column flag."""
        from scripts.geocode_batch import read_addresses_from_csv

        addresses = read_addresses_from_csv(
            custom_column_csv, address_column="raw_address"
        )
        assert len(addresses) == 2
        assert "MG Road Kochi" in addresses

    def test_raises_on_missing_column(self, address_csv: str):
        """Should raise ValueError when the specified column doesn't exist.

        This is a user-facing error: if they pass --address-column wrong_name,
        we should tell them which columns ARE available.
        """
        from scripts.geocode_batch import read_addresses_from_csv

        with pytest.raises(ValueError, match="not found in CSV"):
            read_addresses_from_csv(address_csv, address_column="nonexistent")

    def test_deduplicates_addresses(self, tmp_path: Path):
        """Duplicate addresses should be filtered — no point geocoding twice.

        Google charges $5/1000 requests, so deduplication directly saves money.
        """
        from scripts.geocode_batch import read_addresses_from_csv

        csv_content = (
            "address\n"
            "Edappally Junction Kochi\n"
            "Edappally Junction Kochi\n"
            "Marine Drive Kochi\n"
        )
        csv_file = tmp_path / "dupes.csv"
        csv_file.write_text(csv_content)

        addresses = read_addresses_from_csv(str(csv_file))
        assert len(addresses) == 2, "Duplicates should be removed"

    def test_filters_empty_addresses(self, tmp_path: Path):
        """Empty/whitespace-only address rows should be skipped."""
        from scripts.geocode_batch import read_addresses_from_csv

        csv_content = (
            "address\n"
            "Edappally Junction Kochi\n"
            "  \n"
            "\n"
        )
        csv_file = tmp_path / "empties.csv"
        csv_file.write_text(csv_content)

        addresses = read_addresses_from_csv(str(csv_file))
        assert len(addresses) == 1


# =============================================================================
# read_addresses_from_db() tests
# =============================================================================

class TestReadAddressesFromDb:
    """Test reading ungeocoded addresses from the database.

    The --from-db path queries OrderDB for orders that have address_raw
    but no location (geometry is NULL). These are orders imported with
    text addresses that still need geocoding.
    """

    @pytest.mark.asyncio
    async def test_returns_ungeocoded_addresses(self):
        """Should return addresses from orders that have no coordinates."""
        from scripts.geocode_batch import read_addresses_from_db

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [
            ("Edappally Junction Kochi",),
            ("Marine Drive Kochi",),
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def mock_get_session():
            yield mock_session

        with patch("core.database.connection.get_session", mock_get_session):
            addresses = await read_addresses_from_db()

        assert len(addresses) == 2
        assert "Edappally Junction Kochi" in addresses

    @pytest.mark.asyncio
    async def test_returns_empty_when_all_geocoded(self):
        """Should return empty list if all orders already have coordinates."""
        from scripts.geocode_batch import read_addresses_from_db

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def mock_get_session():
            yield mock_session

        with patch("core.database.connection.get_session", mock_get_session):
            addresses = await read_addresses_from_db()

        assert len(addresses) == 0


# =============================================================================
# geocode_batch() async function tests
# =============================================================================

class TestGeocodeBatch:
    """Test the core geocoding batch function with cache-first strategy."""

    @pytest.mark.asyncio
    async def test_dry_run_checks_cache_only(self):
        """Dry run should check the cache but never call Google API.

        Use case: operator wants to see cache hit rate before spending
        any API credits.
        """
        from scripts.geocode_batch import geocode_batch

        mock_session = AsyncMock()

        # Mock get_session to yield our mock session
        async def mock_get_session():
            yield mock_session

        # Patch at the source modules — geocode_batch imports lazily inside the function,
        # so we must patch the original modules, not attributes on the script module.
        with (
            patch("core.database.connection.get_session", mock_get_session),
            patch("core.database.repository.get_cached_geocode", new_callable=AsyncMock, return_value=None) as mock_cache,
        ):
            stats = await geocode_batch(
                ["Address 1", "Address 2"], dry_run=True
            )

        assert stats["skipped_dry_run"] == 2
        assert stats["api_calls"] == 0, "Dry run should never call API"
        assert stats["cache_hits"] == 0

    @pytest.mark.asyncio
    async def test_cache_hit_skips_api(self):
        """Addresses already in the PostGIS cache should skip the Google API call.

        This is the primary cost-saving mechanism: repeat customers = free geocoding.
        """
        from scripts.geocode_batch import geocode_batch

        cached_location = Location(latitude=9.9816, longitude=76.2996)
        mock_session = AsyncMock()

        async def mock_get_session():
            yield mock_session

        with (
            patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}, clear=False),
            patch("core.database.connection.get_session", mock_get_session),
            patch("core.database.repository.get_cached_geocode", new_callable=AsyncMock, return_value=cached_location),
        ):
            stats = await geocode_batch(["Address 1", "Address 2"])

        assert stats["cache_hits"] == 2
        assert stats["api_calls"] == 0

    @pytest.mark.asyncio
    async def test_cache_miss_calls_api_and_saves(self):
        """Cache misses should call Google API and save results to cache.

        Flow: cache miss → Google API → save_geocode_cache()
        This builds the local address database over time.
        """
        from scripts.geocode_batch import geocode_batch

        mock_result = GeocodingResult(
            location=Location(latitude=9.9674, longitude=76.2855),
            confidence=0.9,
            formatted_address="MG Road, Kochi",
        )
        mock_session = AsyncMock()

        async def mock_get_session():
            yield mock_session

        with (
            patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}, clear=False),
            patch("core.database.connection.get_session", mock_get_session),
            patch("core.database.repository.get_cached_geocode", new_callable=AsyncMock, return_value=None),
            patch("core.database.repository.save_geocode_cache", new_callable=AsyncMock) as mock_save,
            patch("core.geocoding.google_adapter.GoogleGeocoder") as MockGeocoder,
        ):
            mock_geocoder = MockGeocoder.return_value
            mock_geocoder.geocode.return_value = mock_result

            stats = await geocode_batch(["MG Road Kochi"])

        assert stats["api_calls"] == 1
        assert stats["api_success"] == 1
        mock_save.assert_called_once()

    @pytest.mark.asyncio
    async def test_api_failure_counted(self):
        """Failed Google API calls should be counted, not crash the batch.

        Some addresses are genuinely ungeocodable (typos, too vague).
        We track them in stats so the operator knows which addresses need
        manual correction.
        """
        from scripts.geocode_batch import geocode_batch

        mock_result = GeocodingResult(location=None, confidence=0.0)
        mock_session = AsyncMock()

        async def mock_get_session():
            yield mock_session

        with (
            patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}, clear=False),
            patch("core.database.connection.get_session", mock_get_session),
            patch("core.database.repository.get_cached_geocode", new_callable=AsyncMock, return_value=None),
            patch("core.geocoding.google_adapter.GoogleGeocoder") as MockGeocoder,
        ):
            mock_geocoder = MockGeocoder.return_value
            mock_geocoder.geocode.return_value = mock_result

            stats = await geocode_batch(["Vague Address"])

        assert stats["api_failed"] == 1
        assert stats["api_success"] == 0

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_error(self):
        """No API key + not dry-run should return an error dict.

        This prevents silent failures: if someone forgot to set the API key
        in .env, we tell them explicitly instead of just skipping geocoding.
        """
        from scripts.geocode_batch import geocode_batch

        with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": ""}, clear=False):
            stats = await geocode_batch(["some address"], dry_run=False)

        assert "error" in stats
        assert "API key" in stats["error"]

    @pytest.mark.asyncio
    async def test_mixed_cache_hits_and_misses(self):
        """Batch with some cached and some uncached addresses.

        Simulates the normal production flow: some repeat customers (cache hit),
        some new addresses (API call needed).
        """
        from scripts.geocode_batch import geocode_batch

        mock_result = GeocodingResult(
            location=Location(latitude=9.9312, longitude=76.2673),
            confidence=0.85,
        )
        mock_session = AsyncMock()

        async def mock_get_session():
            yield mock_session

        # First address: cache hit; second: cache miss
        cache_responses = [
            Location(latitude=9.9816, longitude=76.2996),  # hit
            None,  # miss
        ]

        with (
            patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}, clear=False),
            patch("core.database.connection.get_session", mock_get_session),
            patch("core.database.repository.get_cached_geocode", new_callable=AsyncMock, side_effect=cache_responses),
            patch("core.database.repository.save_geocode_cache", new_callable=AsyncMock),
            patch("core.geocoding.google_adapter.GoogleGeocoder") as MockGeocoder,
        ):
            mock_geocoder = MockGeocoder.return_value
            mock_geocoder.geocode.return_value = mock_result

            stats = await geocode_batch(["Cached Address", "New Address"])

        assert stats["cache_hits"] == 1
        assert stats["api_calls"] == 1
        assert stats["api_success"] == 1

    @pytest.mark.asyncio
    async def test_rate_limiting_between_api_calls(self):
        """Verify that asyncio.sleep() is called between Google API requests.

        Without rate limiting, large CSVs fire requests as fast as Python loops,
        risking HTTP 429 from Google. This test ensures the rate limiter can't
        be accidentally removed without a test failure.
        """
        from scripts.geocode_batch import geocode_batch

        mock_result = GeocodingResult(
            location=Location(latitude=9.9312, longitude=76.2673),
            confidence=0.85,
        )
        mock_session = AsyncMock()

        async def mock_get_session():
            yield mock_session

        with (
            patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}, clear=False),
            patch("core.database.connection.get_session", mock_get_session),
            patch("core.database.repository.get_cached_geocode", new_callable=AsyncMock, return_value=None),
            patch("core.database.repository.save_geocode_cache", new_callable=AsyncMock),
            patch("core.geocoding.google_adapter.GoogleGeocoder") as MockGeocoder,
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            mock_geocoder = MockGeocoder.return_value
            mock_geocoder.geocode.return_value = mock_result

            stats = await geocode_batch(["Address 1", "Address 2"])

        # Should have rate-limited once per API call
        assert mock_sleep.call_count == 2
        assert stats["api_calls"] == 2


# =============================================================================
# _print_stats() tests
# =============================================================================

class TestPrintStats:
    """Test the statistics display helper."""

    def test_print_stats_shows_summary(self, capsys):
        """Should display cache hit rate, API calls, and cost estimate."""
        from scripts.geocode_batch import _print_stats

        stats = {
            "total": 100,
            "cache_hits": 80,
            "api_calls": 20,
            "api_success": 18,
            "api_failed": 2,
        }
        _print_stats(stats)
        captured = capsys.readouterr()
        assert "100" in captured.out
        assert "80" in captured.out
        assert "Geocoding Batch Summary" in captured.out

    def test_print_stats_zero_total(self, capsys):
        """Should handle zero total addresses gracefully (no division by zero)."""
        from scripts.geocode_batch import _print_stats

        stats = {
            "total": 0,
            "cache_hits": 0,
            "api_calls": 0,
            "api_success": 0,
            "api_failed": 0,
        }
        _print_stats(stats)
        captured = capsys.readouterr()
        assert "N/A" in captured.out  # hit rate is N/A when total=0


# =============================================================================
# CLI argument parser tests
# =============================================================================

class TestArgParser:
    """Test the CLI argument parser in main()."""

    def test_help_flag(self, capsys):
        """--help should print usage info and exit cleanly."""
        from scripts.geocode_batch import main

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["geocode_batch.py", "--help"]):
                main()
        assert exc_info.value.code == 0

    def test_requires_source_argument(self):
        """Running without --from-csv or --from-db should fail.

        The two sources are mutually exclusive (argparse add_mutually_exclusive_group),
        but at least one is required.
        """
        from scripts.geocode_batch import main

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["geocode_batch.py"]):
                main()
        assert exc_info.value.code != 0

    def test_nonexistent_csv_file_exits(self, tmp_path: Path):
        """Passing a CSV path that doesn't exist should exit with error."""
        from scripts.geocode_batch import main

        fake_path = str(tmp_path / "no_such_file.csv")
        with pytest.raises(SystemExit) as exc_info:
            with patch(
                "sys.argv",
                ["geocode_batch.py", "--from-csv", fake_path],
            ):
                main()
        assert exc_info.value.code == 1
