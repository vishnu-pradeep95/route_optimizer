# Phase 4: Geocoding Cache Normalization - Context

**Gathered:** 2026-03-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Unify address normalization across all geocoding cache layers so the same address always resolves to the same cached coordinates. Deprecate the file-based JSON cache — all cache operations go through PostgreSQL/PostGIS only. Re-normalize existing DB entries via Alembic migration. No new geocoding features (duplicate detection, cost tracking are Phase 5).

</domain>

<decisions>
## Implementation Decisions

### Normalization depth
- Single `normalize_address()` pure function in `core/geocoding/` — standalone, testable, imported by all consumers
- Basic normalization: lowercase + collapse all whitespace to single spaces + strip leading/trailing whitespace
- Unicode NFC normalization to handle Malayalam virama/chillu variations if they appear
- Strip common punctuation (periods, commas that are decorative) — e.g., "M.G. Road" and "MG Road" should match
- No abbreviation expansion (too risky for false matches — "NR" could be initials)
- No address suffix injection ("Kerala, India") — Google's `region=in` bias handles this

### File cache deprecation
- Fully remove file cache code from `GoogleGeocoder` — delete `_load_cache()`, `_save_cache()`, `_address_hash()`, `cache_dir` parameter
- `GoogleGeocoder` becomes a pure API caller with no caching responsibility
- `CachedGeocoder` (DB-backed) is the single caching layer
- Check if `data/geocode_cache/google_cache.json` has valuable entries — if so, write a one-time migration script to import them into the DB with the new normalization before removing the code

### Alembic migration for existing DB data
- Re-normalize all `address_norm` values in `geocode_cache` table using the new `normalize_address()` function
- Deduplicate entries that collapse to the same normalized key — keep highest-confidence entry, sum hit counts
- Migration must be reversible (store original `address_norm` values for rollback)

### Address patterns
- Primary input is English transliteration from CDCMS exports (e.g., "Near SBI, MG Road, Vatakara")
- Main mismatch source is inconsistent whitespace, extra commas, and trailing punctuation in CSV data
- Malayalam script addresses are rare but possible — Unicode NFC handles them safely

### Claude's Discretion
- Exact implementation of the normalize function (regex vs sequential string operations)
- Whether to use a hash (SHA-256) as the DB lookup key or the normalized string directly
- Alembic migration batch size and error handling strategy
- Whether to add a unique constraint on `(address_norm, source)` after deduplication
- Test strategy — which edge cases to cover in unit tests

</decisions>

<specifics>
## Specific Ideas

- The normalize function should be the single source of truth — both `repository.get_cached_geocode()` and `repository.save_geocode_cache()` call it, eliminating the current inline `address_raw.strip().lower()`
- The `GoogleGeocoder._address_hash()` approach (SHA-256 of normalized string) is a good reference for the final implementation, but the DB can store the full normalized string (no hash needed for PostgreSQL text matching)

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `CachedGeocoder` (`core/geocoding/cache.py`): Already implements the decorator pattern wrapping GoogleGeocoder — just needs to use the new normalize function
- `GeocodeCacheDB` model (`core/database/models.py:371`): Already has `address_raw` and `address_norm` columns — schema likely unchanged
- `get_cached_geocode()` and `save_geocode_cache()` (`core/database/repository.py:728-822`): Both do inline normalization that needs to be replaced with the shared function

### Established Patterns
- Adapter/decorator pattern: `CachedGeocoder` wraps `GoogleGeocoder` — this pattern stays, just the normalization changes
- Repository pattern: All DB access through `core/database/repository.py` — normalization change is in two functions
- Alembic migrations: Existing migration chain in `infra/alembic/versions/` with async support
- Protocol-based interfaces: `Geocoder` and `AsyncGeocoder` protocols in `core/geocoding/interfaces.py`

### Integration Points
- `apps/kerala_delivery/api/main.py`: Creates `CachedGeocoder(upstream=GoogleGeocoder(...), session=session)` — constructor changes if GoogleGeocoder drops cache_dir param
- `core/database/repository.py`: Two functions need normalize function import
- `infra/alembic/versions/`: New migration file for re-normalization

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-geocoding-cache-normalization*
*Context gathered: 2026-03-01*
