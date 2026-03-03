# Phase 4: Geocoding Cache Normalization - Research

**Researched:** 2026-03-01
**Domain:** Address string normalization, geocoding cache deduplication, Alembic data migrations
**Confidence:** HIGH

## Summary

Phase 4 unifies address normalization across all geocoding cache layers. The current codebase has three separate normalization implementations: `GoogleGeocoder._address_hash()` does `" ".join(address.lower().split())` then SHA-256 hashes it, while `repository.get_cached_geocode()` and `repository.save_geocode_cache()` both do `address_raw.strip().lower()`. These different normalizations mean the same address can produce different cache keys depending on which code path processes it -- the root cause of duplicate map pins.

The fix is straightforward: create a single `normalize_address()` pure function in `core/geocoding/`, replace all inline normalization with calls to it, remove the file-based JSON cache entirely from `GoogleGeocoder`, and run an Alembic data migration to re-normalize existing `address_norm` values in the database. The file cache at `data/geocode_cache/google_cache.json` contains 26 entries that should be migrated to the DB before the code is removed.

**Primary recommendation:** Build the `normalize_address()` function first (with comprehensive unit tests), then use it to refactor all consumers, then write the Alembic migration last -- this order ensures the function is proven correct before it touches production data.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Single `normalize_address()` pure function in `core/geocoding/` -- standalone, testable, imported by all consumers
- Basic normalization: lowercase + collapse all whitespace to single spaces + strip leading/trailing whitespace
- Unicode NFC normalization to handle Malayalam virama/chillu variations if they appear
- Strip common punctuation (periods, commas that are decorative) -- e.g., "M.G. Road" and "MG Road" should match
- No abbreviation expansion (too risky for false matches -- "NR" could be initials)
- No address suffix injection ("Kerala, India") -- Google's `region=in` bias handles this
- Fully remove file cache code from `GoogleGeocoder` -- delete `_load_cache()`, `_save_cache()`, `_address_hash()`, `cache_dir` parameter
- `GoogleGeocoder` becomes a pure API caller with no caching responsibility
- `CachedGeocoder` (DB-backed) is the single caching layer
- Check if `data/geocode_cache/google_cache.json` has valuable entries -- if so, write a one-time migration script to import them into the DB with the new normalization before removing the code
- Re-normalize all `address_norm` values in `geocode_cache` table using the new `normalize_address()` function
- Deduplicate entries that collapse to the same normalized key -- keep highest-confidence entry, sum hit counts
- Migration must be reversible (store original `address_norm` values for rollback)
- Primary input is English transliteration from CDCMS exports (e.g., "Near SBI, MG Road, Vatakara")
- Main mismatch source is inconsistent whitespace, extra commas, and trailing punctuation in CSV data
- Malayalam script addresses are rare but possible -- Unicode NFC handles them safely
- The normalize function should be the single source of truth -- both `repository.get_cached_geocode()` and `repository.save_geocode_cache()` call it
- The DB can store the full normalized string (no hash needed for PostgreSQL text matching)

### Claude's Discretion
- Exact implementation of the normalize function (regex vs sequential string operations)
- Whether to use a hash (SHA-256) as the DB lookup key or the normalized string directly
- Alembic migration batch size and error handling strategy
- Whether to add a unique constraint on `(address_norm, source)` after deduplication
- Test strategy -- which edge cases to cover in unit tests

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| GEO-01 | Geocoding uses a single normalized address key across all cache layers (no duplicate locations from normalization mismatch) | `normalize_address()` function replaces 3 separate inline normalizations; comprehensive unit tests verify edge cases; all cache reads/writes route through this function |
| GEO-02 | All geocoding cache reads/writes go through DB only (file-based JSON cache deprecated) | Remove `_load_cache()`, `_save_cache()`, `_address_hash()`, `cache_dir` from `GoogleGeocoder`; migrate 26 file cache entries to DB; update `main.py` singleton pattern; `GoogleGeocoder` becomes stateless API caller |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python `unicodedata` | stdlib (3.12) | `unicodedata.normalize('NFC', text)` for Unicode canonical composition | Standard library, zero dependencies, handles Malayalam script safely |
| Python `re` | stdlib (3.12) | Punctuation stripping regex pattern | Standard library; regex is cleaner than chained `.replace()` for multi-character removal |
| SQLAlchemy | 2.0+ (project existing) | ORM for geocode_cache table operations | Already in use across entire codebase |
| Alembic | 1.x (project existing) | Database migration for re-normalizing existing data | Already in use with async support configured in `infra/alembic/env.py` |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | existing | Unit tests for normalize function | Testing normalization edge cases (whitespace, punctuation, Unicode, Malayalam) |
| `pytest-asyncio` | existing | Async test support | Testing repository integration with normalize function |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `re` for punctuation | Chained `.replace()` calls | `.replace()` is marginally faster but less maintainable when stripping multiple characters; regex is a single pass and clearer intent |
| Full normalized string as DB key | SHA-256 hash of normalized string | User decided: DB stores full normalized string; PostgreSQL text matching is fast with btree index; hash loses debuggability (can't read the cache table and understand what's there) |

**Installation:** No new packages needed -- all are stdlib or already installed.

## Architecture Patterns

### Recommended Project Structure
```
core/geocoding/
    __init__.py              # unchanged
    interfaces.py            # unchanged
    normalize.py             # NEW: normalize_address() pure function
    google_adapter.py        # MODIFIED: remove file cache, keep API calling
    cache.py                 # unchanged (already delegates to repository)
core/database/
    repository.py            # MODIFIED: import and call normalize_address()
    models.py                # MODIFIED: add __table_args__ with UniqueConstraint
infra/alembic/versions/
    xxxx_renormalize_geocode_cache.py  # NEW: data migration
scripts/
    migrate_file_cache.py    # NEW: one-time import of google_cache.json entries
```

### Pattern 1: Pure Function for Normalization
**What:** A stateless, side-effect-free function that takes a string and returns a normalized string. No I/O, no DB, no imports beyond stdlib.
**When to use:** Whenever address normalization is needed -- cache lookups, cache saves, data migrations, one-time scripts.
**Why pure:** Trivially testable with no mocking. Can be imported anywhere without dependency issues. Can be called inside Alembic migrations without pulling in ORM machinery.

```python
# core/geocoding/normalize.py
import re
import unicodedata

# Punctuation to strip: periods, commas that are decorative separators.
# Kept minimal to avoid false collapses (e.g., "/" in house numbers is meaningful).
_STRIP_PUNCTUATION = re.compile(r'[.,]+')

def normalize_address(address: str) -> str:
    """Normalize an address string for consistent cache lookups.

    Steps (order matters):
    1. Unicode NFC normalization (canonical composition)
    2. Lowercase
    3. Strip decorative punctuation (periods, commas)
    4. Collapse all whitespace to single spaces
    5. Strip leading/trailing whitespace

    Returns:
        Normalized address string suitable as a cache key.
    """
    text = unicodedata.normalize('NFC', address)
    text = text.lower()
    text = _STRIP_PUNCTUATION.sub('', text)
    text = ' '.join(text.split())
    return text
```

### Pattern 2: Data Migration in Alembic
**What:** An Alembic migration that runs Python code to re-normalize existing `address_norm` values and deduplicate collapsed entries.
**When to use:** One-time migration when deploying Phase 4.
**Why in Alembic:** Keeps schema and data changes in the same versioning chain. The alternative (separate script) risks being forgotten during deployment.

Alembic official guidance warns against complex data migrations inside version scripts. However, this migration is bounded (re-normalize strings + deduplicate) and has no external dependencies. The key concern is reversibility -- store original `address_norm` values in a temporary column or backup table for rollback.

**Approach:** Use `op.execute()` with raw SQL for the bulk update, combined with `op.get_bind()` to fetch rows that need Python-level processing. The normalize function must be imported directly (no ORM dependency in migration).

### Pattern 3: File Cache Migration Script
**What:** A standalone script that reads `google_cache.json`, normalizes each entry using `normalize_address()`, and inserts into the `geocode_cache` DB table.
**When to use:** Run once before removing file cache code.
**Why standalone:** Depends on both the file cache format and DB session -- cleaner as a one-time script than an Alembic migration.

### Anti-Patterns to Avoid
- **Inline normalization in each consumer:** The current problem. Every call site does its own `strip().lower()`. New code paths will inevitably forget or diverge.
- **Normalizing at API call time only:** Must normalize at BOTH read and write time. If you normalize only on write but read with raw input, cache misses on hits.
- **Using ORM models inside Alembic migrations:** Import the `normalize_address()` function directly, but do NOT import ORM models -- they may have changed since the migration was written, causing version skew.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Unicode normalization | Manual character replacement for Malayalam | `unicodedata.normalize('NFC', text)` | NFC handles ALL Unicode canonical equivalences, not just the ones you can think of. Malayalam has complex virama/chillu sequences that produce visually identical but byte-different strings. |
| Whitespace collapsing | Chain of `.replace()` calls | `' '.join(text.split())` | `.split()` handles ALL whitespace characters (tabs, non-breaking spaces, etc.), not just regular spaces. A `.replace('  ', ' ')` loop misses tabs and needs multiple passes. |
| Cache deduplication | Manual Python loop comparing entries | SQL window function with `ROW_NUMBER() OVER (PARTITION BY ...)` | Database handles deduplication atomically. Python loop risks race conditions and is slower for large datasets. |

**Key insight:** Address normalization looks trivially simple but has a long tail of Unicode edge cases. Using stdlib `unicodedata.normalize()` handles the entire Unicode standard in one call.

## Common Pitfalls

### Pitfall 1: Normalize-on-Write-Only
**What goes wrong:** You normalize addresses when saving to cache but forget to normalize when reading. Cache lookups fail because the raw input doesn't match the normalized DB value.
**Why it happens:** Developers assume "the data is already normalized in the DB" and forget the query input also needs normalizing.
**How to avoid:** Both `get_cached_geocode()` and `save_geocode_cache()` call `normalize_address()`. The function is imported at the top of `repository.py`.
**Warning signs:** Cache miss rate suddenly increases after deployment.

### Pitfall 2: Punctuation Stripping Collapses Meaningful Characters
**What goes wrong:** Stripping commas aggressively turns "House 1, Street 2" into "House 1 Street 2" which might match "House 1 Street" differently.
**Why it happens:** Commas in addresses serve dual roles: decorative separators AND meaningful delimiters.
**How to avoid:** Only strip commas and periods (the most common decorative punctuation in CDCMS exports). Do NOT strip hyphens, slashes, or parentheses -- those appear in house numbers (e.g., "4/302", "12-B"). Test with actual CDCMS address samples.
**Warning signs:** Addresses that used to resolve correctly now match the wrong entry.

### Pitfall 3: Migration Deduplication Deletes the Wrong Entry
**What goes wrong:** When two entries collapse to the same `address_norm`, the migration keeps the wrong one (e.g., lower confidence, older GPS data).
**Why it happens:** Simple "keep first" deduplication doesn't consider confidence or recency.
**How to avoid:** Use SQL `ORDER BY confidence DESC, hit_count DESC, last_used_at DESC` to keep the highest-quality entry. Sum `hit_count` from all duplicates before deleting losers.
**Warning signs:** Post-migration, some addresses resolve to coordinates farther from the delivery location than before.

### Pitfall 4: ORM Model Import in Alembic Migration
**What goes wrong:** Alembic migration imports `GeocodeCacheDB` from `core/database/models.py`. Six months later, the model changes (new column, renamed field). Running the old migration fails because the ORM model no longer matches the DB schema at that point in time.
**Why it happens:** Alembic migrations are frozen snapshots; ORM models evolve.
**How to avoid:** Use raw SQL via `op.execute()` or define lightweight `sa.table()` / `sa.column()` objects inside the migration. Import only the pure `normalize_address()` function (no ORM dependency).
**Warning signs:** `alembic upgrade head` fails on a fresh database with import errors or column mismatches.

### Pitfall 5: Unique Constraint Violation During Migration
**What goes wrong:** Re-normalization causes two entries to have the same `(address_norm, source)` pair. The existing `UNIQUE(address_norm, source)` constraint (from `init.sql`) blocks the UPDATE.
**Why it happens:** The deduplication step must happen BEFORE re-normalizing, or the re-normalization must be done in a way that handles conflicts.
**How to avoid:** The migration should: (1) temporarily drop the unique constraint, (2) re-normalize all entries, (3) deduplicate collapsed entries, (4) re-add the unique constraint. Alternatively, process in a single transaction that identifies and resolves conflicts before committing.
**Warning signs:** Migration fails with `UniqueViolation` error.

### Pitfall 6: File Cache Entry Format Mismatch
**What goes wrong:** The one-time migration script reads `google_cache.json` and inserts entries, but uses the hash key (e.g., `643965c65f511002`) as the address instead of `original_address`.
**Why it happens:** The file cache stores `{hash: {lat, lon, original_address, ...}}`. The hash is NOT the address.
**How to avoid:** Use the `original_address` field from each cache entry as `address_raw`. The hash is irrelevant once we move to full-text DB storage.
**Warning signs:** 26 entries appear in the DB with hex string addresses instead of real Kerala addresses.

## Code Examples

### normalize_address() Implementation
```python
# core/geocoding/normalize.py
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
    """
    text = unicodedata.normalize('NFC', address)
    text = text.lower()
    text = _DECORATIVE_PUNCT.sub('', text)
    text = ' '.join(text.split())
    return text
```

### Repository Integration
```python
# In core/database/repository.py — replace inline normalization

from core.geocoding.normalize import normalize_address

async def get_cached_geocode(
    session: AsyncSession, address_raw: str
) -> Location | None:
    normalized = normalize_address(address_raw)  # was: address_raw.strip().lower()
    result = await session.execute(
        select(GeocodeCacheDB)
        .where(GeocodeCacheDB.address_norm == normalized)
        .order_by(GeocodeCacheDB.confidence.desc())
        .limit(1)
    )
    # ... rest unchanged

async def save_geocode_cache(
    session: AsyncSession,
    address_raw: str,
    location: Location,
    source: str = "google",
    confidence: float = 0.5,
) -> None:
    normalized = normalize_address(address_raw)  # was: address_raw.strip().lower()
    # ... rest unchanged
```

### GoogleGeocoder After Refactor
```python
# core/geocoding/google_adapter.py — stripped to pure API caller
class GoogleGeocoder:
    API_URL = "https://maps.googleapis.com/maps/api/geocode/json"

    def __init__(
        self,
        api_key: str,
        region_bias: str = "in",
    ):
        self.api_key = api_key
        self.region_bias = region_bias
        # No cache_dir, no _cache, no _load_cache, no _save_cache

    def geocode(self, address: str) -> GeocodingResult:
        return self._call_api(address)

    def geocode_batch(self, addresses: list[str]) -> list[GeocodingResult]:
        return [self.geocode(addr) for addr in addresses]

    def _call_api(self, address: str) -> GeocodingResult:
        # ... unchanged from current implementation
```

### Alembic Data Migration Pattern
```python
# infra/alembic/versions/xxxx_renormalize_geocode_cache.py
"""Re-normalize geocode_cache address_norm values.

Uses the new normalize_address() function to re-process all cached
addresses and deduplicate entries that collapse to the same key.
"""
from alembic import op
import sqlalchemy as sa

# Import the pure function directly -- no ORM dependency
from core.geocoding.normalize import normalize_address

# Lightweight table definition (NOT the ORM model)
geocode_cache = sa.table(
    'geocode_cache',
    sa.column('id', sa.dialects.postgresql.UUID),
    sa.column('address_raw', sa.Text),
    sa.column('address_norm', sa.Text),
    sa.column('address_norm_old', sa.Text),  # for rollback
    sa.column('source', sa.String),
    sa.column('confidence', sa.Float),
    sa.column('hit_count', sa.Integer),
    sa.column('last_used_at', sa.DateTime),
)


def upgrade() -> None:
    # Step 1: Add backup column for reversibility
    op.add_column('geocode_cache',
        sa.Column('address_norm_old', sa.Text, nullable=True))

    # Step 2: Backup current values
    op.execute(
        "UPDATE geocode_cache SET address_norm_old = address_norm"
    )

    # Step 3: Drop unique constraint temporarily
    op.drop_constraint('geocode_cache_address_norm_source_key',
                       'geocode_cache', type_='unique')

    # Step 4: Re-normalize using Python function (batch fetch + update)
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, address_raw FROM geocode_cache")
    ).fetchall()

    for row_id, address_raw in rows:
        new_norm = normalize_address(address_raw)
        conn.execute(
            sa.text(
                "UPDATE geocode_cache SET address_norm = :norm WHERE id = :id"
            ),
            {"norm": new_norm, "id": row_id}
        )

    # Step 5: Deduplicate -- keep highest confidence, sum hit_counts
    # (SQL-based deduplication using window functions)
    conn.execute(sa.text("""
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY address_norm, source
                       ORDER BY confidence DESC, hit_count DESC, last_used_at DESC
                   ) AS rn,
                   SUM(hit_count) OVER (
                       PARTITION BY address_norm, source
                   ) AS total_hits
            FROM geocode_cache
        )
        UPDATE geocode_cache
        SET hit_count = ranked.total_hits
        FROM ranked
        WHERE geocode_cache.id = ranked.id AND ranked.rn = 1
    """))

    conn.execute(sa.text("""
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY address_norm, source
                       ORDER BY confidence DESC, hit_count DESC, last_used_at DESC
                   ) AS rn
            FROM geocode_cache
        )
        DELETE FROM geocode_cache
        USING ranked
        WHERE geocode_cache.id = ranked.id AND ranked.rn > 1
    """))

    # Step 6: Re-add unique constraint
    op.create_unique_constraint(
        'geocode_cache_address_norm_source_key',
        'geocode_cache',
        ['address_norm', 'source']
    )


def downgrade() -> None:
    # Restore original address_norm values from backup column
    op.execute(
        "UPDATE geocode_cache SET address_norm = address_norm_old "
        "WHERE address_norm_old IS NOT NULL"
    )
    op.drop_column('geocode_cache', 'address_norm_old')
```

### Unit Test Edge Cases for normalize_address()
```python
# tests/core/geocoding/test_normalize.py
import pytest
from core.geocoding.normalize import normalize_address

class TestNormalizeAddress:
    def test_lowercase(self):
        assert normalize_address("MG Road") == "mg road"

    def test_whitespace_collapse(self):
        assert normalize_address("Near  SBI   MG Road") == "near sbi mg road"

    def test_strip_leading_trailing(self):
        assert normalize_address("  MG Road  ") == "mg road"

    def test_strip_periods(self):
        assert normalize_address("M.G. Road") == "mg road"

    def test_strip_commas(self):
        assert normalize_address("Near SBI, MG Road, Vatakara") == "near sbi mg road vatakara"

    def test_tabs_and_newlines(self):
        assert normalize_address("MG Road\t\nVatakara") == "mg road vatakara"

    def test_idempotent(self):
        addr = "Near SBI, M.G. Road,  Vatakara "
        assert normalize_address(normalize_address(addr)) == normalize_address(addr)

    def test_unicode_nfc(self):
        # NFD vs NFC form of the same character
        import unicodedata
        nfd = unicodedata.normalize('NFD', '\u00e9')  # e + combining accent
        nfc = unicodedata.normalize('NFC', '\u00e9')  # precomposed e-acute
        assert normalize_address(nfd) == normalize_address(nfc)

    def test_preserves_slashes(self):
        """Slashes are meaningful in house numbers."""
        assert normalize_address("4/302 House Name") == "4/302 house name"

    def test_preserves_hyphens(self):
        """Hyphens appear in house numbers like 12-B."""
        assert normalize_address("12-B MG Road") == "12-b mg road"

    def test_real_cdcms_address(self):
        """Actual CDCMS address format."""
        result = normalize_address(
            "4/146 Aminas Valiya Parambath Near Vallikkadu Sarambi Pallivatakara, Vatakara, Kozhikode, Kerala"
        )
        assert result == "4/146 aminas valiya parambath near vallikkadu sarambi pallivatakara vatakara kozhikode kerala"

    def test_empty_string(self):
        assert normalize_address("") == ""

    def test_periods_and_commas_together(self):
        """M.G. Road, Vatakara -> mg road vatakara"""
        assert normalize_address("M.G. Road, Vatakara") == "mg road vatakara"

    def test_existing_db_normalization_compatibility(self):
        """The new function should normalize a superset of what strip().lower() does."""
        addr = "  Near SBI, MG Road  "
        old_norm = addr.strip().lower()
        new_norm = normalize_address(addr)
        # New norm is MORE normalized (also strips commas, collapses whitespace)
        assert "near sbi, mg road" == old_norm
        assert "near sbi mg road" == new_norm
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| File-based JSON cache (GoogleGeocoder) | DB-backed cache (CachedGeocoder + PostGIS) | Phase 3 / v1.0 | DB cache is already the primary path; file cache is vestigial |
| Inline `strip().lower()` normalization | Centralized normalize function | Phase 4 (this phase) | Eliminates normalization mismatch, the root cause of duplicate pins |
| SHA-256 hash as cache key | Full normalized string as DB key | Phase 4 (this phase) | PostgreSQL text btree index is fast; full string preserves debuggability |

**Deprecated/outdated:**
- `GoogleGeocoder._address_hash()` / `_load_cache()` / `_save_cache()`: Removed in this phase. The file cache was a bootstrap mechanism for pre-DB development.
- Inline `address_raw.strip().lower()` in repository.py: Replaced by `normalize_address()` import.

## Existing Code Analysis

### Current Normalization Implementations (3 separate, inconsistent)

| Location | Current Code | What It Normalizes |
|----------|-------------|-------------------|
| `GoogleGeocoder._address_hash()` (line 195) | `" ".join(address.lower().split())` then SHA-256 | Lowercase + collapse whitespace (but then hashes it) |
| `repository.get_cached_geocode()` (line 741) | `address_raw.strip().lower()` | Lowercase + strip ends (NO whitespace collapse) |
| `repository.save_geocode_cache()` (line 789) | `address_raw.strip().lower()` | Lowercase + strip ends (NO whitespace collapse) |

**Mismatch example:** The address `"Near SBI,  MG Road"` (double space) would:
- In GoogleGeocoder: normalize to `"near sbi, mg road"` (collapsed) then hash
- In repository: normalize to `"near sbi,  mg road"` (double space preserved)

This means a DB cache miss for an address that should have been a hit.

### Consumers That Need Updating

| File | What Changes | Difficulty |
|------|-------------|------------|
| `core/database/repository.py` (lines 741, 789) | Replace `address_raw.strip().lower()` with `normalize_address(address_raw)` | Trivial -- two-line change |
| `core/geocoding/google_adapter.py` | Remove `_address_hash()`, `_load_cache()`, `_save_cache()`, `cache_dir` param, `_cache` dict, file I/O imports | Medium -- significant code removal |
| `apps/kerala_delivery/api/main.py` (line 514-531) | Remove singleton pattern comments about "file-based cache"; update `GoogleGeocoder()` constructor call (drop `cache_dir`) | Trivial |
| `apps/kerala_delivery/api/main.py` (line 849-873) | Currently calls `repo.get_cached_geocode()` directly + `geocoder.geocode()` -- should use `CachedGeocoder` instead for single code path | Medium -- refactor upload geocoding to use CachedGeocoder |
| `scripts/import_orders.py` (line 122-124) | Uses `GoogleGeocoder` directly without DB cache -- update to use CachedGeocoder or at minimum drop `cache_dir` | Low-medium |
| `scripts/geocode_batch.py` (line 188-189) | Uses `GoogleGeocoder` directly -- update constructor | Low |
| `core/database/models.py` | Add `__table_args__` with `UniqueConstraint('address_norm', 'source')` to match init.sql | Trivial |

### File Cache Assessment

The file at `data/geocode_cache/google_cache.json` contains **26 entries** (7,786 bytes). Each entry has: `lat`, `lon`, `formatted_address`, `confidence`, `original_address`. The entries are real Kerala addresses from the Vatakara/Kozhikode area. These should be migrated to the DB before removing the file cache code.

**Migration concern:** Several entries have low confidence (0.4) and resolve to the generic "Vatakara, Kerala, India" coordinates (11.601558, 75.5919758) -- these are APPROXIMATE geocoding results. The migration script should import them as-is (confidence reflects quality).

### Database Schema Notes

- `init.sql` creates `UNIQUE(address_norm, source)` on `geocode_cache` -- but the ORM model (`GeocodeCacheDB`) has no `__table_args__` reflecting this. This should be added for ORM/schema consistency.
- The constraint name auto-generated by PostgreSQL from `init.sql` is `geocode_cache_address_norm_source_key` (PostgreSQL's default naming convention for UNIQUE constraints).
- Existing btree index `idx_geocode_cache_address` on `address_norm` is correct and will continue to work with the new normalization.

## Open Questions

1. **Constraint name verification**
   - What we know: PostgreSQL auto-generates constraint names from `UNIQUE(col1, col2)` as `tablename_col1_col2_key`. For `geocode_cache`, this should be `geocode_cache_address_norm_source_key`.
   - What's unclear: Need to confirm the exact constraint name in the live DB before the Alembic migration can `drop_constraint()` by name.
   - Recommendation: Query `SELECT conname FROM pg_constraint WHERE conrelid = 'geocode_cache'::regclass` in the migration or use a hardcoded name based on PostgreSQL convention. Add a safety check that the constraint exists before dropping.

2. **Parentheses in punctuation stripping**
   - What we know: CDCMS addresses sometimes contain `(P.O.)` or `(Near ...)`. The user decided to strip periods and commas but did not mention parentheses.
   - What's unclear: Should parentheses be stripped? `"Rayarangoth (P.O.)"` would become `"rayarangoth (po)"` with current plan (periods stripped, parens kept).
   - Recommendation: Keep parentheses. They carry structural meaning in Kerala addresses. Stripping them risks merging addresses like "Rayarangoth PO" (post office) with "Rayarangoth" (general area).

3. **Upload endpoint refactor scope**
   - What we know: `main.py` lines 849-873 manually call `repo.get_cached_geocode()` + `geocoder.geocode()` + `repo.save_geocode_cache()` instead of using `CachedGeocoder`. This duplicates the cache logic.
   - What's unclear: Should this phase refactor the upload endpoint to use `CachedGeocoder`, or just ensure it uses `normalize_address()`?
   - Recommendation: Refactor to use `CachedGeocoder` -- it already implements the exact same cache-then-upstream pattern. This eliminates a third place where normalization could diverge. The refactor is low-risk because `CachedGeocoder` is already well-tested.

## Sources

### Primary (HIGH confidence)
- Project codebase analysis -- `core/geocoding/google_adapter.py`, `core/geocoding/cache.py`, `core/database/repository.py` lines 728-822, `core/database/models.py` lines 371-400
- Python `unicodedata` module docs: https://docs.python.org/3/library/unicodedata.html -- verified NFC normalization available in Python 3.12
- SQLAlchemy 2.0 docs (Context7 `/websites/sqlalchemy_en_20`) -- bulk update patterns with `bindparam()` and `session.execute()`
- Alembic official cookbook: https://alembic.sqlalchemy.org/en/latest/cookbook.html -- data migration guidance (recommends caution, keep simple)

### Secondary (MEDIUM confidence)
- `data/geocode_cache/google_cache.json` -- 26 entries verified present, format confirmed (hash key -> {lat, lon, original_address, ...})
- `init.sql` UNIQUE constraint on `(address_norm, source)` -- confirmed in source, constraint name follows PostgreSQL convention

### Tertiary (LOW confidence)
- None -- all findings verified against project source code or official documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all stdlib, no new dependencies
- Architecture: HIGH -- pure function pattern is well-established; existing codebase patterns (decorator, repository) are clear
- Pitfalls: HIGH -- analyzed actual code to identify real normalization mismatches and migration risks; constraint naming verified from init.sql

**Research date:** 2026-03-01
**Valid until:** 2026-04-01 (stable domain, no external dependency changes expected)
