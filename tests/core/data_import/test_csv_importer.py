"""Tests for the CSV importer — handles CDCMS export files."""

import os
import tempfile

import pytest

from core.data_import.csv_importer import CsvImporter, ColumnMapping, ImportResult, RowError
from core.data_import.interfaces import DataImporter


class TestCsvImporter:
    """Tests for importing CDCMS delivery data from CSV files."""

    def test_implements_data_importer_protocol(self):
        """Verify CsvImporter satisfies the DataImporter protocol.

        Protocol compliance ensures we can swap CSV for Google Sheets or
        API-based importers without changing the optimization pipeline.
        """
        importer = CsvImporter()
        assert isinstance(importer, DataImporter)

    def _create_csv(self, content: str) -> str:
        """Helper: write CSV content to a temp file and return the path."""
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w") as f:
            f.write(content)
        return path

    def test_import_standard_csv(self):
        """Import a standard CSV with domestic LPG orders.

        Uses cylinder_weight_lookup to resolve 'domestic' -> 14.2 kg,
        proving the lookup works — not just a coincidence with the default.
        """
        csv = self._create_csv(
            "order_id,address,customer_id,cylinder_type,quantity,priority,notes\n"
            'ORD-001,"Payyoli, Vatakara",CUST-001,domestic,2,2,Ring bell\n'
            'ORD-002,"Chorode, Vatakara",CUST-002,domestic,1,1,Urgent\n'
        )
        try:
            # Pass explicit cylinder weights so the test verifies lookup behavior
            kerala_weights = {"domestic": 14.2, "commercial": 19.0, "industrial": 47.0}
            importer = CsvImporter(cylinder_weight_lookup=kerala_weights)
            result = importer.import_orders(csv)
            assert len(result.orders) == 2
            assert result.orders[0].order_id == "ORD-001"
            assert result.orders[0].weight_kg == 28.4  # 14.2 x 2 via lookup
            assert result.orders[1].priority == 1
        finally:
            os.unlink(csv)

    def test_import_with_coordinates(self):
        """CSV with lat/lon columns produces geocoded orders."""
        csv = self._create_csv(
            "order_id,address,customer_id,weight_kg,latitude,longitude\n"
            "ORD-001,Vatakara,CUST-001,14.2,11.6244,75.5796\n"
        )
        try:
            importer = CsvImporter()
            result = importer.import_orders(csv)
            assert len(result.orders) == 1
            assert result.orders[0].is_geocoded
            assert result.orders[0].location.latitude == 11.6244
        finally:
            os.unlink(csv)

    def test_missing_address_skips_row(self):
        """Rows without an address are skipped and collected as validation error."""
        csv = self._create_csv(
            "order_id,address,customer_id,weight_kg\n"
            "ORD-001,,CUST-001,14.2\n"
            'ORD-002,"Valid Address",CUST-002,14.2\n'
        )
        try:
            importer = CsvImporter()
            result = importer.import_orders(csv)
            assert len(result.orders) == 1  # Bad row skipped
            assert result.orders[0].order_id == "ORD-002"
        finally:
            os.unlink(csv)

    def test_commercial_cylinder_weight(self):
        """Commercial cylinder type resolves to 19 kg when lookup is provided.

        Core module has no default cylinder weights (business-agnostic).
        The consuming app passes its own lookup — here we simulate what
        Kerala LPG config provides.
        """
        csv = self._create_csv(
            "order_id,address,customer_id,cylinder_type,quantity\n"
            'ORD-001,"Hotel XYZ, Vatakara",CUST-001,commercial,1\n'
        )
        try:
            # Kerala-specific weights, normally from apps/kerala_delivery/config.py
            kerala_weights = {"domestic": 14.2, "commercial": 19.0, "industrial": 47.0}
            importer = CsvImporter(cylinder_weight_lookup=kerala_weights)
            result = importer.import_orders(csv)
            assert result.orders[0].weight_kg == 19.0
        finally:
            os.unlink(csv)

    def test_custom_column_mapping(self):
        """Supports remapped column names for different CDCMS exports."""
        csv = self._create_csv(
            "booking_ref,delivery_address,consumer_no,weight\n"
            'BK-001,"Memunda, Vatakara",CON-001,14.2\n'
        )
        try:
            mapping = ColumnMapping(
                order_id="booking_ref",
                address="delivery_address",
                customer_ref="consumer_no",
                weight_kg="weight",
            )
            importer = CsvImporter(column_mapping=mapping)
            result = importer.import_orders(csv)
            assert len(result.orders) == 1
            assert result.orders[0].order_id == "BK-001"
            assert result.orders[0].customer_ref == "CON-001"
        finally:
            os.unlink(csv)

    def test_file_not_found(self):
        """Raise FileNotFoundError for missing files."""
        importer = CsvImporter()
        with pytest.raises(FileNotFoundError):
            importer.import_orders("/nonexistent/file.csv")

    def test_default_weight_when_no_type(self):
        """When no cylinder_type or weight_kg column, uses default weight."""
        csv = self._create_csv(
            "order_id,address,customer_id\n"
            'ORD-001,"Vatakara Address",CUST-001\n'
        )
        try:
            importer = CsvImporter(default_cylinder_weight_kg=14.2)
            result = importer.import_orders(csv)
            assert result.orders[0].weight_kg == 14.2
        finally:
            os.unlink(csv)

    def test_coordinate_bounds_rejects_out_of_range(self):
        """Coordinates outside configured bounds should be treated as ungeocoded.

        This ensures the CsvImporter's coordinate_bounds parameter works.
        A Mumbai food delivery app could pass (18.8, 19.3, 72.7, 73.0) for
        Mumbai-only bounds. Order is still imported but location=None.
        """
        csv = self._create_csv(
            "order_id,address,customer_id,weight_kg,latitude,longitude\n"
            # Point in Kerala — within India bounds
            "ORD-001,Vatakara,CUST-001,14.2,11.6244,75.5796\n"
            # Point in Antarctica — outside India bounds
            "ORD-002,South Pole,CUST-002,14.2,-85.0,0.0\n"
        )
        try:
            importer = CsvImporter(coordinate_bounds=(6.0, 37.0, 68.0, 97.5))
            result = importer.import_orders(csv)
            assert len(result.orders) == 2
            # First order within India -> geocoded
            assert result.orders[0].is_geocoded
            assert result.orders[0].location.latitude == 11.6244
            # Second order outside India -> NOT geocoded (needs geocoding)
            assert not result.orders[1].is_geocoded
        finally:
            os.unlink(csv)

    def test_no_bounds_accepts_all_valid_coordinates(self):
        """Without coordinate_bounds, any valid WGS84 coordinate is accepted."""
        csv = self._create_csv(
            "order_id,address,customer_id,weight_kg,latitude,longitude\n"
            "ORD-001,London,CUST-001,14.2,51.5074,-0.1278\n"
        )
        try:
            # No bounds — core module is business-agnostic
            importer = CsvImporter()
            result = importer.import_orders(csv)
            assert len(result.orders) == 1
            assert result.orders[0].is_geocoded
            assert result.orders[0].location.latitude == 51.5074
        finally:
            os.unlink(csv)

    # =========================================================================
    # NEW TESTS: ImportResult structured return type
    # =========================================================================

    def test_import_result_returns_structured_result(self):
        """import_orders() returns ImportResult with .orders, .errors, .warnings attributes."""
        csv = self._create_csv(
            "order_id,address,customer_id,weight_kg\n"
            'ORD-001,"Vatakara Address",CUST-001,14.2\n'
        )
        try:
            importer = CsvImporter()
            result = importer.import_orders(csv)
            # Must be an ImportResult, not a plain list
            assert isinstance(result, ImportResult)
            assert hasattr(result, "orders")
            assert hasattr(result, "errors")
            assert hasattr(result, "warnings")
            assert hasattr(result, "row_numbers")
            assert len(result.orders) == 1
            assert len(result.errors) == 0
            assert len(result.warnings) == 0
        finally:
            os.unlink(csv)

    def test_empty_address_collected_as_validation_error(self):
        """Empty address produces a RowError with row_number, column name, stage."""
        csv = self._create_csv(
            "order_id,address,customer_id,weight_kg\n"
            'ORD-001,"Valid Address",CUST-001,14.2\n'
            "ORD-002,,CUST-002,14.2\n"
            'ORD-003,"Another Valid",CUST-003,14.2\n'
        )
        try:
            importer = CsvImporter()
            result = importer.import_orders(csv)
            # 2 valid orders, 1 error for empty address
            assert len(result.orders) == 2
            assert len(result.errors) == 1

            error = result.errors[0]
            assert isinstance(error, RowError)
            # Row 3 in spreadsheet: header=row 1, ORD-001=row 2, ORD-002=row 3
            assert error.row_number == 3
            # Column name from ColumnMapping, not internal field name
            assert error.column == "address"
            assert error.stage == "validation"
            assert "address" in error.message.lower() or "empty" in error.message.lower()
        finally:
            os.unlink(csv)

    def test_empty_address_uses_original_column_name_in_error(self):
        """Error message uses the CSV column name from ColumnMapping, not internal name."""
        csv = self._create_csv(
            "booking_ref,ConsumerAddress,consumer_no,weight\n"
            "BK-001,,CON-001,14.2\n"
        )
        try:
            mapping = ColumnMapping(
                order_id="booking_ref",
                address="ConsumerAddress",
                customer_ref="consumer_no",
                weight_kg="weight",
            )
            importer = CsvImporter(column_mapping=mapping)
            result = importer.import_orders(csv)
            assert len(result.orders) == 0
            assert len(result.errors) == 1
            # Column name should be the original CSV column name
            assert result.errors[0].column == "ConsumerAddress"
            assert "ConsumerAddress" in result.errors[0].message
        finally:
            os.unlink(csv)

    def test_duplicate_order_id_collected_as_error(self):
        """Duplicate order_id in same CSV flags the second occurrence as error."""
        csv = self._create_csv(
            "order_id,address,customer_id,weight_kg\n"
            'ORD-001,"Address A",CUST-001,14.2\n'
            'ORD-001,"Address B",CUST-002,14.2\n'
            'ORD-002,"Address C",CUST-003,14.2\n'
        )
        try:
            importer = CsvImporter()
            result = importer.import_orders(csv)
            # First ORD-001 succeeds, second is flagged as duplicate
            assert len(result.orders) == 2
            assert result.orders[0].order_id == "ORD-001"
            assert result.orders[1].order_id == "ORD-002"

            assert len(result.errors) == 1
            dup_error = result.errors[0]
            assert dup_error.stage == "validation"
            assert "duplicate" in dup_error.message.lower() or "ORD-001" in dup_error.message
            # Row 3 in spreadsheet (header=1, first ORD-001=2, second ORD-001=3)
            assert dup_error.row_number == 3
        finally:
            os.unlink(csv)

    def test_invalid_weight_produces_warning_not_error(self):
        """Invalid weight value produces warning, order uses default 14.2kg."""
        csv = self._create_csv(
            "order_id,address,customer_id,weight_kg\n"
            'ORD-001,"Valid Address",CUST-001,abc\n'
        )
        try:
            importer = CsvImporter(default_cylinder_weight_kg=14.2)
            result = importer.import_orders(csv)
            # Order is still imported with default weight
            assert len(result.orders) == 1
            assert result.orders[0].weight_kg == 14.2
            # No errors — weight issues are warnings
            assert len(result.errors) == 0
            # Warning produced for the invalid weight
            assert len(result.warnings) == 1
            warning = result.warnings[0]
            assert warning.row_number == 2  # First data row
            assert "abc" in warning.message.lower() or "weight" in warning.message.lower()
        finally:
            os.unlink(csv)

    def test_row_numbers_are_spreadsheet_accurate(self):
        """Row numbers use 1-based spreadsheet convention: header=1, first data=2."""
        csv = self._create_csv(
            "order_id,address,customer_id,weight_kg\n"
            'ORD-001,"Valid Address 1",CUST-001,14.2\n'
            "ORD-002,,CUST-002,14.2\n"
            'ORD-003,"Valid Address 3",CUST-003,14.2\n'
            "ORD-004,,CUST-004,14.2\n"
        )
        try:
            importer = CsvImporter()
            result = importer.import_orders(csv)
            assert len(result.orders) == 2
            assert len(result.errors) == 2
            # ORD-002 is pandas idx 1 -> row_num = 1 + 2 = 3
            assert result.errors[0].row_number == 3
            # ORD-004 is pandas idx 3 -> row_num = 3 + 2 = 5
            assert result.errors[1].row_number == 5
        finally:
            os.unlink(csv)

    def test_row_numbers_dict_tracks_order_ids(self):
        """ImportResult.row_numbers maps order_id to spreadsheet row number."""
        csv = self._create_csv(
            "order_id,address,customer_id,weight_kg\n"
            'ORD-001,"Address A",CUST-001,14.2\n'
            'ORD-002,"Address B",CUST-002,14.2\n'
        )
        try:
            importer = CsvImporter()
            result = importer.import_orders(csv)
            assert len(result.row_numbers) == 2
            # ORD-001 is pandas idx 0 -> row 2 in spreadsheet
            assert result.row_numbers["ORD-001"] == 2
            # ORD-002 is pandas idx 1 -> row 3 in spreadsheet
            assert result.row_numbers["ORD-002"] == 3
        finally:
            os.unlink(csv)
