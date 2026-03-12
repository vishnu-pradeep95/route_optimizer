# Project Research Summary

**Project:** Kerala LPG Delivery Route Optimizer — v2.2 Address Preprocessing Pipeline
**Domain:** Dictionary-powered address splitting, geocode validation, and location confidence UI
**Researched:** 2026-03-10
**Confidence:** HIGH

## Executive Summary

This is a targeted bug-fix milestone (v2.2) on an existing production system. The core problem is two interacting bugs: CDCMS exports concatenate Malayalam place names without separators (e.g., `MUTTUNGALPOBALAVADI`), causing Google to geocode delivery addresses to locations 40+ km away, while a secondary bug in `vroom_adapter.py` displays Google's `formatted_address` instead of the original cleaned address — so drivers see wrong locations AND wrong text. The fix requires building a domain-specific preprocessing layer tuned for CDCMS Kerala address patterns, not a general-purpose Indian address NLP solution.

The recommended approach is a two-stage fix. Stage one is fast and independent: a one-line display-text fix and an improved regex. Stage two is the core improvement: a static dictionary of ~285 place names within 30km of the Vatakara depot (built from OSM Overpass + India Post APIs, committed to the repo), used by a new `AddressSplitter` class to detect word boundaries in concatenated text. A new `GeocodeValidator` then applies a 30km haversine zone check to every geocode result, with a three-tier fallback chain (area-name retry -> area centroid -> flag as approximate). The pipeline ends by surfacing confidence data through the API to the Driver PWA as an "Approx. location" badge. The entire implementation requires exactly one new runtime dependency: RapidFuzz 3.14.3 (MIT, ~4MB wheel, no compiler needed in Docker).

The primary risks are cache poisoning from preprocessing changes (old cache entries persist with wrong keys — desired behavior, but must be monitored), fuzzy matching false positives on short Kerala place names (mitigated by length-dependent thresholds), and an invalid Google API key causing every address to fall back to centroid-only mode with a wall of orange badges that erodes driver trust. The validator must include a circuit breaker for API failures. NER-based address parsing (IndicBERT) is explicitly deferred to a conditional future path, triggered only if post-deployment metrics show >10% validation failures.

## Key Findings

### Recommended Stack

The existing Python 3.12 / FastAPI / React / TypeScript stack requires no changes to support this feature. One new runtime dependency is needed: RapidFuzz 3.14.3 for fuzzy string matching in the dictionary splitter. All other components — haversine distance (10 lines of stdlib `math`), dictionary storage (static JSON, <50KB), and UI indicators (existing DaisyUI `tw:badge-warning`) — use what is already in the project. The dictionary build script uses `requests` (already in `requirements.txt`) to call the OSM Overpass API and the India Post PostalPinCode API at build time only; the runtime never makes these calls.

See `.planning/research/STACK.md` for full dependency analysis including the optional NER path (Approach B), which would add ~600MB to the Docker image and is explicitly deferred.

**Core technologies:**
- **RapidFuzz 3.14.3**: Fuzzy matching in `AddressSplitter` — C++ core (10-100x faster than fuzzywuzzy), MIT license, pre-built wheel for `python:3.12-slim`, no Dockerfile changes needed
- **Python stdlib `math`**: Haversine zone validation in `GeocodeValidator` — 10 lines, no external dependency, accuracy within 0.5% at 30km
- **OSM Overpass API** (build-time only): Extract ~285 place name nodes within 30km of depot — free, no auth, ODbL licensed
- **India Post PostalPinCode API** (build-time only): Extract post office names for PIN codes 673101-673110 — free, 1000 req/hr, structured JSON
- **Existing DaisyUI `tw:badge-warning tw:badge-sm`**: "Approx. location" badge in Driver PWA — zero new CSS, no build step

### Expected Features

All eight features listed below are required together. Shipping a subset leaves drivers going to wrong locations and the core bug unfixed.

See `.planning/research/FEATURES.md` for full details, dependency graph, and competitor analysis.

**Must have (table stakes — v2.2 launch):**
- **address_display source fix** — one-line change (`vroom_adapter.py:278`); eliminates display inconsistency independently of all other work; must ship first as a safety net
- **Improved regex word splitting** — adds `([a-z])([A-Z])` split to existing `(\d)([A-Z])` pattern; handles common concatenation patterns with ~20 lines; independent and safe
- **Place name dictionary build** — `scripts/build_place_dictionary.py` fetches OSM + India Post data, commits `data/place_names_vatakara.json`; gates dictionary-powered splitting
- **Dictionary-powered word splitting** — `AddressSplitter` class (~150 lines); longest-match-first scan, 85%+ fuzzy threshold, graceful passthrough for unknown text
- **Geocode zone validation** — `GeocodeValidator` with 30km haversine check; standard practice in logistics geocoding (Route4Me, LogiNext, Geocodio all do this)
- **Fallback chain (area retry -> centroid -> flag)** — integrated into `CachedGeocoder.geocode()`; ensures no order is silently dropped; confidence tiers: 1.0 (in-zone first try), 0.7x (area retry), 0.3 (centroid)
- **API confidence fields** — `geocode_confidence` (float) and `location_approximate` (bool) added to stop JSON; additive, backward compatible; `Location` model already has the field
- **Driver PWA "Approx. location" badge** — `tw:badge-warning` on hero card, orange dot on compact cards; informational only, Navigate button still works; existing `save_driver_verified()` self-heals over time

**Should have (add after one week of real-world validation):**
- Dictionary gap reporting — log unmatched address tokens to identify coverage holes
- Dictionary auto-refresh script — when new settlements appear
- Accuracy metrics dashboard view — operator visibility into pipeline performance

**Defer (v3+, conditional on metrics):**
- Approach B NER model (IndicBERT) — only if metrics show >10% validation failures; may never be needed
- Dashboard geocode quality report
- Driver location pin correction (passive self-healing via `save_driver_verified()` already handles this)

**Reject (anti-features):**
- NER as default path (adds 600MB Docker image, 50ms/address, unnecessary for a 30km zone)
- Multiple geocoding providers (coordinate inconsistency outweighs coverage benefit)
- Fuzzy full-address matching (false positives for "VALLIKKADU EAST" vs "VALLIKKADU WEST")
- Real-time address autocomplete (CDCMS is a CSV upload workflow, not manual entry)

### Architecture Approach

The pipeline is an extended preprocessing chain inserted between the existing CDCMS importer and the existing GoogleGeocoder / CachedGeocoder / PostGIS stack. Two new modules (`address_splitter.py`, `validator.py`) integrate via injection: the splitter is called inside `clean_cdcms_address()` as a new Stage 3 (after regex splitting, before abbreviation expansion); the validator is injected into `CachedGeocoder` as an optional constructor parameter (backward compatible, defaults to no-op). The dictionary JSON file (`data/place_names_vatakara.json`) is the single shared data source for both the splitter (word boundary detection) and the validator (area centroid fallback coordinates). All integration points are additive — no existing API fields are removed, no DB schema migrations are needed, and all four modified files preserve existing behavior when new components are absent.

See `.planning/research/ARCHITECTURE.md` for full data flow diagrams, component interfaces, the step-reorder rationale, and the complete dependency graph with build order.

**Major components:**
1. **`core/data_import/address_splitter.py`** (NEW) — dictionary-powered word splitting; lazy init, graceful `None` fallback if dictionary missing; RapidFuzz fuzzy match at 85%+ threshold with longest-match-first ordering
2. **`core/geocoding/validator.py`** (NEW) — 30km haversine zone check; three-tier fallback chain (area geocode retry -> area centroid -> flag); injectable into CachedGeocoder; circuit-breaker for API key failures
3. **`data/place_names_vatakara.json`** (NEW) — static dictionary (~285 entries); built once from OSM + India Post; committed to repo; loaded once per process lifetime; shared between splitter and validator
4. **`scripts/build_place_dictionary.py`** (NEW) — one-time build script; not imported at runtime
5. **`core/data_import/cdcms_preprocessor.py`** (MODIFIED) — adds lowercase->uppercase regex and dictionary splitter call between existing cleanup and abbreviation expansion stages
6. **`core/optimizer/vroom_adapter.py`** (MODIFIED) — one-line fix: `address_display = order.address_raw` always
7. **`core/geocoding/cache.py`** (MODIFIED) — optional `validator` and `area_name` parameters; backward compatible
8. **`apps/kerala_delivery/api/main.py`** (MODIFIED) — adds confidence fields to stop JSON; constructs GeocodeValidator; builds `area_name_map` from preprocessed DataFrame

### Critical Pitfalls

See `.planning/research/PITFALLS.md` for all seven critical pitfalls, integration gotchas, technical debt patterns, and the full "Looks Done But Isn't" checklist.

1. **Cache poisoning from preprocessing changes** — when `clean_cdcms_address()` produces different output, existing PostGIS cache entries become orphaned under old normalized keys. Do NOT change `normalize_address()`. Accept that the first upload after deployment will re-geocode affected addresses (desired — old cache had wrong coordinates). Monitor cache miss spike. Old entries for garbled addresses are harmless but never used again.

2. **Fuzzy matching false positives on short Kerala place names** — at 85% threshold, `EDAPPAL` matches `EDAPALLI` (88% similarity, but different places 50km apart). Implement length-dependent thresholds: 95% for names under 6 characters, 90% for 6-8 characters, 85% for names over 8 characters. Prefer explicit `aliases` arrays in the dictionary over fuzzy matching for known transliteration variants.

3. **Validator retry has no circuit breaker for invalid API key** — if the Google API key is invalid (`REQUEST_DENIED`), every address triggers a retry, producing a wall of "Approx. location" badges that destroys driver trust. Add a circuit breaker: 3 consecutive `REQUEST_DENIED` responses stop all retries for the batch and surface a single batch-level warning banner instead of per-stop badges.

4. **Regex reordering breaks existing tests** — moving abbreviation expansion after word splitting changes how inline abbreviations (`NR.`, `PO.`) are detected in concatenated text. The existing 426 unit tests for `clean_cdcms_address()` establish the contract. Run the full test suite before and after any step reordering. If tests break, add the new regex as an additional step rather than reordering existing steps.

5. **Dictionary incompleteness from OSM/India Post gaps** — OSM has thin coverage for rural Kerala micro-localities. Bootstrap the dictionary from actual historical CDCMS data: `SELECT DISTINCT area_name FROM orders`. Validate coverage against real area names before Phase 3. Hard gate: must cover >80% of area names in sample data before proceeding.

6. **address_display downstream truncation and ripple** — `address_raw` with area suffix can exceed 255 chars (the `address_display` DB column limit). Audit all `address_display` consumers (including `qr_helpers.py` and `scripts/import_orders.py`, which the design spec does not list). Verify `MAX(LENGTH(address_raw)) < 255` in production data or widen the column via Alembic migration.

## Implications for Roadmap

The dependency graph is clear and the architecture research defines the exact build order. Five phases map naturally to the five logical work units.

### Phase 1: Foundation Fixes

**Rationale:** The `address_display` fix and improved regex are independent of all other work and immediately beneficial. They can — and should — ship first as a safety net regardless of whether the dictionary infrastructure is ever built. They also establish the test baseline before any riskier pipeline changes.

**Delivers:** Correct address display text in the Driver PWA for all routes; improved word splitting for the most common CDCMS concatenation patterns (digit-to-uppercase and lowercase-to-uppercase transitions).

**Addresses (from FEATURES.md):** `address_display source fix`, `Improved regex word splitting`

**Avoids (from PITFALLS.md):** Downstream consumer breakage (requires full audit of `address_display` consumers including `qr_helpers.py` and `scripts/import_orders.py`; length check against DB column limit); regex reordering regressions (run full test suite before and after, add new regex as additional step rather than reorder if tests break)

**Research flag:** Standard patterns — no additional research needed. Implementation is clear with line-number precision from ARCHITECTURE.md.

### Phase 2: Place Name Dictionary and Address Splitter

**Rationale:** The dictionary is the shared data foundation for both the `AddressSplitter` (this phase) and the `GeocodeValidator` (Phase 3). It must exist and be validated for completeness before either consumer can work correctly. Dictionary completeness is a hard gate — if it covers less than 80% of real CDCMS area names, Phase 3's centroid fallback will silently fail for missing areas.

**Delivers:** `data/place_names_vatakara.json` (~285 entries from OSM + India Post + historical CDCMS area names); `AddressSplitter` class with RapidFuzz fuzzy matching and length-dependent thresholds; splitter integrated into `clean_cdcms_address()` pipeline; unit tests for all splitter paths including short-name false-positive cases.

**Uses (from STACK.md):** RapidFuzz 3.14.3 (NEW dependency — add to `requirements.txt` and verify Docker build), OSM Overpass API (build-time), India Post PostalPinCode API (build-time), existing `requests` library

**Implements (from ARCHITECTURE.md):** `address_splitter.py` component, `build_place_dictionary.py` script, dictionary JSON schema

**Avoids (from PITFALLS.md):** Dictionary incompleteness (bootstrap from `SELECT DISTINCT area_name FROM orders`, validate before proceeding to Phase 3); fuzzy matching false positives (length-dependent thresholds: 95%/90%/85%, explicit alias arrays, log and manually review all matches below 90%); RapidFuzz Docker build failure (rebuild image from scratch, verify `import rapidfuzz` inside container after adding to `requirements.txt`)

**Research flag:** Moderate risk — dictionary coverage is the primary unknown and cannot be confirmed without running the build script against real CDCMS data. Treat the 80% coverage threshold as a hard gate before Phase 3.

### Phase 3: Geocode Validation and Fallback Chain

**Rationale:** Depends on the dictionary (Phase 2) for area centroid coordinates. The zone validator is the core correctness fix — the display fix (Phase 1) and splitting (Phase 2) reduce the frequency of wrong geocodes, but the validator catches any that still slip through and ensures every delivery gets a usable location within the zone.

**Delivers:** `GeocodeValidator` class with haversine zone check and three-tier fallback chain; circuit breaker for API key failures (`REQUEST_DENIED`); validator injected into `CachedGeocoder` with optional parameters (backward compatible); `area_name_map` built from preprocessed DataFrame and passed through geocoding loop; unit tests for all validation paths and fallback tiers including the circuit-breaker path.

**Uses (from STACK.md):** stdlib `math` for haversine (no new dependency), existing `CachedGeocoder`, upstream `GoogleGeocoder` (for area-name retry — must go through upstream, NOT through CachedGeocoder, to avoid recursive validation loop)

**Implements (from ARCHITECTURE.md):** `validator.py` component; modified `cache.py` (`validator` + `area_name` optional params); modified `main.py` (`GeocodeValidator` construction, `area_name_map` side-channel pattern)

**Avoids (from PITFALLS.md):** Validator retry infinite loop (retry must use upstream GoogleGeocoder directly, not CachedGeocoder); inconsistent confidence scores (use discrete levels: 1.0 in-zone, 0.7x area retry, 0.3 centroid — document semantics, avoid multiplying ambiguous intermediate values); API key failure wall-of-badges (circuit breaker after 3 consecutive `REQUEST_DENIED`); haversine implementation error (validate against known distances: depot to Kozhikode city ~37km, depot to Mahe ~12km)

**Research flag:** Medium complexity — the `area_name` side-channel (building `area_name_map` from preprocessed DataFrame) needs careful testing to ensure CDCMS and non-CDCMS upload paths both work correctly.

### Phase 4: API Confidence Fields and Driver PWA Badge

**Rationale:** UI work depends on the pipeline being complete (Phase 3) so that confidence values are meaningful before being surfaced. Exposing `geocode_confidence` before zone validation would surface Google's raw confidence, not the delivery-zone-validated confidence — a wrong signal to the driver.

**Delivers:** Two new fields (`geocode_confidence`, `location_approximate`) in the stop JSON for both route endpoints (`GET /api/routes/{vehicle_id}` and `GET /api/routes?include_stops=true`); "Approx. location" badge on hero card; orange dot on compact cards in the Driver PWA; E2E Playwright tests verifying badge appears/hides correctly and handles `null` confidence from pre-upgrade routes (old cached routes have no confidence data).

**Implements (from ARCHITECTURE.md):** Modified `main.py` stop JSON dict comprehension (2 new fields, additive); modified `index.html` (badge HTML for hero card and compact cards, conditional on `location_approximate` boolean)

**Avoids (from PITFALLS.md):** Null confidence crash (Driver PWA must handle `null` gracefully — pre-upgrade routes have NULL confidence in DB); badge color contrast on dark saffron-themed PWA (test on real phone in sunlight — consider `tw:badge-info` blue if amber `tw:badge-warning` blends into existing saffron buttons); all-approximate scenario (surface a batch-level warning banner when ALL stops are approximate, not just per-stop badges)

**Research flag:** Standard patterns — DaisyUI badge rendering is well-documented. UX decision on badge color vs. existing saffron theme requires a subjective visual test on a real device.

### Phase 5: Integration Testing and Accuracy Metrics

**Rationale:** Tests the assembled pipeline end-to-end with real CDCMS sample data. This phase is verification, not implementation. It also establishes the go/no-go criteria for the conditional Approach B (NER model) upgrade path.

**Delivers:** Full pipeline test with `sample_cdcms_export.csv`; verification that the "HDFC ERGO" and other known wrong-geocode bugs are fixed; measured accuracy metrics (% within 30km target >90%, % needing centroid fallback target <10%, dictionary coverage target >95% of area names); documented upgrade trigger criteria for NER (>10% validation failures or >5% centroid fallback rate).

**Avoids (from PITFALLS.md):** Cache poisoning not caught in development (monitor cache miss count on first real upload post-deployment; verify no duplicate cache entries within 50m proximity); driver-verified entries orphaned by preprocessing changes (verify proximity-based lookup path still works after key changes); all 10 items in the "Looks Done But Isn't" checklist in PITFALLS.md

**Research flag:** No additional research needed — this is measurement and validation work. The metrics targets are specified in FEATURES.md and the test methodology is clear.

### Phase Ordering Rationale

- Phase 1 before all others because the display fix and regex improvement are safe, independent, and provide immediate value with minimal risk. They also establish a clean test baseline before introducing more complex changes.
- Phase 2 before Phase 3 because the dictionary is a shared dependency — the validator's centroid fallback requires dictionary coordinates, and building both components against a confirmed-complete dictionary avoids retrofitting coverage gaps after the validator is already integrated.
- Phase 3 before Phase 4 because the `location_approximate` field is only meaningful after zone validation assigns validated confidence values. Without validation, all cache-miss results show Google's raw confidence (0.40-0.95), which does not reflect delivery-zone accuracy.
- Phase 4 before Phase 5 because integration testing needs the complete assembled system, including the UI indicator that will reveal any remaining bugs in the confidence pipeline.
- Phase 5 gates the conditional Approach B NER upgrade — measurable evidence required before investing in 600MB of dependencies.

### Research Flags

Phases likely needing deeper validation during execution:

- **Phase 2:** Dictionary completeness is the single biggest uncertainty in this entire project. Cannot be confirmed without running `build_place_dictionary.py` and comparing against `SELECT DISTINCT area_name FROM orders`. Treat the 80% coverage threshold as a hard gate. Also: tune length-dependent fuzzy thresholds empirically against the full sample CDCMS addresses (not just the 4 examples in the design spec).
- **Phase 3:** The `area_name` side-channel through the geocoding loop is the most complex integration point. Test thoroughly that non-CDCMS uploads pass empty `area_name` and degrade gracefully to zone-check-only without attempting the area-name retry.

Phases with standard, well-understood patterns:

- **Phase 1:** One-line fix plus additive regex. Full test suite provides immediate regression coverage. Clear implementation with exact line numbers.
- **Phase 4:** DaisyUI badge rendering is documented. Additive API fields are backward compatible. Standard Driver PWA patterns already in the codebase.
- **Phase 5:** Measurement and comparison against a fixed sample dataset. No novel patterns.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All dependencies verified against the actual `requirements.txt`, `Dockerfile`, and `docker-compose.yml`. RapidFuzz 3.14.3 confirmed on PyPI with pre-built wheels for `python:3.12-slim`. One MEDIUM note: PostalPinCode API docs verified via third-party source (official site was unresponsive during research). |
| Features | HIGH | Feature set derived from an existing design spec with clearly defined bugs to fix and a working system to verify against. Competitor analysis (Route4Me, LogiNext, Geocodio, Veho) confirms zone validation + fallback chain is standard logistics practice. Anti-feature rejections grounded in concrete system constraints (40-50 orders/day, CSV upload workflow, 30km zone). |
| Architecture | HIGH | Integration points traced through actual source code with line-number precision. Every file modification identified. Component interfaces defined in the design spec and verified against existing Pydantic models and API response structure. No speculative components — all proposed modules have clear analogues in the existing codebase. |
| Pitfalls | HIGH | Critical pitfalls identified through direct source code analysis (cache key tracing, downstream consumer audit of `address_display`, RapidFuzz behavior on short strings verified against API docs). One area of MEDIUM: OSM/India Post coverage for rural Kerala micro-localities cannot be confirmed without running the build script. |

**Overall confidence:** HIGH

### Gaps to Address

- **Dictionary coverage for rural Kerala**: Cannot be confirmed without running `build_place_dictionary.py` and comparing against `SELECT DISTINCT area_name FROM orders`. This is the primary unknown. Address in Phase 2 by treating the 80% coverage threshold as a hard gate before proceeding to Phase 3.

- **Fuzzy threshold calibration**: The 85% global threshold in the design spec is likely too aggressive for short place names. Length-dependent thresholds (95% / 90% / 85%) need empirical tuning against real CDCMS data. Address in Phase 2 integration testing with the full sample address set.

- **Google Maps navigation URL parsing**: Changing `address_display` from Google's `formatted_address` to `order.address_raw` changes what Google Maps receives when the driver taps "Navigate." Whether verbose CDCMS addresses (e.g., "8/542 Sreeshylam, Anandamandiram, K.T. Bazar, Vatakara, Kozhikode, Kerala") parse correctly in Google Maps needs manual testing on a real device. Address in Phase 4 E2E testing.

- **`scripts/import_orders.py:219-220`**: PITFALLS research flags this file as a potential missed consumer of `address_display` logic not listed in the design spec's "Unchanged Files" section. Needs explicit audit in Phase 1 before the display fix is considered complete.

- **Invalid Google API key on day one**: The project is known to have an invalid API key. The circuit breaker design must be tested against `REQUEST_DENIED` responses from the very first upload post-deployment, not just against transient failures. The centroid fallback must provide serviceable (area-level) locations even when the API is completely unavailable.

## Sources

### Primary (HIGH confidence)

- Project design spec: `docs/superpowers/specs/2026-03-10-address-preprocessing-design.md` — feature requirements, algorithm design, interface definitions, implementation plan
- Project codebase architecture: `.planning/codebase/ARCHITECTURE.md`, `CONCERNS.md`, `INTEGRATIONS.md` — existing system architecture and known issues
- Source files analyzed: `core/data_import/cdcms_preprocessor.py`, `core/geocoding/cache.py`, `core/geocoding/google_adapter.py`, `core/optimizer/vroom_adapter.py`, `core/database/models.py`, `core/models/location.py`, `apps/kerala_delivery/api/main.py`, `infra/Dockerfile`, `docker-compose.yml`, `requirements.txt`
- [RapidFuzz PyPI](https://pypi.org/project/RapidFuzz/) — v3.14.3, MIT, Python 3.10+ pre-built wheels confirmed
- [RapidFuzz fuzz module docs](https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html) — `fuzz.ratio()` and `process.extractOne()` semantics and behavior on short strings
- [OSM Overpass API wiki](https://wiki.openstreetmap.org/wiki/Overpass_API) — `around` spatial query syntax, 10K req/day rate limit
- [Google Geocoding API Best Practices](https://developers.google.com/maps/documentation/geocoding/best-practices) — handling ambiguous results, `formatted_address` semantics
- [Geocodio Accuracy Types](https://www.geocod.io/guides/accuracy-types-scores/) — confidence score tiers and fallback strategies in logistics geocoding
- [Route4Me Geocoding Guide](https://support.route4me.com/geocoding-guide-address-verification/) — zone validation in delivery logistics as standard practice
- [LogiNext Geocoding Intelligence](https://www.loginextsolutions.com/blog/geocoding-intelligence-that-reduces-exceptions-before-they-happen/) — confidence scores preventing delivery exceptions

### Secondary (MEDIUM confidence)

- [PostalPinCode API](http://www.postalpincode.in/Api-Details) — endpoint and rate limits verified via third-party docs (official site unresponsive during research)
- [Kestrel Insights Geofencing](https://www.kestrelinsights.com/blog/how-accurate-precise-geofencing-optimizes-last-mile-delivery) — zone-based validation in last-mile logistics
- [Veho Self-Serve Geocode Corrections](https://www.shipveho.com/blog/improving-delivery-accuracy-with-self-serve-customer-geocode-corrections) — self-healing geocode patterns
- [Radar Geocoding APIs Guide](https://radar.com/blog/geocoding-apis) — logistics geocoding caching and fallback

### Tertiary (context / reference)

- [GeoIndia Seq2Seq Geocoding EMNLP 2024](https://aclanthology.org/2024.emnlp-industry.29/) — Indian address geocoding challenges (informs why NER is deferred to Approach B)
- [haversine package source](https://github.com/mapado/haversine/blob/main/haversine/haversine.py) — confirms stdlib `math` sufficiency for 30km zone check
- [shiprocket-ai/open-indicbert-indian-address-ner](https://huggingface.co/shiprocket-ai/open-indicbert-indian-address-ner) — NER model specifications for Approach B reference only

---
*Research completed: 2026-03-10*
*Ready for roadmap: yes*
