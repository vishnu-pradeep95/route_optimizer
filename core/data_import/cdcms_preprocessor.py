"""CDCMS export preprocessor — converts HPCL's raw export into clean delivery data.

HPCL's CDCMS (Cylinder Delivery & Customer Management System) exports daily
delivery lists as tab-separated files with 19 columns. Most columns are
irrelevant for route optimization. This preprocessor:

1. Reads the raw CDCMS export (tab-separated, with HPCL-specific column names)
2. Extracts only the columns we need (OrderNo, ConsumerAddress, OrderQuantity,
   AreaName, DeliveryMan)
3. Cleans up the messy address format (CDCMS concatenates address parts without
   proper spacing or separators)
4. Outputs a clean CSV that CsvImporter can process

Why a separate preprocessor instead of extending CsvImporter?
- CsvImporter is generic (works with any CSV). This module handles CDCMS-specific
  quirks: tab-separated format, HPCL column names, address concatenation issues,
  phone number formatting, and area-based grouping.
- Separation of concerns: CsvImporter knows about Orders; this module knows
  about HPCL's export format. When CDCMS changes its export layout, only this
  file needs updating.
- Another LPG distributor (Bharat Gas, Indane) would write their own preprocessor
  but reuse CsvImporter.

Data flow:
    CDCMS export (.csv/.xlsx, tab-separated)
      → CdcmsPreprocessor.preprocess()
      → Clean DataFrame with renamed columns
      → CsvImporter.import_orders()
      → list[Order]

Address format challenge:
    CDCMS concatenates address fields without separators:
    "4/146 AMINAS VALIYA PARAMBATH NR. VALLIKKADU SARAMBI PALLIVATAKARA"
    This is actually: house_no + house_name + landmark + area + post_office
    We keep the full string as-is (geocoding handles the parsing), but clean up
    common formatting issues like double spaces, missing separators, and phone
    numbers embedded in addresses.
"""

import logging
import re
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


# CDCMS column names (as they appear in the export file).
# These come from HPCL's system — if they change column names in a future
# version, update these constants. The rest of the code uses these constants,
# not raw strings.
CDCMS_COL_ORDER_NO = "OrderNo"
CDCMS_COL_ORDER_STATUS = "OrderStatus"
CDCMS_COL_ORDER_DATE = "OrderDate"
CDCMS_COL_ORDER_QTY = "OrderQuantity"
CDCMS_COL_AREA = "AreaName"
CDCMS_COL_DELIVERY_MAN = "DeliveryMan"
CDCMS_COL_ADDRESS = "ConsumerAddress"
CDCMS_COL_MOBILE = "MobileNo"


def preprocess_cdcms(
    source: str | Path,
    *,
    filter_status: str | None = "Allocated-Printed",
    filter_delivery_man: str | None = None,
    filter_area: str | None = None,
    area_suffix: str = "",
) -> pd.DataFrame:
    """Read a CDCMS export and return a clean DataFrame for CsvImporter.

    Reads the raw CDCMS tab-separated file, extracts route-relevant columns,
    cleans addresses, and returns a DataFrame with standardized column names
    that match CsvImporter's default ColumnMapping.

    Args:
        source: Path to the CDCMS export file (tab-separated .csv or .xlsx).
        filter_status: Only include orders with this status. CDCMS uses
            "Allocated-Printed" for orders ready for delivery. Set to None
            to include all statuses.
        filter_delivery_man: Only include orders assigned to this delivery man.
            Useful when generating a route sheet for a single driver. Set to
            None to include all drivers.
        filter_area: Only include orders from this CDCMS area name.
            CDCMS pre-groups orders by area (e.g., "VALLIKKADU", "RAYARANGOTH").
            Set to None to include all areas.
        area_suffix: Appended to each address to improve geocoding accuracy.
            CDCMS addresses rarely mention the city/district/state, but geocoders
            need this context. Default is for the Vatakara/Kozhikode area.
            Change this to match your distributor's delivery zone.

    Returns:
        DataFrame with columns: order_id, address, quantity, area_name,
        delivery_man. Ready to be saved as CSV or passed to CsvImporter.

    Example:
        >>> df = preprocess_cdcms("data/cdcms_export.csv")
        >>> df.to_csv("data/today_deliveries.csv", index=False)
        >>> # Then: importer.import_orders("data/today_deliveries.csv")
    """
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"CDCMS export file not found: {source}")

    # Step 1: Read the file — CDCMS exports are tab-separated
    # Why dtype=str? Prevents pandas from interpreting OrderNo as int
    # (which would lose leading zeros if any) and MobileNo as float
    # (which would mangle phone numbers).
    df = _read_cdcms_file(path)

    logger.info(
        "Read CDCMS export: %d orders, columns: %s",
        len(df),
        list(df.columns),
    )

    # Step 2: Validate that expected CDCMS columns exist
    _validate_cdcms_columns(df)

    # Step 3: Filter by status (default: only "Allocated-Printed")
    if filter_status:
        before = len(df)
        df = df[df[CDCMS_COL_ORDER_STATUS].str.strip() == filter_status]
        logger.info(
            "Filtered by status '%s': %d → %d orders",
            filter_status,
            before,
            len(df),
        )

    # Step 4: Filter by delivery man (optional — for single-driver route sheets)
    if filter_delivery_man:
        before = len(df)
        df = df[
            df[CDCMS_COL_DELIVERY_MAN].str.strip().str.upper()
            == filter_delivery_man.strip().upper()
        ]
        logger.info(
            "Filtered by delivery man '%s': %d → %d orders",
            filter_delivery_man,
            before,
            len(df),
        )

    # Step 5: Filter by area (optional)
    if filter_area:
        before = len(df)
        df = df[
            df[CDCMS_COL_AREA].str.strip().str.upper()
            == filter_area.strip().upper()
        ]
        logger.info(
            "Filtered by area '%s': %d → %d orders",
            filter_area,
            before,
            len(df),
        )

    if df.empty:
        logger.warning("No orders remain after filtering — check your filters.")
        return pd.DataFrame(
            columns=["order_id", "address", "quantity", "area_name", "delivery_man"]
        )

    # Step 6: Extract and rename columns to match CsvImporter expectations
    result = pd.DataFrame(
        {
            "order_id": df[CDCMS_COL_ORDER_NO].astype(str).str.strip(),
            "address": df[CDCMS_COL_ADDRESS].apply(
                lambda addr: clean_cdcms_address(addr, area_suffix=area_suffix)
            ),
            "quantity": pd.to_numeric(
                df[CDCMS_COL_ORDER_QTY].str.strip(), errors="coerce"
            )
            .fillna(1)
            .astype(int),
            # Keep area_name and delivery_man as metadata — useful for grouping
            # and filtering, but not consumed by CsvImporter directly.
            "area_name": df[CDCMS_COL_AREA].str.strip().str.title(),
            "delivery_man": df[CDCMS_COL_DELIVERY_MAN].str.strip(),
        }
    )

    # Reset index so row numbers are clean (0, 1, 2, ...)
    result = result.reset_index(drop=True)

    logger.info(
        "Preprocessed %d orders across %d areas for %d drivers",
        len(result),
        result["area_name"].nunique(),
        result["delivery_man"].nunique(),
    )

    return result


def clean_cdcms_address(raw_address: str, *, area_suffix: str = "") -> str:
    """Clean a raw CDCMS address string for geocoding.

    CDCMS addresses are messy — fields concatenated without separators,
    phone numbers mixed in, inconsistent punctuation. This function
    applies a series of cleaning steps to make the address more
    geocoder-friendly.

    Why not split the address into structured parts?
    CDCMS doesn't use consistent separators between house number, house name,
    landmark, area, and post office. Splitting would require ML or heuristic
    parsing with high error rates. Instead, we clean the string minimally and
    let the geocoder (Google Maps) handle the interpretation — it's surprisingly
    good at parsing Indian addresses.

    Args:
        raw_address: The ConsumerAddress field from CDCMS.
        area_suffix: Extra location context appended to the end (e.g.,
            ", Vatakara, Kozhikode, Kerala") to help the geocoder.

    Returns:
        Cleaned address string ready for geocoding.

    Examples:
        >>> clean_cdcms_address("4/146 AMINAS VALIYA PARAMBATH NR. VALLIKKADU SARAMBI PALLIVATAKARA")
        '4/146 Aminas Valiya Parambath, Nr. Vallikkadu, Sarambi, Pallivatakara'
    """
    if not raw_address or not raw_address.strip():
        return ""

    addr = raw_address.strip()

    # Step 1: Remove embedded phone numbers.
    # CDCMS sometimes puts phone numbers in the address field:
    # "VALIYAPARAMBATH (H) 9847862734KURUPAL" → remove "9847862734"
    # Pattern: 10-digit number not preceded by / (to preserve house nos like "4/146")
    # Using (?<![/\d]) instead of \b because word boundary doesn't match after
    # punctuation like ')' in "(H) 9847862734".
    addr = re.sub(r"(?<![/\d])\d{10}(?!\d)", " ", addr)

    # Step 2: Remove CDCMS-specific artifacts
    # - Phone annotations like "/ PH: 2511259" or "/ 2513264"
    # - Leading apostrophes on phone numbers (CDCMS quirk: '1111111111)
    addr = re.sub(r"/\s*PH:\s*\d+", " ", addr, flags=re.IGNORECASE)
    addr = re.sub(r"/\s*\d{5,}", " ", addr)

    # Step 3: Normalize backticks and double-quotes used as house name markers
    # ``THANAL`` → THANAL, "ARUNIMA" → ARUNIMA, "CHAITHANIYA" → CHAITHANIYA
    addr = addr.replace("``", "").replace('""', "").replace('"', " ")

    # Step 4: Expand common Kerala address abbreviations
    # NR. / NR; / NR: → Near (geocoders understand "Near" better)
    addr = re.sub(r"\bNR[.;:]\s*", "Near ", addr, flags=re.IGNORECASE)

    # Kerala convention: Post Office name concatenated with PO/PO.
    # "KUNIYILPO." → "KUNIYIL P.O.", "EDAPOIPO." → "EDAPOI P.O."
    # This is very common in CDCMS — the PO name runs directly into "PO."
    # Must come BEFORE the standalone PO pattern below.
    addr = re.sub(r"([a-zA-Z])PO\.", r"\1 P.O.", addr, flags=re.IGNORECASE)

    # PO / PO. as a standalone word → P.O. (Post Office abbreviation)
    addr = re.sub(r"\bPO\b\.?\s*", "P.O. ", addr, flags=re.IGNORECASE)

    # (H) → House (common CDCMS notation for "house")
    addr = re.sub(r"\(H\)", "House", addr, flags=re.IGNORECASE)

    # Step 5: Add spaces before uppercase words that are stuck together.
    # CDCMS often concatenates: "VATTEPARAMBU PONR JUMA MASJID"
    # Pattern: lowercase/digit immediately followed by uppercase letter
    # "4/146AMINAS" → "4/146 AMINAS"
    # "MUTTUNGAL-POBALAVADI" → leave hyphens alone, handle PO separately
    addr = re.sub(r"(\d)([A-Z])", r"\1 \2", addr)

    # Step 6: Collapse multiple spaces and clean up
    addr = re.sub(r"\s+", " ", addr).strip()

    # Step 7: Remove dangling punctuation (leading/trailing semicolons, dashes, plus signs)
    addr = re.sub(r"^[;:\-+\s]+|[;:\-+\s]+$", "", addr)

    # Step 8: Title case — makes the address more readable on the route sheet.
    # "KALAMASSERY HMT COLONY" → "Kalamassery Hmt Colony"
    # Not perfect (HMT should stay uppercase) but good enough for readability.
    addr = addr.title()

    # Step 9: Fix common title-case artifacts
    # "P.o." → "P.O.", "Po." → "P.O.", "Kseb" → "KSEB"
    addr = re.sub(r"\bP\.?o\.\b", "P.O.", addr)
    addr = re.sub(r"\bPo\.\b", "P.O.", addr)
    addr = re.sub(r"\bKseb\b", "KSEB", addr)

    # Step 10: Append area suffix for geocoding context
    if area_suffix:
        addr = f"{addr}, {area_suffix.strip(', ')}"

    return addr


def _read_cdcms_file(path: Path) -> pd.DataFrame:
    """Read a CDCMS export file (tab-separated CSV or Excel).

    CDCMS exports are tab-separated, not comma-separated. Some employees
    may also save as .xlsx from Excel. We handle both.
    """
    suffix = path.suffix.lower()

    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(path, dtype=str, keep_default_na=False)

    # Default: try tab-separated first, fall back to comma-separated.
    # Why try tab first? CDCMS exports are tab-separated, but if someone
    # re-saves in Excel it might become comma-separated.
    # CDCMS exports have 19 columns. If tab-separated parsing produces
    # very few columns, the file is likely comma-separated and all data
    # ended up in a single column. We use 5 as the threshold — the bare
    # minimum CDCMS columns we need are OrderNo, OrderStatus,
    # ConsumerAddress, ProductDesc, and Quantity.
    CDCMS_MIN_EXPECTED_COLUMNS = 5
    try:
        df = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
        if len(df.columns) >= CDCMS_MIN_EXPECTED_COLUMNS:
            return df
    except pd.errors.ParserError:
        # Tab-separated parsing failed — try comma-separated below.
        pass
    except pd.errors.EmptyDataError:
        # File is empty or has only headers — let comma-separated path
        # handle it (it will produce a more informative error).
        pass

    # Fallback: comma-separated
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def _validate_cdcms_columns(df: pd.DataFrame) -> None:
    """Check that the DataFrame has the expected CDCMS columns.

    Not all columns are required — we only check for the ones we actually use.
    This catches the case where someone uploads a completely wrong file.
    """
    # These are the minimum columns we need from a CDCMS export
    required = {CDCMS_COL_ORDER_NO, CDCMS_COL_ADDRESS}
    # These are nice to have but not fatal if missing
    optional = {CDCMS_COL_ORDER_QTY, CDCMS_COL_AREA, CDCMS_COL_DELIVERY_MAN, CDCMS_COL_ORDER_STATUS}

    present = set(df.columns)
    missing_required = required - present
    missing_optional = optional - present

    if missing_required:
        raise ValueError(
            f"CDCMS export is missing required columns: {missing_required}. "
            f"Found columns: {sorted(present)}. "
            f"Expected at least: {sorted(required)}. "
            "Make sure you're uploading the raw CDCMS export file."
        )

    if missing_optional:
        logger.warning(
            "CDCMS export is missing optional columns: %s. "
            "These features will use defaults.",
            missing_optional,
        )

    # Check for empty address column (common if wrong file uploaded)
    if CDCMS_COL_ADDRESS in present:
        # Count non-empty addresses: empty strings are falsy, so .astype(bool)
        # converts "" → False and "any text" → True. .sum() counts the Trues.
        non_empty = df[CDCMS_COL_ADDRESS].str.strip().astype(bool).sum()
        if non_empty == 0:
            raise ValueError(
                f"The '{CDCMS_COL_ADDRESS}' column exists but all values are empty. "
                "Check the file format."
            )


def get_cdcms_column_mapping():
    """Return a CsvImporter ColumnMapping configured for preprocessed CDCMS data.

    After preprocessing, the DataFrame has our standard column names
    (order_id, address, quantity). This mapping tells CsvImporter exactly
    where to find each field.

    Usage:
        from core.data_import.csv_importer import CsvImporter
        from core.data_import.cdcms_preprocessor import preprocess_cdcms, get_cdcms_column_mapping

        df = preprocess_cdcms("cdcms_export.csv")
        df.to_csv("clean.csv", index=False)
        importer = CsvImporter(column_mapping=get_cdcms_column_mapping())
        orders = importer.import_orders("clean.csv")
    """
    from core.data_import.csv_importer import ColumnMapping

    return ColumnMapping(
        order_id="order_id",
        address="address",
        quantity="quantity",
        # CDCMS exports don't have these columns — CsvImporter will use defaults
        customer_ref="customer_id",
        cylinder_type="cylinder_type",
        weight_kg="weight_kg",
        priority="priority",
        notes="notes",
        latitude="latitude",
        longitude="longitude",
        delivery_window_start="delivery_window_start",
        delivery_window_end="delivery_window_end",
    )
