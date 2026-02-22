"""CSV/Excel importer for CDCMS delivery data.

HPCL's CDCMS (Cylinder Delivery & Customer Management System) allows
distributors to export daily delivery lists as CSV/Excel. This importer
reads that export and converts each row into an Order.

Expected columns (flexible — mapped via config):
  - order_id or booking_ref: Unique order identifier
  - address: Customer delivery address (text)
  - customer_id or consumer_no: Customer reference (kept pseudonymized)
  - weight_kg or cylinder_type + quantity: For capacity calculation
  - priority (optional): 1=high, 2=normal, 3=low
  - notes (optional): Delivery instructions

LPG cylinder weights:
  - Domestic (14.2 kg): Most common, ~95% of deliveries
  - Commercial (19 kg): Restaurants, businesses
  - 5 kg FTL cylinder: Smaller, less common
"""

import logging
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, Field

from core.models.location import Location
from core.models.order import Order

logger = logging.getLogger(__name__)

# Default cylinder weight lookup — empty by default to keep core/ business-agnostic.
# Business-specific consumers pass their own lookup via constructor injection.
# For example, the Kerala LPG app passes config.CYLINDER_WEIGHTS with
# domestic/commercial/5kg cylinder weights. A food delivery app wouldn't need this.
DEFAULT_CYLINDER_WEIGHTS: dict[str, float] = {}


class ColumnMapping(BaseModel):
    """Maps CSV column names to our Order fields.

    Why configurable mappings?
    CDCMS exports may change column names between versions, or users
    might adapt the CSV before importing. This lets us handle any
    reasonable column naming without code changes.
    """

    order_id: str = Field(default="order_id", description="Column for booking/order reference")
    address: str = Field(default="address", description="Column for delivery address text")
    customer_ref: str = Field(default="customer_id", description="Column for customer reference")
    weight_kg: str = Field(default="weight_kg", description="Column for weight (if explicit)")
    cylinder_type: str = Field(default="cylinder_type", description="Column for cylinder type name")
    quantity: str = Field(default="quantity", description="Column for number of cylinders")
    priority: str = Field(default="priority", description="Column for delivery priority")
    notes: str = Field(default="notes", description="Column for delivery notes")
    latitude: str = Field(default="latitude", description="Column for latitude (if available)")
    longitude: str = Field(default="longitude", description="Column for longitude (if available)")


class CsvImporter:
    """Imports delivery orders from CSV or Excel files.

    Handles the messy reality of CDCMS exports: inconsistent column names,
    missing fields, mixed cylinder types, and text addresses that need
    geocoding later.

    Usage:
        importer = CsvImporter(column_mapping=ColumnMapping(order_id="booking_ref"))
        orders = importer.import_orders("today_deliveries.csv")
    """

    def __init__(
        self,
        column_mapping: ColumnMapping | None = None,
        default_cylinder_weight_kg: float = 14.2,
        cylinder_weight_lookup: dict[str, float] | None = None,
    ):
        """Initialize the CSV importer.

        Args:
            column_mapping: How CSV columns map to Order fields.
                If None, uses default column names.
            default_cylinder_weight_kg: Weight to assume when no type/weight
                column is present. Default 14.2 kg (standard domestic cylinder).
            cylinder_weight_lookup: Mapping from cylinder type name to weight in kg.
                If None, uses the built-in defaults (domestic/commercial/5kg).
                Business-specific consumers can pass their own lookup table.
        """
        self.mapping = column_mapping or ColumnMapping()
        self.default_weight = default_cylinder_weight_kg
        # Why injectable? The cylinder types and weights are business-specific.
        # LPG has domestic/commercial; a food delivery app would not need this at all.
        self.weight_lookup = cylinder_weight_lookup or DEFAULT_CYLINDER_WEIGHTS

    def import_orders(self, source: str) -> list[Order]:
        """Read a CSV or Excel file and return a list of Orders.

        Supports .csv, .xlsx, .xls files. Auto-detects format from extension.

        Args:
            source: File path to the CSV/Excel file.

        Returns:
            List of Order objects. Orders with text-only addresses will have
            location=None — they need geocoding before optimization.

        Raises:
            FileNotFoundError: If the source file doesn't exist.
            ValueError: If required columns are missing.
        """
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Data file not found: {source}")

        # Read into a pandas DataFrame — handles both CSV and Excel
        df = self._read_file(path)

        # Normalize column names: strip whitespace, lowercase
        # Why? CDCMS exports sometimes have inconsistent casing/spacing
        df.columns = [col.strip().lower().replace(" ", "_") for col in df.columns]

        # Validate that we have at minimum an address and some identifier
        self._validate_columns(df)

        # Convert each row to an Order
        orders: list[Order] = []
        for idx, row in df.iterrows():
            try:
                order = self._row_to_order(row, idx)
                orders.append(order)
            except (ValueError, KeyError, TypeError) as e:
                # Log bad rows but don't fail the entire import.
                # These are the expected failure modes for malformed CSV data:
                #   ValueError — bad numeric conversions, empty required fields
                #   KeyError   — missing expected columns
                #   TypeError  — null/NaN where a string was expected
                # Unexpected exceptions (MemoryError, etc.) should propagate.
                # TODO: collect these into a validation report
                logger.warning("Skipping row %s: %s", idx, e)

        return orders

    def _read_file(self, path: Path) -> pd.DataFrame:
        """Read CSV or Excel file into a DataFrame."""
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(path, dtype=str, keep_default_na=False)
        elif suffix in (".xlsx", ".xls"):
            return pd.read_excel(path, dtype=str, keep_default_na=False)
        else:
            raise ValueError(
                f"Unsupported file format: {suffix}. Use .csv, .xlsx, or .xls"
            )

    def _validate_columns(self, df: pd.DataFrame) -> None:
        """Ensure the DataFrame has the minimum required columns.

        We need at least an address column and either an order_id or we'll
        generate sequential IDs. Weight can come from weight_kg column OR
        from cylinder_type + quantity.
        """
        address_col = self.mapping.address.lower()
        if address_col not in df.columns:
            # Try common alternatives before failing
            alternatives = ["address", "delivery_address", "addr", "customer_address"]
            found = [alt for alt in alternatives if alt in df.columns]
            if not found:
                raise ValueError(
                    f"Missing address column. Expected '{address_col}' or one of "
                    f"{alternatives}. Found columns: {list(df.columns)}"
                )

    def _row_to_order(self, row: pd.Series, idx: Any) -> Order:
        """Convert a single DataFrame row into an Order.

        Handles multiple naming conventions and fills in defaults where needed.
        """
        # --- Order ID: use CSV column, or generate from row index ---
        order_id = self._get_field(row, self.mapping.order_id, default=f"ORD-{idx + 1:04d}")

        # --- Address: always required ---
        address_raw = self._get_field(row, self.mapping.address, default="")
        if not address_raw:
            raise ValueError("Empty address")

        # --- Customer ref: pseudonymized, or generate ---
        customer_ref = self._get_field(
            row, self.mapping.customer_ref, default=f"CUST-{idx + 1:04d}"
        )

        # --- Weight: from explicit weight_kg, or from cylinder_type × quantity ---
        weight_kg = self._resolve_weight(row)

        # --- Quantity ---
        quantity = int(self._get_field(row, self.mapping.quantity, default="1") or "1")

        # --- Priority ---
        priority = int(self._get_field(row, self.mapping.priority, default="2") or "2")

        # --- Notes ---
        notes = self._get_field(row, self.mapping.notes, default="")

        # --- Location: only if lat/lon columns exist and have values ---
        location = self._resolve_location(row)

        return Order(
            order_id=order_id,
            location=location,
            address_raw=address_raw,
            customer_ref=customer_ref,
            weight_kg=weight_kg,
            quantity=quantity,
            priority=priority,
            notes=notes,
        )

    def _get_field(self, row: pd.Series, column_name: str, default: str = "") -> str:
        """Safely get a field value from a row, handling missing columns."""
        col = column_name.lower()
        if col in row.index:
            val = str(row[col]).strip()
            return val if val else default
        return default

    def _resolve_weight(self, row: pd.Series) -> float:
        """Calculate delivery weight from available columns.

        Priority:
        1. Explicit weight_kg column
        2. cylinder_type → lookup weight × quantity
        3. Default cylinder weight × quantity
        """
        # Try explicit weight column first
        weight_str = self._get_field(row, self.mapping.weight_kg)
        if weight_str:
            try:
                return float(weight_str)
            except ValueError:
                pass

        # Try cylinder_type lookup
        cyl_type = self._get_field(row, self.mapping.cylinder_type).lower()
        quantity = int(self._get_field(row, self.mapping.quantity, default="1") or "1")

        if cyl_type and cyl_type in self.weight_lookup:
            return self.weight_lookup[cyl_type] * quantity

        # Fallback: default weight × quantity
        return self.default_weight * quantity

    def _resolve_location(self, row: pd.Series) -> Location | None:
        """Try to extract GPS coordinates from lat/lon columns.

        Returns None if coordinates aren't available — the order will
        need geocoding before it can be optimized.
        """
        lat_str = self._get_field(row, self.mapping.latitude)
        lon_str = self._get_field(row, self.mapping.longitude)

        if lat_str and lon_str:
            try:
                lat = float(lat_str)
                lon = float(lon_str)
                # Basic sanity check: is this even in India?
                if 6.0 <= lat <= 37.0 and 68.0 <= lon <= 97.5:
                    return Location(latitude=lat, longitude=lon)
            except ValueError:
                pass

        return None
