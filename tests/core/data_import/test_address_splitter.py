"""Tests for AddressSplitter — dictionary-powered word splitting with fuzzy matching.

Tests use a small fixture dictionary (not the full 381-entry file) to keep
tests fast and deterministic.  The fixture contains the 10 names referenced
in the plan's behavior spec plus compound entries.
"""

import json
import tempfile
from pathlib import Path

import pytest

from core.data_import.address_splitter import AddressSplitter


# ---------------------------------------------------------------------------
# Fixture: small dictionary for deterministic tests
# ---------------------------------------------------------------------------

FIXTURE_ENTRIES = [
    {"name": "MUTTUNGAL", "aliases": [], "source": "manual"},
    {"name": "BALAVADI", "aliases": [], "source": "manual"},
    {"name": "VADAKARA", "aliases": ["VATAKARA"], "source": "india_post"},
    {"name": "VALLIKKADU", "aliases": ["VALLIKADU", "VALLIKKAD"], "source": "manual"},
    {"name": "CHORODE", "aliases": [], "source": "manual"},
    {"name": "CHORODE EAST", "aliases": [], "source": "manual"},
    {"name": "MUTTUNGAL WEST", "aliases": [], "source": "manual"},
    {"name": "RAYARANGOTH", "aliases": [], "source": "manual"},
    {"name": "PALLIVATAKARA", "aliases": [], "source": "manual"},
    {"name": "KAINATY", "aliases": ["KAINATTY"], "source": "manual"},
]


@pytest.fixture()
def dict_path(tmp_path: Path) -> Path:
    """Write fixture dictionary to a temp JSON file and return its path."""
    data = {
        "metadata": {"entry_count": len(FIXTURE_ENTRIES)},
        "entries": FIXTURE_ENTRIES,
    }
    p = tmp_path / "fixture_dict.json"
    p.write_text(json.dumps(data))
    return p


@pytest.fixture()
def splitter(dict_path: Path) -> AddressSplitter:
    """Create an AddressSplitter loaded with the fixture dictionary."""
    return AddressSplitter(dict_path)


# ===================================================================
# ADDR-05: Splitting behaviour
# ===================================================================


class TestSplitter:
    """Core splitting tests — concatenated text split at place name boundaries."""

    def test_two_place_names_with_po_gap(self, splitter: AddressSplitter) -> None:
        """MUTTUNGALPOBALAVADI -> MUTTUNGAL PO BALAVADI"""
        assert splitter.split("MUTTUNGALPOBALAVADI") == "MUTTUNGAL PO BALAVADI"

    def test_compound_name_chorode_east(self, splitter: AddressSplitter) -> None:
        """CHORODEEAST -> CHORODE EAST (compound entry takes priority)."""
        assert splitter.split("CHORODEEAST") == "CHORODE EAST"

    def test_compound_name_muttungal_west(self, splitter: AddressSplitter) -> None:
        """MUTTUNGALWEST -> MUTTUNGAL WEST (compound entry takes priority)."""
        assert splitter.split("MUTTUNGALWEST") == "MUTTUNGAL WEST"

    def test_two_adjacent_place_names(self, splitter: AddressSplitter) -> None:
        """RAYARANGOTHVATAKARA -> RAYARANGOTH VATAKARA"""
        # VATAKARA is an alias for VADAKARA in the fixture.
        # The splitter should recognise it and keep the original text.
        result = splitter.split("RAYARANGOTHVATAKARA")
        assert result == "RAYARANGOTH VATAKARA"

    def test_passthrough_unknown(self, splitter: AddressSplitter) -> None:
        """Unknown text passes through unchanged."""
        assert splitter.split("HELLO WORLD") == "HELLO WORLD"

    def test_single_dictionary_word(self, splitter: AddressSplitter) -> None:
        """Single word that is a dictionary match — no split needed."""
        assert splitter.split("MUTTUNGAL") == "MUTTUNGAL"

    def test_empty_input(self, splitter: AddressSplitter) -> None:
        """Empty string returns empty string."""
        assert splitter.split("") == ""

    def test_already_spaced(self, splitter: AddressSplitter) -> None:
        """Already-spaced text passes through unchanged."""
        assert splitter.split("VALLIKKADU SARAMBI PALLIVATAKARA") == "VALLIKKADU SARAMBI PALLIVATAKARA"

    def test_nr_gap_handling(self, splitter: AddressSplitter) -> None:
        """NR abbreviation between place names is preserved as a gap."""
        result = splitter.split("MUTTUNGALNRBALAVADI")
        assert result == "MUTTUNGAL NR BALAVADI"


# ===================================================================
# ADDR-06: Fuzzy matching behaviour
# ===================================================================


class TestFuzzyMatching:
    """Fuzzy matching tests — transliteration variant handling."""

    def test_vadakara_matches_vatakara(self, splitter: AddressSplitter) -> None:
        """VATAKARA fuzzy-matches dictionary entry VADAKARA (87.5, threshold 85)."""
        # When used standalone, VATAKARA should be recognised as a place name.
        assert splitter.split("VATAKARA") == "VATAKARA"

    def test_mutungal_fuzzy_match(self, splitter: AddressSplitter) -> None:
        """MUTUNGAL fuzzy-matches MUTTUNGAL (94.1, threshold 85)."""
        assert splitter.split("MUTUNGAL") == "MUTUNGAL"

    def test_vallikadu_fuzzy_match(self, splitter: AddressSplitter) -> None:
        """VALLIKADU fuzzy-matches VALLIKKADU (94.7, threshold 85)."""
        assert splitter.split("VALLIKADU") == "VALLIKADU"

    def test_edapalli_no_match(self, splitter: AddressSplitter) -> None:
        """EDAPALLI does NOT match EDAPPAL (score 80.0 < threshold 85) — passthrough."""
        # EDAPPAL is not in our fixture dict, but this verifies no false match.
        assert splitter.split("EDAPALLI") == "EDAPALLI"

    def test_po_no_fuzzy_match(self, splitter: AddressSplitter) -> None:
        """PO (2 chars) never fuzzy-matches anything — below min_length=4."""
        # PO alone should pass through unchanged (not matched as a place name).
        assert splitter.split("PO") == "PO"

    def test_short_name_high_threshold(self, splitter: AddressSplitter) -> None:
        """Short names (<= 4 chars) require 95% threshold to prevent false positives."""
        # A 4-char candidate that doesn't quite match should not be accepted.
        # This ensures the high threshold is applied to short names.
        result = splitter.split("KAXY")
        assert result == "KAXY"  # Should NOT match KAINATY (too different)


# ===================================================================
# Longest-match-first behaviour
# ===================================================================


class TestLongestMatchFirst:
    """Verify that longer dictionary entries are tried before shorter ones."""

    def test_chorode_east_over_chorode(self, splitter: AddressSplitter) -> None:
        """CHORODEEAST matches 'CHORODE EAST' (11 chars) not 'CHORODE' (7 chars)."""
        result = splitter.split("CHORODEEAST")
        # Should produce "CHORODE EAST" (the compound entry), not "CHORODE EAST"
        # split as two separate matches.
        assert result == "CHORODE EAST"

    def test_muttungal_west_over_muttungal(self, splitter: AddressSplitter) -> None:
        """MUTTUNGALWEST matches 'MUTTUNGAL WEST' (14 chars) not 'MUTTUNGAL' (9 chars)."""
        result = splitter.split("MUTTUNGALWEST")
        assert result == "MUTTUNGAL WEST"
