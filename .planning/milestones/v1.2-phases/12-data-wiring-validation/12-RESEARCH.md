# Phase 12: Place Name Dictionary and Address Splitter - Research

**Researched:** 2026-03-11
**Domain:** Kerala place name dictionary construction, fuzzy string matching, concatenated address splitting
**Confidence:** HIGH

## Summary

Phase 12 creates a domain-specific Kerala place name dictionary and integrates a dictionary-aware word splitter into the CDCMS address cleaning pipeline. The dictionary is built from two free APIs (OSM Overpass + India Post PIN Code) and committed as a static JSON file. The splitter finds known place names inside concatenated CDCMS text and inserts spaces at boundaries.

**Critical finding from live API testing:** The CDCMS delivery-zone place names (VALLIKKADU, RAYARANGOTH, MUTTUNGAL, BALAVADI, KAINATY, K.T.BAZAR) are NOT present in OSM's place node data for the Vatakara area. OSM has 367 nodes within 30km but uses different names. The India Post API covers 5 of 9 CDCMS area names exactly (CHORODE, CHORODE EAST, MUTTUNGAL, MUTTUNGAL WEST, RAYARANGOTH) and 1 via fuzzy match (VATAKARA/VADAKARA), but misses 3 (VALLIKKADU, KAINATY, K.T.BAZAR). The India Post API also does NOT provide lat/lon coordinates. The build script must therefore: (1) merge both API sources, (2) include a hardcoded seed list for hyper-local names missing from both APIs, (3) extract coordinates from OSM where available or use approximate depot-relative positions.

**Primary recommendation:** Build the dictionary in three layers: India Post API (area names that match CDCMS), OSM Overpass (broader geographical coverage with lat/lon), and a manual seed list (CDCMS-specific names neither API has). Use RapidFuzz 3.14.x with length-dependent thresholds (85% for 7+ char names, 90% for 5-6 char, 95% for 4 char) for transliteration variant matching.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ADDR-04 | Place name dictionary (~285 entries) built from OSM Overpass + India Post APIs and committed to repo | OSM provides 367 place nodes within 30km; India Post provides ~22 post offices in Vadakara division; merge + deduplicate + manual seed yields 200+ entries. Build script pattern and API query syntax documented below. |
| ADDR-05 | Dictionary-aware word splitter splits concatenated text at known place name boundaries | Longest-match-first algorithm with positional scanning. Integration point is between Step 6 (trailing letter split) and Step 7 (second-pass abbreviation expansion) in `clean_cdcms_address()`. |
| ADDR-06 | Fuzzy matching handles transliteration variants with length-dependent thresholds | RapidFuzz 3.14.3 `fuzz.ratio` validated: VATAKARA/VADAKARA=87.5, VALLIKKADU/VALLIKADU=94.7, MUTTUNGAL/MUTUNGAL=94.1. Length-dependent thresholds (85/90/95) correctly accept all true variants and reject all false positives in testing. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| RapidFuzz | 3.14.3 | Fuzzy string matching for transliteration variants | MIT license, C++ backend (~3.2MB wheel), 10-100x faster than thefuzz/fuzzywuzzy. Only new dependency needed. |
| requests | 2.32.5 | HTTP calls to OSM Overpass and India Post APIs (build script only) | Already in requirements.txt. Used only by build script, not at runtime. |
| json (stdlib) | - | Dictionary file format (read/write) | Zero dependency. Static JSON file committed to repo. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | 0.28.1 | Alternative to requests for async HTTP in build script | Already installed; use if async API calls needed |
| pandas | 3.0.1 | CSV analysis for coverage validation | Already installed; useful for analyzing sample_cdcms_export.csv during build |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| RapidFuzz | thefuzz (fuzzywuzzy) | RapidFuzz is 10-100x faster, MIT licensed (no GPL issues), same API |
| RapidFuzz | python-Levenshtein | Lower-level, would need to implement ratio scoring manually |
| Static JSON | SQLite dictionary | Overkill for ~300 entries, adds complexity; JSON loads in <1ms |

**Installation:**
```bash
pip install rapidfuzz==3.14.3
```

**Also add to requirements.txt:**
```
rapidfuzz==3.14.3
```

**Also add to Dockerfile (already handled by requirements.txt).**

## Architecture Patterns

### Recommended Project Structure
```
data/
  place_names_vatakara.json       # Static dictionary (committed to repo)
scripts/
  build_place_dictionary.py       # One-time build script (OSM + India Post + seeds)
core/data_import/
  address_splitter.py             # AddressSplitter class (new)
  cdcms_preprocessor.py           # Modified: integrate splitter call
tests/core/data_import/
  test_address_splitter.py        # Splitter tests (new)
```

### Pattern 1: Dictionary Build Script
**What:** Standalone Python script that queries external APIs and generates a static JSON file.
**When to use:** One-time or periodic dictionary refresh. Not called at runtime.
**Key design decisions:**
- Script is idempotent -- re-running produces the same output (modulo API data changes)
- Three-layer merge: India Post (primary for area names) + OSM (primary for coordinates and broader names) + manual seed (for hyper-local CDCMS-specific names)
- Deduplication uses fuzzy matching at 85% threshold to merge variants
- Output sorted alphabetically for easy diffing

**OSM Overpass query (verified working):**
```python
# Queries 367 place nodes within 30km of Vatakara depot
OVERPASS_QUERY = """
[out:json][timeout:30];
(
  node["place"~"^(village|hamlet|town|neighbourhood|suburb|locality)$"]
    (around:30000,11.6244,75.5796);
);
out body;
"""
# Endpoint: https://overpass-api.de/api/interpreter
# Method: POST, data={'data': OVERPASS_QUERY}
# Returns: {"elements": [{"type":"node","id":...,"lat":...,"lon":...,"tags":{"name":"...","name:ml":"...","place":"..."}}]}
```

**India Post API (verified working):**
```python
# Returns post offices for a given PIN code
# Endpoint: https://api.postalpincode.in/pincode/{pin}
# Method: GET, no auth required
# Returns: [{"Status":"Success","PostOffice":[{"Name":"Muttungal","Pincode":"673106","District":"Kozhikode",...}]}]
# Pin codes for Vatakara delivery zone: 673101-673106
# NOTE: Does NOT return lat/lon coordinates
```

**Manual seed list (critical for CDCMS coverage):**
```python
# Names found in CDCMS data but missing from both APIs
MANUAL_SEEDS = [
    {"name": "VALLIKKADU", "aliases": ["VALLIKADU", "VALLIKKAD"], "type": "locality"},
    {"name": "BALAVADI", "type": "locality"},
    {"name": "KAINATY", "aliases": ["KAINATTY"], "type": "locality"},
    {"name": "K.T.BAZAR", "aliases": ["KT BAZAR", "KTBAZAR"], "type": "locality"},
    {"name": "SARAMBI", "type": "locality"},
    {"name": "EYYAMKUTTI", "type": "locality"},
    {"name": "PALLIVATAKARA", "type": "locality"},
    {"name": "MEATHALA", "type": "locality"},
    {"name": "KALARIKKANDI", "type": "locality"},
    {"name": "PADINJARA", "type": "locality"},
    {"name": "ONTHAMKAINATTY", "aliases": ["ONTHAM KAINATTY"], "type": "locality"},
    {"name": "SREESHYLAM", "type": "house_name"},
    # ... expand from full CDCMS data analysis
]
```

### Pattern 2: AddressSplitter with Lazy Loading
**What:** Class that loads the dictionary once and provides a `split()` method for the cleaning pipeline.
**When to use:** Called from `clean_cdcms_address()` between existing steps.

```python
# Source: Design spec + validated algorithm
from pathlib import Path
from rapidfuzz import fuzz

class AddressSplitter:
    """Split concatenated CDCMS address text using a place name dictionary."""

    def __init__(self, dictionary_path: str | Path):
        """Load place name dictionary from JSON file.

        Builds internal lookup sorted by name length descending
        (longest-match-first strategy).
        """
        self._entries = []  # List of (name, entry_dict), sorted by len(name) desc
        self._load(dictionary_path)

    def split(self, text: str) -> str:
        """Split concatenated words at known place name boundaries.

        Algorithm:
        1. Uppercase the input for matching
        2. Scan left-to-right, at each position try longest dictionary match first
        3. On match: extract matched text, check for PO/NR gap before next match
        4. Recurse on remainder
        5. Unknown text passes through unchanged
        """
        ...

    def _find_match(self, text: str, start: int) -> tuple[str, int] | None:
        """Find best dictionary match starting at position `start`.

        Uses exact match first, then fuzzy match with length-dependent threshold:
        - len <= 4: threshold 95
        - len 5-6: threshold 90
        - len >= 7: threshold 85
        """
        ...
```

**Integration point in `clean_cdcms_address()`:**
```python
# Between Step 6 (trailing letter split) and Step 7 (second-pass abbreviations)
# Lazy initialization: splitter is None if dictionary file is missing
if _splitter is not None:
    addr = _splitter.split(addr)
```

### Pattern 3: Length-Dependent Fuzzy Thresholds
**What:** Shorter place names require stricter matching to prevent false positives.
**Validated with RapidFuzz 3.14.3:**

| Name Length | Threshold | Rationale |
|-------------|-----------|-----------|
| <= 4 chars | 95 | Very short names like "PO", "NR" must match almost exactly |
| 5-6 chars | 90 | Medium names like "CHORODE" need moderate strictness |
| >= 7 chars | 85 | Long names like "MUTTUNGAL", "VALLIKKADU" tolerate more variation |

**Verified test results:**

| Dictionary Entry | Candidate | Score | Threshold | Result |
|-----------------|-----------|-------|-----------|--------|
| MUTTUNGAL | MUTUNGAL | 94.1 | 85 | MATCH (correct) |
| VALLIKKADU | VALLIKADU | 94.7 | 85 | MATCH (correct) |
| KAINATY | KAINATTY | 93.3 | 85 | MATCH (correct) |
| VATAKARA | VADAKARA | 87.5 | 85 | MATCH (correct) |
| EDAPPAL | EDAPALLI | 80.0 | 85 | NO MATCH (correct -- different place) |
| MUTTUNGAL | MUTTATHUPLAVU | 54.5 | 85 | NO MATCH (correct) |
| PALLIVATAKARA | VADAKARA | 66.7 | 85 | NO MATCH (correct) |

### Anti-Patterns to Avoid
- **Using `fuzz.partial_ratio` for substring detection:** Returns 100.0 for "PO" in "MUTTUNGALPOBALAVADI" -- produces massive false positives on short strings. Use positional scanning with `fuzz.ratio` on candidate substrings instead.
- **Splitting at every dictionary match without length priority:** Would incorrectly match "MUTTU" inside "MUTTUNGAL" if "MUTTU" were in the dictionary. Always try longest matches first.
- **Making API calls at runtime:** The dictionary is static JSON. OSM/India Post APIs are called only by the build script, never during address cleaning.
- **Relying solely on OSM for CDCMS area names:** OSM has zero overlap with the 9 CDCMS area names in the sample data. India Post + manual seeds are required.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fuzzy string matching | Custom Levenshtein implementation | RapidFuzz `fuzz.ratio` | C++ backend, handles Unicode, well-tested edge cases, score_cutoff for early termination |
| Place name deduplication | Manual name comparison loops | RapidFuzz `process.extractOne` | Optimized for one-to-many matching, handles large dictionaries efficiently |
| OSM data extraction | Custom HTTP + XML parsing | `requests` + JSON output mode (`[out:json]`) | Overpass API natively returns JSON, no XML parsing needed |
| Haversine distance | Custom math | Already available or trivial formula | Used in build script for radius filtering; 6 lines of math, well-known formula |

**Key insight:** The only new dependency is RapidFuzz (~3.2MB). Everything else uses existing libraries (requests, json, pathlib) or standard library math.

## Common Pitfalls

### Pitfall 1: India Post API Has No Coordinates
**What goes wrong:** The design spec mentions both APIs as data sources, but India Post API returns only names and PIN codes -- no lat/lon. Building a dictionary entry without coordinates makes centroid fallback (Phase 13) impossible.
**Why it happens:** The postalpincode.in API schema does not include geographic coordinates.
**How to avoid:** For India Post entries, attempt to find matching coordinates from OSM data (using fuzzy name matching). For entries with no OSM match, use the depot coordinates as approximate center or leave coordinates null with a flag.
**Warning signs:** Dictionary entries with null/zero lat/lon values.

### Pitfall 2: OSM Name Mismatch with CDCMS Names
**What goes wrong:** OSM names the town "Vadakara" but CDCMS uses "VATAKARA". OSM has "Chorode" but not "CHORODE EAST". OSM has zero entries for VALLIKKADU, RAYARANGOTH, MUTTUNGAL, BALAVADI, KAINATY.
**Why it happens:** CDCMS uses India Post delivery area names, which are hyper-local subdivisions not always mapped in OSM.
**How to avoid:** Use India Post as the primary source for delivery-area names. Use OSM for broader geographic coverage and coordinates. Include a manual seed list for names in neither.
**Warning signs:** Dictionary coverage below 80% of distinct CDCMS area names.

### Pitfall 3: False Positives on Short Name Substrings
**What goes wrong:** A 3-letter place name like "PO" matches inside every word containing "PO". "NR" matches inside "KUNIYILNR".
**Why it happens:** Short strings have high partial match probability in concatenated text.
**How to avoid:** (1) Length-dependent thresholds prevent fuzzy matches on short names. (2) The splitter algorithm uses positional scanning (not substring search) -- it only tries matches at positions where previous matches ended, not arbitrary positions. (3) Abbreviations like PO/NR are handled by the existing abbreviation expansion steps, NOT by the dictionary splitter.
**Warning signs:** Addresses being split at incorrect boundaries; words like "POOL" being mistaken for "PO" + "OL".

### Pitfall 4: Greedy Matching Conflicts
**What goes wrong:** "MUTTUNGALWEST" contains both "MUTTUNGAL" and "MUTTUNGAL WEST" in the dictionary. Greedy longest-match picks "MUTTUNGAL WEST" (13 chars) over "MUTTUNGAL" (9 chars), which is correct. But if only "MUTTUNGAL" and "WEST" are separate entries, greedy match might not combine them.
**Why it happens:** Compound names (CHORODE EAST, MUTTUNGAL WEST) need special handling.
**How to avoid:** Include compound names as single dictionary entries. The splitter should check multi-word matches before single-word matches. Sort entries by total character length descending.
**Warning signs:** "CHORODEEAST" splitting as "CHOROD" + "EEAST" instead of "CHORODE EAST".

### Pitfall 5: Dictionary Coverage Hard Gate
**What goes wrong:** The 80% coverage threshold (success criterion 2) is measured against distinct area names in historical CDCMS data. If coverage falls below 80%, Phase 13 is blocked.
**Why it happens:** Only 9 distinct areas in the 27-row sample CSV. Full historical data may have 20-40+ areas.
**How to avoid:** The build script must analyze the sample CDCMS CSV (`data/sample_cdcms_export.csv`) and report coverage. Manual seeds should be added until coverage exceeds 80%. Coverage validation should be a test, not just a log message.
**Warning signs:** Build script reports coverage below threshold. Missing areas not in manual seed list.

## Code Examples

### OSM Overpass API Call (verified working)
```python
# Source: Verified via live API call to overpass-api.de on 2026-03-11
import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
DEPOT_LAT, DEPOT_LON = 11.6244, 75.5796
RADIUS_M = 30000

query = f"""
[out:json][timeout:30];
(
  node["place"~"^(village|hamlet|town|neighbourhood|suburb|locality)$"]
    (around:{RADIUS_M},{DEPOT_LAT},{DEPOT_LON});
);
out body;
"""

response = requests.post(OVERPASS_URL, data={"data": query})
data = response.json()
elements = data["elements"]  # 367 nodes returned in testing

for elem in elements:
    name = elem.get("tags", {}).get("name", "")
    name_ml = elem.get("tags", {}).get("name:ml", "")
    lat = elem["lat"]
    lon = elem["lon"]
    place_type = elem["tags"]["place"]
    # Process...
```

### India Post API Call (verified working)
```python
# Source: Verified via live API call to api.postalpincode.in on 2026-03-11
import requests

VATAKARA_PINS = ["673101", "673102", "673103", "673104", "673105", "673106"]
# Note: 673107-673110 return no data or errors

for pin in VATAKARA_PINS:
    resp = requests.get(f"https://api.postalpincode.in/pincode/{pin}")
    data = resp.json()
    if data[0]["Status"] == "Success" and data[0]["PostOffice"]:
        for po in data[0]["PostOffice"]:
            name = po["Name"].upper()
            pincode = po["Pincode"]
            # NOTE: No lat/lon in response! Must cross-reference with OSM.
            # Fields available: Name, BranchType, DeliveryStatus, District, Division, State
```

### RapidFuzz Length-Dependent Matching (verified working)
```python
# Source: Validated via RapidFuzz 3.14.3 testing on 2026-03-11
from rapidfuzz import fuzz

def fuzzy_match(dictionary_name: str, candidate: str, min_length: int = 4) -> bool:
    """Match candidate against dictionary entry with length-dependent threshold.

    Thresholds calibrated against Kerala transliteration variants:
    - Short names (<=4): 95% (prevents "PO" matching "PA")
    - Medium names (5-6): 90% (prevents "EDAPPAL" matching "EDAPALLI")
    - Long names (7+): 85% (allows "VATAKARA" matching "VADAKARA" at 87.5%)
    """
    if len(candidate) < min_length:
        return False

    name_len = len(dictionary_name)
    if name_len <= 4:
        threshold = 95
    elif name_len <= 6:
        threshold = 90
    else:
        threshold = 85

    score = fuzz.ratio(dictionary_name, candidate, score_cutoff=threshold)
    return score > 0  # score_cutoff returns 0 if below threshold
```

### Splitter Algorithm (core logic)
```python
# Source: Design spec + validation against real CDCMS addresses
def split(self, text: str) -> str:
    """Split concatenated text at place name boundaries.

    Example: "MUTTUNGALPOBALAVADI" -> "MUTTUNGAL PO BALAVADI"
    (PO expansion to P.O. happens in Step 7 of clean_cdcms_address)
    """
    upper = text.upper()
    result_parts = []
    pos = 0

    while pos < len(upper):
        match = self._find_best_match(upper, pos)
        if match:
            name, end_pos = match
            result_parts.append(text[pos:pos + len(name)])  # Preserve original case
            pos = end_pos
            # Check for PO/NR gap between matches
            remainder = upper[pos:]
            for abbr in ("PO", "NR"):
                if remainder.startswith(abbr):
                    result_parts.append(abbr)
                    pos += len(abbr)
                    # Skip separator chars (-.)
                    while pos < len(upper) and upper[pos] in "-. ":
                        pos += 1
                    break
        else:
            # No match at this position -- advance one character
            # (Accumulate unmatched characters as a chunk)
            next_match_pos = self._find_next_match_start(upper, pos + 1)
            result_parts.append(text[pos:next_match_pos])
            pos = next_match_pos

    return " ".join(part for part in result_parts if part.strip())
```

### Integration into clean_cdcms_address()
```python
# Source: cdcms_preprocessor.py -- insert between Step 6 and Step 7
# Module-level lazy initialization
_splitter: "AddressSplitter | None" = None
_splitter_loaded: bool = False

def _get_splitter() -> "AddressSplitter | None":
    global _splitter, _splitter_loaded
    if not _splitter_loaded:
        _splitter_loaded = True
        dict_path = Path(__file__).parent.parent.parent / "data" / "place_names_vatakara.json"
        if dict_path.exists():
            from core.data_import.address_splitter import AddressSplitter
            _splitter = AddressSplitter(dict_path)
    return _splitter

# In clean_cdcms_address(), after Step 6 (trailing letter split):
#   Step 6.5: Dictionary-powered word splitting
    splitter = _get_splitter()
    if splitter is not None:
        addr = splitter.split(addr)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Regex-only word splitting | Dictionary-powered splitting + regex | Phase 12 (this phase) | Handles concatenated place names that regex cannot detect |
| No fuzzy matching | RapidFuzz with length-dependent thresholds | Phase 12 (this phase) | Handles VATAKARA/VADAKARA, VALLIKADU/VALLIKKADU transliteration |
| Google formatted_address as display | address_raw always shown | Phase 11 (complete) | Fixed "HDFC ERGO" display bug |
| Single-pass abbreviation expansion | Two-pass (inline + standalone after split) | Phase 11 (complete) | PO/NR detected after word splitting creates boundaries |

**Deprecated/outdated:**
- thefuzz/fuzzywuzzy: Use RapidFuzz instead (faster, MIT license, same API)

## Open Questions

1. **Coordinates for India Post entries**
   - What we know: India Post API returns name + pincode but no lat/lon. OSM has coordinates but different names.
   - What's unclear: How to assign coordinates to India Post entries that have no OSM name match (e.g., VALLIKKADU).
   - Recommendation: For unmatched names, use the depot coordinates (11.6244, 75.5796) as a placeholder. These entries are primarily used for name matching in the splitter, not for centroid fallback (which is Phase 13). Mark them with `"coordinates_approximate": true`.

2. **Full CDCMS historical data coverage**
   - What we know: The sample has 9 distinct area names. Real historical data likely has 20-40+.
   - What's unclear: We only have `data/sample_cdcms_export.csv` (27 rows). Full coverage validation requires more data.
   - Recommendation: Build the dictionary to cover the 9 known areas + all OSM/India Post names in the zone (~200+ entries). The 80% gate is measured against the sample data initially. Add more seeds as new CDCMS data is processed.

3. **Dictionary entry schema: places vs post_offices**
   - What we know: Design spec separates `places` and `post_offices` arrays. India Post entries lack coordinates.
   - What's unclear: Whether the splitter should treat them differently.
   - Recommendation: Flatten into a single `entries` array with a `source` field. The splitter only needs `name` and `aliases` for matching. Coordinates are metadata for Phase 13 centroid fallback.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 with pytest-asyncio 1.3.0 |
| Config file | `pytest.ini` |
| Quick run command | `python -m pytest tests/core/data_import/test_address_splitter.py -x` |
| Full suite command | `python -m pytest tests/core/data_import/ -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ADDR-04 | Dictionary JSON exists with 200+ entries | unit | `python -m pytest tests/core/data_import/test_address_splitter.py::test_dictionary_exists -x` | Wave 0 |
| ADDR-04 | Build script regenerates dictionary from APIs | integration | `python scripts/build_place_dictionary.py --dry-run` | Wave 0 |
| ADDR-04 | Dictionary covers >80% of sample CDCMS area names | unit | `python -m pytest tests/core/data_import/test_address_splitter.py::test_dictionary_coverage -x` | Wave 0 |
| ADDR-05 | Concatenated text split at place name boundaries | unit | `python -m pytest tests/core/data_import/test_address_splitter.py::TestSplitter -x` | Wave 0 |
| ADDR-05 | Unknown text passes through unchanged | unit | `python -m pytest tests/core/data_import/test_address_splitter.py::test_passthrough_unknown -x` | Wave 0 |
| ADDR-06 | Fuzzy match accepts transliteration variants | unit | `python -m pytest tests/core/data_import/test_address_splitter.py::TestFuzzyMatching -x` | Wave 0 |
| ADDR-06 | Length-dependent thresholds prevent false positives | unit | `python -m pytest tests/core/data_import/test_address_splitter.py::test_no_false_positives -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/core/data_import/test_address_splitter.py -x`
- **Per wave merge:** `python -m pytest tests/core/data_import/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/core/data_import/test_address_splitter.py` -- covers ADDR-04, ADDR-05, ADDR-06
- [ ] `data/place_names_vatakara.json` -- dictionary file (output of build script)
- [ ] `scripts/build_place_dictionary.py` -- build script
- [ ] `core/data_import/address_splitter.py` -- AddressSplitter class
- [ ] `rapidfuzz==3.14.3` added to `requirements.txt`

## Sources

### Primary (HIGH confidence)
- OSM Overpass API (https://overpass-api.de/) -- live query on 2026-03-11 returned 367 place nodes within 30km of Vatakara
- India Post API (https://api.postalpincode.in/) -- live queries on 2026-03-11 for PIN codes 673101-673106 returned 22 post offices in Vadakara division
- RapidFuzz 3.14.3 (https://github.com/rapidfuzz/RapidFuzz) -- installed and tested fuzzy matching with Kerala place name pairs
- Existing codebase: `core/data_import/cdcms_preprocessor.py` -- current 12-step cleaning pipeline, integration points verified
- Existing codebase: `data/sample_cdcms_export.csv` -- 27 orders, 9 distinct area names, used for coverage analysis

### Secondary (MEDIUM confidence)
- [Overpass API Wiki](https://wiki.openstreetmap.org/wiki/Overpass_API) -- query syntax documentation
- [Overpass API Examples](https://wiki.openstreetmap.org/wiki/Overpass_API/Overpass_API_by_Example) -- `around` filter syntax
- [PostalPinCode API documentation](https://publicapi.dev/postal-pin-code-api) -- endpoint format and rate limits
- [RapidFuzz documentation](https://rapidfuzz.github.io/RapidFuzz/) -- `fuzz.ratio` API, `score_cutoff` parameter
- Design spec: `docs/superpowers/specs/2026-03-10-address-preprocessing-design.md` -- architecture and algorithm design

### Tertiary (LOW confidence)
- None -- all findings verified via live API calls and code testing

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- RapidFuzz is the clear choice, verified version and API
- Architecture: HIGH -- Integration points in existing code verified, algorithm validated with real data
- Pitfalls: HIGH -- All pitfalls discovered through actual API testing (OSM name gap, India Post no-coordinates)
- Dictionary coverage: MEDIUM -- Based on 27-row sample; full historical data may reveal additional gaps

**Research date:** 2026-03-11
**Valid until:** 2026-04-11 (stable APIs, static dictionary approach)
