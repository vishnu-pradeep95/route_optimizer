"""Address normalization for geocoding cache key consistency.

Single source of truth for all address normalization in the project.
Every cache read and cache write MUST use this function.

Why a dedicated module?
The codebase previously had three separate normalization implementations:
- GoogleGeocoder: `" ".join(address.lower().split())` then SHA-256
- repository.get_cached_geocode(): `address_raw.strip().lower()`
- repository.save_geocode_cache(): `address_raw.strip().lower()`

These produced different results for the same address, causing duplicate
map pins and cache misses. This module eliminates that inconsistency.
"""

import re
import unicodedata

# Strip periods and commas -- decorative in CDCMS addresses.
# Examples: "M.G. Road" -> "MG Road", "Near SBI, MG Road" -> "Near SBI MG Road"
# Do NOT strip: hyphens (house numbers "12-B"), slashes ("4/302"),
# parentheses (P.O. names "(P.O.)").
_DECORATIVE_PUNCT = re.compile(r'[.,]+')


def normalize_address(address: str) -> str:
    """Normalize an address for geocoding cache key consistency.

    Deterministic, pure function. No I/O, no side effects.

    Steps (order matters):
    1. Unicode NFC normalization
    2. Lowercase
    3. Strip decorative punctuation (periods, commas)
    4. Collapse whitespace to single space + strip ends

    Args:
        address: Raw address string from any source (CDCMS export, user input, etc.)

    Returns:
        Normalized address suitable for cache key lookup.
    """
    text = unicodedata.normalize('NFC', address)
    text = text.lower()
    text = _DECORATIVE_PUNCT.sub('', text)
    text = ' '.join(text.split())
    return text
