# Pitfalls Research

**Domain:** Address preprocessing pipeline, geocode validation, and confidence UI -- adding to an existing LPG delivery routing system (Kerala/Vatakara region)
**Researched:** 2026-03-10
**Confidence:** HIGH for cache/integration pitfalls (verified against codebase analysis); HIGH for fuzzy matching pitfalls (verified against RapidFuzz documentation); MEDIUM for dictionary data quality (based on OSM Overpass and India Post API characteristics); HIGH for address_display downstream impact (traced through vroom_adapter.py, repository.py, OrderDB, RouteStopDB, driver PWA)

---

## Critical Pitfalls

### Pitfall 1: Geocode Cache Poisoning from Preprocessing Changes

**What goes wrong:**
The existing geocode cache in PostGIS contains ~hundreds of entries keyed by `normalize_address(address_raw)`. When you change how `clean_cdcms_address()` works (adding word splitting, reordering abbreviation expansion), the same CDCMS input now produces a DIFFERENT cleaned address. This new address does not match any existing cache key, causing a cache miss. The system re-geocodes all addresses on next upload, consuming Google API quota. Worse: the cache now contains TWO entries for the same physical address -- the old garbled version AND the new cleaned version -- potentially with different coordinates.

The old cache entries are never invalidated. If a future code path or script uses the raw CDCMS text without going through the new preprocessing, it hits the old (wrong) cache entry and gets the wrong coordinates.

**Why it happens:**
The cache key flows through `normalize_address()` which lowercases, strips punctuation, and collapses whitespace -- but it does NOT perform word splitting or abbreviation expansion. So `clean_cdcms_address("MUTTUNGALPOBALAVADI")` currently produces `"Muttungalpobalavadi"` which normalizes to `"muttungalpobalavadi"`. After the fix, it produces `"Muttungal P.O. Balavadi"` which normalizes to `"muttungal po balavadi"`. These are different cache keys. The existing cached geocode for `"muttungalpobalavadi"` (which may point to the wrong location) remains in the database forever.

**How to avoid:**
1. Do NOT touch `normalize_address()`. It is the cache key function and must remain stable. The design spec correctly identifies it as "unchanged" -- enforce this.
2. Accept that preprocessing changes will cause cache misses for affected addresses. This is the DESIRED behavior -- the old cache entries had wrong coordinates because the garbled address geocoded incorrectly.
3. Add a migration script (or one-time cleanup) that identifies orphaned cache entries where `address_raw` contains concatenated text patterns (no spaces between words) and flags them for review. Do not auto-delete -- some may have been driver-verified.
4. Log when a "similar but different" cache key is created for an address that already has a nearby variant. The duplicate detector (15m proximity) may catch some of these.

**Warning signs:**
- Spike in Google API calls after deploying preprocessing changes (monitor `stats["misses"]` counter)
- Duplicate location warnings from the existing duplicate detector for addresses that differ only in whitespace/abbreviation
- Two geocode_cache rows where `address_raw` values are clearly the same physical address with different formatting

**Phase to address:**
Phase 1 (Foundation) -- document expected cache miss behavior. Phase 5 (Integration Testing) -- verify cache miss count is within budget and old entries are not causing confusion.

---

### Pitfall 2: address_display Change Breaks Downstream Consumers Silently

**What goes wrong:**
The design spec calls for changing `vroom_adapter.py:278` from `order.location.address_text or order.address_raw` to `order.address_raw`. This one-line change affects every downstream consumer that reads `address_display`:

1. **OrderDB.address_display** (String(255)) -- stored in the database during `save_optimization_run()`
2. **RouteStopDB.address_display** (String(255)) -- stored for each stop in the route
3. **API response** -- `/api/routes/{vehicle_id}` returns `address_display` to the driver PWA
4. **QR sheet generation** -- `qr_helpers.py` uses `address_display` for print labels
5. **Google Maps navigation URL** -- the driver's "Navigate" button passes the address to Google Maps
6. **Dashboard route details** -- the React dashboard shows `address_display` in route tables

If `order.address_raw` is longer than 255 characters (the DB column limit for `address_display`), the database INSERT will either truncate silently (depending on PostgreSQL strict mode) or raise a `DataError`. CDCMS addresses with area suffix appended can easily reach 200+ characters; with the new word splitting adding spaces and commas, some may exceed 255.

Additionally, changing the address source changes what Google Maps searches for when the driver taps "Navigate." If the old `formatted_address` was "Vatakara, Kerala, India" (wrong place but parseable by Google Maps) and the new `address_raw` is "8/542 Sreeshylam, Anandamandiram, K.T. Bazar, Vatakara, Kozhikode, Kerala" (correct but verbose), Google Maps may interpret it differently.

**Why it happens:**
The fix is conceptually correct (show the original address, not Google's interpretation), but the ripple effects through multiple database columns, API responses, and UI consumers are easy to underestimate. The `address_display` field appears in 6+ code paths.

**How to avoid:**
1. Check the maximum length of `address_raw` values in production data before deploying. Run: `SELECT MAX(LENGTH(address_raw)) FROM orders;` and verify it is under 255 characters.
2. If CDCMS addresses with area suffix can exceed 255 chars, either increase the column size via Alembic migration or truncate explicitly with a logged warning: `address_display = (order.address_raw or "")[:255]`.
3. Test the Google Maps navigation URL with several real `address_raw` values to ensure Google Maps can parse them. The area suffix (", Vatakara, Kozhikode, Kerala") is critical for Google Maps -- verify it is present.
4. Grep the entire codebase for `address_display` consumers before making the change. The design spec lists "Unchanged Files" but does NOT list `qr_helpers.py` or `import_orders.py`, both of which reference `address_display` or `address_text`.
5. Write a test that uploads a CSV, runs optimization, and verifies `address_display` in the API response matches the cleaned CDCMS address (not Google's formatted_address).

**Warning signs:**
- `DataError` or `StringDataRightTruncation` in PostgreSQL logs during upload
- Driver PWA shows truncated addresses (ending in "...")
- Google Maps opens to wrong location when driver taps "Navigate" with the new address format
- QR sheet prints show garbled or overly long addresses that wrap badly

**Phase to address:**
Phase 1 (Foundation) -- the `address_display` source fix is listed as task 1.1 and must include downstream consumer audit. Phase 4 (API + Driver UI) -- verify end-to-end that the address shown in the PWA is correct and navigable.

---

### Pitfall 3: Fuzzy Matching False Positives on Short Kerala Place Names

**What goes wrong:**
The dictionary-powered word splitter uses RapidFuzz with an 85% similarity threshold. Kerala has many short place names (4-6 characters) that are similar to each other or to common Malayalam words:

| Place A | Place B | `fuzz.ratio` | Should match? |
|---------|---------|--------------|---------------|
| EDAPPAL | EDAPPAL | 100 | Yes |
| EDAPPAL | EDAPALLI | 88 | No -- different place (50km apart) |
| KUTTUR | KUTTOOR | 86 | Maybe -- transliteration variant |
| AZHIKODE | AZHIYUR | 71 | No |
| VADAKARA | VADAKKARA | 94 | Yes -- same place |
| PARAMBA | PARAMBU | 86 | No -- "paramba" = compound, "parambu" = land |

At 85% threshold, `EDAPPAL` and `EDAPALLI` would match (88% similarity), which is wrong -- they are completely different places 50km apart. The splitter would then insert a word break and assign coordinates for the wrong location.

For 4-character names, an 85% threshold means 1 character difference triggers a match. `KODI` matches `KADI` (75%), `PADI` matches `MADI` (75%) -- these are wrong. RapidFuzz's `fuzz.ratio` on short strings is inherently unreliable because one character edit represents a high percentage of the total length.

**Why it happens:**
The design spec recommends 85% threshold as "conservative," but this assessment assumes longer strings where 85% is indeed conservative. For strings under 8 characters, 85% is very aggressive. Malayalam place names in romanized form are typically 5-10 characters.

**How to avoid:**
1. Use a **length-dependent threshold**: 95% for names under 6 characters, 90% for 6-8 characters, 85% for names over 8 characters. Short names need near-exact matches because one character flip changes meaning.
2. Prefer `rapidfuzz.fuzz.ratio` over `token_sort_ratio` or `partial_ratio` -- the latter are even more permissive and produce more false positives for place name matching.
3. Require that fuzzy matches are within the delivery zone (30km). If `EDAPPAL` in the dictionary is at lat/lon X and the matched `EDAPALLI` would be 50km away, reject the match. The dictionary already has coordinates -- use them for spatial validation of fuzzy matches.
4. Build a curated **alias list** in the dictionary rather than relying on fuzzy matching for known variants. The design spec already supports an `aliases` array per place entry. Explicit aliases ("VADAKARA" -> "VADAKKARA") are always safer than fuzzy matching.
5. Add a logging mode that reports all fuzzy matches with their scores during testing. Review the match list manually for false positives before deploying to production.

**Warning signs:**
- Addresses geocode to a place name that sounds similar but is in a different district
- The splitter inserts word breaks at unexpected positions in an address
- Fuzzy match log shows matches at exactly the threshold (85-87%) -- these are the most likely false positives

**Phase to address:**
Phase 2 (Place Name Dictionary) -- the fuzzy matching threshold must be tuned with real CDCMS data, not hypothetical examples. Phase 5 (Integration Testing) -- measure false positive rate on the 27 sample addresses.

---

### Pitfall 4: Fallback Chain Creates Inconsistent Confidence Across Re-uploads

**What goes wrong:**
The geocode validation fallback chain (geocode -> validate -> retry with area name -> centroid fallback) produces different confidence scores depending on when an address is first geocoded:

- **Day 1:** Upload CSV. Address "MUTTUNGALPOBALAVADI" geocodes to wrong location (50km away). Validator catches it, retries with "Muttungal, Vatakara, Kozhikode, Kerala", gets a valid result at confidence 0.7 * 0.6 = 0.42. Cached at 0.42.
- **Day 2:** New preprocessing deployed. Same address now cleans to "Muttungal P.O., Balavadi". Different cache key -> cache miss. Google geocodes it correctly within the zone at confidence 0.60. Cached at 0.60.
- **Day 3:** Same address uploaded again. Cache hit from Day 2 entry at 0.60.

Now the database has TWO cache entries for the same physical address, with different confidence scores (0.42 and 0.60). Depending on which cleaned form is used, the driver sees different confidence badges for the same delivery location. If a third upload uses yet another cleaning variant, a third entry appears.

The fallback chain also means that two addresses in the SAME upload batch can get different treatment: one geocodes correctly on first try (confidence 0.80), another goes through the area-only retry (confidence 0.56). The driver sees the first as "confirmed" and the second as "approximate" even though both are equally accurate delivery locations.

**Why it happens:**
The confidence score conflates two meanings: (1) how confident Google is in the geocode, and (2) how many fallback steps were needed to get a valid result. A centroid fallback with confidence 0.3 is genuinely approximate, but an area-only retry with confidence 0.42 might be perfectly accurate -- it just went through an extra step.

**How to avoid:**
1. Separate `geocode_confidence` (Google's raw score) from `validation_confidence` (whether the result passed zone validation). The driver cares about the FINAL result quality, not how many retries it took.
2. Set clear thresholds: confidence < 0.5 shows "Approx. location" badge. Document that this threshold applies to the FINAL confidence after all fallbacks, not to intermediate values.
3. When the fallback chain produces a result, log the full chain for debugging: "Address X: geocoded at 0.40 (outside zone) -> retry with area at 0.60 (within zone) -> final confidence 0.60."
4. When a driver-verified location is saved (confidence 0.95), it overrides ALL previous cache entries for that normalized address. Ensure the `save_driver_verified()` path uses the same normalized key as the preprocessing pipeline.

**Warning signs:**
- Same physical address shows "Approx. location" badge on one day but not another
- Driver-verified locations (0.95) coexist with low-confidence entries (0.30) for the same address
- Confidence scores cluster around arbitrary multiplication products (0.42, 0.28) rather than meaningful values

**Phase to address:**
Phase 3 (Geocode Validation) -- design the confidence calculation carefully. Phase 4 (API + Driver UI) -- set the "approximate" badge threshold with clear documentation of what it means.

---

### Pitfall 5: Dictionary Build Script Fetches Stale or Incomplete OSM Data

**What goes wrong:**
The place name dictionary is built once from OSM Overpass API and India Post API. Both data sources have significant coverage gaps for rural Kerala:

1. **OSM coverage in rural Kerala is spotty.** Many hamlets, colonies, and micro-localities in the Vatakara region are not mapped in OpenStreetMap. OSM has good road coverage for Kerala but place name coverage for small settlements (which is exactly what CDCMS addresses reference) is incomplete. A 30km radius query might return 200 place nodes, but the actual CDCMS dataset references 50+ place names not in OSM.

2. **India Post API returns post office names, not localities.** The PostalPinCode API for PIN codes 673101-673110 returns ~77 post office names. But CDCMS addresses reference landmarks, house names, colonies, and micro-areas that are NOT post offices. "K.T. Bazar" is a market area, not a post office. "Sarambi" is a locality, not a post office.

3. **OSM Overpass API has no SLA.** The public Overpass API at `overpass-api.de` has rate limits (~10,000 requests/day) and occasionally goes down. If the build script runs when the API is slow or down, it produces an incomplete dictionary. The script should retry, but the design spec shows a single query approach.

The dictionary is committed to the repo, so a bad build persists until someone notices and rebuilds.

**Why it happens:**
The design spec correctly identifies these as data sources but overestimates their coverage for rural Kerala micro-localities. OSM is excellent for cities like Kozhikode or Kochi but has much thinner coverage for the hamlets and colonies that CDCMS addresses reference in the Vatakara hinterland. The spec estimates "~200-300 entries" but the actual unique place names in CDCMS data may number 400+.

**How to avoid:**
1. **Bootstrap the dictionary from actual CDCMS data**, not just OSM/India Post. Extract unique AreaName values from historical CDCMS uploads and add them to the dictionary. The area_name column in existing orders contains the most relevant place names. Run: `SELECT DISTINCT area_name FROM orders;` to get the real-world vocabulary.
2. **Treat the dictionary as a living document.** When the splitter encounters an address it cannot split (no dictionary match), log the address. Periodically review logged addresses and add new place names to the dictionary.
3. **Validate the dictionary against the 27 sample CDCMS addresses** from the test suite. Every area_name in the sample data must appear in the dictionary. If any are missing, the dictionary is incomplete.
4. **Add a fallback for dictionary build failures.** If the Overpass API is down, the build script should fail loudly (not produce a partial dictionary) and documentation should explain how to retry.
5. **Include GPS coordinates for CDCMS area names** from the geocode cache. If "MUTTUNGAL" has been geocoded before (even incorrectly), the cache has approximate coordinates that can seed the dictionary entry.

**Warning signs:**
- Dictionary has fewer than 150 entries (suggests API returned incomplete data)
- CDCMS area names in the sample CSV do not appear in the dictionary
- Build script completes in under 2 seconds (suggests API returned empty or cached error response)
- Multiple addresses fall through to "passthrough for unknown text" in the splitter logs

**Phase to address:**
Phase 2 (Place Name Dictionary) -- validate dictionary completeness against real CDCMS data before proceeding to Phase 3. This is a gate: if the dictionary covers less than 80% of area names in sample data, stop and augment before continuing.

---

### Pitfall 6: Validator Retry Doubles Google API Cost Without Budget Guard

**What goes wrong:**
The geocode validation fallback chain can make up to 3 Google API calls per address:
1. Original geocode (always)
2. Retry with area name only (if original is outside 30km)
3. Potential additional call if the area-only retry also fails and a different reformulation is attempted

For a batch of 50 addresses where 30% fail zone validation (15 addresses), that is 15 extra API calls. At $5/1000 requests, the cost is negligible ($0.075). But the design spec does not address what happens when the Google API key is invalid (`REQUEST_DENIED` -- the current known state of the system).

With an invalid API key, EVERY geocode call fails. The fallback chain then retries EVERY address, doubling the number of failed API calls and associated error logging. The system degrades to: geocode fails -> validator retries -> retry also fails -> centroid fallback for ALL addresses. Every delivery gets confidence 0.3 and "Approx. location" badge. Drivers see a wall of orange badges and lose trust in the system.

**Why it happens:**
The design spec acknowledges the invalid API key as a "known constraint" but the fallback chain design assumes the API is functional and only SOME addresses fail validation. When the API is completely down, the entire chain degrades to centroid-only mode, which is not the intended behavior.

**How to avoid:**
1. **Check API key validity BEFORE running the fallback chain.** If the first geocode call returns `REQUEST_DENIED`, skip all retries and use cache-only mode. Do not retry with area name -- the same key will be denied again.
2. **Add a circuit breaker for Google API calls.** If 3 consecutive calls return `REQUEST_DENIED` or `OVER_QUERY_LIMIT`, stop making API calls for this batch and log a clear error: "Google Maps API key is invalid -- all addresses will use cached or approximate locations."
3. **Track retry API cost separately.** The existing cost tracking (cache hits vs API calls) should distinguish between first-attempt calls and retry calls. This makes the retry cost visible.
4. **When ALL addresses fall back to centroid, surface a prominent warning** in the upload response and on the dashboard -- not just individual "approximate" badges on each stop.

**Warning signs:**
- Upload response shows 100% of addresses as "approximate" (centroid fallback)
- Google API cost tracker shows double the expected number of API calls
- Logs show `REQUEST_DENIED` errors for every geocode attempt plus every retry attempt
- Driver PWA shows "Approx. location" badge on every single stop

**Phase to address:**
Phase 3 (Geocode Validation) -- the circuit breaker and API key check must be part of the validator, not an afterthought. Phase 4 (API + Driver UI) -- add a batch-level warning when all addresses are approximate.

---

### Pitfall 7: Regex Reordering Breaks Existing Clean Address Tests

**What goes wrong:**
The design spec calls for reordering cleaning steps: "split words BEFORE expanding abbreviations" (task 1.3). The current step order in `clean_cdcms_address()` is:

1. Remove phone numbers
2. Remove CDCMS artifacts
3. Normalize backticks
4. Expand abbreviations (NR -> Near, PO -> P.O., (H) -> House)
5. Add spaces before uppercase after digits
6. Collapse whitespace
7. Remove dangling punctuation
8. Title case
9. Fix title-case artifacts
10. Append area suffix

The proposed reorder moves step 5 before step 4. But the abbreviation expansion in step 4 depends on the text NOT having spaces inserted yet. For example:

- Input: `KUNIYILNR.EK GOPALAN`
- Current step 4: `NR.` matched as abbreviation -> `KUNIYIL Near EK GOPALAN`
- Proposed step 5 first: `(\d)([A-Z])` and `([a-z])([A-Z])` regexes -> no match (NR. has period, not case transition)

But consider: `CHEKKIPURATHPO.`
- Current step 4: `([a-zA-Z])PO\.` matches -> `CHEKKIPURATH P.O.`
- Proposed step 5 first: `([a-z])([A-Z])` on uppercase text -> no match (all uppercase)

The reordering seems safe for the specific examples in the design spec, but there are edge cases where abbreviation patterns like `NR` or `PO` appear at positions that interact with the word-splitting regex. The existing 426 unit tests include tests for `clean_cdcms_address()` that may fail if the step order changes.

**Why it happens:**
Text processing pipelines are order-dependent. Each regex assumes a specific input format produced by the previous step. Changing the order is equivalent to changing the input contract for each subsequent step. The design spec identifies the happy-path cases but does not exhaustively test all combinations.

**How to avoid:**
1. **Run existing tests BEFORE and AFTER the reorder.** The test suite has tests for `clean_cdcms_address()` in `tests/core/data_import/test_cdcms_preprocessor.py`. Run them first to establish a baseline, then after reordering.
2. **Add the new `lowercase -> uppercase` regex as an ADDITIONAL step, not a replacement.** The design spec says "Also add: `re.sub(r"([a-z])([A-Z])", r"\1 \2", addr)`" -- keep this as a new step 5b alongside the existing step 5, not as a replacement.
3. **Do NOT reorder abbreviation expansion.** The existing abbreviation expansion (PO -> P.O., NR -> Near) works correctly on concatenated text because the regex patterns handle inline detection (`([a-zA-Z])PO\.`). Moving word splitting before abbreviation expansion would break this inline detection because the text would already have spaces inserted.
4. **Test with ALL 27 sample CDCMS addresses**, not just the 4 examples in the design spec. Edge cases will surface with real data.

**Warning signs:**
- Existing `test_cdcms_preprocessor.py` tests start failing after the reorder
- Addresses that previously cleaned correctly now have garbled abbreviations ("P.o." instead of "P.O.", "Nr." not expanding)
- The `clean_cdcms_address()` function grows beyond 50 lines with interleaved regex steps that are hard to reason about

**Phase to address:**
Phase 1 (Foundation) -- tasks 1.2 through 1.5 must be done carefully with full test coverage before AND after changes. Do NOT change step order unless tests prove it is necessary and safe.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcoding 85% fuzzy threshold | Simple, one value to tune | False positives on short names; need per-length thresholds | Never for place name matching -- use length-dependent thresholds from the start |
| Committing a dictionary built from one-time API fetch | Quick, no ongoing maintenance | Dictionary becomes stale as new addresses appear; misses localities not in OSM/India Post | Acceptable for MVP if combined with a logging-and-augment workflow for missed names |
| Multiplying confidence scores (0.7 * 0.6 = 0.42) | Simple arithmetic | Confidence values become meaningless products; hard to interpret or set thresholds against | Never -- use discrete confidence levels or clearly defined multiplier semantics |
| Storing area centroid fallback with same Location model | No model changes needed | Centroid locations are fundamentally different from geocoded locations (100m accuracy vs 5km accuracy) but stored identically | Acceptable if `geocode_confidence` clearly distinguishes them (0.3 for centroid vs 0.6+ for geocoded) |
| Skipping Alembic migration for confidence field exposure | No DB schema change needed (field already exists) | Future developers assume no migration means no DB impact; may miss that the field was NULL for old records | Acceptable here -- the field exists and is nullable. Document that old records have NULL confidence. |
| Using `order.address_raw` directly as `address_display` | One-line fix, eliminates the display inconsistency | `address_raw` may contain CDCMS artifacts not caught by preprocessing; driver sees semi-raw text | Acceptable if preprocessing is thorough enough; add a "cleaned but unrecognizable" safety net |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| AddressSplitter + CachedGeocoder | Initializing the splitter inside the geocoder (tight coupling); if dictionary file is missing, geocoder crashes | Splitter is initialized in `cdcms_preprocessor.py` (preprocessing layer), not in the geocoder. Geocoder receives already-split text. Splitter is `None` if dictionary missing -- graceful degradation. |
| GeocodeValidator + CachedGeocoder | Validator calls upstream geocoder for retry, creating a recursive loop (cached -> validate -> retry via cached -> validate again) | Validator retries must go through the UPSTREAM geocoder directly (GoogleGeocoder), not through CachedGeocoder. Otherwise the retry result gets cached with wrong confidence before validation completes. |
| Dictionary JSON + Docker volume | Dictionary file in `data/` directory is bind-mounted in Docker; rebuilding dictionary on host requires container restart to pick up changes | The dictionary is loaded lazily on first use per the design spec. Add a reload mechanism or document that container restart is needed after dictionary rebuild. |
| RapidFuzz + Docker image | `rapidfuzz` has C++ extensions that need compilation; `python:3.12-slim` may lack build tools | Use `rapidfuzz` wheel (pre-compiled for linux/x86_64) or install `gcc` in the Dockerfile build stage. Test the Docker build BEFORE deploying -- a missing wheel causes `pip install` failure. |
| Haversine validator + PostGIS | Implementing haversine in Python when PostGIS already provides `ST_DistanceSphere` for the same calculation | The Python haversine is correct here -- the validator runs BEFORE saving to the database, so PostGIS is not available. But if validation is ever moved to a DB query, use `ST_DistanceSphere` instead. |
| New `location_approximate` field + existing API consumers | Adding a new field to the API response that the dashboard does not expect; dashboard TypeScript types may need updating | The driver PWA (vanilla JS) handles unknown fields gracefully. The dashboard (TypeScript) will NOT break on extra fields but will not display them either. Update TypeScript types if dashboard should show confidence. |
| Driver-verified geocode + preprocessing pipeline | Driver confirms delivery at GPS coordinates; `save_driver_verified()` stores with confidence 0.95. Next upload preprocesses the same address differently, creates a new cache key, and geocodes again -- ignoring the driver-verified entry. | Ensure `save_driver_verified()` uses the SAME normalized key that the preprocessing pipeline produces. If preprocessing changes the cleaned address, the driver-verified entry becomes orphaned. Consider linking driver-verified entries by physical proximity (within 50m), not just by text match. |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Loading full dictionary JSON on every request | 200-300 entry JSON parsed and fuzzy index rebuilt per geocode call; adds ~50ms per address | Load dictionary once at startup (module-level or singleton); the design spec calls for lazy initialization -- do it exactly once, not per-call | Immediately noticeable at 50 addresses/batch (~2.5s overhead) |
| RapidFuzz `extractOne` on full dictionary for every word in an address | O(N*M) where N = words in address, M = dictionary entries; ~10ms per word * 8 words * 50 addresses = 4 seconds | Pre-sort dictionary by length (longest first) for greedy matching; use `rapidfuzz.process.extractOne` with `score_cutoff` parameter to skip low-score comparisons early | At 300+ dictionary entries with 8+ word addresses |
| Haversine calculation per validation | Negligible (~0.1ms per call) | Not a performance concern at this scale | Never at 50 addresses/day; would matter at 10K+/day |
| Fallback retry doubles geocode time for out-of-zone results | Addresses that fail validation take 2x as long (two API calls instead of one); if 30% fail, batch takes 30% longer | Acceptable at current scale (extra 15 API calls * 1 sec rate limit = 15 extra seconds). Would be a problem at 500+ addresses where 150 retries = 2.5 extra minutes. | At 200+ addresses per batch with >20% validation failure rate |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Dictionary JSON containing exact delivery zone boundary (depot lat/lon + 30km radius) | Reveals the business's operational area to anyone with repo access; competitive intelligence risk | The dictionary is committed to the repo (by design). If the repo is private, this is acceptable. If public/shared, strip depot coordinates from the dictionary metadata and store them only in `config.py`. |
| Logging full addresses in fuzzy match debug output | CDCMS addresses contain customer names, house names, and potentially phone numbers; logging them violates privacy | Log only the address fragment being matched (first 30 chars) and the match score, not the full address. The existing codebase follows this pattern (`address[:50]` in log messages). |
| Area centroid coordinates hardcoded in dictionary | If dictionary is leaked, reveals exact delivery area boundaries | Acceptable risk -- OSM data is public. The centroid coordinates are derived from publicly available OpenStreetMap data. |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| "Approx. location" badge on EVERY stop when API key is invalid | Drivers lose trust in the system; badge becomes meaningless noise; drivers stop paying attention to it | When ALL stops are approximate, show a SINGLE banner at the top ("Location data unavailable -- all locations are approximate today") instead of per-stop badges. |
| Orange badge color on orange/saffron-themed dark PWA | The design spec uses `tw:badge-warning` (DaisyUI warning = amber/orange). The driver PWA already uses saffron as an accent color for buttons. Orange badge blends with orange buttons -- low visual contrast. | Use a distinct color for the approximate badge. Consider `tw:badge-info` (blue) or a custom color that stands out against the dark theme. Test on a real phone screen in sunlight. |
| "Approx. location" text without actionable guidance | Driver sees "approximate" but does not know what to do. Call the customer? Navigate anyway? Report to office? | Add a tap action to the badge that shows a tooltip or small dialog: "Location is approximate. Navigate to this area, then call customer for exact directions." Link to the Call Office FAB. |
| Confidence score displayed as a number (0.42) | Numbers below 1.0 are meaningless to delivery drivers. "0.42 confidence" means nothing. | Never show the raw confidence number to drivers. Map it to simple categories: green check (> 0.7), orange tilde (0.3-0.7), red question mark (< 0.3). Only show the icon, not the number. |

## "Looks Done But Isn't" Checklist

- [ ] **address_display fix:** Often changes `vroom_adapter.py:278` but forgets to update `scripts/import_orders.py:219-220` which also sets `address_display` from `order.location.address_text` -- the script still uses the old logic.
- [ ] **Dictionary build script:** Often fetches OSM data and commits JSON but forgets to validate against real CDCMS area names -- dictionary may miss 30% of actual delivery areas.
- [ ] **Fuzzy matching:** Often tests with the 4 examples from the design spec but forgets to test with short names (4-5 chars) where false positive rate is highest.
- [ ] **Geocode validation:** Often tests the happy path (address within zone) and the fallback (centroid) but forgets to test the intermediate case (area-only retry succeeds) -- the retry confidence multiplier may produce unexpected values.
- [ ] **API confidence field:** Often adds `geocode_confidence` to the route response but forgets that OLD routes (before this feature) have `NULL` confidence -- driver PWA must handle `null` without crashing.
- [ ] **Driver PWA badge:** Often adds the badge HTML but forgets to test with `location_approximate: false` (badge should be hidden) and with missing field (pre-upgrade API responses) -- badge must default to hidden.
- [ ] **RapidFuzz in Docker:** Often adds `rapidfuzz` to `requirements.txt` but forgets to verify the Docker build succeeds -- `rapidfuzz` C++ extensions may need build tools in the Docker image.
- [ ] **Haversine formula:** Often implements the formula correctly but uses degrees instead of radians in the `math.sin()`/`math.cos()` calls -- produces wildly wrong distances. Always convert lat/lon to radians first.
- [ ] **Existing tests:** Often adds new preprocessing tests but forgets to run the existing 426 unit tests -- regex reordering may break tests for `clean_cdcms_address()` that passed before.
- [ ] **Cache key consistency:** Often changes preprocessing but forgets that `normalize_address()` is a SEPARATE function from `clean_cdcms_address()` -- changes to cleaning do NOT automatically update cache keys, which is correct but must be understood.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Cache poisoning (duplicate entries for same address) | LOW | Run deduplication query: find geocode_cache entries where `address_norm` values differ but locations are within 50m. Keep the highest-confidence entry. No data loss -- addresses re-geocode on next upload with new preprocessing. |
| address_display truncation in DB | LOW | Alter column: `ALTER TABLE orders ALTER COLUMN address_display TYPE TEXT;` (removes 255 char limit). Re-upload affected CSV to populate correct values. |
| Fuzzy matching false positive (wrong place assigned) | MEDIUM | Identify affected addresses in the geocode cache by checking if cached location is far from the dictionary's coordinates for the matched place name. Delete incorrect cache entries. Re-geocode on next upload. Driver-verified entries override any cache errors over time. |
| Inconsistent confidence scores across uploads | LOW | Redefine confidence as a simple function of the final state, not a product of intermediate scores. Update existing cache entries with recalculated confidence. No delivery impact -- confidence is informational only. |
| Dictionary missing critical place names | LOW | Add missing names manually to the JSON file and re-commit. No code change needed. The splitter picks up new entries on next lazy load (container restart). |
| Regex reordering breaks existing tests | LOW | Revert to original step order. Add the new regex as an ADDITIONAL step at the end (before title case) rather than reordering. Run test suite to confirm. |
| All addresses show "approximate" due to API key failure | MEDIUM | Fix the Google API key (enable Geocoding API, set up billing). Re-upload the CSV. Addresses will geocode correctly this time and cache will be populated. Until the key is fixed, the centroid fallback provides serviceable (not perfect) locations. |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Cache poisoning from preprocessing changes | Phase 1: Foundation | Monitor cache miss count on first upload after deployment; verify no duplicate cache entries within 50m |
| address_display downstream breakage | Phase 1: Foundation | Grep for `address_display` in all `.py`, `.tsx`, `.html` files; verify max length of `address_raw` < 255 chars |
| Fuzzy matching false positives | Phase 2: Place Name Dictionary | Test with ALL sample addresses; log all fuzzy matches with scores; manual review of matches below 90% |
| Inconsistent confidence across re-uploads | Phase 3: Geocode Validation | Upload same CSV twice; verify confidence scores are identical for all addresses |
| Dictionary incompleteness | Phase 2: Place Name Dictionary | Compare dictionary place names against `SELECT DISTINCT area_name FROM orders`; coverage must be > 80% |
| Validator retry doubling API cost | Phase 3: Geocode Validation | Add circuit breaker for `REQUEST_DENIED`; test with invalid API key -- verify retry count is bounded |
| Regex reordering breaking tests | Phase 1: Foundation | Run full test suite before AND after changes; zero regressions allowed |
| "Approx. location" badge UX problems | Phase 4: API + Driver UI | Test on real phone in sunlight; verify badge contrast ratio; test with all-approximate scenario |
| RapidFuzz Docker build failure | Phase 2: Place Name Dictionary | Rebuild Docker image from scratch after adding rapidfuzz to requirements.txt; verify successful `import rapidfuzz` inside container |
| Haversine implementation error | Phase 3: Geocode Validation | Test with known distance pairs: Vatakara depot to Kozhikode city (~37km), depot to Mahe (~12km); compare with Google Maps distance |
| Driver-verified entries orphaned by preprocessing changes | Phase 3: Geocode Validation | Verify that driver-verified entries are accessible after preprocessing changes; test the proximity-based lookup path |

## Sources

- [Google Geocoding API Best Practices](https://developers.google.com/maps/documentation/geocoding/best-practices) -- official guidance on handling ambiguous results, not parsing formatted_address
- [Indian Address Geocoding Challenges](https://thebangaloreguy.com/problem-of-geocoding-non-standardised-addresses-in-india-an-nlp-problem/) -- non-standardized Indian address formats as NLP problem
- [RapidFuzz Documentation](https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html) -- fuzzy matching functions and score behavior on different string lengths
- [RapidFuzz GitHub](https://github.com/rapidfuzz/RapidFuzz) -- C++ extension build requirements, wheel availability
- [OSM Overpass API Rate Limiting](https://wiki.openstreetmap.org/wiki/Overpass_API) -- 10,000 requests/day guideline, 429 rate limit responses
- [India Post PIN Code API](http://www.postalpincode.in/Api-Details) -- 1000 requests/hour rate limit, post office names (not localities)
- [Haversine vs OSRM for Routing](https://www.nextmv.io/blog/haversine-vs-osrm-distance-and-cost-experiments-on-a-vehicle-routing-problem-vrp) -- haversine accuracy limitations for actual road distance
- [Geocoding Tips for Last-Mile Delivery](https://routinguk.descartes.com/resources/geocoding-best-practices-delivery-management) -- inaccurate geocode knock-on effect on all routes
- [Google Geocoding Request/Response](https://developers.google.com/maps/documentation/geocoding/requests-geocoding) -- formatted_address field semantics, location_type confidence mapping
- Codebase analysis: `.planning/codebase/ARCHITECTURE.md`, `CONCERNS.md`, `INTEGRATIONS.md` -- existing system architecture and known issues
- Design spec: `docs/superpowers/specs/2026-03-10-address-preprocessing-design.md` -- the plan being evaluated for pitfalls
- Source code: `core/geocoding/cache.py`, `core/geocoding/normalize.py`, `core/data_import/cdcms_preprocessor.py`, `core/optimizer/vroom_adapter.py`, `core/database/models.py` -- actual implementation being modified

---
*Pitfalls research for: v2.2 Address Preprocessing Pipeline*
*Researched: 2026-03-10*
