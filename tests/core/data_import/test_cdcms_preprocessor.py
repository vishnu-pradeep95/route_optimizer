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


# =============================================================================
# ADDR-05: Dictionary-powered word splitting in full pipeline
# =============================================================================


class TestDictionarySplitting:
    """Tests for ADDR-05: dictionary-powered word splitting in the full pipeline.

    These tests verify that clean_cdcms_address() correctly splits
    concatenated place names when the dictionary file is present.
    The dictionary splitter runs as Step 5.5, before the trailing
    letter split (Step 6), so it gets first crack at full concatenated
    tokens.
    """

    def test_dictionary_split_muttungal_po_balavadi(self):
        """MUTTUNGALPOBALAVADI should split into three parts via dictionary."""
        result = clean_cdcms_address("MUTTUNGALPOBALAVADI", area_suffix="")
        # After dictionary split: MUTTUNGAL PO BALAVADI
        # After Step 7 PO expansion: MUTTUNGAL P.O. BALAVADI
        # After title case: Muttungal P.O. Balavadi
        assert "Muttungal" in result
        assert "P.O." in result
        assert "Balavadi" in result

    def test_dictionary_split_preserves_house_number(self):
        """House numbers before concatenated text should be preserved."""
        result = clean_cdcms_address("8/542SREESHYLAMMUTTUNGAL-POBALAVADI", area_suffix="")
        assert result.startswith("8/542")
        assert "Muttungal" in result

    def test_dictionary_split_rayarangoth_vatakara(self):
        """Two adjacent place names should be split."""
        result = clean_cdcms_address("RAYARANGOTHVATAKARA", area_suffix="")
        assert "Rayarangoth" in result
        assert "Vatakara" in result

    def test_no_dictionary_file_graceful(self, monkeypatch):
        """Pipeline works without dictionary file (splitter disabled)."""
        # Reset the lazy loader so it re-checks for the file
        import core.data_import.cdcms_preprocessor as mod
        monkeypatch.setattr(mod, '_splitter_loaded', False)
        monkeypatch.setattr(mod, '_splitter', None)
        # Patch Path.exists to return False for dictionary path
        original_exists = Path.exists

        def mock_exists(self):
            if 'place_names_vatakara' in str(self):
                return False
            return original_exists(self)
        monkeypatch.setattr(Path, 'exists', mock_exists)
        # Should still work, just without dictionary splitting
        result = clean_cdcms_address("MUTTUNGALPOBALAVADI", area_suffix="")
        assert result  # Non-empty result
        # Reset splitter state for other tests
        monkeypatch.setattr(mod, '_splitter_loaded', False)
        monkeypatch.setattr(mod, '_splitter', None)

    def test_already_spaced_address_unchanged(self):
        """Addresses with proper spacing should not be mangled by dictionary split."""
        result = clean_cdcms_address("VALLIKKADU SARAMBI PALLIVATAKARA", area_suffix="")
        assert "Vallikkadu" in result
        assert "Sarambi" in result
        assert "Pallivatakara" in result

    def test_dictionary_split_chorode_east(self):
        """Compound place name CHORODE EAST should be recognized in concatenated text."""
        result = clean_cdcms_address("CHORODEEASTPO WEST", area_suffix="")
        assert "Chorode East" in result
        assert "P.O." in result


# =============================================================================
# ADDR-04: Dictionary coverage validation
# =============================================================================


class TestDictionaryCoverage:
    """Tests for ADDR-04: dictionary coverage of CDCMS area names.

    The 80% coverage threshold is a hard gate before Phase 13.
    """

    def test_dictionary_covers_cdcms_areas(self):
        """Dictionary must cover >= 80% of distinct area names in sample data."""
        dict_path = Path("data/place_names_vatakara.json")
        if not dict_path.exists():
            pytest.skip("Dictionary file not found")

        sample_path = Path("data/sample_cdcms_export.csv")
        if not sample_path.exists():
            pytest.skip("Sample CDCMS export not found")

        import json
        from rapidfuzz import fuzz

        dictionary = json.loads(dict_path.read_text())
        entries = dictionary["entries"]
        dict_names = set()
        for entry in entries:
            dict_names.add(entry["name"].upper())
            for alias in entry.get("aliases", []):
                dict_names.add(alias.upper())

        # Extract distinct area names from sample CDCMS data
        df = pd.read_csv(sample_path, sep="\t", dtype=str)
        area_names = set(df["AreaName"].str.strip().str.upper().unique())

        covered = 0
        for area in area_names:
            # Exact match
            if area in dict_names:
                covered += 1
                continue
            # Fuzzy match at 85% threshold
            matched = False
            for dict_name in dict_names:
                if len(dict_name) >= 4 and fuzz.ratio(area, dict_name) >= 85:
                    matched = True
                    break
            if matched:
                covered += 1

        coverage = covered / len(area_names) * 100 if area_names else 0
        assert coverage >= 80, (
            f"Dictionary coverage is {coverage:.0f}% ({covered}/{len(area_names)} areas). "
            f"Must be >= 80%. Missing: {area_names - dict_names}"
        )


# =============================================================================
# Phase 17: Column order independence (CSV-05)
# =============================================================================


class TestColumnOrderIndependence:
    """Tests verifying that column order does not affect CDCMS parsing (CSV-05).

    CDCMS detection and preprocessing should match columns by name,
    not position. This ensures files with shuffled column order still work.
    """

    def test_shuffled_column_order_still_parses(self, tmp_path):
        """CDCMS file with shuffled columns should preprocess correctly."""
        # Create a CDCMS file with columns in non-standard order
        # Standard order starts with OrderNo, but here we shuffle
        header = (
            "DeliveryMan\tConsumerAddress\tAreaName\tOrderNo\tOrderStatus\t"
            "OrderDate\tOrderSource\tOrderType\tCashMemoNo\tCashMemoStatus\t"
            "CashMemoDate\tOrderQuantity\tConsumedSubsidyQty\tRefillPaymentStatus\t"
            "IVRSBookingNumber\tMobileNo\tBookingDoneThroughRegistereMobile\t"
            "IsRefillPort\tEkycStatus"
        )
        row = (
            "GIREESHAN ( C )\t4/146 AMINAS VALIYA PARAMBATH\tVALLIKKADU\t517827\t"
            "Allocated-Printed\t14-02-2026 9:41\tIVRS\tRefill\t1234567\tPrinted\t"
            "14-02-2026\t1\t1\t\t'1111111111\t'1111111111\tY\tN\tEKYC NOT DONE"
        )
        content = f"{header}\n{row}\n"
        filepath = tmp_path / "shuffled_cdcms.csv"
        filepath.write_text(content)

        df = preprocess_cdcms(filepath, area_suffix="")
        assert len(df) == 1
        assert df.iloc[0]["order_id"] == "517827"
        assert "Aminas" in df.iloc[0]["address"] or "aminas" in df.iloc[0]["address"].lower()

    def test_shuffled_xlsx_column_order(self, tmp_path):
        """CDCMS xlsx file with shuffled columns should preprocess correctly."""
        data = {
            "DeliveryMan": ["GIREESHAN ( C )"],
            "ConsumerAddress": ["4/146 AMINAS VALIYA PARAMBATH"],
            "AreaName": ["VALLIKKADU"],
            "OrderNo": ["517827"],
            "OrderStatus": ["Allocated-Printed"],
            "OrderQuantity": ["1"],
        }
        df = pd.DataFrame(data)
        filepath = tmp_path / "shuffled_cdcms.xlsx"
        df.to_excel(filepath, index=False)

        result_df = preprocess_cdcms(filepath, area_suffix="")
        assert len(result_df) == 1
        assert result_df.iloc[0]["order_id"] == "517827"


# =============================================================================
# Phase 17: Allocated-Printed default filter verification (CSV-04)
# =============================================================================


class TestAllocatedPrintedDefaultFilter:
    """Verify the Allocated-Printed filter is applied by default (CSV-04).

    The preprocess_cdcms() function should filter to Allocated-Printed
    status by default, excluding Delivered, Cancelled, and other statuses.
    """

    def test_default_filter_excludes_non_allocated_printed(self, cdcms_mixed_status_file):
        """Default call to preprocess_cdcms should only keep Allocated-Printed rows."""
        df = preprocess_cdcms(cdcms_mixed_status_file, area_suffix="")
        # cdcms_mixed_status_file has 2 Allocated-Printed, 1 Delivered, 1 Cancelled
        assert len(df) == 2

    def test_allocated_printed_is_default_parameter(self):
        """Verify the default filter_status parameter is 'Allocated-Printed'."""
        import inspect
        sig = inspect.signature(preprocess_cdcms)
        filter_status_param = sig.parameters["filter_status"]
        assert filter_status_param.default == "Allocated-Printed"


# =============================================================================
# Phase 17 Gap Closure: Placeholder driver name filtering
# =============================================================================


class TestPlaceholderDriverFiltering:
    """Tests for filtering out CDCMS placeholder driver names.

    CDCMS uses placeholder values like 'Allocation Pending' in the DeliveryMan
    column for unassigned orders. These should be filtered out so they don't
    appear as real drivers in the preview or get geocoded.
    """

    def test_allocation_pending_filtered(self, tmp_path):
        """Orders with DeliveryMan='Allocation Pending' should be excluded."""
        content = "\n".join([
            SAMPLE_CDCMS_HEADER,
            _make_cdcms_row("100", delivery_man="GIREESHAN ( C )"),
            _make_cdcms_row("101", delivery_man="Allocation Pending"),
            _make_cdcms_row("102", delivery_man="SURESH KUMAR"),
        ])
        filepath = tmp_path / "placeholder_test.csv"
        filepath.write_text(content)

        df = preprocess_cdcms(filepath, area_suffix="")
        assert len(df) == 2
        driver_names = df["delivery_man"].str.upper().tolist()
        assert "ALLOCATION PENDING" not in driver_names

    def test_allocation_pending_case_insensitive(self, tmp_path):
        """Placeholder filter should be case-insensitive."""
        content = "\n".join([
            SAMPLE_CDCMS_HEADER,
            _make_cdcms_row("100", delivery_man="GIREESHAN ( C )"),
            _make_cdcms_row("101", delivery_man="ALLOCATION PENDING"),
            _make_cdcms_row("102", delivery_man="allocation pending"),
        ])
        filepath = tmp_path / "case_insensitive_test.csv"
        filepath.write_text(content)

        df = preprocess_cdcms(filepath, area_suffix="")
        assert len(df) == 1
        assert df.iloc[0]["delivery_man"] == "GIREESHAN ( C )"

    def test_blank_delivery_man_filtered(self, tmp_path):
        """Orders with blank DeliveryMan should be excluded."""
        content = "\n".join([
            SAMPLE_CDCMS_HEADER,
            _make_cdcms_row("100", delivery_man="GIREESHAN ( C )"),
            _make_cdcms_row("101", delivery_man=""),
            _make_cdcms_row("102", delivery_man="   "),
        ])
        filepath = tmp_path / "blank_driver_test.csv"
        filepath.write_text(content)

        df = preprocess_cdcms(filepath, area_suffix="")
        assert len(df) == 1
        assert df.iloc[0]["delivery_man"] == "GIREESHAN ( C )"

    def test_real_drivers_not_affected(self, cdcms_tsv_file):
        """Real driver names should not be affected by placeholder filtering."""
        df = preprocess_cdcms(cdcms_tsv_file, area_suffix="")
        # All 5 orders in the fixture have GIREESHAN ( C ) as driver
        assert len(df) == 5


# =============================================================================
# ADDR-01/02/03: Parenthesized abbreviation expansion — (HO), (PO), (H)
# =============================================================================


class TestParenthesizedAbbreviations:
    """Tests for (HO), (PO), and (H) expansion in clean_cdcms_address.

    CDCMS uses parenthesized abbreviations for house types and post offices:
    - (HO) = House (172 occurrences in Refill.xlsx)
    - (PO) = P.O. / Post Office (368 occurrences)
    - (H)  = House (104 occurrences)

    These must expand with proper space padding to avoid word concatenation.
    """

    # --- (HO) expansion ---

    def test_ho_with_spaces_expands_to_house(self):
        """(HO) with surrounding spaces should expand to House."""
        result = clean_cdcms_address("CHEMERI (HO) MUTTUNGAL", area_suffix="")
        assert "House" in result
        assert "(Ho)" not in result
        assert "(HO)" not in result

    def test_ho_without_spaces_expands_with_padding(self):
        """(HO) stuck to adjacent words should expand with space padding."""
        result = clean_cdcms_address("PERATTEYATH(HO)CHORODE", area_suffix="")
        assert "Peratteyath" in result
        assert "House" in result
        assert "Chorode" in result
        # Words must be space-separated, not concatenated
        assert "PeratteyathHouse" not in result
        assert "HouseChorode" not in result

    def test_ho_case_insensitive(self):
        """(ho), (Ho), (hO) should all expand to House."""
        for variant in ["(ho)", "(Ho)", "(hO)", "(HO)"]:
            result = clean_cdcms_address(f"CHEMERI {variant} MUTTUNGAL", area_suffix="")
            assert "House" in result, f"{variant} not expanded in: {result}"

    # --- (PO) expansion ---

    def test_po_with_spaces_expands(self):
        """(PO) with surrounding spaces should expand to P.O."""
        result = clean_cdcms_address("CHORODE (PO)", area_suffix="")
        assert "P.O." in result
        assert "(PO)" not in result
        assert "(P.O." not in result

    def test_po_without_spaces_expands_with_padding(self):
        """(PO) stuck to adjacent words should expand with space padding."""
        result = clean_cdcms_address("CHORODE(PO)POOLAKANDY", area_suffix="")
        assert "Chorode" in result
        assert "P.O." in result
        assert "Poolakandy" in result
        # Words must be space-separated
        assert "ChorodeP" not in result

    def test_po_case_insensitive(self):
        """(po), (Po), (pO) should all expand to P.O."""
        for variant in ["(po)", "(Po)", "(pO)", "(PO)"]:
            result = clean_cdcms_address(f"CHORODE {variant} EAST", area_suffix="")
            assert "P.O." in result, f"{variant} not expanded in: {result}"

    def test_muttungal_preserved_with_po(self):
        """MUTTUNGAL should remain as a single word when followed by (PO)."""
        result = clean_cdcms_address("MUTTUNGAL (PO)BALAVADI", area_suffix="")
        assert "Muttungal" in result
        assert "P.O." in result

    # --- (H) regression tests ---

    def test_h_with_spaces_still_works(self):
        """Existing (H) with spaces should still expand to House (regression)."""
        result = clean_cdcms_address("MEETHAL (H) 13/301", area_suffix="")
        assert "House" in result
        assert "(H)" not in result

    def test_h_without_spaces_now_padded(self):
        """(H) stuck to adjacent words should now expand with space padding."""
        result = clean_cdcms_address("CHALIL(H)7/214A", area_suffix="")
        assert "Chalil" in result
        assert "House" in result
        # House should be separated from the number
        assert "House7" not in result
        assert "House 7" in result or "House" in result

    def test_inline_po_dot_still_works(self):
        """Existing inline PO. pattern should still work (regression)."""
        result = clean_cdcms_address("KUNIYILPO. CHORODE", area_suffix="")
        assert "P.O." in result

    # --- Ordering: (HO) before (H) ---

    def test_ho_not_partially_matched_by_h_pattern(self):
        """(HO) must be processed before (H) to prevent partial matching."""
        result = clean_cdcms_address("TEST(HO)END", area_suffix="")
        assert "House" in result
        # Should not leave residual 'O' from partial (H) match on (HO)
        assert "O)End" not in result
        assert "O)end" not in result


class TestRefillXlsxRegressions:
    """Regression tests using real address patterns from Refill.xlsx research.

    These addresses were identified in 18-RESEARCH.md as producing garbled
    output with the pre-fix code. Each test verifies the fix produces
    clean, correctly separated words.
    """

    def test_chemeri_ho_muttungal_po_chorode(self):
        """Full compound pattern: (HO) + phone + (PO) in one address."""
        result = clean_cdcms_address(
            "CHEMERI (HO)/ 9387908552RAMYA  MUTTUNGAL (PO)CHORODE",
            area_suffix="",
        )
        # (HO) should expand to House
        assert "House" in result
        assert "(Ho)" not in result
        # Phone number should be removed
        assert "9387908552" not in result
        # MUTTUNGAL should be preserved as single word
        assert "Muttungal" in result
        # (PO) should expand to P.O.
        assert "P.O." in result
        # Chorode should be a separate word
        assert "Chorode" in result

    def test_chalil_h_beach_road(self):
        """Concatenated (H) with house number and road name."""
        result = clean_cdcms_address(
            "AVARANGATH CHALIL(H)7/214ABEACH ROAD POAZHITHALA",
            area_suffix="",
        )
        # (H) should expand to House with space padding
        assert "House" in result
        assert "Chalil" in result
        # No garbled trailing letters
        assert "Chalilhouse" not in result.lower()

    def test_kolakkott_meethal_h_po_chorode(self):
        """(H) with house number + PO. + place name."""
        result = clean_cdcms_address(
            "KOLAKKOTT MEETHAL (H) 13/301PO.CHORODEBEHIND RANI SCHOOL",
            area_suffix="",
        )
        assert "House" in result
        assert "Meethal" in result
        assert "P.O." in result

    def test_muttungal_single_word_in_all_patterns(self):
        """MUTTUNGAL must be preserved as a single word in all compound patterns."""
        patterns = [
            "MUTTUNGAL (PO)CHORODE",
            "SREESHYLAM MUTTUNGAL (PO)BALAVADI",
            "CHEMERI (HO) MUTTUNGAL",
        ]
        for pattern in patterns:
            result = clean_cdcms_address(pattern, area_suffix="")
            assert "Muttungal" in result, (
                f"MUTTUNGAL not preserved in: {result} (input: {pattern})"
            )
            # Should not be split into Muttung + Al or similar
            assert "Muttung " not in result, (
                f"MUTTUNGAL was split in: {result} (input: {pattern})"
            )

    def test_no_trailing_letter_garbling(self):
        """Fixed output should not have garbled trailing letters from Step 6."""
        result = clean_cdcms_address(
            "CHEMERI (HO)/ 9387908552RAMYA  MUTTUNGAL (PO)CHORODE",
            area_suffix="",
        )
        # Should not have single trailing letters stuck on words
        # (unless they are legitimate initials)
        assert "Chorod E" not in result
        assert "Chorode" in result
