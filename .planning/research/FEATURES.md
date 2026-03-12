# Feature Research

**Domain:** Address preprocessing, geocode validation, and location confidence for LPG delivery route optimization (Kerala, India)
**Researched:** 2026-03-10
**Confidence:** HIGH

## Feature Landscape

This analysis covers the v2.2 milestone scope: fixing wrong route locations caused by concatenated CDCMS addresses and unvalidated geocoding results. All features build on the existing geocoding pipeline (`GoogleGeocoder` -> `CachedGeocoder` -> PostGIS cache) and the existing CDCMS preprocessor (`clean_cdcms_address()`).

### Table Stakes (Users Expect These)

Features that must ship together. Without all of these, drivers still get sent to wrong locations and the core value proposition ("every address must appear on the map and be assigned to an optimized route") is broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **address_display source fix** | Drivers see Google's `formatted_address` ("HDFC ERGO Insurance Agent, Palayam, Kozhikode") in navigation links but the correct address in the stops list. Root cause: `vroom_adapter.py:278` uses `order.location.address_text` (Google's response) on cache miss but `address_raw` on cache hit. Both paths must always show the cleaned original. | LOW | One-line change: `address_display=order.address_raw`. Eliminates display inconsistency regardless of cache state. Independent of all other features -- ship first as safety net. |
| **Improved regex word splitting** | CDCMS concatenates words without separators: `ANANDAMANDIRAMK.T.BAZAR`, `CHEKKIPURATHPO.`. Current regex (`re.sub(r"(\d)([A-Z])", ...)`) only splits digit-to-uppercase transitions. Adding lowercase-to-uppercase splitting covers the most common concatenation pattern. | LOW | Add `re.sub(r"([a-z])([A-Z])", r"\1 \2", addr)` and reorder cleaning steps so splitting runs before abbreviation expansion. ~20 lines changed, ~30 lines new tests. Safe, independent regex change. |
| **Geocode zone validation (30km check)** | Google geocodes garbled addresses to locations 40+ km away (Kozhikode city center, random places in Karnataka). Without validation, drivers follow routes to completely wrong locations. The delivery zone is a 30km radius around the Vatakara depot -- any result outside this boundary is definitively wrong. | MEDIUM | New `GeocodeValidator` class using haversine distance (~10 lines of pure Python math, no dependencies). The 30km threshold is generous (actual delivery zone is ~15-20km). This is standard practice in logistics geocoding: Geocodio, Route4Me, and LogiNext all validate results against service area boundaries. |
| **Fallback chain (area retry -> centroid)** | When zone validation rejects a geocode result, the system needs a recovery path instead of dropping the order. Three-tier chain: (1) retry geocoding with AreaName only, (2) use area centroid from place dictionary, (3) keep original result but flag as approximate. | MEDIUM | Integrates into `CachedGeocoder.geocode()`. Area retry costs one extra Google API call (negligible at 40-50 orders/day). Centroid fallback uses static dictionary coordinates -- no API call. Final fallback ensures no order is silently dropped. Depends on zone validation and place name dictionary. |
| **geocode_confidence + location_approximate in API response** | Without confidence data in the API response, neither the driver app nor the dashboard can distinguish between accurate and approximate locations. The `Location` model already has `geocode_confidence` -- this feature just exposes it in the stop JSON. | LOW | Add two fields to stop JSON in `main.py`: `geocode_confidence` (float 0-1, already on the model) and `location_approximate` (boolean, true when confidence < 0.5). ~5 lines per endpoint. Backward compatible -- new fields only. |
| **"Approx. location" badge in Driver PWA** | Drivers need to know when a stop's location is approximate so they can call the customer for directions. Without a visual indicator, approximate locations silently fail -- the driver arrives at the wrong place. | LOW | DaisyUI `tw:badge-warning` on hero card, orange dot on compact cards. ~15 lines HTML/CSS in `index.html`. Informational only -- Navigate button still works. The self-healing loop already exists: when drivers mark "Done" with GPS, `save_driver_verified()` caches correct coordinates for next time. Depends on API confidence fields. |

### Differentiators (Competitive Advantage)

Features that go beyond baseline correctness. These solve the hardest cases that regex alone cannot handle.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Dictionary-powered word splitting** | Regex alone cannot split `MUTTUNGALPOBALAVADI` into `MUTTUNGAL` + `PO` + `BALAVADI` because there is no case transition or separator. A local dictionary of ~200-300 place names within 30km enables splitting at known word boundaries. This is the key differentiator over naive preprocessing -- it handles the hardest CDCMS concatenation patterns that cause wrong geocoding. | MEDIUM | New `AddressSplitter` class (~150 lines). Longest-match-first algorithm prevents false splits. Fuzzy matching via RapidFuzz (threshold 85%) handles transliteration variants. Passthrough for unknown text -- if no dictionary match, text goes to geocoder unchanged. Graceful degradation if dictionary file is missing. |
| **Place name dictionary from OSM + India Post** | Static JSON dictionary of hamlet, village, town, and post office names within 30km of depot. Built from two free, public APIs (OSM Overpass + India Post PostalPinCode). No API key needed, no authentication, no personal data sent. Committed to repo -- runtime never calls these APIs. | MEDIUM | Build script (~150 lines): queries OSM for place nodes within 30km, India Post for post offices by PIN code (673101-673110), deduplicates with fuzzy matching, outputs `data/place_names_vatakara.json`. Each entry has name, aliases, type, lat/lon, source. Dictionary also provides centroid coordinates for the geocode fallback chain. |
| **Self-healing geocode cache (amplified)** | Already built: `save_driver_verified()` writes confidence=0.95 coordinates when drivers mark deliveries as done. The new confidence system amplifies this: an address starting at confidence=0.3 (centroid fallback) gets promoted to 0.95 after one successful delivery. Over weeks, the system learns correct locations for its delivery zone without any manual intervention. | ALREADY EXISTS | No new code. Documented here because the new confidence pipeline gives existing self-healing much more leverage -- approximate locations are now visible to drivers, who naturally correct them through normal delivery workflow. |
| **Integration testing with accuracy metrics** | After implementing, measure on real CDCMS data: % within 30km (target >90%), % needing centroid fallback (target <10%), dictionary coverage (target >95% of area names). These metrics define the upgrade trigger to Approach B (NER model). | LOW | Test script + documentation of metrics. Not user-facing but critical for engineering confidence. Establishes measurable go/no-go criteria for the NER upgrade path. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem useful but would cause harm for this specific system.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| **NER model as default path** | ML-powered Named Entity Recognition (IndicBERT) could parse any Indian address into structured components. Seems like the "proper" solution. | Adds ~400MB dependency (transformers + torch), 50ms/address vs <1ms dictionary lookup, requires model download, and 95% of CDCMS addresses reference the same ~200 places. Overkill for a 30km zone. | Dictionary + regex first (Approach A). NER designed as conditional Approach B, triggered only if measurable accuracy criteria are not met after testing. |
| **Fuzzy address matching across full addresses** | Match incoming addresses against cached ones using Levenshtein distance. Saves API calls. | False positives assign wrong coordinates. "VALLIKKADU EAST" and "VALLIKKADU WEST" differ by one word but are 3km apart. The API cost savings (~$0.25/day) do not justify the accuracy risk. | Already in PROJECT.md Out of Scope. PostGIS cache with `normalize_address()` handles exact matches. RapidFuzz used only within dictionary splitter on individual place name tokens, not full addresses. |
| **Multiple geocoding provider fallback** | If Google fails, try Bing, Nominatim, or OLA Maps. More providers = more coverage. | Mixing providers creates coordinate inconsistency -- Google and Nominatim geocode the same address to points 200m apart, producing suboptimal route sequences. Complicates caching and confidence comparison. | Single provider (Google) with zone validation + area centroid fallback. Centroid guarantees a result within the delivery zone even when Google fails entirely. |
| **Real-time address autocomplete** | As the office employee types, suggest completions from the dictionary. Prevent typos before geocoding. | CDCMS addresses come from a CSV file export, not manual typing. The office employee uploads a file -- they never type individual addresses. Autocomplete solves a problem that does not exist in this workflow. | Dictionary used server-side during preprocessing. If manual entry is ever needed, autocomplete can be added then. |
| **Auto-correcting addresses** | Fix spelling errors in CDCMS addresses before geocoding. | CDCMS text is ALL-CAPS transliterated Malayalam. Standard spell checkers flag every word. Kerala places have legitimate variant spellings (Vadakara/Vatakara). Auto-correction would introduce errors. | RapidFuzz matching within the dictionary handles transliteration variants without modifying the original text. The dictionary acts as a domain-specific "spell checker" -- it matches, not replaces. |
| **Reverse geocoding for telemetry** | Convert driver GPS pings to street addresses. | $0.005/call, 13 vehicles every 30s for 8 hours = ~12,480 calls/day = ~$62/day. Already in PROJECT.md Out of Scope. | Raw GPS coordinates for telemetry. Forward-geocode only during CSV upload (40-50 calls/day). |

## Feature Dependencies

```
[address_display source fix]  (standalone, no deps)
    independent -- ship first as safety net

[Improved regex splitting]  (standalone, no deps)
    independent -- safe to ship alongside address_display fix

[Place name dictionary build]
    └──enables──> [Dictionary-powered word splitting]
                      └──integrates into──> [clean_cdcms_address() pipeline]

[Geocode zone validation (haversine + 30km check)]
    └──enables──> [Fallback chain (area retry -> centroid)]
                      └──requires──> [Place name dictionary] (for centroid coordinates)

[Fallback chain]
    └──populates──> [geocode_confidence values in Location model]
                         └──exposed by──> [API confidence fields]
                                               └──consumed by──> [Driver PWA "Approx." badge]

[Integration testing + accuracy metrics]
    └──requires──> ALL of the above
    └──gates──> [Approach B: NER model] (future, conditional)
```

### Dependency Notes

- **address_display fix is independent:** One-line change in `vroom_adapter.py:278`. Can and should ship first. Even if every other feature fails, this fix eliminates the display inconsistency bug.
- **Regex improvements are independent:** Safe regex change in `cdcms_preprocessor.py` with no external dependencies. Can ship alongside the address_display fix in the same phase.
- **Dictionary must exist before splitter:** `AddressSplitter` loads `data/place_names_vatakara.json` at init. Build script must run first. If the dictionary file is missing, the splitter gracefully degrades to None and the pipeline falls back to regex-only behavior.
- **Centroid fallback requires dictionary:** When zone validation rejects a geocode and area-name retry also fails, the system looks up area centroid coordinates from the dictionary. Without the dictionary, the fallback chain degrades to "flag as unvalidated" instead of providing approximate coordinates.
- **API fields require meaningful confidence values:** Exposing `geocode_confidence` is trivial (field already exists on `Location` model), but the values are only meaningful after zone validation and fallback chain populate them. Without validation, all results show 0.40-0.95 based solely on Google's `location_type`, which does not reflect delivery zone accuracy.
- **Driver badge requires API fields:** The PWA reads `location_approximate` from the stop JSON. The API must expose this field before the badge can render.
- **NER upgrade is gated by metrics:** Approach B is explicitly NOT a dependency. It is a conditional future feature triggered only if Phase 5 metrics show >10% validation failures or >5% centroid fallback rate.

## MVP Definition

This is a subsequent milestone (v2.2) on an existing product (v2.0 shipped). The framing below reflects what must ship to fix the "wrong route locations" bug.

### Launch With (v2.2 Core)

All of these are required to fix the bug. Shipping a subset leaves drivers going to wrong locations.

- [ ] address_display source fix -- eliminates display inconsistency (1 line)
- [ ] Improved regex splitting -- handles common concatenation patterns (~20 lines)
- [ ] Place name dictionary build -- enables dictionary-powered splitting
- [ ] Dictionary-powered word splitting -- the core preprocessing improvement
- [ ] Geocode zone validation -- catches results outside delivery zone
- [ ] Fallback chain -- ensures every address gets a usable location
- [ ] API confidence fields -- exposes quality signal to consumers
- [ ] Driver PWA "Approx. location" badge -- informs drivers about quality

### Add After Validation (v2.2.x)

Features to add once the pipeline has run with real delivery data for at least one week.

- [ ] Accuracy metrics dashboard view -- trigger: operators asking "how is the new pipeline performing?"
- [ ] Dictionary auto-refresh script -- trigger: new settlements appear that the dictionary misses
- [ ] Dictionary gap reporting -- log which address tokens had no dictionary match to identify coverage holes

### Future Consideration (v3+, Conditional)

Features to defer until measurable evidence justifies the investment.

- [ ] Approach B: NER model -- defer until accuracy metrics show >10% validation failures. May never be needed.
- [ ] Dashboard geocode quality report -- per-upload breakdown of fallback usage and driver corrections over time.
- [ ] Driver location pin correction -- drag-to-correct in the PWA map. Lower priority because `save_driver_verified()` already handles this passively.

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| address_display source fix | HIGH | LOW | P1 |
| Improved regex splitting | HIGH | LOW | P1 |
| Cleaning step reorder | MEDIUM | LOW | P1 |
| Place name dictionary build script | HIGH | MEDIUM | P1 |
| Dictionary-powered word splitting | HIGH | MEDIUM | P1 |
| Geocode zone validation | HIGH | MEDIUM | P1 |
| Fallback chain | HIGH | MEDIUM | P1 |
| API confidence fields | MEDIUM | LOW | P1 |
| Driver PWA badge | MEDIUM | LOW | P1 |
| Integration testing + metrics | MEDIUM | LOW | P1 |
| NER model (Approach B) | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for v2.2 launch (fixes the bug)
- P2: Should have, add after real-world validation
- P3: Nice to have, conditional on metrics

## Existing Infrastructure Leveraged

These features build on already-shipped capabilities, keeping implementation cost low.

| Existing Component | How New Features Use It |
|--------------------|------------------------|
| `Location.geocode_confidence` field | Already on the Pydantic model. Zone validation populates it; API exposes it; PWA reads it. No model change needed. |
| `CachedGeocoder.save_driver_verified()` | Already wired to delivery status endpoint. Self-healing cache corrects approximate locations over time without new code. |
| `clean_cdcms_address()` pipeline | Dictionary splitter inserts as Stage 2 between existing cleanup (Stage 1) and title case (Stage 3). Existing stages unchanged. |
| `normalize_address()` for cache keys | Orthogonal to preprocessing. No changes needed. |
| Google `location_type` -> confidence mapping | Already in `google_adapter.py` (lines 111-118). Zone validation adjusts these values: multiply by 0.7 for area retry, set to 0.3 for centroid fallback. |
| `address_raw` on Order model | Already stored separately from `location.address_text`. Source fix just changes which field populates `address_display`. |
| PostGIS `geocode_cache` table | No schema migration needed. New confidence values flow through existing columns. |
| DaisyUI component library | PWA badge uses existing `tw:badge-warning tw:badge-sm` classes. No new CSS dependency. |
| Haversine formula | Standard math (acos, sin, cos, radians). ~10 lines of stdlib Python. No external dependency. |

## Competitor Feature Analysis

| Feature | Route4Me | LogiNext | Veho | Our Approach |
|---------|----------|----------|------|--------------|
| Address preprocessing | US-focused USPS standardization | API-based address verification | Customer self-service pin correction | Dictionary-powered splitting tuned for CDCMS Kerala addresses |
| Geocode validation | Service area geofence check | Zone-based validation with confidence | Delivery zone verification | 30km haversine radius around depot |
| Confidence scores | Match codes (A-F grade) | Internal scoring | Binary valid/invalid | 0-1 float with threshold at 0.5 for "approximate" |
| Fallback strategy | Re-geocode with partial address | Multiple provider fallback | Customer pin correction | Area retry -> area centroid -> flag as approximate |
| Driver notification | Address quality indicators | Delivery risk flags | Customer-corrected pins shown | "Approx. location" badge with orange warning styling |
| Self-correction | Manual address editing | Support ticket workflow | Customer moves pin | Automatic GPS caching when driver marks delivery done |

## Sources

- [Google Maps Geocoding API: Request and Response](https://developers.google.com/maps/documentation/geocoding/requests-geocoding) -- location_type values and confidence mapping
- [Google Maps Platform: Address Validation Architecture](https://developers.google.com/maps/architecture/geocoding-address-validation) -- geocoding validation patterns
- [Geocodio: Accuracy Types and Scores](https://www.geocod.io/guides/accuracy-types-scores/) -- confidence score tiers and fallback strategies
- [Radar: Complete Guide to Geocoding APIs](https://radar.com/blog/geocoding-apis) -- logistics geocoding caching and fallback
- [Route4Me: Geocoding Guide](https://support.route4me.com/geocoding-guide-address-verification/) -- delivery-specific geocode validation
- [Kestrel Insights: Geofencing for Last-Mile Delivery](https://www.kestrelinsights.com/blog/how-accurate-precise-geofencing-optimizes-last-mile-delivery) -- zone-based validation in logistics
- [LogiNext: Geocoding Intelligence in Logistics](https://www.loginextsolutions.com/blog/geocoding-intelligence-that-reduces-exceptions-before-they-happen/) -- confidence scores preventing delivery exceptions
- [Veho: Self-Serve Customer Geocode Corrections](https://www.shipveho.com/blog/improving-delivery-accuracy-with-self-serve-customer-geocode-corrections) -- self-healing geocode patterns
- [RapidFuzz GitHub](https://github.com/rapidfuzz/RapidFuzz) -- fuzzy string matching for place name dictionary
- [PostalPinCode API](http://www.postalpincode.in/Api-Details) -- free India Post API for post office names by PIN code
- [OSM Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API) -- free API for place name extraction
- [GeoIndia: Seq2Seq Geocoding for Indian Addresses (EMNLP 2024)](https://aclanthology.org/2024.emnlp-industry.29/) -- Indian address geocoding challenges
- [libpostal](https://github.com/openvenues/libpostal) -- reference for statistical NLP address parsing (not recommended for this use case due to deployment weight)
- Design spec: `docs/superpowers/specs/2026-03-10-address-preprocessing-design.md`

---
*Feature research for: Address preprocessing pipeline, geocode validation, and location confidence (v2.2)*
*Researched: 2026-03-10*
