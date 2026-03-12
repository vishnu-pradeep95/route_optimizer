# Phase 11: Foundation Fixes - Context

**Gathered:** 2026-03-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Fix address_display source to always use cleaned original CDCMS address, improve regex word splitting for concatenated CDCMS text, and reorder the abbreviation expansion step. No new geocoding features -- strictly fixing the address display pipeline and word splitting. Requirements: ADDR-01, ADDR-02, ADDR-03.

</domain>

<decisions>
## Implementation Decisions

### Navigate button behavior (ADDR-01)
- Use BOTH coordinates AND address text in Google Maps URL (coords as destination, address text as context/label)
- No Navigate tap telemetry tracking
- Success criteria updated: "Navigate button opens Google Maps with coordinates as destination and original address text as context"
- Claude's discretion: exact Google Maps URL format, fallback behavior for missing coordinates, intent:// vs web URL, button text/layout within 66px constraint, whether compact cards get Navigate buttons

### Address display: dual text (ADDR-01)
- Show BOTH cleaned address AND completely unprocessed CDCMS text in the Driver PWA
- Hero card: cleaned address prominent (primary, 22px), raw CDCMS text below in smaller muted text (secondary)
- Compact cards: also show both versions (cleaned primary, raw secondary)
- "Raw" means completely unprocessed CDCMS field value -- ALL CAPS, concatenated, phone numbers included, no changes at all
- "Cleaned" means full clean_cdcms_address() output -- title case, expanded abbreviations (NR->Near, PO->P.O.), word splitting, punctuation cleanup

### API response fields (ADDR-01)
- Add new `address_raw` field to API stop response (completely unprocessed CDCMS text)
- Keep existing `address` field name (now sourced from cleaned address_raw, NOT Google's formatted_address)
- `address` = cleaned CDCMS text (primary display), `address_raw` = unprocessed CDCMS text (secondary reference)

### Word splitting (ADDR-02)
- Split before lone trailing uppercase letters: `ANANDAMANDIRAMK` -> `ANANDAMANDIRAM K`
- Claude's discretion: exact regex patterns, whether to split before 1-2 or 1-3 letter groups, handling of known abbreviations (KSEB, BSNL, KSRTC), step ordering relative to title case, protection rules for abbreviation patterns

### Step reordering (ADDR-03)
- Abbreviation expansion (NR, PO) must run AFTER word splitting so patterns are detected at word boundaries
- Claude's discretion: exact new step order in the 10-step pipeline

### Existing data migration
- Backfill address_display from address_raw for all existing routes via Alembic migration
- Geocoding cache invalidation left for Phase 13 (scope boundary)
- Claude's discretion: whether to backfill from existing address_raw or re-process, migration implementation details

### Database schema
- Need to store unprocessed CDCMS text (currently not stored -- address_raw stores cleaned output)
- Claude's discretion: add new column vs repurpose existing, field naming, migration approach

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

</decisions>

<specifics>
## Specific Ideas

- Navigate button should include both coordinates (for precise navigation) and address text (for context) -- not one or the other
- Drivers should see BOTH the cleaned readable address AND the unprocessed CDCMS text for reference -- cleaned primary, raw secondary
- The completely unprocessed CDCMS text (not even whitespace-normalized) is what should appear as "raw"
- Abbreviation expansion level for cleaned text is correct as-is: NR->Near, PO->P.O., (H)->House
- Title case + word splitting + abbreviation expansion = right transformation level for primary display
- No Navigate tap telemetry -- keep it simple

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `clean_cdcms_address()` in `core/data_import/cdcms_preprocessor.py` (lines 198-293): 10-step cleaning pipeline, needs step reorder and regex enhancement
- `Order.address_raw` in `core/models/order.py` (line 58-60): Currently stores cleaned text, needs to also preserve unprocessed original
- `StatusBadge` and card components in Driver PWA `index.html`: Hero card (line 1366) and compact cards (line 1398) need dual-address layout
- 32 existing tests in `tests/core/data_import/test_cdcms_preprocessor.py`

### Established Patterns
- Tailwind v4 with `tw:` prefix in dashboard, WCAG AAA contrast in Driver PWA
- `fetchRoutes()`, `fetchRouteDetail()` in `lib/api.ts` -- API fetch helpers
- Alembic migrations for schema changes (`alembic/versions/`)
- Google Maps URL: `https://www.google.com/maps/dir/?api=1&destination=${lat},${lon}` (line 1515 in index.html)

### Integration Points
- `core/optimizer/vroom_adapter.py` line 278: `address_display=order.location.address_text or order.address_raw` -- BUG: uses Google's formatted_address
- `core/database/repository.py` lines 141-142: `address_display=(order.location.address_text if order.location else None)` -- BUG: stores Google's address
- `apps/kerala_delivery/api/main.py` line 1472: `"address": stop.address_display` -- returns address to PWA
- `core/database/models.py` line 186: `address_display` column in OrderDB
- `core/geocoding/google_adapter.py` line 123: Sets `address_text=result.get("formatted_address", address)` -- source of the bug

### Data Flow (Current - Buggy)
```
CDCMS CSV -> clean_cdcms_address() -> Order.address_raw (cleaned)
                                   -> GoogleGeocoder -> formatted_address
                                   -> repository saves formatted_address as address_display
                                   -> API returns formatted_address to PWA
                                   -> Driver sees wrong address
```

### Data Flow (Target - Fixed)
```
CDCMS CSV -> store unprocessed text as address_original
          -> clean_cdcms_address() -> Order.address_raw (cleaned)
          -> API returns cleaned text as 'address' + unprocessed as 'address_raw'
          -> Driver sees cleaned address (primary) + raw CDCMS text (secondary)
          -> Navigate button uses coordinates + address text
```

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 11-foundation-fixes*
*Context gathered: 2026-03-10*
