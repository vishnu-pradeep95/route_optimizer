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


# Words that must never be split by the trailing-letter-split heuristic in
# Step 6 of clean_cdcms_address(). Includes:
# - Known abbreviations (KSEB, BSNL, KSRTC, KT, EK)
# - Common Kerala place/house name words (8+ chars) whose natural endings
#   (TH, DU, RY, RA, TY) would be mistaken for concatenated initials.
# This set grows as we encounter new false positives in real CDCMS data.
_PROTECTED_WORDS = frozenset({
    # Abbreviations
    "KSEB", "BSNL", "KSRTC", "KT", "EK",
    # Common Kerala place/house name words
    "PARAMBATH", "VALLIKKADU", "KALAMASSERY", "PALLIVATAKARA",
    "ONTHAMKAINATTY", "VATAKARA", "KAINATTY", "VALIYAPARAMBATH",
    "RAYARANGOTH", "EYYAMKUTTI", "SREESHYLAM", "MUTTUNGAL",
    "MADATHIL", "PANAKKULATHIL", "KALARIKKANDI", "PADINJARA",
    "MEATHALA", "BALAVADI", "MASTERVALLIKKADU", "MALAYILVALLIKKAD",
    "SREESHYLAMMUTTUNGAL", "POBALAVADI",
    "PERATTEYATH", "POOLAKANDY", "KOLAKKOTT",
})

# Trailing suffixes that are meaningful abbreviations. When found at the end
# of a concatenated word, we prefer splitting at this boundary instead of
# defaulting to a single trailing letter.
_MEANINGFUL_SUFFIXES = frozenset({"PO", "NR", "KB", "NKB"})

# Known CDCMS placeholder values in DeliveryMan column.
# These are not real drivers -- they indicate unassigned orders.
PLACEHOLDER_DRIVER_NAMES = {"ALLOCATION PENDING", ""}

# ---------------------------------------------------------------------------
# Lazy-loaded dictionary splitter (ADDR-05)
# ---------------------------------------------------------------------------

_splitter: "AddressSplitter | None" = None
_splitter_loaded: bool = False


def _get_splitter() -> "AddressSplitter | None":
    """Return the cached AddressSplitter instance, loading on first call.

    The dictionary is loaded once on first call and cached for the process
    lifetime.  This avoids loading the JSON file on module import (which
    would slow down imports for code paths that never call
    clean_cdcms_address).  The ``_splitter_loaded`` flag ensures we only
    attempt loading once, even if the file is missing.
    """
    global _splitter, _splitter_loaded
    if not _splitter_loaded:
        _splitter_loaded = True
        dict_path = Path(__file__).parent.parent.parent / "data" / "place_names_vatakara.json"
        if dict_path.exists():
            from core.data_import.address_splitter import AddressSplitter
            _splitter = AddressSplitter(dict_path)
            logger.info("Loaded place name dictionary from %s", dict_path)
        else:
            logger.debug(
                "Place name dictionary not found at %s — dictionary splitting disabled",
                dict_path,
            )
    return _splitter


def _split_word_if_concatenated(token: str) -> str:
    """Split trailing 1-3 uppercase letters from a long ALL-CAPS word.

    CDCMS concatenates address parts without separators — a person's initial
    or abbreviation often appears stuck to the end of a house or place name:
    "ANANDAMANDIRAMK" (house name + initial K), "CHORODEEASTPO" (area + PO).

    This function applies a 3-priority heuristic to decide where to split:

    1. If trailing 2-3 chars form a meaningful abbreviation (PO, NR, KB, NKB),
       split there. E.g., "CHORODEEASTPO" -> "CHORODEEAST PO".
    2. If removing 2-3 chars reveals a known protected word as the prefix,
       split there. E.g., "VALIYAPARAMBATHKB" -> "VALIYAPARAMBATH KB".
    3. Default: split off the last 1 character as a person's initial.
       E.g., "ANANDAMANDIRAMK" -> "ANANDAMANDIRAM K".

    Constraints:
    - Only processes ALL-CAPS tokens of 8+ characters.
    - Protected words (common Kerala place names, abbreviations) are never split.
    - Trailing punctuation (., ;, :) is preserved in its original position.

    Args:
        token: A single whitespace-delimited token from the address.

    Returns:
        The token with a space inserted before trailing letters, or unchanged.
    """
    # Separate trailing punctuation from the alpha core.
    # E.g., "MUTTUNGALNR." -> core="MUTTUNGALNR", trail="."
    core = token.rstrip(".;:")
    trail = token[len(core):]

    if not core.isupper() or len(core) < 8:
        return token
    if core in _PROTECTED_WORDS:
        return token

    # Priority 1: Check if trailing 2-3 chars are a meaningful abbreviation
    for suffix_len in (3, 2):
        if len(core) - suffix_len >= 5:
            suffix = core[-suffix_len:]
            if suffix in _MEANINGFUL_SUFFIXES:
                return core[:-suffix_len] + " " + suffix + trail

    # Priority 2: Check if removing 2-3 chars reveals a protected prefix
    for suffix_len in (3, 2):
        if len(core) - suffix_len >= 5:
            prefix = core[:-suffix_len]
            if prefix in _PROTECTED_WORDS:
                return prefix + " " + core[-suffix_len:] + trail

    # Priority 3: Default to splitting off last 1 character (person's initial)
    if len(core) - 1 >= 5:
        return core[:-1] + " " + core[-1] + trail

    return token


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

    # Step 3b: Filter out placeholder driver names (not real drivers).
    # CDCMS uses values like "Allocation Pending" for unassigned orders.
    # These are not real drivers and should never appear in previews or be geocoded.
    if CDCMS_COL_DELIVERY_MAN in df.columns:
        before = len(df)
        df = df[
            ~df[CDCMS_COL_DELIVERY_MAN].str.strip().str.upper().isin(PLACEHOLDER_DRIVER_NAMES)
        ]
        filtered_count = before - len(df)
        if filtered_count > 0:
            logger.info(
                "Filtered %d placeholder driver entries (Allocation Pending, blank)",
                filtered_count,
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
            columns=["order_id", "address", "quantity", "area_name", "delivery_man", "address_original"]
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
            # Completely unprocessed CDCMS ConsumerAddress text, only stripped.
            # Preserved so the API can expose both cleaned and raw address forms.
            "address_original": df[CDCMS_COL_ADDRESS].str.strip(),
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
    applies a 13-step cleaning pipeline to make the address more
    geocoder-friendly.

    Pipeline overview (13 steps):
        1. Remove embedded phone numbers
        2. Remove CDCMS-specific artifacts (PH:, leading apostrophes)
        3. Normalize backticks/quotes
        4. Expand abbreviations — first pass (inline NR., inline PO., (H))
        5. Add spaces before uppercase words stuck to digits
        5.5. Dictionary-powered word splitting (ADDR-05)
        6. Split trailing letters from concatenated ALL-CAPS words (ADDR-02)
        7. Expand abbreviations — second pass (standalone PO, NR after Steps 5.5/6)
        8. Collapse multiple spaces
        9. Remove dangling punctuation
        10. Title case
        11. Fix title-case artifacts (P.o. → P.O., Kseb → KSEB, etc.)
        12. Append area suffix

    Two-pass abbreviation strategy (ADDR-03):
        Pass 1 (Step 4): Inline patterns that work on concatenated text BEFORE
        word splitting. E.g., ``([a-zA-Z])PO\\.`` catches "KUNIYILPO." because
        the letter before PO is part of the same token.

        Pass 2 (Step 7): Standalone patterns (``\\bPO\\b``, ``\\bNR\\b``) that
        rely on word boundaries. These only work AFTER word splitting (Step 6)
        creates those boundaries. E.g., "CHORODEEASTPO" → "CHORODEEAST PO" →
        then ``\\bPO\\b`` matches.

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
        >>> clean_cdcms_address("ANANDAMANDIRAMK")
        'Anandamandiram K'
        >>> clean_cdcms_address("KUNIYILPO. CHORODE EAST")
        'Kuniyil P.O. Chorode East'
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

    # Step 4: Expand common Kerala address abbreviations (first pass — inline patterns)
    #
    # Two-pass abbreviation strategy:
    #   Pass 1 (here): Inline patterns that work on concatenated text BEFORE word
    #   splitting — e.g., ([a-zA-Z])PO\. catches "KUNIYILPO." because the letter
    #   before PO is part of the same token. NR[.;:] with \b also works here
    #   because NR is typically preceded by a space or start-of-string.
    #
    #   Pass 2 (Step 5c): Standalone patterns (\bPO\b, \bNR\b) that rely on word
    #   boundaries — these only work AFTER word splitting (Step 5b) creates the
    #   boundaries. Example: "CHORODEEASTPO WEST" → after split "CHORODEEAST PO WEST"
    #   → then \bPO\b matches.
    #
    # NR. / NR; / NR: → Near (geocoders understand "Near" better)
    addr = re.sub(r"\bNR[.;:]\s*", "Near ", addr, flags=re.IGNORECASE)

    # Kerala convention: Post Office name concatenated with PO/PO.
    # "KUNIYILPO." → "KUNIYIL P.O.", "EDAPOIPO." → "EDAPOI P.O."
    # This is very common in CDCMS — the PO name runs directly into "PO."
    # Must come BEFORE the standalone PO pattern below.
    addr = re.sub(r"([a-zA-Z])PO\.", r"\1 P.O.", addr, flags=re.IGNORECASE)

    # (HO) → House (common CDCMS notation for "house" — 172 Refill.xlsx occurrences)
    # Must come BEFORE (H) pattern to prevent partial matching.
    # Space padding " House " ensures no word concatenation when (HO) is stuck
    # to adjacent text like "PERATTEYATH(HO)CHORODE". Step 8 collapses extra spaces.
    addr = re.sub(r"\(HO\)", " House ", addr, flags=re.IGNORECASE)

    # (H) → House (common CDCMS notation for "house" — 104 Refill.xlsx occurrences)
    # Space padding added to prevent concatenation: "CHALIL(H)7/214A" → "CHALIL House 7/214A"
    addr = re.sub(r"\(H\)", " House ", addr, flags=re.IGNORECASE)

    # (PO) → P.O. (post office — 368 Refill.xlsx occurrences)
    # Space padding ensures "CHORODE(PO)POOLAKANDY" → "CHORODE P.O. POOLAKANDY"
    addr = re.sub(r"\(PO\)", " P.O. ", addr, flags=re.IGNORECASE)

    # Step 5: Add spaces before uppercase words that are stuck together.
    # CDCMS often concatenates: "VATTEPARAMBU PONR JUMA MASJID"
    # Pattern: lowercase/digit immediately followed by uppercase letter
    # "4/146AMINAS" → "4/146 AMINAS"
    # "MUTTUNGAL-POBALAVADI" → leave hyphens alone, handle PO separately
    addr = re.sub(r"(\d)([A-Z])", r"\1 \2", addr)

    # Step 5.5: Dictionary-powered word splitting (ADDR-05)
    # Uses the place name dictionary to find known place names in concatenated
    # text and insert spaces at their boundaries.  Runs BEFORE Step 6
    # (trailing letter split) so the dictionary gets first crack at the full
    # concatenated tokens — e.g., "MUTTUNGALPOBALAVADI" is correctly split
    # into "MUTTUNGAL PO BALAVADI" before Step 6 would incorrectly split
    # the trailing "I".  Must also run BEFORE Step 7 (abbreviation expansion)
    # so that PO/NR gaps created by the splitter are picked up by the
    # standalone \bPO\b and \bNR\b patterns.
    splitter = _get_splitter()
    if splitter is not None:
        addr = splitter.split(addr)

    # Step 6: Split trailing letters from concatenated ALL-CAPS words.
    # "ANANDAMANDIRAMK" → "ANANDAMANDIRAM K", "CHORODEEASTPO" → "CHORODEEAST PO"
    # See _split_word_if_concatenated() docstring for the 3-priority heuristic
    # and _PROTECTED_WORDS / _MEANINGFUL_SUFFIXES for the word lists.
    # Runs AFTER dictionary splitting (Step 5.5) to handle initials and
    # abbreviations that are NOT in the place name dictionary.
    words = addr.split()
    words = [_split_word_if_concatenated(w) for w in words]
    addr = " ".join(words)

    # Step 7: Second-pass abbreviation expansion (standalone patterns).
    # Now that Steps 5.5 and 6 have created word boundaries, standalone
    # \bPO\b and \bNR\b patterns will match words that were previously
    # concatenated.
    # Example: "CHORODEEAST PO WEST" — PO is a standalone word after splitting.
    addr = re.sub(r"\bPO\b\.?\s*", "P.O. ", addr, flags=re.IGNORECASE)
    addr = re.sub(r"\bNR\b[.;:]?\s*", "Near ", addr, flags=re.IGNORECASE)

    # Step 8: Collapse multiple spaces and clean up
    addr = re.sub(r"\s+", " ", addr).strip()

    # Step 9: Remove dangling punctuation (leading/trailing semicolons, dashes, plus signs)
    addr = re.sub(r"^[;:\-+\s]+|[;:\-+\s]+$", "", addr)

    # Step 10: Title case — makes the address more readable on the route sheet.
    # "KALAMASSERY HMT COLONY" → "Kalamassery Hmt Colony"
    # Not perfect (HMT should stay uppercase) but good enough for readability.
    addr = addr.title()

    # Step 11: Fix common title-case artifacts
    # "P.o." → "P.O.", "Po." → "P.O.", "Kseb" → "KSEB", "Bsnl" → "BSNL", "Ksrtc" → "KSRTC"
    addr = re.sub(r"\bP\.?o\.\b", "P.O.", addr)
    addr = re.sub(r"\bPo\.\b", "P.O.", addr)
    addr = re.sub(r"\bKseb\b", "KSEB", addr)
    addr = re.sub(r"\bBsnl\b", "BSNL", addr)
    addr = re.sub(r"\bKsrtc\b", "KSRTC", addr)

    # Step 12: Append area suffix for geocoding context
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
        logger.warning(
            "CDCMS missing required columns: %s. Found: %s",
            missing_required,
            sorted(present),
        )
        raise ValueError(
            f"Required columns missing: {', '.join(sorted(missing_required))} "
            f"-- make sure you're uploading the raw CDCMS export"
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
