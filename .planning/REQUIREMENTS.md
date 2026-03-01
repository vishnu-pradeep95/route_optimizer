# Requirements: Kerala LPG Delivery Route Optimizer

**Defined:** 2026-03-01
**Core Value:** Every delivery address uploaded must appear on the map and be assigned to an optimized route — no silent drops, no missing stops.

## v1 Requirements

Requirements for this milestone. Each maps to roadmap phases.

### Data Integrity

- [ ] **DATA-01**: User sees which orders failed geocoding, with reason per row (not silently dropped)
- [ ] **DATA-02**: Upload response includes import summary: N succeeded, M failed, with downloadable failure report
- [ ] **DATA-03**: Partially-geocoded batches still optimize the successful orders (not all-or-nothing)
- [ ] **DATA-04**: Depot coordinates from config.py (Vatakara 11.52°N) flow correctly through entire pipeline — audit and fix any leaks
- [ ] **DATA-05**: CSV import validation shows row-level errors (missing fields, bad formats) before geocoding starts

### UI/UX — Dashboard

- [ ] **DASH-01**: Install Tailwind 4 + DaisyUI 5 with collision-safe prefix (`tw`) in Vite pipeline
- [ ] **DASH-02**: Define logistics SaaS theme (clean colors, professional typography, consistent spacing)
- [ ] **DASH-03**: Migrate Upload/Routes page to Tailwind/DaisyUI — file upload, progress, results table
- [ ] **DASH-04**: Migrate Live Map page — clean map container, vehicle sidebar, status indicators
- [ ] **DASH-05**: Migrate Fleet Management page — vehicle cards/table, driver info, capacity indicators
- [ ] **DASH-06**: Migrate Run History page — sortable run table, expandable route details
- [ ] **DASH-07**: Empty states for all pages (no routes yet, no vehicles, no history)
- [ ] **DASH-08**: Toast notification system for success, error, and warning feedback

### UI/UX — Driver PWA

- [ ] **PWA-01**: Pre-compiled Tailwind CSS via standalone CLI (no CDN, offline-capable)
- [ ] **PWA-02**: Professional mobile layout — clean route list, map, delivery cards
- [ ] **PWA-03**: Service worker cache updated for new CSS assets
- [ ] **PWA-04**: Toast/alert system for delivery status feedback on mobile

### Security

- [ ] **SEC-01**: HTTP security headers via middleware — CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy
- [ ] **SEC-02**: CORS hardened — no wildcard origins, explicit whitelist from env var
- [ ] **SEC-03**: API docs (/docs, /redoc) gated behind environment check — hidden in production
- [ ] **SEC-04**: Input validation audit — all file upload endpoints check file type, size, content
- [ ] **SEC-05**: Replace deprecated security libraries if present (python-jose → PyJWT, passlib → pwdlib)
- [ ] **SEC-06**: Rate limiter state isolated in tests — no cross-test bleed

### Code Quality

- [ ] **QUAL-01**: Dead code removal — identify and remove unused functions, AI-generated slop using vulture + ruff
- [ ] **QUAL-02**: main.py refactored — break 1760-line file into focused modules (routes, upload, telemetry, auth)
- [ ] **QUAL-03**: Remove hardcoded placeholder driver names — read from config or database
- [ ] **QUAL-04**: Thread-safety fix — asyncio.Lock for geocoder singleton initialization

### Testing

- [ ] **TEST-01**: Fix E2E test coordinates — use Vatakara (11.52°N) instead of Kochi (9.97°N)
- [ ] **TEST-02**: Add hypothesis property-based tests for CSV parsing edge cases
- [ ] **TEST-03**: Add factory_boy factories for Order, Vehicle, Route test data
- [ ] **TEST-04**: Add respx mocks for Google Geocoding, VROOM, OSRM external API calls
- [ ] **TEST-05**: pytest-cov coverage gate — establish baseline and prevent regression
- [ ] **TEST-06**: Async test configuration — set asyncio_mode=auto in pytest.ini

### Documentation

- [ ] **DOCS-01**: README rewrite — clear project description, one-command Docker setup, screenshots
- [ ] **DOCS-02**: Environment variable guide — all vars documented with defaults and examples
- [ ] **DOCS-03**: Troubleshooting section — OSRM startup order, common Docker issues, geocoding API setup
- [ ] **DOCS-04**: Developer guide — project structure, how to run tests, how to add new features

## v2 Requirements

Deferred to future milestone. Tracked but not in current roadmap.

### Advanced UI

- **ADV-01**: Dark mode toggle for dashboard
- **ADV-02**: Route drag-and-drop reordering on map
- **ADV-03**: Multi-file CSV upload in single batch
- **ADV-04**: Real-time vehicle tracking on live map

### Advanced Features

- **ADV-05**: Customer-facing delivery tracking page
- **ADV-06**: Push notifications for drivers
- **ADV-07**: AI-powered address suggestion for failed geocoding
- **ADV-08**: Automated re-geocoding queue for failed addresses

## Out of Scope

| Feature | Reason |
|---------|--------|
| Mobile native app | PWA sufficient for driver use case |
| Real-time chat/messaging | Not needed for delivery workflow |
| Multi-tenant/multi-region | Vatakara-only for now |
| Payment processing | Handled outside this system |
| Customer-facing tracking | Drivers and office staff only |
| Leaflet 2.0 upgrade | Alpha-only, plugins not ported, would break existing map functionality |
| React component libraries (MUI, Ant) | DaisyUI chosen for simplicity and no-build PWA compatibility |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DATA-01 | Phase 3 | Pending |
| DATA-02 | Phase 3 | Pending |
| DATA-03 | Phase 3 | Pending |
| DATA-04 | Phase 3 | Pending |
| DATA-05 | Phase 3 | Pending |
| DASH-01 | Phase 1 | Pending |
| DASH-02 | Phase 1 | Pending |
| DASH-03 | Phase 4 | Pending |
| DASH-04 | Phase 4 | Pending |
| DASH-05 | Phase 4 | Pending |
| DASH-06 | Phase 4 | Pending |
| DASH-07 | Phase 4 | Pending |
| DASH-08 | Phase 4 | Pending |
| PWA-01 | Phase 1 | Pending |
| PWA-02 | Phase 5 | Pending |
| PWA-03 | Phase 5 | Pending |
| PWA-04 | Phase 5 | Pending |
| SEC-01 | Phase 2 | Pending |
| SEC-02 | Phase 2 | Pending |
| SEC-03 | Phase 2 | Pending |
| SEC-04 | Phase 2 | Pending |
| SEC-05 | Phase 2 | Pending |
| SEC-06 | Phase 2 | Pending |
| QUAL-01 | Phase 6 | Pending |
| QUAL-02 | Phase 6 | Pending |
| QUAL-03 | Phase 6 | Pending |
| QUAL-04 | Phase 6 | Pending |
| TEST-01 | Phase 1 | Pending |
| TEST-02 | Phase 6 | Pending |
| TEST-03 | Phase 6 | Pending |
| TEST-04 | Phase 6 | Pending |
| TEST-05 | Phase 6 | Pending |
| TEST-06 | Phase 1 | Pending |
| DOCS-01 | Phase 6 | Pending |
| DOCS-02 | Phase 6 | Pending |
| DOCS-03 | Phase 6 | Pending |
| DOCS-04 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 37 total (note: initial count of 31 was incorrect — actual count is 37)
- Mapped to phases: 37
- Unmapped: 0

---
*Requirements defined: 2026-03-01*
*Last updated: 2026-03-01 — traceability populated by roadmapper*
