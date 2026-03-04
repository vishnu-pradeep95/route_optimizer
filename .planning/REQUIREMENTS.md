# Requirements: Kerala LPG Delivery Route Optimizer

**Defined:** 2026-03-03
**Core Value:** Every delivery address uploaded must appear on the map and be assigned to an optimized route — no silent drops, no missing stops.

## v1.2 Requirements

Requirements for tech debt cleanup. Each maps to roadmap phases.

### Driver PWA Safety

- [ ] **PWA-01**: Call Office FAB reads phone number from API config endpoint — no hardcoded placeholder
- [ ] **PWA-02**: GPS `watchPosition` watch ID saved and cleared on route reset/page unload
- [ ] **PWA-03**: Offline error dialog uses styled `<dialog>` element, not browser `alert()`

### Driver PWA Quality

- [ ] **PWA-04**: PWA manifest uses proper PNG icons (192px, 512px) instead of `data:` SVG emoji
- [ ] **PWA-05**: `tailwind.css` included in service worker `APP_SHELL` pre-cache list
- [ ] **PWA-06**: Production `console.log` calls gated behind debug flag or removed

### API Cleanup

- [ ] **API-01**: Dead `_build_fleet()` function removed
- [ ] **API-02**: Unused imports removed from `main.py`
- [ ] **API-03**: Mid-file `Response as _Response` import consolidated to top
- [ ] **API-04**: Unused `OSRM_URL` removed from `config.py`
- [ ] **API-05**: Stale SHA-256 docstring in `cache.py` corrected
- [ ] **API-06**: PostGIS geometry helper replaces 6× `type: ignore` suppressions
- [ ] **API-07**: `save_driver_verified()` wired into delivery status update endpoint

### Config Consistency

- [ ] **CFG-01**: Depot coordinates served from API config endpoint — frontend reads dynamically, not hardcoded
- [ ] **CFG-02**: Safety multiplier served from API config endpoint — frontend reads dynamically, not hardcoded
- [ ] **CFG-03**: QR sheet duration buffer uses named constant aligned with safety multiplier

### Dashboard Cleanup

- [ ] **DASH-01**: Dead CSS variable aliases removed from `index.css`
- [ ] **DASH-02**: `.text-muted-30` uses design token instead of hardcoded hex
- [ ] **DASH-03**: `RouteDetail` TypeScript interface includes `total_weight_kg` and `total_items`
- [ ] **DASH-04**: `RunHistory.tsx` status cast replaced with proper type narrowing
- [ ] **DASH-05**: LiveMap batch endpoint replaces N+1 route detail fetching

### Data Validation

- [ ] **DATA-01**: Duplicate detection thresholds validated against actual geocode_cache location_type distribution

## Future Requirements

### Deferred from v1.2

- **MAP-01**: Drag-and-drop route adjustment on map — deferred, conflicts with VROOM optimizer philosophy
- **SCALE-01**: Redis-backed rate limiter for multi-instance deployment — not needed at current single-instance scale

## Out of Scope

| Feature | Reason |
|---------|--------|
| Drag-and-drop route reordering | Undermines VROOM optimizer; deferred indefinitely |
| Multi-instance rate limiting | Single API instance is sufficient for 13-vehicle fleet |
| New feature development | v1.2 is exclusively tech debt — no new capabilities |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PWA-01 | — | Pending |
| PWA-02 | — | Pending |
| PWA-03 | — | Pending |
| PWA-04 | — | Pending |
| PWA-05 | — | Pending |
| PWA-06 | — | Pending |
| API-01 | — | Pending |
| API-02 | — | Pending |
| API-03 | — | Pending |
| API-04 | — | Pending |
| API-05 | — | Pending |
| API-06 | — | Pending |
| API-07 | — | Pending |
| CFG-01 | — | Pending |
| CFG-02 | — | Pending |
| CFG-03 | — | Pending |
| DASH-01 | — | Pending |
| DASH-02 | — | Pending |
| DASH-03 | — | Pending |
| DASH-04 | — | Pending |
| DASH-05 | — | Pending |
| DATA-01 | — | Pending |

**Coverage:**
- v1.2 requirements: 22 total
- Mapped to phases: 0
- Unmapped: 22 ⚠️

---
*Requirements defined: 2026-03-03*
*Last updated: 2026-03-03 after initial definition*
