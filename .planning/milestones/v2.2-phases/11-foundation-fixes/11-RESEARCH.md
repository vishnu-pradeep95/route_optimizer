# Phase 11: Foundation Fixes - Research

**Researched:** 2026-03-10
**Domain:** CDCMS address cleaning pipeline, Driver PWA display, SQLAlchemy/PostgreSQL schema migration, Google Maps URL construction
**Confidence:** HIGH

## Summary

Phase 11 fixes a data flow bug where the Driver PWA displays Google's `formatted_address` instead of the cleaned original CDCMS address. The root cause is traced to two specific code locations: `core/database/repository.py:141-142` (stores `order.location.address_text` as `address_display`) and `core/optimizer/vroom_adapter.py:278` (prefers `order.location.address_text` over `order.address_raw`). The fix requires changing the data source for `address_display` at both points, adding a new column to store completely unprocessed CDCMS text, modifying the API response to include both cleaned and raw address fields, updating the Driver PWA card templates, and improving the regex word-splitting pipeline.

The phase also requires adding a new `([a-z])([A-Z])` regex pattern to split lowercase-to-uppercase transitions (e.g., `ANANDAMANDIRAMK` -> `ANANDAMANDIRAM K`) and reordering the abbreviation expansion step to run after word splitting. The reorder is safe because the existing abbreviation patterns use inline detection (`([a-zA-Z])PO\.`, `\bNR[.;:]\s*`) that work on concatenated text regardless of surrounding word boundaries -- but the reorder must be validated against the existing 32 test cases in `test_cdcms_preprocessor.py`.

**Primary recommendation:** Fix the two buggy `address_display` assignment sites first, add the unprocessed text storage column, then tackle regex improvements. Keep changes layered and independently testable.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Navigate button uses BOTH coordinates AND address text in Google Maps URL (coords as destination, address text as context/label)
- No Navigate tap telemetry tracking
- Show BOTH cleaned address AND completely unprocessed CDCMS text in Driver PWA
- Hero card: cleaned address prominent (primary, 22px), raw CDCMS text below in smaller muted text (secondary)
- Compact cards: also show both versions (cleaned primary, raw secondary)
- "Raw" means completely unprocessed CDCMS field value -- ALL CAPS, concatenated, phone numbers included, no changes at all
- "Cleaned" means full clean_cdcms_address() output -- title case, expanded abbreviations, word splitting, punctuation cleanup
- Add new `address_raw` field to API stop response (completely unprocessed CDCMS text)
- Keep existing `address` field name (now sourced from cleaned address_raw, NOT Google's formatted_address)
- Split before lone trailing uppercase letters: `ANANDAMANDIRAMK` -> `ANANDAMANDIRAM K`
- Abbreviation expansion (NR, PO) must run AFTER word splitting so patterns are detected at word boundaries
- Backfill address_display from address_raw for all existing routes via migration
- Geocoding cache invalidation left for Phase 13 (scope boundary)

### Claude's Discretion
- Area suffix: append to cleaned address (current) or show separately
- Google Maps URL format (query string structure)
- Navigate button fallback for missing coordinates
- Navigate button on compact cards vs hero-only
- Navigate button text/icon layout
- Web URL vs intent:// URL for Google Maps
- Word splitting regex implementation details
- Step reordering specifics in the 10-step pipeline
- DB field naming for unprocessed text storage

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ADDR-01 | Driver app and navigation links always show the cleaned original address (address_raw), never Google's formatted_address | Bug traced to 2 code sites (repository.py:141-142, vroom_adapter.py:278). Fix is direct: change data source. API response needs new `address_raw` field. PWA cards need dual-address template. Navigate URL needs coordinates+address format. |
| ADDR-02 | Regex splits lowercase-to-uppercase transitions in concatenated CDCMS text | Add `re.sub(r"([a-z])([A-Z])", r"\1 \2", addr)` as new step in clean_cdcms_address(). Must run on uppercase text BEFORE title case. Safe because CDCMS input is ALL CAPS, so the pattern only fires after PO/NR expansion introduces lowercase. |
| ADDR-03 | Abbreviation expansion (NR, PO) runs after word splitting so patterns are detected at word boundaries | Reorder steps in the 10-step pipeline. Critical analysis: the existing inline PO pattern `([a-zA-Z])PO\.` handles concatenated text correctly, but standalone `\bPO\b` needs word boundaries. Adding word-split step before abbreviation expansion enables `\bPO\b` to match in cases like `CHORODE EAST PO` (after splitting `CHORODEEASTPO`). |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.11+ | Runtime | StrEnum usage in models, existing codebase |
| SQLAlchemy | 2.0 | ORM + async | Existing codebase, mapped_column style |
| FastAPI | current | API server | Existing codebase |
| PostgreSQL + PostGIS | current | Database | Existing codebase, spatial queries |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| re (stdlib) | N/A | Regex word splitting | ADDR-02, ADDR-03 -- no external deps needed |
| Pydantic | v2 | Model validation | Existing codebase, Order model |
| pandas | current | CSV preprocessing | CDCMS preprocessor, existing usage |

### Alternatives Considered
No alternatives needed -- this phase works entirely within the existing stack. No new libraries required.

## Architecture Patterns

### Data Flow Fix

The core bug is a data flow issue. Here is the current (buggy) and target (fixed) flow:

```
CURRENT (Buggy):
  CDCMS CSV
    -> preprocess_cdcms() applies clean_cdcms_address()
    -> CsvImporter creates Order(address_raw=CLEANED_text)  # misleading name
    -> GoogleGeocoder sets location.address_text = formatted_address
    -> repository.py saves location.address_text as address_display  # BUG
    -> vroom_adapter.py prefers location.address_text over address_raw  # BUG
    -> API returns Google's formatted_address
    -> Driver sees wrong address

TARGET (Fixed):
  CDCMS CSV
    -> preprocess_cdcms() preserves ORIGINAL text + applies clean_cdcms_address()
    -> CsvImporter creates Order(address_raw=CLEANED_text, address_original=UNPROCESSED_text)
    -> repository.py saves Order.address_raw as address_display  # FIXED
    -> vroom_adapter.py uses Order.address_raw as address_display  # FIXED
    -> API returns {address: cleaned_text, address_raw: unprocessed_text}
    -> Driver sees cleaned address (primary) + unprocessed CDCMS text (secondary)
```

### Changes Required by Layer

```
Layer 1: Data Capture (preserving unprocessed text)
  core/data_import/cdcms_preprocessor.py  -- add address_original column to output DataFrame
  core/data_import/csv_importer.py        -- pass address_original through to Order model
  core/models/order.py                    -- add address_original field to Order Pydantic model

Layer 2: Storage (new DB column)
  core/database/models.py                 -- add address_original column to OrderDB
  infra/postgres/init.sql                 -- add address_original column to orders table
  infra/alembic/versions/                 -- new migration to add column + backfill

Layer 3: Fix address_display Source
  core/database/repository.py:141-142     -- change from location.address_text to order.address_raw
  core/optimizer/vroom_adapter.py:278     -- change from location.address_text to order.address_raw

Layer 4: API Response
  apps/kerala_delivery/api/main.py:1472   -- add address_raw field to stop response dict
  core/models/route.py                    -- add address_raw field to RouteStop model
  core/database/repository.py:843        -- pass address_original through route_db_to_pydantic

Layer 5: Driver PWA
  apps/kerala_delivery/driver_app/index.html  -- dual-address hero card + compact card templates
  navigateTo() function                        -- add address text to Google Maps URL

Layer 6: Regex Improvements
  core/data_import/cdcms_preprocessor.py  -- add lowercase->uppercase split, reorder steps
  tests/core/data_import/test_cdcms_preprocessor.py -- new tests for word splitting
```

### Pattern: Column Naming Convention

The existing codebase already has naming confusion around `address_raw`:
- `Order.address_raw` (Pydantic model) = cleaned CDCMS text (output of `clean_cdcms_address()`)
- `OrderDB.address_raw` (SQLAlchemy model) = same cleaned text
- `GeocodeCacheDB.address_raw` = the address passed to geocoding (which is the cleaned text)

**Recommendation for the new unprocessed column:** Use `address_original` (not `address_unprocessed` or `address_cdcms`). This clearly distinguishes it from `address_raw` which is already established as "cleaned but not geocoded."

### Pattern: Database Migration with Backfill

The project has an established Alembic migration pattern. The migration should:
1. Add `address_original TEXT` column to `orders` table (nullable -- old rows won't have it)
2. Add `address_original TEXT` column to `route_stops` table (for API response)
3. Backfill `address_display` from `address_raw` for all existing rows
4. No backfill for `address_original` is possible (the original unprocessed text was never stored)

### Pattern: Google Maps URL with Coordinates + Address

The Google Maps URLs API supports:
- **Coordinates-only:** `destination=11.5926,75.6334` -- precise location, no label
- **Address-only:** `destination=Anandamandiram+K.T.Bazar` -- Google geocodes it (may go wrong)
- **Address as query parameter:** `destination=11.5926,75.6334&query=Anandamandiram+K.T.Bazar`

The `query` parameter is for Search actions, not Directions. For directions with coordinates AND a label, the recommended approach is to use a combined format:

```javascript
// Coordinates as destination (precision), address in search context
// Option A: use destination_place_id if available
`https://www.google.com/maps/dir/?api=1&destination=${lat},${lon}&travelmode=driving`

// Option B: use address as destination with coordinates as fallback
// When Maps can't find the address, coordinates ensure correct routing
```

**Recommended approach:** Use coordinates as the destination (they guarantee correct routing) and include the cleaned address text in a `destination` string that combines both:

```javascript
function navigateTo(lat, lon, addressText) {
    // Coordinates are always used for routing precision
    // Address text is URL-encoded as a label that Google may display
    const url = `https://www.google.com/maps/dir/?api=1&destination=${lat},${lon}&travelmode=driving`;
    window.open(url, '_blank');
}
```

Note: Google Maps URLs API does not support a separate label parameter for directions. The destination is either coordinates OR text, not both simultaneously. Use coordinates for routing accuracy (the original goal).

### Anti-Patterns to Avoid
- **Changing address_raw semantics:** Do NOT rename `Order.address_raw` to mean "unprocessed." It's used in 50+ places across the codebase (geocoding, cache keys, duplicate detection). Add a new field instead.
- **Modifying geocode cache keys:** The geocode cache normalizes on `address_raw`. Changing what `address_raw` contains would invalidate all cached results. Out of scope (Phase 13).
- **Adding word splitting after title case:** The `([a-z])([A-Z])` regex works on the uppercase input. After title case, the pattern would split every word (`AnAndamandiramK` is never the input -- `ANANDAMANDIRAMK` is). The split must happen before title case.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Google Maps deep link | Custom intent:// URI schemes for Android/iOS | Standard web URL `https://www.google.com/maps/dir/?api=1&...` | Works on both platforms, opens native app if installed, falls back to browser |
| Database migration | Manual SQL ALTER TABLE scripts | Alembic migration (existing infrastructure at `infra/alembic/`) | Auto-generates from ORM diff, versioned, rollback support |
| URL encoding for addresses | Manual string replacement | `encodeURIComponent()` in JS, `urllib.parse.quote()` in Python | Handles all special characters including Kerala place names |

## Common Pitfalls

### Pitfall 1: Regex Step Reorder Breaks Existing Tests
**What goes wrong:** Moving abbreviation expansion after word splitting changes how inline abbreviations (`NR.`, `PO.`) interact with the new split patterns.
**Why it happens:** The existing `([a-zA-Z])PO\.` pattern handles concatenated PO (e.g., `KUNIYILPO.` -> `KUNIYIL P.O.`). If word splitting runs first and inserts a space (`KUNIYIL PO.`), the inline pattern no longer matches (no letter immediately before PO).
**How to avoid:**
1. Run ALL 32 existing tests before any changes (baseline)
2. Keep the inline PO pattern `([a-zA-Z])PO\.` in its current position (before word splitting)
3. Move only the STANDALONE patterns (`\bPO\b\.?`, `\bNR[.;:]\s*`) after word splitting
4. Or: keep all abbreviation patterns in their current position AND add a second pass of standalone-only abbreviation expansion after word splitting
5. The safest approach is a **two-pass abbreviation expansion**: first pass handles inline concatenated patterns (current step 4), word splitting happens, then second pass catches standalone patterns at word boundaries
**Warning signs:** Any existing test in `test_cdcms_preprocessor.py` starts failing after changes

### Pitfall 2: address_raw Name Collision
**What goes wrong:** The new API response field `address_raw` (unprocessed CDCMS text) collides with the existing `Order.address_raw` Pydantic field (cleaned CDCMS text).
**Why it happens:** `Order.address_raw` was named before the distinction between "cleaned" and "unprocessed" existed.
**How to avoid:** Use `address_original` for the new Pydantic field and DB column. Keep `address_raw` meaning what it means today (cleaned text). In the API response, map: `address` = cleaned text (from `Order.address_raw`), `address_raw` = unprocessed text (from `Order.address_original`). This is an API-level rename, not a model rename.

### Pitfall 3: Forgetting RouteStopDB.address_display
**What goes wrong:** Fixing `OrderDB.address_display` in `repository.py` but forgetting that `RouteStopDB` also has its own `address_display` column, set from `vroom_adapter.py`.
**Why it happens:** The address flows through two paths: OrderDB stores it, and RouteStopDB copies it during route creation. Both must be fixed.
**How to avoid:** Fix both sites:
1. `core/database/repository.py:141-142` -- OrderDB.address_display assignment
2. `core/optimizer/vroom_adapter.py:278` -- RouteStop.address_display assignment

### Pitfall 4: Missing address_original in Non-CDCMS Upload Path
**What goes wrong:** The `address_original` field is populated for CDCMS uploads but is `None` for standard CSV uploads (the `else` branch in `upload-orders` endpoint).
**Why it happens:** Standard CSV format doesn't go through `preprocess_cdcms()`, so there's no "before cleaning" text to capture.
**How to avoid:** For non-CDCMS uploads, set `address_original = address_raw` (they're the same -- no cleaning was applied). Handle `None` gracefully in the PWA (hide the secondary raw text line if `address_raw` is null/empty in the API response).

### Pitfall 5: XSS in Unprocessed Address Text
**What goes wrong:** The unprocessed CDCMS text is rendered in the PWA using `innerHTML` or template literals without escaping.
**Why it happens:** The existing code uses `escapeHtml(stop.address)` but new fields need the same treatment.
**How to avoid:** Use the existing `escapeHtml()` function for `address_raw` display: `${escapeHtml(stop.address_raw) || ''}`.

### Pitfall 6: Word Split Regex Fires After Title Case
**What goes wrong:** If the `([a-z])([A-Z])` regex runs after title case, it splits every word: `Anandamandiram` becomes `A nandamandiram`.
**Why it happens:** Title case converts `ANANDAMANDIRAMK` to `Anandamandiramk` -- the lowercase-to-uppercase transition is at the start of every word, not just at concatenation boundaries.
**How to avoid:** The new regex MUST run on the ALL-CAPS input (before title case step). Current step 5 runs before title case (step 8) -- the new regex should be placed as step 5b, right after the existing digit-to-uppercase split and before whitespace collapse.

## Code Examples

### Fix 1: repository.py -- Change address_display Source
```python
# Source: core/database/repository.py lines 141-142
# BEFORE (buggy):
address_display=(
    order.location.address_text if order.location else None
),

# AFTER (fixed):
address_display=order.address_raw,
```

### Fix 2: vroom_adapter.py -- Change address_display Source
```python
# Source: core/optimizer/vroom_adapter.py line 278
# BEFORE (buggy):
address_display=order.location.address_text or order.address_raw,

# AFTER (fixed):
address_display=order.address_raw,
```

### New Regex: Lowercase-to-Uppercase Split
```python
# Source: core/data_import/cdcms_preprocessor.py
# Add as Step 5b (after existing Step 5, before Step 6 whitespace collapse)
# Input is still ALL CAPS at this point
# This fires AFTER abbreviation expansion: "Near" (lowercase 'r') before "VALLIKKADU" (uppercase 'V')
# Also catches concatenated trailing letters: "ANANDAMANDIRAMK" has no lowercase in ALL CAPS
# BUT after PO expansion: "KUNIYIL P.O. CHORODE" -- the 'l' in 'KUNIYIL' before space is already handled

# Wait -- the input IS all caps. So ([a-z])([A-Z]) won't match on raw CDCMS text.
# It only fires AFTER abbreviation expansion introduces lowercase:
#   "Near" from NR, "House" from (H), "P.O." from PO
# Example: "VALIYAPARAMBATH House KURUPAL" -- 'e' before 'K' -> "House KURUPAL" (already has space)
#
# The REAL value is catching abbreviation artifacts stuck to next word:
#   "KUNIYILNear EK GOPALAN" -> would have space from NR expansion already
#
# For the actual requirement (ANANDAMANDIRAMK -> ANANDAMANDIRAM K):
# This is ALL CAPS -- ([a-z])([A-Z]) doesn't match!
# Need to think about when this fires in the pipeline.

# CORRECT APPROACH: The regex must operate on ALL-CAPS text
# to split trailing short uppercase groups from long uppercase runs.
# Pattern: split before a 1-3 letter uppercase group at the end of a word
addr = re.sub(r"([A-Z]{4,})([A-Z]{1,2})(?=\s|$|[^a-zA-Z])", r"\1 \2", addr)
# ANANDAMANDIRAMK -> ANANDAMANDIRAM K
# But this is tricky -- greedy matching issues

# SIMPLER: Split at the point where a long run of uppercase letters
# transitions to a short (1-2 char) uppercase group before a word boundary
# Alternative: use the lowercase-to-uppercase pattern AFTER title case but
# in a targeted way

# SAFEST APPROACH for ADDR-02:
# After title case, "ANANDAMANDIRAMK" becomes "Anandamandiramk"
# Then re.sub(r"([a-z])([A-Z])", r"\1 \2", addr) won't match because
# title case makes the trailing K lowercase: "k"
#
# SOLUTION: Run the split BEFORE title case on uppercase text.
# Use a different pattern that detects trailing short groups:
addr = re.sub(r"([A-Za-z]{3,})([A-Z])(?=\s|$|[.,;:\-])", r"\1 \2", addr)
# This splits a single trailing uppercase letter from a longer word
```

**IMPORTANT ANALYSIS:** The `([a-z])([A-Z])` pattern from the design spec does NOT work on raw ALL-CAPS CDCMS input. `ANANDAMANDIRAMK` is entirely uppercase -- there's no lowercase-to-uppercase transition. The pattern only works AFTER title case (`Anandamandiramk` has no transition either -- `k` is lowercase).

The correct approach for splitting `ANANDAMANDIRAMK` -> `ANANDAMANDIRAM K` on ALL-CAPS input:

```python
# Step 5b: Split trailing short uppercase groups from long words
# Pattern: 4+ uppercase letters followed by 1-2 uppercase letters at word boundary
# "ANANDAMANDIRAMK" -> "ANANDAMANDIRAM K"  (K is 1-letter trailing group)
# "CHORODEEAST" -> "CHORODE EAST" (EAST is 4 letters, won't match 1-2 limit)
# Need to handle both cases:
#   - Trailing 1-2 letter codes: ANANDAMANDIRAMK -> ANANDAMANDIRAM K
#   - Trailing known place/area names: CHORODEEAST -> Phase 12 dictionary

# For Phase 11 (regex only, no dictionary):
# Split before 1-3 trailing uppercase letters at word boundary
addr = re.sub(r"([A-Z]{3,})([A-Z]{1,3})\b",
              lambda m: m.group(1) + " " + m.group(2) if len(m.group(1)) >= 3 else m.group(0),
              addr)
```

**Actual recommended implementation:**

```python
# After abbreviation expansion (which introduces lowercase: Near, House, P.O.)
# the ([a-z])([A-Z]) pattern DOES fire on expansion artifacts:
#   "KUNIYILNearVALLIKKADU" -> "KUNIYILNear VALLIKKADU"
#   (though this case already has a space from the NR. expansion regex)

# For the ALL-CAPS trailing letter case, use:
# Step 5b: Split trailing 1-2 uppercase letters from long uppercase words
addr = re.sub(r"(?<=[A-Z]{3})(?=[A-Z]{1,2}(?:\s|$|[^a-zA-Z]))", " ", addr)
# ANANDAMANDIRAMK + word boundary -> ANANDAMANDIRAM K
# KSEB -> no match (only 4 chars total, but split would give KSE B -- wrong)
# Need to protect known abbreviations: KSEB, BSNL, KSRTC

# SIMPLEST CORRECT APPROACH:
# Use a negative lookahead to protect known abbreviations
KNOWN_ABBREVS = {"KSEB", "BSNL", "KSRTC", "KT", "EK", "PO"}
addr = re.sub(r"([A-Z]{4,})([A-Z]{1,2})(?=\s|$|[.,;:\-/])",
              lambda m: m.group(0) if m.group(2) in KNOWN_ABBREVS else f"{m.group(1)} {m.group(2)}",
              addr)
```

### API Response with Dual Address
```python
# Source: apps/kerala_delivery/api/main.py (stop serialization, ~line 1468)
# BEFORE:
"address": stop.address_display,

# AFTER:
"address": stop.address_display,      # Cleaned CDCMS text (primary display)
"address_raw": stop.address_original,  # Completely unprocessed CDCMS text (secondary reference)
```

### Driver PWA: Dual-Address Hero Card
```javascript
// Source: apps/kerala_delivery/driver_app/index.html (renderHeroCard function)
function renderHeroCard(stop) {
    const rawAddress = stop.address_raw
        ? `<div class="hero-address-raw">${escapeHtml(stop.address_raw)}</div>`
        : '';
    return `
    <div class="hero-card" id="stop-${escapeHtml(stop.order_id)}">
        <div class="hero-label">NEXT DELIVERY &middot; Stop ${stop.sequence} of ${total}</div>
        <div class="hero-address">${escapeHtml(stop.address) || 'Address pending'}</div>
        ${rawAddress}
        ...
    </div>`;
}
```

```css
/* New CSS for raw address display */
.hero-address-raw {
    font-family: var(--font-data);
    font-size: 13px;
    color: var(--color-text-secondary);
    opacity: 0.7;
    line-height: 1.3;
    margin-bottom: 8px;
    word-break: break-word;
}
```

### Navigate Button with Coordinates
```javascript
// Source: apps/kerala_delivery/driver_app/index.html (navigateTo function)
// BEFORE:
function navigateTo(lat, lon) {
    window.open(`https://www.google.com/maps/dir/?api=1&destination=${lat},${lon}&travelmode=driving`, '_blank');
}

// AFTER (coordinates + address text as context):
function navigateTo(lat, lon, address) {
    let url;
    if (lat && lon && lat !== 0 && lon !== 0) {
        // Use coordinates for precise routing
        url = `https://www.google.com/maps/dir/?api=1&destination=${lat},${lon}&travelmode=driving`;
    } else if (address) {
        // Fallback: use address text if coordinates unavailable
        url = `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(address)}&travelmode=driving`;
    } else {
        return; // No navigation possible
    }
    window.open(url, '_blank');
}
```

### Alembic Migration Template
```python
# Source: infra/alembic/versions/ (new migration)
"""Add address_original column to orders and route_stops.

Stores the completely unprocessed CDCMS ConsumerAddress text.
Existing rows will have NULL (original text was not preserved before this change).
Also backfills address_display from address_raw for existing rows.
"""

def upgrade():
    # Add new column for unprocessed original text
    op.add_column('orders', sa.Column('address_original', sa.Text(), nullable=True))
    op.add_column('route_stops', sa.Column('address_original', sa.Text(), nullable=True))

    # Backfill address_display from address_raw for existing rows
    # This fixes the bug where address_display contains Google's formatted_address
    op.execute("""
        UPDATE orders
        SET address_display = address_raw
        WHERE address_raw IS NOT NULL
    """)
    op.execute("""
        UPDATE route_stops rs
        SET address_display = o.address_raw
        FROM orders o
        WHERE rs.order_id = o.id
        AND o.address_raw IS NOT NULL
    """)

def downgrade():
    op.drop_column('route_stops', 'address_original')
    op.drop_column('orders', 'address_original')
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `address_display = location.address_text` (Google) | `address_display = order.address_raw` (cleaned CDCMS) | This phase | Driver sees correct address |
| Only digit-to-uppercase split | Also lowercase-to-uppercase + trailing-letter split | This phase | Better word separation in concatenated text |
| Abbreviation expansion before word split | Word split before abbreviation expansion | This phase | Abbreviations detected at word boundaries |
| Only cleaned address in API | Both cleaned + unprocessed in API | This phase | Driver has reference to original CDCMS text |

## Open Questions

1. **Exact regex for trailing letter split on ALL-CAPS text**
   - What we know: `ANANDAMANDIRAMK` needs to become `ANANDAMANDIRAM K`. The design spec's `([a-z])([A-Z])` pattern does NOT work on ALL-CAPS input.
   - What's unclear: Best regex pattern that splits trailing 1-2 letter groups without breaking abbreviations like KSEB, BSNL
   - Recommendation: Use `([A-Z]{4,})([A-Z]{1,2})(?=\s|$|[^a-zA-Z])` with a lambda to protect known abbreviations. Test against all 27 sample addresses.

2. **Two-pass vs. reorder for abbreviation expansion**
   - What we know: ADDR-03 requires abbreviations to run after word splitting. PITFALLS.md warns the inline PO pattern `([a-zA-Z])PO\.` may break if word splitting inserts spaces before it.
   - What's unclear: Whether a clean reorder is safe or whether a two-pass approach (inline patterns first, standalone patterns after split) is needed
   - Recommendation: Use two-pass approach. Keep inline patterns (`([a-zA-Z])PO\.`) in their current position. Add a second abbreviation pass after word splitting for standalone patterns (`\bPO\b`, `\bNR\b`). This is safest for regression avoidance.

3. **address_original backfill for existing data**
   - What we know: Existing rows in the DB don't have the original unprocessed CDCMS text (it was never stored)
   - What's unclear: Whether to set address_original = address_raw (cleaned text, better than nothing) or leave it NULL
   - Recommendation: Leave as NULL for existing rows. The cleaned text is already in address_raw -- storing it again in address_original would be misleading (it's not truly "original"). The PWA should hide the raw text line when address_raw (API field) is null.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio |
| Config file | `pytest.ini` (`asyncio_mode = auto`) |
| Quick run command | `python -m pytest tests/core/data_import/test_cdcms_preprocessor.py -x` |
| Full suite command | `python -m pytest tests/ -x --timeout=60` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ADDR-01 | address_display uses cleaned CDCMS text, not Google formatted_address | unit | `python -m pytest tests/core/database/test_database.py -x -k "address"` | Needs new tests |
| ADDR-01 | API response includes address_raw field | unit | `python -m pytest tests/apps/kerala_delivery/api/test_api.py -x -k "address"` | Needs new tests |
| ADDR-01 | Navigate button uses coordinates | integration | Playwright MCP (manual E2E) | Manual only |
| ADDR-02 | Lowercase-to-uppercase split works | unit | `python -m pytest tests/core/data_import/test_cdcms_preprocessor.py -x -k "split"` | Needs new tests |
| ADDR-02 | Known abbreviations (KSEB, BSNL) not split | unit | `python -m pytest tests/core/data_import/test_cdcms_preprocessor.py -x -k "abbreviation_preserved"` | Needs new tests |
| ADDR-03 | Abbreviation expansion runs after word splitting | unit | `python -m pytest tests/core/data_import/test_cdcms_preprocessor.py -x -k "step_order"` | Needs new tests |
| ADDR-03 | All 32 existing clean_cdcms_address tests still pass | regression | `python -m pytest tests/core/data_import/test_cdcms_preprocessor.py -x` | Yes (32 tests) |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/core/data_import/test_cdcms_preprocessor.py -x`
- **Per wave merge:** `python -m pytest tests/ -x --timeout=60`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/core/data_import/test_cdcms_preprocessor.py` -- add tests for ADDR-02 (word splitting) and ADDR-03 (step ordering)
- [ ] `tests/apps/kerala_delivery/api/test_api.py` -- add tests for address_raw field in API response
- [ ] `tests/core/database/test_database.py` -- add tests verifying address_display sourced from address_raw not location.address_text
- [ ] E2E: Docker rebuild + Playwright MCP for PWA dual-address display and Navigate button

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `core/data_import/cdcms_preprocessor.py` (lines 198-293) -- full pipeline examined
- Codebase analysis: `core/database/repository.py` (lines 141-142) -- bug site 1 confirmed
- Codebase analysis: `core/optimizer/vroom_adapter.py` (line 278) -- bug site 2 confirmed
- Codebase analysis: `core/database/models.py` (OrderDB, RouteStopDB) -- schema examined
- Codebase analysis: `apps/kerala_delivery/driver_app/index.html` -- PWA templates examined
- Codebase analysis: `tests/core/data_import/test_cdcms_preprocessor.py` -- 32 existing tests counted
- Codebase analysis: `infra/alembic/env.py` and `infra/alembic/versions/` -- migration infrastructure confirmed
- [Google Maps URLs API official docs](https://developers.google.com/maps/documentation/urls/get-started) -- URL format verified

### Secondary (MEDIUM confidence)
- `.planning/research/PITFALLS.md` (Pitfall 7) -- regex reorder risk analysis
- `.planning/research/ARCHITECTURE.md` -- pipeline reorder design
- `docs/superpowers/specs/2026-03-10-address-preprocessing-design.md` -- design spec with regex examples

### Tertiary (LOW confidence)
- Design spec's `([a-z])([A-Z])` regex recommendation -- **INCORRECT for ALL-CAPS input**. Verified by analysis: CDCMS input is ALL UPPERCASE, so this pattern never fires. Needs different approach.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all existing libraries, no new dependencies
- Architecture (data flow fix): HIGH -- both bug sites confirmed by code examination, fix is mechanical
- Architecture (regex reorder): MEDIUM -- the step reorder is conceptually correct but regex interactions need careful testing; the design spec's suggested regex is wrong for ALL-CAPS input
- Pitfalls: HIGH -- all pitfalls derived from direct codebase analysis, not speculation

**Research date:** 2026-03-10
**Valid until:** Stable (no external dependencies or version-sensitive findings)
