# Requirements: Kerala LPG Delivery Route Optimizer

**Defined:** 2026-03-03
**Core Value:** Every delivery address uploaded must appear on the map and be assigned to an optimized route -- no silent drops, no missing stops.

## v1.2 Requirements

Requirements for tech debt cleanup. Each maps to roadmap phases.

### Driver PWA Safety

- [x] **PWA-01**: Call Office FAB reads phone number from API config endpoint -- no hardcoded placeholder
- [x] **PWA-02**: GPS `watchPosition` watch ID saved and cleared on route reset/page unload
- [x] **PWA-03**: Offline error dialog uses styled `<dialog>` element, not browser `alert()`

### Driver PWA Quality

- [x] **PWA-04**: PWA manifest uses proper PNG icons (192px, 512px) instead of `data:` SVG emoji
- [x] **PWA-05**: `tailwind.css` included in service worker `APP_SHELL` pre-cache list
- [x] **PWA-06**: Production `console.log` calls gated behind debug flag or removed

### API Cleanup

- [x] **API-01**: Dead `_build_fleet()` function removed
- [x] **API-02**: Unused imports removed from `main.py`
- [x] **API-03**: Mid-file `Response as _Response` import consolidated to top
- [x] **API-04**: Unused `OSRM_URL` removed from `config.py`
- [x] **API-05**: Stale SHA-256 docstring in `cache.py` corrected
- [x] **API-06**: PostGIS geometry helper replaces 6x `type: ignore` suppressions
- [x] **API-07**: `save_driver_verified()` wired into delivery status update endpoint

### Config Consistency

- [x] **CFG-01**: Depot coordinates served from API config endpoint -- frontend reads dynamically, not hardcoded
- [x] **CFG-02**: Safety multiplier served from API config endpoint -- frontend reads dynamically, not hardcoded
- [x] **CFG-03**: QR sheet duration buffer uses named constant aligned with safety multiplier

### Dashboard Cleanup

- [x] **DASH-01**: Dead CSS variable aliases removed from `index.css`
- [x] **DASH-02**: `.text-muted-30` uses design token instead of hardcoded hex
- [x] **DASH-03**: `RouteDetail` TypeScript interface includes `total_weight_kg` and `total_items`
- [x] **DASH-04**: `RunHistory.tsx` status cast replaced with proper type narrowing
- [x] **DASH-05**: LiveMap batch endpoint replaces N+1 route detail fetching

### Data Validation

- [ ] **DATA-01**: Duplicate detection thresholds validated against actual geocode_cache location_type distribution

## Future Requirements

### Deferred from v1.2

- **MAP-01**: Drag-and-drop route adjustment on map -- deferred, conflicts with VROOM optimizer philosophy
- **SCALE-01**: Redis-backed rate limiter for multi-instance deployment -- not needed at current single-instance scale

## Out of Scope

| Feature | Reason |
|---------|--------|
| Drag-and-drop route reordering | Undermines VROOM optimizer; deferred indefinitely |
| Multi-instance rate limiting | Single API instance is sufficient for 13-vehicle fleet |
| New feature development | v1.2 is exclusively tech debt -- no new capabilities |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PWA-01 | Phase 10 | Complete |
| PWA-02 | Phase 10 | Complete |
| PWA-03 | Phase 10 | Complete |
| PWA-04 | Phase 10 | Complete |
| PWA-05 | Phase 10 | Complete |
| PWA-06 | Phase 10 | Complete |
| API-01 | Phase 8 | Complete |
| API-02 | Phase 8 | Complete |
| API-03 | Phase 8 | Complete |
| API-04 | Phase 8 | Complete |
| API-05 | Phase 8 | Complete |
| API-06 | Phase 8 | Complete |
| API-07 | Phase 12 | Complete |
| CFG-01 | Phase 9 | Complete |
| CFG-02 | Phase 9 | Complete |
| CFG-03 | Phase 9 | Complete |
| DASH-01 | Phase 11 | Complete |
| DASH-02 | Phase 11 | Complete |
| DASH-03 | Phase 11 | Complete |
| DASH-04 | Phase 11 | Complete |
| DASH-05 | Phase 11 | Complete |
| DATA-01 | Phase 12 | Pending |

**Coverage:**
- v1.2 requirements: 22 total
- Mapped to phases: 22
- Unmapped: 0

---
*Requirements defined: 2026-03-03*
*Last updated: 2026-03-04 after Phase 9 completion*
