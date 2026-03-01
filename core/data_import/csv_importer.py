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
from datetime import time
from pathlib import Path
from typing import Any, Literal

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
    # Phase 2: time window columns for VRPTW support
    delivery_window_start: str = Field(
        default="delivery_window_start", description="Column for earliest delivery time (HH:MM)"
    )
    delivery_window_end: str = Field(
        default="delivery_window_end", description="Column for latest delivery time (HH:MM)"
    )


class RowError(BaseModel):
    """A single row-level validation error or warning.

    Messages use original CSV column names (from ColumnMapping) so office
    staff see exactly which spreadsheet column to fix. Row numbers are
    1-based spreadsheet convention: header = row 1, first data = row 2.
    """

    row_number: int = Field(
        ..., description="1-based CSV row number (header=row 1, first data=row 2)"
    )
    column: str = Field(default="", description="CSV column name that caused the error")
    message: str = Field(..., description="Human-readable error for office staff")
    stage: Literal["validation"] = "validation"


class ImportResult(BaseModel):
    """Result of CSV import: valid orders + row-level errors + warnings.

    Separates errors (row rejected) from warnings (row imported with defaults).
    The row_numbers dict maps order_id to spreadsheet row number for downstream
    geocoding error tracking — when geocoding fails, the API can report the
    original spreadsheet row to the user.
    """

    orders: list[Order] = Field(default_factory=list)
    errors: list[RowError] = Field(default_factory=list)
    warnings: list[RowError] = Field(default_factory=list)
    row_numbers: dict[str, int] = Field(
        default_factory=dict, description="order_id -> spreadsheet row number"
    )


class CsvImporter:
    """Imports delivery orders from CSV or Excel files.

    Handles the messy reality of CDCMS exports: inconsistent column names,
    missing fields, mixed cylinder types, and text addresses that need
    geocoding later.

    Usage:
        importer = CsvImporter(column_mapping=ColumnMapping(order_id="booking_ref"))
        result = importer.import_orders("today_deliveries.csv")
        orders = result.orders  # valid orders
        errors = result.errors  # row-level validation errors
    """

    def __init__(
        self,
        column_mapping: ColumnMapping | None = None,
        default_cylinder_weight_kg: float = 14.2,
        cylinder_weight_lookup: dict[str, float] | None = None,
        coordinate_bounds: tuple[float, float, float, float] | None = None,
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
            coordinate_bounds: Optional (lat_min, lat_max, lon_min, lon_max) for
                sanity-checking coordinates. If None, no bounds check is applied.
                Example for India: (6.0, 37.0, 68.0, 97.5).
        """
        self.mapping = column_mapping or ColumnMapping()
        self.default_weight = default_cylinder_weight_kg
        # Why injectable? The cylinder types and weights are business-specific.
        # LPG has domestic/commercial; a food delivery app would not need this at all.
        self.weight_lookup = cylinder_weight_lookup or DEFAULT_CYLINDER_WEIGHTS
        # Coordinate bounds are injected so core/ stays business-agnostic.
        # The Kerala app passes India bounds; a European user passes European bounds.
        self.coordinate_bounds = coordinate_bounds

    def import_orders(self, source: str) -> "ImportResult":
        """Read a CSV or Excel file and return an ImportResult.

        Supports .csv, .xlsx, .xls files. Auto-detects format from extension.

        Returns an ImportResult containing:
        - orders: Successfully parsed Order objects
        - errors: Row-level validation errors (row was rejected)
        - warnings: Row-level warnings (row imported with defaults)
        - row_numbers: Mapping of order_id to spreadsheet row number

        Args:
            source: File path to the CSV/Excel file.

        Returns:
            ImportResult with valid orders and structured row-level errors.

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

        # Convert each row to an Order, collecting errors along the way
        result = ImportResult()
        seen_order_ids: set[str] = set()

        for idx, row in df.iterrows():
            # Spreadsheet row number: pandas 0-based idx + 1 (1-based) + 1 (header row)
            row_num = int(idx) + 2

            # --- Pre-validation: empty address ---
            address_raw = self._get_field(row, self.mapping.address, default="")
            if not address_raw:
                result.errors.append(
                    RowError(
                        row_number=row_num,
                        column=self.mapping.address,
                        message=f"Empty {self.mapping.address} -- add a delivery address",
                        stage="validation",
                    )
                )
                continue

            # --- Pre-validation: duplicate order_id ---
            order_id = self._get_field(
                row, self.mapping.order_id, default=f"ORD-{int(idx) + 1:04d}"
            )
            if order_id in seen_order_ids:
                result.errors.append(
                    RowError(
                        row_number=row_num,
                        column=self.mapping.order_id,
                        message=f"Duplicate {self.mapping.order_id} '{order_id}' -- "
                        f"already imported from an earlier row",
                        stage="validation",
                    )
                )
                continue

            try:
                order, row_warnings = self._row_to_order_with_warnings(row, idx, row_num)
                orders_list = result.orders
                orders_list.append(order)
                seen_order_ids.add(order.order_id)
                result.row_numbers[order.order_id] = row_num
                # Collect any warnings (e.g., invalid weight defaulted)
                result.warnings.extend(row_warnings)
            except (ValueError, KeyError, TypeError) as e:
                # Catch remaining conversion errors not caught by pre-validation.
                # These are the expected failure modes for malformed CSV data:
                #   ValueError -- bad numeric conversions, unexpected field values
                #   KeyError   -- missing expected columns
                #   TypeError  -- null/NaN where a string was expected
                # Unexpected exceptions (MemoryError, etc.) should propagate.
                result.errors.append(
                    RowError(
                        row_number=row_num,
                        column="",
                        message=str(e),
                        stage="validation",
                    )
                )
                logger.warning("Skipping row %s: %s", row_num, e)

        return result

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

    def _row_to_order_with_warnings(
        self, row: pd.Series, idx: Any, row_num: int
    ) -> tuple["Order", list["RowError"]]:
        """Convert a single DataFrame row into an Order, collecting warnings.

        Returns a tuple of (Order, list of RowError warnings). Warnings are
        non-fatal: the order is still imported but with defaulted values.

        Handles multiple naming conventions and fills in defaults where needed.
        """
        warnings: list[RowError] = []

        # --- Order ID: use CSV column, or generate from row index ---
        order_id = self._get_field(row, self.mapping.order_id, default=f"ORD-{idx + 1:04d}")

        # --- Address: already validated in import_orders() pre-check ---
        address_raw = self._get_field(row, self.mapping.address, default="")

        # --- Customer ref: pseudonymized, or generate ---
        customer_ref = self._get_field(
            row, self.mapping.customer_ref, default=f"CUST-{idx + 1:04d}"
        )

        # --- Weight: from explicit weight_kg, or from cylinder_type x quantity ---
        weight_kg, weight_warning = self._resolve_weight_with_warning(row, row_num)
        if weight_warning:
            warnings.append(weight_warning)

        # --- Quantity ---
        quantity = int(self._get_field(row, self.mapping.quantity, default="1") or "1")

        # --- Priority ---
        priority = int(self._get_field(row, self.mapping.priority, default="2") or "2")

        # --- Notes ---
        notes = self._get_field(row, self.mapping.notes, default="")

        # --- Location: only if lat/lon columns exist and have values ---
        location = self._resolve_location(row)

        # --- Time windows (Phase 2): "deliver between 09:00 and 12:00" ---
        tw_start = self._resolve_time(row, self.mapping.delivery_window_start)
        tw_end = self._resolve_time(row, self.mapping.delivery_window_end)

        order = Order(
            order_id=order_id,
            location=location,
            address_raw=address_raw,
            customer_ref=customer_ref,
            weight_kg=weight_kg,
            quantity=quantity,
            priority=priority,
            notes=notes,
            delivery_window_start=tw_start,
            delivery_window_end=tw_end,
        )
        return order, warnings

    def _get_field(self, row: pd.Series, column_name: str, default: str = "") -> str:
        """Safely get a field value from a row, handling missing columns."""
        col = column_name.lower()
        if col in row.index:
            val = str(row[col]).strip()
            return val if val else default
        return default

    def _resolve_weight_with_warning(
        self, row: pd.Series, row_num: int
    ) -> tuple[float, "RowError | None"]:
        """Calculate delivery weight, returning a warning if value was invalid.

        Priority:
        1. Explicit weight_kg column (return warning if not a valid number)
        2. cylinder_type -> lookup weight x quantity
        3. Default cylinder weight x quantity

        Returns:
            Tuple of (weight_kg, optional RowError warning).
        """
        # Try explicit weight column first
        weight_str = self._get_field(row, self.mapping.weight_kg)
        if weight_str:
            try:
                return float(weight_str), None
            except ValueError:
                # Invalid weight string -- use default and warn
                warning = RowError(
                    row_number=row_num,
                    column=self.mapping.weight_kg,
                    message=(
                        f"Invalid weight '{weight_str}' in {self.mapping.weight_kg} column "
                        f"-- using default {self.default_weight} kg"
                    ),
                    stage="validation",
                )
                return self.default_weight, warning

        # Try cylinder_type lookup
        cyl_type = self._get_field(row, self.mapping.cylinder_type).lower()
        quantity = int(self._get_field(row, self.mapping.quantity, default="1") or "1")

        if cyl_type and cyl_type in self.weight_lookup:
            return self.weight_lookup[cyl_type] * quantity, None

        # Fallback: default weight x quantity
        return self.default_weight * quantity, None

    def _resolve_weight(self, row: pd.Series) -> float:
        """Calculate delivery weight from available columns.

        Convenience wrapper that discards warnings. Used by legacy callers.

        Priority:
        1. Explicit weight_kg column
        2. cylinder_type -> lookup weight x quantity
        3. Default cylinder weight x quantity
        """
        weight, _warning = self._resolve_weight_with_warning(row, row_num=0)
        return weight

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
                # Sanity check coordinates against bounds if configured.
                # Without bounds, all valid WGS84 coordinates are accepted.
                if self.coordinate_bounds:
                    lat_min, lat_max, lon_min, lon_max = self.coordinate_bounds
                    if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
                        return Location(latitude=lat, longitude=lon)
                else:
                    return Location(latitude=lat, longitude=lon)
            except ValueError:
                pass

        return None

    def _resolve_time(self, row: pd.Series, column_name: str) -> time | None:
        """Parse a time string (HH:MM or HH:MM:SS) from a CSV column.

        Supports common time formats:
        - "09:00", "9:00", "09:00:00"
        - "9 AM", "09:00 AM" (12-hour format)

        Returns None if the column doesn't exist, is empty, or can't be parsed.
        Time windows are optional — if not provided, the order has no time
        constraint (pure CVRP instead of VRPTW).
        """
        from datetime import datetime as dt

        time_str = self._get_field(row, column_name)
        if not time_str:
            return None

        # Try common time formats
        for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M:%S %p", "%I %p"):
            try:
                parsed = dt.strptime(time_str, fmt)
                return time(parsed.hour, parsed.minute, parsed.second)
            except ValueError:
                continue

        logger.warning("Could not parse time '%s' from column '%s'", time_str, column_name)
        return None
