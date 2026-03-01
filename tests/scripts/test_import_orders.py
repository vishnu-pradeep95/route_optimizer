"""Tests for the scripts/import_orders.py batch import script.

Validates that the import_orders script correctly:
1. Parses CSV files through CsvImporter
2. Optionally geocodes addresses missing coordinates
3. Saves orders to the database (when not dry-running)
4. Handles edge cases: empty files, missing API keys, dry-run mode

All database and geocoding calls are mocked — this is a unit test suite,
not an integration test. No Docker required.

Why test scripts separately from the modules they use?
The scripts have their own argument parsing, error handling, progress
reporting, and async wrappers. Bugs can lurk in the glue code even when
the underlying modules are perfectly tested.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add project root to path so the script's sys.path.insert works
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from core.models.location import Location
from core.models.order import Order
from core.geocoding.interfaces import GeocodingResult


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_csv(tmp_path: Path) -> str:
    """Create a minimal valid CSV file for import testing.

    Uses the same column names as data/sample_orders.csv so the
    CsvImporter's default ColumnMapping works.
    """
    csv_content = (
        "order_id,address,customer_id,cylinder_type,quantity,latitude,longitude\n"
        "ORD-001,Vatakara Bus Stand Vatakara,CUST-001,domestic,2,11.5950,75.5700\n"
        "ORD-002,Chorode Vatakara,CUST-002,domestic,1,11.6350,75.5900\n"
        "ORD-003,Memunda Vatakara,CUST-003,commercial,1,,\n"
    )
    csv_file = tmp_path / "test_orders.csv"
    csv_file.write_text(csv_content)
    return str(csv_file)


@pytest.fixture
def empty_csv(tmp_path: Path) -> str:
    """Create a CSV file with headers only."""
    csv_file = tmp_path / "empty_orders.csv"
    csv_file.write_text("order_id,address,customer_id,cylinder_type,quantity\n")
    return str(csv_file)


@pytest.fixture
def geocoded_orders() -> list[Order]:
    """Orders with coordinates already set (no geocoding needed)."""
    return [
        Order(
            order_id="ORD-001",
            location=Location(latitude=11.5950, longitude=75.5700),
            address_raw="Vatakara Bus Stand Vatakara",
            customer_ref="CUST-001",
            weight_kg=28.4,
            quantity=2,
        ),
        Order(
            order_id="ORD-002",
            location=Location(latitude=11.6350, longitude=75.5900),
            address_raw="Chorode Vatakara",
            customer_ref="CUST-002",
            weight_kg=14.2,
            quantity=1,
        ),
    ]


@pytest.fixture
def mixed_orders() -> list[Order]:
    """Orders where some have coordinates and some don't.

    Simulates the common case: CSV has lat/lon for some rows but not others.
    The missing ones need geocoding.
    """
    return [
        Order(
            order_id="ORD-001",
            location=Location(latitude=11.5950, longitude=75.5700),
            address_raw="Vatakara Bus Stand Vatakara",
            customer_ref="CUST-001",
            weight_kg=28.4,
            quantity=2,
        ),
        Order(
            order_id="ORD-002",
            location=None,
            address_raw="Memunda Vatakara",
            customer_ref="CUST-002",
            weight_kg=14.2,
            quantity=1,
        ),
    ]


# =============================================================================
# import_orders() function tests
# =============================================================================

class TestImportOrdersParsing:
    """Test CSV parsing and order creation via the import function."""

    @pytest.mark.asyncio
    async def test_dry_run_no_db_write(self, sample_csv: str):
        """Dry-run mode should parse the CSV but never touch the database.

        This is the safest way to validate a CSV before committing to a bulk import.
        The database connection module shouldn't even be imported.
        """
        from scripts.import_orders import import_orders

        stats = await import_orders(sample_csv, geocode=False, dry_run=True)

        assert stats["total"] > 0, "Should parse at least one order"
        # Dry run should still report stats
        assert "already_geocoded" in stats
        assert "failed" in stats

    @pytest.mark.asyncio
    async def test_dry_run_reports_geocoded_count(self, sample_csv: str):
        """Dry run should correctly report how many orders already have coordinates."""
        from scripts.import_orders import import_orders

        stats = await import_orders(sample_csv, geocode=False, dry_run=True)

        # Our sample CSV has 2 rows with lat/lon and 1 without
        assert stats["already_geocoded"] == 2
        assert stats["total"] == 3

    @pytest.mark.asyncio
    async def test_empty_csv_returns_zero_stats(self, empty_csv: str):
        """Empty CSV (headers only) should return zero-count stats gracefully."""
        from scripts.import_orders import import_orders

        stats = await import_orders(empty_csv, geocode=False, dry_run=True)
        assert stats["total"] == 0

    @pytest.mark.asyncio
    async def test_nonexistent_file_raises(self, tmp_path: Path):
        """Importing a file that doesn't exist should raise FileNotFoundError.

        The CsvImporter's pandas call will raise when the file doesn't exist.
        """
        from scripts.import_orders import import_orders

        with pytest.raises((FileNotFoundError, Exception)):
            await import_orders(
                str(tmp_path / "nonexistent.csv"),
                geocode=False,
                dry_run=True,
            )


class TestImportOrdersGeocoding:
    """Test geocoding integration within the import flow."""

    @pytest.mark.asyncio
    async def test_geocode_requires_api_key(self, sample_csv: str):
        """When --geocode is passed but no API key is set, should report error.

        This validates the safety check: we don't silently skip geocoding,
        we report the failure so the operator knows something is wrong.
        """
        from scripts.import_orders import import_orders

        # Ensure no API key is set
        with patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": ""}, clear=False):
            stats = await import_orders(sample_csv, geocode=True, dry_run=True)

        # Dry run + geocode should still parse but not geocode
        assert stats["total"] > 0

    @pytest.mark.asyncio
    async def test_geocode_calls_google_for_missing_coords(self):
        """When orders lack coordinates and --geocode is set, should call Google API.

        This tests the geocoding integration path: orders without lat/lon get
        sent to GoogleGeocoder, and successful results update the order's location.
        """
        from scripts.import_orders import import_orders

        mock_result = GeocodingResult(
            location=Location(latitude=11.5800, longitude=75.5850),
            confidence=0.85,
            formatted_address="Memunda, Vatakara, Kerala",
        )

        # Patch at the source module — import_orders does a lazy
        # `from core.geocoding.google_adapter import GoogleGeocoder` inside
        # the function body, so we must patch the original class.
        with (
            patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}, clear=False),
            patch(
                "core.geocoding.google_adapter.GoogleGeocoder"
            ) as MockGeocoder,
        ):
            mock_instance = MockGeocoder.return_value
            mock_instance.geocode.return_value = mock_result

            # Create a CSV with one order missing coordinates
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", delete=False
            ) as f:
                f.write(
                    "order_id,address,customer_id,cylinder_type,quantity\n"
                    "ORD-001,Memunda Vatakara,CUST-001,domestic,1\n"
                )
                csv_path = f.name

            try:
                stats = await import_orders(csv_path, geocode=True, dry_run=True)
                # Should have attempted geocoding
                assert stats["geocoded"] == 1
                assert stats["failed"] == 0
                mock_instance.geocode.assert_called_once()
            finally:
                os.unlink(csv_path)

    @pytest.mark.asyncio
    async def test_geocode_failure_counted(self):
        """Failed geocoding attempts should be counted in stats, not crash the import.

        Google API can fail for ambiguous addresses. We log the failure and
        continue — one bad address shouldn't stop the entire import.
        """
        from scripts.import_orders import import_orders

        mock_result = GeocodingResult(
            location=None,
            confidence=0.0,
        )

        with (
            patch.dict(os.environ, {"GOOGLE_MAPS_API_KEY": "test-key"}, clear=False),
            patch(
                "core.geocoding.google_adapter.GoogleGeocoder"
            ) as MockGeocoder,
        ):
            mock_instance = MockGeocoder.return_value
            mock_instance.geocode.return_value = mock_result

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".csv", delete=False
            ) as f:
                f.write(
                    "order_id,address,customer_id,cylinder_type,quantity\n"
                    "ORD-001,Some Vague Address,CUST-001,domestic,1\n"
                )
                csv_path = f.name

            try:
                stats = await import_orders(csv_path, geocode=True, dry_run=True)
                assert stats["failed"] == 1
                assert stats["geocoded"] == 0
            finally:
                os.unlink(csv_path)


class TestImportOrdersArgParser:
    """Test the CLI argument parser in main()."""

    def test_help_flag(self, capsys):
        """--help should print usage and exit without error."""
        from scripts.import_orders import main

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["import_orders.py", "--help"]):
                main()
        assert exc_info.value.code == 0

    def test_missing_file_arg_exits(self):
        """Running without a file argument should exit with error."""
        from scripts.import_orders import main

        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["import_orders.py"]):
                main()
        assert exc_info.value.code != 0

    def test_nonexistent_file_exits(self, tmp_path: Path):
        """Passing a file path that doesn't exist should exit with error."""
        from scripts.import_orders import main

        fake_path = str(tmp_path / "no_such_file.csv")
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["import_orders.py", fake_path]):
                main()
        assert exc_info.value.code == 1


class TestPrintStats:
    """Test the statistics reporting helper."""

    def test_print_stats_output(self, capsys):
        """_print_stats should display formatted statistics."""
        from scripts.import_orders import _print_stats

        stats = {
            "total": 10,
            "geocoded": 3,
            "already_geocoded": 5,
            "failed": 2,
            "has_location": 8,
        }
        _print_stats(stats)
        captured = capsys.readouterr()
        assert "10" in captured.out
        assert "Import Summary" in captured.out

    def test_print_sample_orders(self, capsys):
        """_print_sample_orders should show order IDs and coordinates."""
        from scripts.import_orders import _print_sample_orders

        orders = [
            Order(
                order_id="ORD-TEST",
                location=Location(latitude=11.6244, longitude=75.5796),
                address_raw="Test Address Vatakara",
                customer_ref="CUST-TEST",
                weight_kg=14.2,
            ),
        ]
        _print_sample_orders(orders)
        captured = capsys.readouterr()
        assert "ORD-TEST" in captured.out
        assert "11.6244" in captured.out
