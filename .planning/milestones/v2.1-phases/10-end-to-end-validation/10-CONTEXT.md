# Phase 10: End-to-End Validation - Context

**Gathered:** 2026-03-11
**Status:** Ready for planning

<domain>
## Phase Boundary

Test the complete v2.1 security pipeline end-to-end and update all documentation for v2.1 changes. Three deliverables: (1) E2E tests for integrity tamper detection, periodic re-validation, license renewal via file drop, and fingerprint mismatch rejection (DOC-01), (2) Full rewrite of LICENSING.md plus updates to SETUP.md and ERROR-MAP.md (DOC-02), (3) Updated customer migration document with v2.1-specific verification steps (DOC-03).

</domain>

<decisions>
## Implementation Decisions

### E2E Test Scenarios (DOC-01)
- Claude decides the right balance of Docker integration vs pytest unit tests per scenario
- Claude decides whether to extend existing `e2e/license.spec.ts` or create a new spec file
- Lower re-validation threshold for tests: add a test-only env var (e.g., `REVALIDATION_INTERVAL=10`) so re-validation tests only need ~10 requests instead of 500
- Fingerprint mismatch test: generate a license with a different fingerprint than the container's, verify 503 rejection at startup
- Integrity tamper test: use `docker exec` to modify a protected file inside a running container, then verify next re-validation cycle catches it
- Renewal test: full lifecycle — start with expired license, verify 503/GRACE, drop renewal.key via Docker, restart container, verify VALID status restored

### Documentation Rewrite (DOC-02)
- **LICENSING.md: full rewrite** — current content significantly outdated (references old fingerprint formula, .pyc not .so, no renewal.key, no integrity checking, no periodic re-validation)
- Claude decides LICENSING.md audience structure (developer-only vs current dev+customer split) based on cross-reference patterns
- **ERROR-MAP.md: audit and add** — grep codebase for all new error messages from Phases 5-9, add with source code paths, keep existing traceability format
- **SETUP.md: config changes + monitoring** — add v2.1 configuration (machine-id bind mount, renewal.key location, env vars) AND a monitoring section showing /health license fields and X-License-Expires-In header

### Migration Document (DOC-03)
- Claude decides whether to keep MIGRATION.md focused on breaking changes only or expand with "What's New" section
- Update verification checklist to be v2.1-specific: verify /health license.status = 'valid', fingerprint_match = true, X-License-Expires-In header present (not just generic 'curl /health')

### Test Infrastructure
- Docker exec approach for integrity tamper tests (modify file inside running container)
- Full container lifecycle for renewal test (start → verify expired → drop key → restart → verify renewed)
- Security pipeline tests run as a **separate CI step** (not part of regular Playwright suite) — gated for main branch or explicit trigger due to Docker container start/stop overhead
- Reuse existing docker-compose.license-test.yml pattern for container management

### Claude's Discretion
- Test file organization (extend license.spec.ts vs new spec file)
- LICENSING.md audience structure (developer-only vs dev+customer split)
- Migration doc scope (breaking changes only vs full changelog)
- Exact Docker compose configuration for renewal and tamper test scenarios
- Which error messages from Phases 5-9 need ERROR-MAP.md entries (grep-based audit)

</decisions>

<specifics>
## Specific Ideas

- Success criteria #1 specifies exact scenarios: "integrity tamper detection, periodic re-validation triggering, license renewal via file drop, and fingerprint mismatch rejection"
- MIGRATION.md was deliberately written in Phase 6 "while context is fresh" with execution deferred to Phase 10
- Renewal lifecycle test proves the customer-facing workflow: expired → drop file → restart → valid
- REVALIDATION_INTERVAL env var keeps test fast without compromising production default of 500

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `e2e/license.spec.ts`: Existing Docker-based license E2E tests with container lifecycle management (beforeAll/afterAll), waitForContainer helper, docker-compose.license-test.yml integration
- `docs/LICENSING.md`: Comprehensive structure (overview, developer guide, customer guide, lifecycle, grace period, troubleshooting) — rewrite will preserve good structural patterns
- `docs/MIGRATION.md`: Phase 6 migration document covering fingerprint + HMAC breaking changes — update, not replace
- `playwright.config.ts`: 4-project config (api, driver-pwa, dashboard, license) — security tests can be a 5th project or extend license project

### Established Patterns
- Docker Compose override pattern for isolated test containers (port 8001, separate from dev stack)
- Sequential test story pattern in license.spec.ts (shared context across ordered tests)
- ERROR-MAP.md traceability: maps error messages to source code file paths
- docs/INDEX.md as central documentation hub with audience badges

### Integration Points
- `docker-compose.license-test.yml`: Add configuration for tamper and renewal test scenarios
- `core/licensing/license_manager.py`: REVALIDATION_INTERVAL env var for test threshold override
- `.github/workflows/`: New CI step for security pipeline tests
- `docs/INDEX.md`: Update cross-references if LICENSING.md structure changes

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 10-end-to-end-validation*
*Context gathered: 2026-03-11*
