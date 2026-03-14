"""Dictionary-powered address splitter for concatenated CDCMS text.

CDCMS (Cylinder Delivery & Customer Management System) exports addresses with
place names concatenated without spaces.  The regex-based trailing-letter split
in ``cdcms_preprocessor.py`` handles single trailing initials but cannot detect
multi-character place names embedded in concatenated text.

This module provides ``AddressSplitter`` which loads a place name dictionary
(``data/place_names_vatakara.json``) and scans concatenated text left-to-right,
inserting spaces at known place name boundaries.

Example::

    >>> splitter = AddressSplitter("data/place_names_vatakara.json")
    >>> splitter.split("MUTTUNGALPOBALAVADI")
    'MUTTUNGAL PO BALAVADI'

The splitter runs on raw uppercase text *before* title-casing — it is inserted
between Step 6 (trailing letter split) and Step 7 (second-pass abbreviation
expansion) of ``clean_cdcms_address()``.
"""

import json
import logging
from pathlib import Path

from rapidfuzz import fuzz

logger = logging.getLogger(__name__)

# Abbreviation gaps that appear between concatenated place names.
# These are handled by existing pipeline steps (Step 7), not by this splitter.
# We detect them here only to skip past them when scanning.
_ABBR_GAPS = ("PO", "NR")

# Minimum candidate length for fuzzy matching.  Substrings shorter than this
# are never attempted as fuzzy matches to prevent false positives on
# abbreviations like PO, NR, KB.
_MIN_FUZZY_LENGTH = 4


def _get_threshold(name_len: int) -> int:
    """Return the fuzzy-match threshold for a dictionary entry of given length.

    Shorter place names require stricter matching to prevent false positives:
    - len <= 4:  threshold 95  (e.g. prevents "PO" matching "PA")
    - len 5-6:   threshold 90  (e.g. prevents "EDAPPAL" matching "EDAPALLI")
    - len >= 7:  threshold 85  (e.g. allows "VATAKARA" matching "VADAKARA")
    """
    if name_len <= 4:
        return 95
    elif name_len <= 6:
        return 90
    else:
        return 85


class AddressSplitter:
    """Split concatenated CDCMS address text using a place name dictionary.

    Loads a JSON dictionary file containing Kerala place names and uses
    longest-match-first scanning with optional fuzzy matching to find
    place name boundaries in concatenated text.

    Args:
        dictionary_path: Path to the place name dictionary JSON file.
            Expected schema: ``{"entries": [{"name": "...", ...}, ...]}``
    """

    def __init__(self, dictionary_path: str | Path) -> None:
        self._entries: list[str] = []  # Sorted by len desc (longest-match-first)
        self._load(dictionary_path)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def _load(self, path: str | Path) -> None:
        """Load and index dictionary entries from JSON file."""
        path = Path(path)
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)

        raw_entries: list[str] = []
        for entry in data.get("entries", []):
            name = entry.get("name", "").strip().upper()
            if name:
                raw_entries.append(name)
            # Also index any aliases so fuzzy matching can find them
            for alias in entry.get("aliases", []):
                alias_upper = alias.strip().upper()
                if alias_upper and alias_upper not in raw_entries:
                    raw_entries.append(alias_upper)

        # Deduplicate and sort by length descending (longest-match-first)
        seen: set[str] = set()
        unique: list[str] = []
        for name in raw_entries:
            if name not in seen:
                seen.add(name)
                unique.append(name)

        self._entries = sorted(unique, key=len, reverse=True)
        logger.info(
            "AddressSplitter loaded %d entries from %s",
            len(self._entries),
            path.name,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def split(self, text: str) -> str:
        """Split concatenated words at known place name boundaries.

        Algorithm:
        1. Split input on whitespace into tokens.
        2. For each token, run ``_split_token`` which scans left-to-right
           trying longest dictionary matches first (exact then fuzzy).
        3. On match: extract matched text, check for PO/NR gap, advance.
        4. Unmatched text passes through unchanged.
        5. Re-join all output parts with single spaces.

        This per-token approach prevents false positives from spaces being
        included in fuzzy-match candidates when the input is already
        partially spaced (e.g. ``"VALLIKKADU SARAMBI PALLIVATAKARA"``).

        Args:
            text: Raw address text (typically uppercase from CDCMS).

        Returns:
            Text with spaces inserted at place name boundaries.
        """
        if not text or not text.strip():
            return text

        tokens = text.split()
        result_parts: list[str] = []
        for token in tokens:
            split_parts = self._split_token(token)
            result_parts.extend(split_parts)

        return " ".join(result_parts)

    def _split_token(self, token: str) -> list[str]:
        """Split a single whitespace-free token at place name boundaries.

        Scans left-to-right through the uppercase token, trying each
        dictionary entry (longest first).  Handles PO/NR abbreviation
        gaps between consecutive place names.

        Returns:
            List of sub-parts (may be just ``[token]`` if no splits found).
        """
        upper = token.upper()
        parts: list[str] = []
        pos = 0

        while pos < len(upper):
            match = self._find_match(upper, pos)
            if match is not None:
                matched_name, end_pos = match
                # For compound names (with spaces), output the entry name
                # so the space is restored.  For simple names, preserve
                # the original token case (important for fuzzy matches
                # where input differs from dictionary spelling).
                if " " in matched_name:
                    parts.append(matched_name)
                else:
                    parts.append(token[pos:end_pos])
                pos = end_pos

                # Check for abbreviation gap (PO, NR) immediately after
                remainder = upper[pos:]
                for abbr in _ABBR_GAPS:
                    if remainder.startswith(abbr):
                        parts.append(token[pos:pos + len(abbr)])
                        pos += len(abbr)
                        break
            else:
                # No dictionary match at this position.
                # Accumulate unmatched characters until next match or end.
                chunk_start = pos
                pos += 1
                while pos < len(upper):
                    if self._find_match(upper, pos) is not None:
                        break
                    pos += 1
                parts.append(token[chunk_start:pos])

        return parts

    # ------------------------------------------------------------------
    # Internal matching
    # ------------------------------------------------------------------

    def _find_match(self, text: str, start: int) -> tuple[str, int] | None:
        """Find best dictionary match starting at position ``start``.

        Tries each dictionary entry (longest first):
        1. Exact substring match at position.
        2. Fuzzy match on the candidate substring of the same length,
           using length-dependent threshold.

        For entries with spaces (compound names like "CHORODE EAST"),
        the spaces in the entry name are stripped for matching against
        the concatenated text, but the full spaced name is what gets
        "matched" for output purposes.

        Returns:
            ``(matched_name, end_position)`` or ``None``.
        """
        remaining = len(text) - start

        for entry_name in self._entries:
            # For compound names, the match length in concatenated text
            # is the entry name without spaces.
            compact_name = entry_name.replace(" ", "")
            match_len = len(compact_name)

            if match_len > remaining:
                continue

            candidate = text[start:start + match_len]

            # Exact match
            if candidate == compact_name:
                return (entry_name, start + match_len)

            # Fuzzy match (only for candidates >= _MIN_FUZZY_LENGTH)
            # Guard: first AND last characters must match to prevent false
            # positives from off-by-one alignment. Without this guard,
            # "LMUTTUNGA" fuzzy-matches "MUTTUNGAL" (ratio 88.9% > 85%
            # threshold) and "MMUTTUNGA" also matches (same score, same
            # first char). Requiring last-char match catches both cases.
            if (
                match_len >= _MIN_FUZZY_LENGTH
                and candidate[0] == compact_name[0]
                and candidate[-1] == compact_name[-1]
            ):
                threshold = _get_threshold(match_len)
                score = fuzz.ratio(compact_name, candidate, score_cutoff=threshold)
                if score > 0:
                    return (entry_name, start + match_len)

        return None
