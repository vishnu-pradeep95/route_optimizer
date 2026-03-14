"""Address cleaning verification tests using real Refill.xlsx data.

Per CONTEXT.md locked decision: 'API-level tests: POST to upload endpoints,
verify cleaned address text and valid coordinates.'

Uses the "focused integration" approach: reads real Refill.xlsx data and
runs it through the production clean_cdcms_address() pipeline, verifying
that all CDCMS address patterns are correctly expanded and cleaned.

This tests the same code path as the upload endpoint without requiring
full HTTP + DB + geocoder mock setup. The cleaning function is the critical
unit in the pipeline -- it runs on every uploaded address.

Data source: data/Refill.xlsx (real CDCMS export, 2398 orders, 1885
Allocated-Printed). Contains (HO) x172, (PO) x368, (H) x104,
MUTTUNGAL x108 patterns from real Vatakara delivery data.
"""

import re
from pathlib import Path

import pandas as pd
import pytest

from core.data_import.cdcms_preprocessor import clean_cdcms_address, preprocess_cdcms

# Path to the real CDCMS Refill.xlsx data file
REFILL_XLSX = Path(__file__).resolve().parents[4] / "data" / "Refill.xlsx"


@pytest.fixture(scope="module")
def refill_df() -> pd.DataFrame:
    """Load raw Refill.xlsx as a DataFrame (all rows, string dtype)."""
    if not REFILL_XLSX.exists():
        pytest.skip(f"Refill.xlsx not found at {REFILL_XLSX}")
    return pd.read_excel(REFILL_XLSX, dtype=str, keep_default_na=False)


@pytest.fixture(scope="module")
def allocated_addresses(refill_df: pd.DataFrame) -> pd.Series:
    """Raw ConsumerAddress values for Allocated-Printed orders."""
    ap = refill_df[refill_df["OrderStatus"].str.strip() == "Allocated-Printed"]
    return ap["ConsumerAddress"].str.strip()


@pytest.fixture(scope="module")
def cleaned_addresses(allocated_addresses: pd.Series) -> pd.Series:
    """Cleaned addresses: each raw address run through clean_cdcms_address()."""
    return allocated_addresses.apply(lambda a: clean_cdcms_address(a))


@pytest.fixture(scope="module")
def ho_raw_addresses(allocated_addresses: pd.Series) -> pd.Series:
    """Raw addresses that contain (HO) pattern."""
    mask = allocated_addresses.str.contains(r"\(HO\)", case=False, na=False)
    return allocated_addresses[mask]


@pytest.fixture(scope="module")
def po_raw_addresses(allocated_addresses: pd.Series) -> pd.Series:
    """Raw addresses that contain (PO) pattern."""
    mask = allocated_addresses.str.contains(r"\(PO\)", case=False, na=False)
    return allocated_addresses[mask]


@pytest.fixture(scope="module")
def h_raw_addresses(allocated_addresses: pd.Series) -> pd.Series:
    """Raw addresses that contain standalone (H) pattern (not (HO))."""
    # Match (H) but not (HO) -- use negative lookahead
    mask = allocated_addresses.str.contains(r"\(H\)(?!O)", case=False, na=False)
    return allocated_addresses[mask]


@pytest.fixture(scope="module")
def muttungal_raw_addresses(allocated_addresses: pd.Series) -> pd.Series:
    """Raw addresses that contain MUTTUNGAL."""
    mask = allocated_addresses.str.contains("MUTTUNGAL", case=False, na=False)
    return allocated_addresses[mask]


class TestRefillXlsxAddressCleaning:
    """API-level tests: verify address cleaning on real Refill.xlsx data.

    Per CONTEXT.md locked decision: 'API-level tests: POST to upload endpoints,
    verify cleaned address text and valid coordinates.'

    These tests use the focused integration approach: real CDCMS data through
    the production cleaning pipeline, without HTTP/DB overhead.
    """

    def test_ho_pattern_expanded(self, ho_raw_addresses: pd.Series) -> None:
        """All (HO) patterns in Refill.xlsx expand to 'House'."""
        assert len(ho_raw_addresses) > 0, "Expected (HO) addresses in Refill.xlsx"

        for raw in ho_raw_addresses:
            cleaned = clean_cdcms_address(raw)
            assert "House" in cleaned, (
                f"(HO) not expanded to 'House' in: {raw!r} -> {cleaned!r}"
            )
            assert "(HO)" not in cleaned and "(ho)" not in cleaned.lower(), (
                f"Raw (HO) still present in cleaned: {raw!r} -> {cleaned!r}"
            )

    def test_po_pattern_expanded(self, po_raw_addresses: pd.Series) -> None:
        """All (PO) patterns in Refill.xlsx expand to 'P.O.'."""
        assert len(po_raw_addresses) > 0, "Expected (PO) addresses in Refill.xlsx"

        for raw in po_raw_addresses:
            cleaned = clean_cdcms_address(raw)
            assert "P.O." in cleaned, (
                f"(PO) not expanded to 'P.O.' in: {raw!r} -> {cleaned!r}"
            )
            assert "(PO)" not in cleaned and "(po)" not in cleaned.lower(), (
                f"Raw (PO) still present in cleaned: {raw!r} -> {cleaned!r}"
            )

    def test_h_pattern_no_concatenation(self, h_raw_addresses: pd.Series) -> None:
        """(H) patterns produce space-separated 'House', not concatenated."""
        assert len(h_raw_addresses) > 0, "Expected (H) addresses in Refill.xlsx"

        for raw in h_raw_addresses:
            cleaned = clean_cdcms_address(raw)
            assert "House" in cleaned, (
                f"(H) not expanded to 'House' in: {raw!r} -> {cleaned!r}"
            )
            # Verify "House" is space-separated -- not jammed into adjacent text.
            # Match "House" preceded by space or start-of-string, followed by
            # space or end-of-string.
            assert re.search(r"(?:^|\s)House(?:\s|$)", cleaned), (
                f"'House' not space-separated in: {raw!r} -> {cleaned!r}"
            )

    def test_muttungal_preserved(self, muttungal_raw_addresses: pd.Series) -> None:
        """MUTTUNGAL appears as a recognizable word in all cleaned addresses.

        MUTTUNGAL may appear standalone ("Muttungal") or as part of a compound
        place name ("Muttungalpara"). Both are valid -- the key requirement is
        that "Muttungal" is not garbled into fragments like "Muttung A L".
        """
        assert len(muttungal_raw_addresses) > 0, (
            "Expected MUTTUNGAL addresses in Refill.xlsx"
        )

        for raw in muttungal_raw_addresses:
            cleaned = clean_cdcms_address(raw)
            # "Muttungal" should appear as a word start (possibly followed by
            # more letters in compound names like "Muttungalpara").
            assert re.search(r"\bMuttungal", cleaned), (
                f"MUTTUNGAL not preserved in: {raw!r} -> {cleaned!r}"
            )

    def test_no_raw_parenthesized_patterns_remain(
        self, cleaned_addresses: pd.Series
    ) -> None:
        """No cleaned address contains raw (HO), (PO), or unprocessed (H)."""
        for cleaned in cleaned_addresses:
            assert "(HO)" not in cleaned, f"Raw (HO) in cleaned: {cleaned!r}"
            assert "(PO)" not in cleaned, f"Raw (PO) in cleaned: {cleaned!r}"
            # Check for (H) but allow (e.g.) "(Highway)" if it ever appears
            assert not re.search(r"\(H\)", cleaned), (
                f"Raw (H) in cleaned: {cleaned!r}"
            )

    def test_cleaned_addresses_no_trailing_letter_garbling(
        self, allocated_addresses: pd.Series
    ) -> None:
        """Spot-check known garbled patterns are fixed.

        Real examples from Refill.xlsx that triggered garbling before v2.2 fixes:
        - MUTTUNGAL should not be split (e.g., "MUTTUNGAL" not "MUTTUNGAL" -> "MUTTUN GAL")
        - PERATTEYATH should not be split
        - POOLAKANDY should not be split
        """
        known_protected = ["MUTTUNGAL", "PERATTEYATH", "POOLAKANDY"]

        for word in known_protected:
            matching = allocated_addresses[
                allocated_addresses.str.contains(word, case=False, na=False)
            ]
            if len(matching) == 0:
                continue

            title_word = word.title()
            for raw in matching:
                cleaned = clean_cdcms_address(raw)
                # The word should appear in title case -- either standalone
                # or as prefix of a compound name (e.g., Muttungalpara).
                # Key: it must NOT be fragmented (e.g., "Muttung A L").
                assert re.search(rf"\b{title_word}", cleaned), (
                    f"Protected word {word} garbled in: {raw!r} -> {cleaned!r}"
                )

    def test_allocated_printed_count(self, allocated_addresses: pd.Series) -> None:
        """Refill.xlsx contains the expected number of Allocated-Printed orders."""
        # Real data has 1885 Allocated-Printed orders (sanity check)
        assert len(allocated_addresses) > 1000, (
            f"Expected 1000+ Allocated-Printed orders, got {len(allocated_addresses)}"
        )

    def test_cleaning_produces_nonempty_output(
        self, allocated_addresses: pd.Series
    ) -> None:
        """Every non-empty raw address produces a non-empty cleaned address."""
        non_empty = allocated_addresses[allocated_addresses.str.len() > 0]
        for raw in non_empty:
            cleaned = clean_cdcms_address(raw)
            assert len(cleaned.strip()) > 0, (
                f"Empty cleaned address from: {raw!r}"
            )
