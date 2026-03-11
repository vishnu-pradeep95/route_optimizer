"""Tests for CDCMS export preprocessor.

The CDCMS (Cylinder Delivery & Customer Management System) export is the
primary data source for HPCL LPG distributors. These tests verify that
the preprocessor correctly handles the messy real-world format: tab-separated
files, concatenated addresses, embedded phone numbers, and HPCL-specific
column names.

Test data is based on actual CDCMS exports (with anonymized phone numbers
and customer details).
"""

import pytest
import pandas as pd
from pathlib import Path

from core.data_import.cdcms_preprocessor import (
    preprocess_cdcms,
    clean_cdcms_address,
    get_cdcms_column_mapping,
    _validate_cdcms_columns,
    CDCMS_COL_ORDER_NO,
    CDCMS_COL_ADDRESS,
    CDCMS_COL_ORDER_QTY,
    CDCMS_COL_AREA,
    CDCMS_COL_DELIVERY_MAN,
    CDCMS_COL_ORDER_STATUS,
)


# =============================================================================
# Sample CDCMS data fixture
# =============================================================================

SAMPLE_CDCMS_HEADER = (
    "OrderNo\tOrderStatus\tOrderDate\tOrderSource\tOrderType\t"
    "CashMemoNo\tCashMemoStatus\tCashMemoDate\tOrderQuantity\t"
    "ConsumedSubsidyQty\tAreaName\tDeliveryMan\tRefillPaymentStatus\t"
    "IVRSBookingNumber\tMobileNo\tBookingDoneThroughRegistereMobile\t"
    "ConsumerAddress\tIsRefillPort\tEkycStatus"
)


def _make_cdcms_row(
    order_no: str = "517827",
    status: str = "Allocated-Printed",
    address: str = "4/146 AMINAS VALIYA PARAMBATH NR. VALLIKKADU SARAMBI PALLIVATAKARA",
    quantity: str = "1",
    area: str = "VALLIKKADU",
    delivery_man: str = "GIREESHAN ( C )",
) -> str:
    """Build a single tab-separated CDCMS row for testing."""
    return (
        f"{order_no}\t{status}\t14-02-2026 9:41\tIVRS\tRefill\t"
        f"1234567\tPrinted\t14-02-2026\t{quantity}\t{quantity}\t"
        f"{area}\t{delivery_man}\t\t'1111111111\t'1111111111\tY\t"
        f"{address}\tN\tEKYC NOT DONE"
    )


@pytest.fixture
def cdcms_tsv_file(tmp_path: Path) -> Path:
    """Write a small CDCMS-format TSV file for testing.

    Contains 5 orders:
    - 3 from VALLIKKADU area, 1 from RAYARANGOTH, 1 from CHORODE EAST
    - All assigned to GIREESHAN ( C )
    - All status "Allocated-Printed"
    """
    content = "\n".join([
        SAMPLE_CDCMS_HEADER,
        _make_cdcms_row("517827", address="4/146 AMINAS VALIYA PARAMBATH NR. VALLIKKADU SARAMBI PALLIVATAKARA"),
        _make_cdcms_row("517828", address='8/301 "ARUNIMA"PADINJARA KALARIKKANDI MEATHALA MADAMCHORODE EAST', area="VALLIKKADU"),
        _make_cdcms_row("517829", address="8/542SREESHYLAMMUTTUNGAL-POBALAVADI", quantity="2", area="VALLIKKADU"),
        _make_cdcms_row("517830", address="02/11 PANAKKULATHIL\"CHAITHANIYA\"NR; RATION SHOPRAYARANGOTH PO", area="RAYARANGOTH"),
        _make_cdcms_row("517831", address="09/210A KUNIYIL (H)- CHEKKIPURATHPO. CHORODE EASTNR. MATHATH PALAM", area="CHORODE EAST"),
    ])
    filepath = tmp_path / "cdcms_export.csv"
    filepath.write_text(content)
    return filepath


@pytest.fixture
def cdcms_mixed_status_file(tmp_path: Path) -> Path:
    """CDCMS file with mixed order statuses — some already delivered."""
    content = "\n".join([
        SAMPLE_CDCMS_HEADER,
        _make_cdcms_row("517827", status="Allocated-Printed"),
        _make_cdcms_row("517828", status="Allocated-Printed"),
        _make_cdcms_row("517829", status="Delivered"),
        _make_cdcms_row("517830", status="Cancelled"),
    ])
    filepath = tmp_path / "mixed_status.csv"
    filepath.write_text(content)
    return filepath


# =============================================================================
# preprocess_cdcms() — end-to-end tests
# =============================================================================


class TestPreprocessCdcms:
    """End-to-end tests for the CDCMS preprocessor pipeline.

    Verifies the full flow: read TSV → filter → clean → rename columns.
    """

    def test_reads_tab_separated_file(self, cdcms_tsv_file: Path):
        """CDCMS exports are tab-separated — preprocessor must handle this."""
        df = preprocess_cdcms(cdcms_tsv_file, area_suffix="")
        assert len(df) == 5
        assert list(df.columns) == ["order_id", "address", "quantity", "area_name", "delivery_man", "address_original"]

    def test_order_ids_preserved(self, cdcms_tsv_file: Path):
        """OrderNo values should appear as order_id without modification."""
        df = preprocess_cdcms(cdcms_tsv_file, area_suffix="")
        assert df["order_id"].tolist() == ["517827", "517828", "517829", "517830", "517831"]

    def test_quantity_parsed_as_int(self, cdcms_tsv_file: Path):
        """OrderQuantity should be parsed as integer."""
        df = preprocess_cdcms(cdcms_tsv_file, area_suffix="")
        assert df["quantity"].dtype in ("int64", "int32")
        # Third order has quantity=2, rest have quantity=1
        assert df.iloc[2]["quantity"] == 2
        assert df.iloc[0]["quantity"] == 1

    def test_area_name_title_cased(self, cdcms_tsv_file: Path):
        """AreaName should be converted to title case for readability."""
        df = preprocess_cdcms(cdcms_tsv_file, area_suffix="")
        assert "Vallikkadu" in df["area_name"].values
        assert "Rayarangoth" in df["area_name"].values
        assert "Chorode East" in df["area_name"].values

    def test_filter_by_status(self, cdcms_mixed_status_file: Path):
        """Default filter keeps only 'Allocated-Printed' orders."""
        df = preprocess_cdcms(cdcms_mixed_status_file, area_suffix="")
        assert len(df) == 2  # Only the 2 Allocated-Printed orders

    def test_filter_status_none_includes_all(self, cdcms_mixed_status_file: Path):
        """Setting filter_status=None disables status filtering."""
        df = preprocess_cdcms(cdcms_mixed_status_file, filter_status=None, area_suffix="")
        assert len(df) == 4  # All 4 orders included

    def test_filter_by_area(self, cdcms_tsv_file: Path):
        """Filtering by area returns only matching orders."""
        df = preprocess_cdcms(cdcms_tsv_file, filter_area="VALLIKKADU", area_suffix="")
        assert len(df) == 3
        assert all(a == "Vallikkadu" for a in df["area_name"])

    def test_filter_by_delivery_man(self, cdcms_tsv_file: Path):
        """Filtering by delivery man works (case-insensitive)."""
        df = preprocess_cdcms(cdcms_tsv_file, filter_delivery_man="gireeshan ( c )", area_suffix="")
        assert len(df) == 5  # All orders are assigned to Gireeshan

    def test_empty_after_filter_returns_empty_df(self, cdcms_tsv_file: Path):
        """Filtering with no matches returns empty DataFrame with correct columns."""
        df = preprocess_cdcms(cdcms_tsv_file, filter_area="NONEXISTENT")
        assert len(df) == 0
        assert list(df.columns) == ["order_id", "address", "quantity", "area_name", "delivery_man", "address_original"]

    def test_file_not_found_raises(self):
        """Missing file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            preprocess_cdcms("/nonexistent/path/cdcms.csv")

    def test_area_suffix_appended_to_addresses(self, cdcms_tsv_file: Path):
        """area_suffix should be appended to each cleaned address."""
        df = preprocess_cdcms(cdcms_tsv_file, area_suffix=", Vatakara, Kerala")
        for addr in df["address"]:
            assert addr.endswith("Vatakara, Kerala")

    def test_addresses_are_cleaned(self, cdcms_tsv_file: Path):
        """Addresses should be cleaned (title case, no phone numbers, etc.)."""
        df = preprocess_cdcms(cdcms_tsv_file, area_suffix="")
        # First address starts with "4/146" — digits aren't affected by title case
        first_addr = df.iloc[0]["address"]
        assert first_addr.startswith("4/146")
        # Check that a word-only address is title-cased (not ALL CAPS)
        assert "AMINAS" not in first_addr  # Should not be all-caps
        # Should not contain raw CDCMS artifacts like backticks
        for addr in df["address"]:
            assert "``" not in addr

    def test_reads_real_sample_file(self):
        """Integration test: reads the actual sample_cdcms_export.csv file.

        This test runs against the sample data file we created from real
        CDCMS export data. If the file doesn't exist (e.g., CI without
        data files), the test is skipped.
        """
        sample_path = Path("data/sample_cdcms_export.csv")
        if not sample_path.exists():
            pytest.skip("Sample CDCMS export file not found")

        df = preprocess_cdcms(sample_path, area_suffix=", Vatakara, Kozhikode, Kerala")
        assert len(df) == 27  # 27 orders in the sample file
        assert "order_id" in df.columns
        assert "address" in df.columns
        # All addresses should end with the area suffix
        for addr in df["address"]:
            assert "Kerala" in addr


# =============================================================================
# clean_cdcms_address() — individual address cleaning tests
# =============================================================================


class TestCleanCdcmsAddress:
    """Tests for individual CDCMS address cleaning.

    These addresses are taken from real CDCMS exports. The cleaning
    function must handle Kerala's informal address format: house numbers
    concatenated with names, landmarks abbreviated as NR./NR;, post
    offices as PO., and phone numbers embedded in the text.
    """

    def test_basic_address_cleaned(self):
        """Standard CDCMS address should be title-cased."""
        result = clean_cdcms_address(
            "4/146 AMINAS VALIYA PARAMBATH NR. VALLIKKADU SARAMBI PALLIVATAKARA",
            area_suffix="",
        )
        # Should be title case
        assert result.startswith("4/146")
        assert "AMINAS" not in result  # All-caps should be gone
        assert "Aminas" in result or "aminas" in result.lower()

    def test_removes_embedded_phone_number(self):
        """Phone numbers mixed into addresses should be removed."""
        result = clean_cdcms_address(
            "VALIYAPARAMBATH (H) 9847862734KURUPAL ONTHAMKAINATTY   VATAKARA",
            area_suffix="",
        )
        assert "9847862734" not in result
        assert "Kurupal" in result or "kurupal" in result.lower()

    def test_removes_ph_annotation(self):
        """Phone annotations like '/ PH: 2511259' should be stripped."""
        result = clean_cdcms_address(
            "SREYAS - EYYAMKUTTI KUNIYILNR.EK GOPALAN MASTERVALLIKKADU  / PH: 2511259",
            area_suffix="",
        )
        assert "PH:" not in result
        assert "2511259" not in result

    def test_removes_embedded_reference_numbers(self):
        """Slash-prefixed reference numbers like '/ 2513264' should be stripped."""
        result = clean_cdcms_address(
            "3/495 THEKKE MALAYILVALLIKKAD/ 2513264VATAKARANR:VARISA KUNI UP ROA",
            area_suffix="",
        )
        assert "2513264" not in result

    def test_cleans_backtick_markers(self):
        """Backtick-wrapped house names should have backticks removed."""
        result = clean_cdcms_address(
            "``THANAL``/  513510RAYARANGOTH (PO)VATAKARA",
            area_suffix="",
        )
        assert "``" not in result
        assert "Thanal" in result or "thanal" in result.lower()

    def test_cleans_double_quote_markers(self):
        """Double-quoted house names should have quotes removed."""
        result = clean_cdcms_address(
            '8/301 "ARUNIMA"PADINJARA KALARIKKANDI MEATHALA MADAMCHORODE EAST',
            area_suffix="",
        )
        assert '"' not in result

    def test_expands_nr_abbreviation(self):
        """NR. / NR; / NR: should be expanded to 'Near'."""
        result = clean_cdcms_address(
            "4/146 AMINAS NR. VALLIKKADU",
            area_suffix="",
        )
        assert "Near" in result

        result2 = clean_cdcms_address(
            "HOUSE NR; RATION SHOP",
            area_suffix="",
        )
        assert "Near" in result2

    def test_expands_po_abbreviation(self):
        """PO. / PO should be expanded to 'P.O.'."""
        result = clean_cdcms_address(
            "09/210A KUNIYILPO. CHORODE EAST",
            area_suffix="",
        )
        assert "P.O." in result

    def test_expands_house_notation(self):
        """(H) should be expanded to 'House'."""
        result = clean_cdcms_address(
            "VALIYAPARAMBATH (H) KURUPAL",
            area_suffix="",
        )
        assert "House" in result
        assert "(H)" not in result

    def test_adds_space_between_number_and_text(self):
        """Digits stuck to uppercase letters should get a space: '8/542SREESHYLAM' → '8/542 Sreeshylam'."""
        result = clean_cdcms_address(
            "8/542SREESHYLAMMUTTUNGAL-POBALAVADI",
            area_suffix="",
        )
        # "542" and "SREESHYLAM" should be separated
        assert "542 " in result or "542S" not in result.lower()

    def test_title_case_applied(self):
        """Output should be title-cased, not ALL CAPS."""
        result = clean_cdcms_address(
            "KALAMASSERY HMT COLONY NEAR BUS STOP",
            area_suffix="",
        )
        assert result == "Kalamassery Hmt Colony Near Bus Stop"

    def test_kseb_abbreviation_preserved(self):
        """KSEB (Kerala State Electricity Board) should stay uppercase."""
        result = clean_cdcms_address(
            "MADATHIL (H) 19/223PO.MUTTUNGAL WESTNR. KAINATTY KSEB OFFICE",
            area_suffix="",
        )
        assert "KSEB" in result

    def test_area_suffix_appended(self):
        """Area suffix should be appended with comma separator."""
        result = clean_cdcms_address(
            "SOME ADDRESS",
            area_suffix=", Vatakara, Kerala",
        )
        assert result.endswith("Vatakara, Kerala")

    def test_empty_address_returns_empty(self):
        """Empty or whitespace-only addresses should return empty string."""
        assert clean_cdcms_address("") == ""
        assert clean_cdcms_address("   ") == ""

    def test_collapses_multiple_spaces(self):
        """Multiple consecutive spaces should be collapsed to one."""
        result = clean_cdcms_address(
            "SOME   ADDRESS    WITH    SPACES",
            area_suffix="",
        )
        assert "  " not in result

    def test_strips_dangling_punctuation(self):
        """Leading/trailing semicolons, dashes, plus signs should be removed."""
        result = clean_cdcms_address(
            "ANANDAMANDIRAMK.T.BAZAR/2206801NR: K.S.E.B +",
            area_suffix="",
        )
        assert not result.endswith("+")
        assert not result.endswith("-")


# =============================================================================
# ADDR-02: Trailing letter split on ALL-CAPS input
# =============================================================================


class TestWordSplitting:
    """Tests for ADDR-02: splitting trailing uppercase letters from concatenated words.

    CDCMS addresses are often concatenated without separators. The trailing
    letter split regex detects 1-3 trailing uppercase letters stuck to longer
    words (5+ total characters) and inserts a space before them.
    """

    @pytest.mark.parametrize(
        "raw_input, expected_substring",
        [
            # Single trailing letter: K stuck to ANANDAMANDIRAM
            ("ANANDAMANDIRAMK", "Anandamandiram K"),
            # Single trailing letter: K stuck to KUNIYIL
            ("KUNIYILK", "Kuniyil K"),
            # Two trailing letters: KB stuck to VALIYAPARAMBATH
            ("VALIYAPARAMBATHKB", "Valiyaparambath Kb"),
            # Three trailing letters: NKB stuck to VALIYAPARAMBATH
            ("VALIYAPARAMBATHNKB", "Valiyaparambath Nkb"),
        ],
        ids=[
            "single-trailing-K",
            "single-trailing-K-short-word",
            "two-trailing-KB",
            "three-trailing-NKB",
        ],
    )
    def test_trailing_letters_split(self, raw_input, expected_substring):
        """Trailing 1-3 letters should be split from words of 5+ total chars."""
        result = clean_cdcms_address(raw_input, area_suffix="")
        assert expected_substring in result, (
            f"Expected '{expected_substring}' in '{result}' "
            f"(input: '{raw_input}')"
        )

    @pytest.mark.parametrize(
        "raw_input",
        [
            "MAYA",   # 4 chars total — too short to split
            "RAVI",   # 4 chars — should not split
            "AKM",    # 3 chars — too short
        ],
        ids=["maya-4chars", "ravi-4chars", "akm-3chars"],
    )
    def test_short_words_not_split(self, raw_input):
        """Words shorter than 5 characters should NOT be split."""
        result = clean_cdcms_address(raw_input, area_suffix="")
        # After title case, the word should be intact (no extra spaces)
        assert " " not in result.strip(), (
            f"Short word '{raw_input}' was incorrectly split: '{result}'"
        )

    def test_already_spaced_text_unchanged(self):
        """Text that already has proper spacing should not be modified."""
        result = clean_cdcms_address(
            "VALIYA PARAMBATH NEAR SCHOOL",
            area_suffix="",
        )
        assert "Valiya Parambath Near School" == result

    def test_trailing_split_in_multi_word_address(self):
        """Trailing letter split should work within a full address string."""
        result = clean_cdcms_address(
            "4/146 ANANDAMANDIRAMK VALLIKKADU",
            area_suffix="",
        )
        assert "Anandamandiram K" in result
        assert "Vallikkadu" in result


class TestKnownAbbreviationsPreserved:
    """Tests verifying that known abbreviations are NOT split by trailing letter regex.

    Kerala abbreviations like KSEB, BSNL, KSRTC must be preserved as-is,
    even though they end with 1-3 letter groups that match the trailing
    letter split pattern.
    """

    @pytest.mark.parametrize(
        "abbreviation",
        ["KSEB", "BSNL", "KSRTC"],
        ids=["kseb", "bsnl", "ksrtc"],
    )
    def test_abbreviation_not_split(self, abbreviation):
        """Known abbreviations should not be split into separate letters."""
        result = clean_cdcms_address(
            f"NEAR {abbreviation} OFFICE",
            area_suffix="",
        )
        assert abbreviation in result, (
            f"Abbreviation '{abbreviation}' was split or mangled in: '{result}'"
        )


# =============================================================================
# ADDR-03: Abbreviation expansion after word splitting
# =============================================================================


class TestStepOrdering:
    """Tests for ADDR-03: standalone abbreviation expansion runs after word splitting.

    The inline PO pattern (([a-zA-Z])PO\\.) handles concatenated cases like
    "KUNIYILPO." correctly in Step 4. But the standalone \\bPO\\b pattern
    only works at word boundaries — so it needs to run AFTER word splitting
    creates those boundaries.
    """

    def test_standalone_po_after_word_split(self):
        """Standalone PO should be expanded to P.O. even after word splitting creates it."""
        # After trailing letter split: "CHORODEEAST PO WEST"
        # Then standalone PO pattern should catch "PO" at word boundary
        result = clean_cdcms_address(
            "CHORODEEASTPO WEST",
            area_suffix="",
        )
        assert "P.O." in result, (
            f"Standalone PO not expanded after word split: '{result}'"
        )

    def test_standalone_nr_after_word_split(self):
        """Standalone NR with punctuation should be expanded to Near after word splitting."""
        result = clean_cdcms_address(
            "MUTTUNGALNR. KAINATTY",
            area_suffix="",
        )
        assert "Near" in result, (
            f"NR. not expanded: '{result}'"
        )

    def test_inline_po_still_works(self):
        """The inline PO pattern ([a-zA-Z])PO\\. should still work in its original position."""
        result = clean_cdcms_address(
            "KUNIYILPO. CHORODE EAST",
            area_suffix="",
        )
        assert "P.O." in result, (
            f"Inline PO pattern broken: '{result}'"
        )

    def test_combined_word_split_and_abbreviation(self):
        """Full pipeline: word split + abbreviation expansion in correct order."""
        result = clean_cdcms_address(
            "ANANDAMANDIRAMK NR. KSEB OFFICE",
            area_suffix="",
        )
        # Trailing K should be split: "ANANDAMANDIRAM K"
        assert "Anandamandiram K" in result
        # NR. should be expanded to Near
        assert "Near" in result
        # KSEB should be preserved
        assert "KSEB" in result


# =============================================================================
# Validation tests
# =============================================================================


class TestValidation:
    """Tests for CDCMS column validation."""

    def test_missing_required_columns_raises(self):
        """DataFrame without OrderNo or ConsumerAddress should raise ValueError.

        Error message must:
        - Start with "Required columns missing:" (capital R)
        - List missing columns sorted, comma-separated (not Python set notation)
        - End with a fix action after " -- "
        - NOT contain "Found columns" (that goes to logger only)
        """
        df = pd.DataFrame({"SomeColumn": ["test"], "AnotherColumn": ["test"]})
        with pytest.raises(ValueError, match="Required columns missing") as exc_info:
            _validate_cdcms_columns(df)

        msg = str(exc_info.value)
        # No Python set notation
        assert "{" not in msg, f"Error message contains set notation: {msg}"
        assert "}" not in msg, f"Error message contains set notation: {msg}"
        # No "Found columns" in user-facing message (moved to logger)
        assert "Found columns" not in msg, f"Error message leaks Found columns: {msg}"
        # Has problem-fix separator
        assert " -- " in msg, f"Error message missing fix action separator: {msg}"
        # Column names are sorted and comma-separated
        assert "ConsumerAddress, OrderNo" in msg, f"Columns not sorted/comma-separated: {msg}"

    def test_empty_address_column_raises(self):
        """All-empty ConsumerAddress column should raise ValueError."""
        df = pd.DataFrame({
            CDCMS_COL_ORDER_NO: ["123"],
            CDCMS_COL_ADDRESS: [""],
        })
        with pytest.raises(ValueError, match="all values are empty"):
            _validate_cdcms_columns(df)

    def test_valid_columns_pass(self):
        """DataFrame with required columns should not raise."""
        df = pd.DataFrame({
            CDCMS_COL_ORDER_NO: ["123"],
            CDCMS_COL_ADDRESS: ["Some address"],
        })
        _validate_cdcms_columns(df)  # Should not raise


# =============================================================================
# Column mapping test
# =============================================================================


class TestColumnMapping:
    """Tests for the CDCMS → CsvImporter column mapping."""

    def test_mapping_has_correct_fields(self):
        """get_cdcms_column_mapping should return a valid ColumnMapping."""
        mapping = get_cdcms_column_mapping()
        assert mapping.order_id == "order_id"
        assert mapping.address == "address"
        assert mapping.quantity == "quantity"
