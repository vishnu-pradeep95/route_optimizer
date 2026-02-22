"""Tests for the CSV importer — handles CDCMS export files."""

import os
import tempfile

import pytest

from core.data_import.csv_importer import CsvImporter, ColumnMapping
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

        Uses cylinder_weight_lookup to resolve 'domestic' → 14.2 kg,
        proving the lookup works — not just a coincidence with the default.
        """
        csv = self._create_csv(
            "order_id,address,customer_id,cylinder_type,quantity,priority,notes\n"
            'ORD-001,"Kalamassery, Kochi",CUST-001,domestic,2,2,Ring bell\n'
            'ORD-002,"Marine Drive, Kochi",CUST-002,domestic,1,1,Urgent\n'
        )
        try:
            # Pass explicit cylinder weights so the test verifies lookup behavior
            kerala_weights = {"domestic": 14.2, "commercial": 19.0, "industrial": 47.0}
            importer = CsvImporter(cylinder_weight_lookup=kerala_weights)
            orders = importer.import_orders(csv)
            assert len(orders) == 2
            assert orders[0].order_id == "ORD-001"
            assert orders[0].weight_kg == 28.4  # 14.2 × 2 via lookup
            assert orders[1].priority == 1
        finally:
            os.unlink(csv)

    def test_import_with_coordinates(self):
        """CSV with lat/lon columns produces geocoded orders."""
        csv = self._create_csv(
            "order_id,address,customer_id,weight_kg,latitude,longitude\n"
            "ORD-001,Kochi,CUST-001,14.2,9.9716,76.2846\n"
        )
        try:
            importer = CsvImporter()
            orders = importer.import_orders(csv)
            assert len(orders) == 1
            assert orders[0].is_geocoded
            assert orders[0].location.latitude == 9.9716
        finally:
            os.unlink(csv)

    def test_missing_address_skips_row(self):
        """Rows without an address are skipped with a warning."""
        csv = self._create_csv(
            "order_id,address,customer_id,weight_kg\n"
            "ORD-001,,CUST-001,14.2\n"
            'ORD-002,"Valid Address",CUST-002,14.2\n'
        )
        try:
            importer = CsvImporter()
            orders = importer.import_orders(csv)
            assert len(orders) == 1  # Bad row skipped
            assert orders[0].order_id == "ORD-002"
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
            'ORD-001,"Hotel XYZ, Kochi",CUST-001,commercial,1\n'
        )
        try:
            # Kerala-specific weights, normally from apps/kerala_delivery/config.py
            kerala_weights = {"domestic": 14.2, "commercial": 19.0, "industrial": 47.0}
            importer = CsvImporter(cylinder_weight_lookup=kerala_weights)
            orders = importer.import_orders(csv)
            assert orders[0].weight_kg == 19.0
        finally:
            os.unlink(csv)

    def test_custom_column_mapping(self):
        """Supports remapped column names for different CDCMS exports."""
        csv = self._create_csv(
            "booking_ref,delivery_address,consumer_no,weight\n"
            'BK-001,"MG Road, Kochi",CON-001,14.2\n'
        )
        try:
            mapping = ColumnMapping(
                order_id="booking_ref",
                address="delivery_address",
                customer_ref="consumer_no",
                weight_kg="weight",
            )
            importer = CsvImporter(column_mapping=mapping)
            orders = importer.import_orders(csv)
            assert len(orders) == 1
            assert orders[0].order_id == "BK-001"
            assert orders[0].customer_ref == "CON-001"
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
            'ORD-001,"Kochi Address",CUST-001\n'
        )
        try:
            importer = CsvImporter(default_cylinder_weight_kg=14.2)
            orders = importer.import_orders(csv)
            assert orders[0].weight_kg == 14.2
        finally:
            os.unlink(csv)
