# Requirements: Kerala LPG Delivery Route Optimizer

**Defined:** 2026-03-08
**Core Value:** Every delivery address uploaded must appear on the map and be assigned to an optimized route — no silent drops, no missing stops.

## v1.4 Requirements

Requirements for Ship-Ready QA milestone. Each maps to roadmap phases.

### Testing

- [ ] **TEST-01**: Playwright E2E tests verify all API endpoints return expected status codes against running Docker stack
- [ ] **TEST-02**: Playwright E2E tests cover full Driver PWA flow: upload CSV → vehicle select → route view → mark done/fail → all-done banner
- [ ] **TEST-03**: Playwright E2E tests verify Dashboard: route cards render, QR sheet generates, map loads after upload
- [ ] **TEST-04**: Playwright E2E tests verify license validation: expired/missing/invalid keys return 503
- [ ] **TEST-05**: All existing 420 pytest unit tests pass in CI

### CI/CD

- [ ] **CICD-01**: GitHub Actions pipeline passes (fix any failing jobs)
- [ ] **CICD-02**: Playwright E2E job added to CI (Chromium-only, runs on push to main)
- [ ] **CICD-03**: Playwright HTML report uploaded as CI artifact on failure
- [ ] **CICD-04**: CI status badge added to README.md

### Operations

- [ ] **OPS-01**: `scripts/stop.sh` gracefully stops all services (docker compose stop, not down -v)
- [ ] **OPS-02**: `stop.sh --gc` cleans dangling images, orphan containers, and truncates container logs
- [ ] **OPS-03**: Clean install from `build-dist.sh` tarball verified in fresh environment

### Documentation

- [ ] **DOCS-01**: Distribution workflow documented: build tarball → generate license → deliver to customer → verify install
- [ ] **DOCS-02**: License lifecycle documented: generate → deliver → activate → monitor grace → renew → troubleshoot 503
- [ ] **DOCS-03**: Production vs development environment comparison documented
- [ ] **DOCS-04**: Google API key troubleshooting guide (Cloud Console setup, key validation, common errors)
- [ ] **DOCS-05**: Third-party license/attribution audit documented (OSM, OSRM, VROOM, Leaflet, Google Maps terms)

## Future Requirements

### Deferred from v1.4

- **VIS-01**: Playwright visual regression tests (screenshot comparison for CSS regressions)
- **OFFLINE-01**: Offline PWA E2E test (service worker caching verification)
- **PERF-01**: Performance budgets in E2E tests (assert response times < thresholds)
- **A11Y-01**: Automated accessibility testing (axe-core integration)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Multi-browser E2E testing | Drivers use Chrome on Android, office uses Chrome on Windows — Firefox/Safari adds 3x CI time for zero coverage |
| Performance/load testing | Single-laptop, 13-vehicle system processing ~50 orders/day — load testing adds no value at this scale |
| Docker image size optimization | Customer laptop has 256+ GB SSD — image size is not a deployment blocker |
| Automated dependency updates | Solo-dev project with pinned dependencies — automated updates risk breaking the stack |
| Test coverage metrics | 420 tests exist; chasing coverage percentages doesn't find bugs — E2E flow coverage matters more |
| Canary/blue-green deployment | Single-laptop deployment with no staging environment — "stop, update, start" is sufficient |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| TEST-01 | TBD | Pending |
| TEST-02 | TBD | Pending |
| TEST-03 | TBD | Pending |
| TEST-04 | TBD | Pending |
| TEST-05 | TBD | Pending |
| CICD-01 | TBD | Pending |
| CICD-02 | TBD | Pending |
| CICD-03 | TBD | Pending |
| CICD-04 | TBD | Pending |
| OPS-01 | TBD | Pending |
| OPS-02 | TBD | Pending |
| OPS-03 | TBD | Pending |
| DOCS-01 | TBD | Pending |
| DOCS-02 | TBD | Pending |
| DOCS-03 | TBD | Pending |
| DOCS-04 | TBD | Pending |
| DOCS-05 | TBD | Pending |

**Coverage:**
- v1.4 requirements: 17 total
- Mapped to phases: 0
- Unmapped: 17 ⚠️

---
*Requirements defined: 2026-03-08*
*Last updated: 2026-03-08 after initial definition*
