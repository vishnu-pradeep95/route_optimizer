"""Tests for address normalization used in geocoding cache key consistency.

Verifies that normalize_address() correctly:
- Lowercases all characters
- Collapses multiple whitespace to a single space
- Strips leading/trailing whitespace
- Strips decorative punctuation (periods, commas)
- Preserves meaningful punctuation (slashes, hyphens, parentheses)
- Normalizes Unicode to NFC form
- Is idempotent (applying twice produces same result)
- Handles empty strings gracefully
- Works with real CDCMS Kerala delivery addresses

normalize_address() is a pure function with no I/O, no DB, no side effects.
It is the single source of truth for all cache key normalization.
"""

import unicodedata

import pytest

from core.geocoding.normalize import normalize_address


class TestNormalizeAddress:
    """Comprehensive tests for the normalize_address() pure function."""

    # --- Basic transformations ---

    def test_lowercase(self):
        """Uppercase letters are converted to lowercase."""
        assert normalize_address("MG Road") == "mg road"

    def test_whitespace_collapse(self):
        """Multiple spaces between words collapse to a single space."""
        assert normalize_address("Near  SBI   MG Road") == "near sbi mg road"

    def test_strip_ends(self):
        """Leading and trailing whitespace is removed."""
        assert normalize_address("  MG Road  ") == "mg road"

    def test_tabs_and_newlines(self):
        """Tabs and newlines are treated as whitespace and collapsed."""
        assert normalize_address("MG Road\t\nVatakara") == "mg road vatakara"

    # --- Decorative punctuation removal ---

    def test_strip_periods(self):
        """Periods are stripped (decorative in Kerala addresses like M.G. Road)."""
        assert normalize_address("M.G. Road") == "mg road"

    def test_strip_commas(self):
        """Commas are stripped (decorative address separators)."""
        assert normalize_address("Near SBI, MG Road, Vatakara") == "near sbi mg road vatakara"

    # --- Meaningful punctuation preserved ---

    def test_preserve_slashes(self):
        """Slashes in house numbers like 4/302 are preserved."""
        assert normalize_address("4/302 House Name") == "4/302 house name"

    def test_preserve_hyphens(self):
        """Hyphens in house numbers like 12-B are preserved."""
        assert normalize_address("12-B MG Road") == "12-b mg road"

    def test_preserve_parentheses(self):
        """Parentheses in post office names are preserved (periods inside stripped)."""
        assert normalize_address("Rayarangoth (P.O.)") == "rayarangoth (po)"

    # --- Unicode NFC normalization ---

    def test_unicode_nfc_normalization(self):
        """NFD and NFC forms of the same character produce identical output.

        This matters for Malayalam text where virama/chillu variations
        may appear in different Unicode forms from different input sources.
        """
        # Create the same string in NFD and NFC forms
        nfc_form = unicodedata.normalize("NFC", "\u00e9")  # e-acute composed
        nfd_form = unicodedata.normalize("NFD", "\u00e9")  # e + combining acute
        assert nfc_form != nfd_form  # Sanity: they ARE different byte sequences
        assert normalize_address(nfd_form) == normalize_address(nfc_form)

    # --- Idempotency ---

    def test_idempotent_simple(self):
        """Normalizing an already-normalized string returns the same result."""
        addr = "M.G. Road, Vatakara"
        once = normalize_address(addr)
        twice = normalize_address(once)
        assert once == twice

    def test_idempotent_complex(self):
        """Idempotency holds for complex addresses with multiple normalizations."""
        addr = "  Near  SBI,  M.G. Road,  Vatakara  "
        once = normalize_address(addr)
        twice = normalize_address(once)
        assert once == twice

    # --- Edge cases ---

    def test_empty_string(self):
        """Empty string normalizes to empty string."""
        assert normalize_address("") == ""

    def test_combined_transformations(self):
        """Multiple normalization steps applied together."""
        assert normalize_address("M.G. Road, Vatakara") == "mg road vatakara"

    # --- Real CDCMS addresses ---

    def test_real_cdcms_address(self):
        """A real CDCMS export address normalizes correctly.

        This is the kind of address that comes from Kerala delivery data.
        Commas and periods stripped, whitespace collapsed, lowercased.
        """
        raw = "4/146 Aminas Valiya Parambath Near Vallikkadu Sarambi Pallivatakara, Vatakara, Kozhikode, Kerala"
        expected = "4/146 aminas valiya parambath near vallikkadu sarambi pallivatakara vatakara kozhikode kerala"
        assert normalize_address(raw) == expected
