# Requirements: Kerala LPG Delivery Route Optimizer

**Defined:** 2026-03-10
**Core Value:** Every delivery address uploaded must appear on the map and be assigned to an optimized route -- no silent drops, no missing stops.

## v2.2 Requirements

Requirements for v2.2 Address Preprocessing Pipeline. Each maps to roadmap phases.

### Address Preprocessing

- [x] **ADDR-01**: Driver app and navigation links always show the cleaned original address (address_raw), never Google's formatted_address
- [x] **ADDR-02**: Regex splits lowercase-to-uppercase transitions in concatenated CDCMS text (e.g., `ANANDAMANDIRAMK` -> `ANANDAMANDIRAM K`)
- [x] **ADDR-03**: Abbreviation expansion (NR, PO) runs after word splitting so patterns are detected at word boundaries
- [x] **ADDR-04**: Place name dictionary (~285 entries) built from OSM Overpass + India Post APIs and committed to repo
- [x] **ADDR-05**: Dictionary-aware word splitter splits concatenated text at known place name boundaries (e.g., `MUTTUNGALPOBALAVADI` -> `MUTTUNGAL P.O. BALAVADI`)
- [x] **ADDR-06**: Fuzzy matching (RapidFuzz) handles transliteration variants of Kerala place names with length-dependent thresholds

### Geocode Validation

- [x] **GVAL-01**: Geocoded coordinates validated against 30km radius from Vatakara depot via haversine distance check
- [x] **GVAL-02**: Out-of-zone geocode results trigger automatic retry with CDCMS area name only
- [x] **GVAL-03**: Failed area-name retry falls back to area centroid coordinates from place name dictionary
- [x] **GVAL-04**: Confidence score adjusted based on validation outcome (1.0 direct hit, 0.7 area retry, 0.3 centroid fallback)

### API & Driver UI

- [ ] **APUI-01**: API route response includes geocode_confidence field for each delivery stop
- [ ] **APUI-02**: API route response includes location_approximate flag (true when confidence < 0.5)
- [ ] **APUI-03**: Driver PWA hero card shows "Approx. location" warning badge for approximate stops
- [ ] **APUI-04**: Driver PWA compact cards show orange dot indicator for approximate stops

### Testing & Metrics

- [ ] **TEST-01**: Full pipeline tested with sample CDCMS CSV -- all addresses geocode within 30km zone or are flagged approximate
- [ ] **TEST-02**: Original "HDFC ERGO" bug verified fixed (wrong-location address handled correctly by validation)
- [ ] **TEST-03**: Accuracy metrics measured and documented: geocode success rate (>90%), fallback rate (<10%), dictionary coverage (>80% of area names)
- [ ] **TEST-04**: Approach B (NER model) upgrade criteria documented with measurable thresholds

## v2.1 Requirements (Parallel -- Main Branch)

v2.1 Licensing & Distribution Security is being executed in parallel on the main branch.
See main branch `.planning/REQUIREMENTS.md` for full v2.1 tracking.

### Fingerprinting (Complete)

- [x] **FPR-01**: Machine fingerprint uses /etc/machine-id + CPU model
- [x] **FPR-02**: Docker Compose mounts /etc/machine-id read-only
- [x] **FPR-03**: get_machine_id.py updated for new fingerprint signals

### Remaining (In Progress on Main)

- ENF-01 through ENF-04: Enforcement hardening
- RTP-01 through RTP-03: Runtime protection
- LIC-01 through LIC-03: License management
- BLD-01 through BLD-03: Build pipeline
- DOC-01 through DOC-03: Testing & documentation

## Future Requirements

Deferred to future release. Tracked but not in current roadmap.

### Address Intelligence

- **AINT-01**: NER model (Approach B) for addresses not matched by dictionary (conditional on >10% validation failures)
- **AINT-02**: Circuit breaker for bulk geocoding API failures with batch-level warning
- **AINT-03**: Batch-level "all approximate" banner in Driver PWA when API key is invalid

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| NER model implementation | Conditional on accuracy metrics -- documented as upgrade path only |
| Multiple geocoding providers | Mixing providers creates coordinate inconsistency |
| Fuzzy address matching for cache keys | False positives assign wrong cached coordinates |
| Real-time dictionary updates | Dictionary is static, refreshed manually via build script |
| Reverse geocoding for validation | $45K/year at scale, haversine check is sufficient |
| Malayalam script processing | CDCMS data is romanized; dictionary stores Malayalam as metadata only |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| ADDR-01 | Phase 11 | Complete |
| ADDR-02 | Phase 11 | Complete |
| ADDR-03 | Phase 11 | Complete |
| ADDR-04 | Phase 12 | Complete |
| ADDR-05 | Phase 12 | Complete |
| ADDR-06 | Phase 12 | Complete |
| GVAL-01 | Phase 13 | Complete |
| GVAL-02 | Phase 13 | Complete |
| GVAL-03 | Phase 13 | Complete |
| GVAL-04 | Phase 13 | Complete |
| APUI-01 | Phase 14 | Pending |
| APUI-02 | Phase 14 | Pending |
| APUI-03 | Phase 14 | Pending |
| APUI-04 | Phase 14 | Pending |
| TEST-01 | Phase 15 | Pending |
| TEST-02 | Phase 15 | Pending |
| TEST-03 | Phase 15 | Pending |
| TEST-04 | Phase 15 | Pending |

**Coverage:**
- v2.2 requirements: 18 total
- Mapped to phases: 18
- Unmapped: 0

---
*Requirements defined: 2026-03-10*
*Last updated: 2026-03-10 after roadmap creation (all 18 requirements mapped to Phases 11-15)*
