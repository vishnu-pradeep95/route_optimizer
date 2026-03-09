---
phase: 21
slug: playwright-e2e-test-suite
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-08
---

# Phase 21 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | @playwright/test 1.58.2 + pytest 7.x |
| **Config file** | `playwright.config.ts` (Wave 0 — needs creation) |
| **Quick run command** | `npx playwright test --project=api` |
| **Full suite command** | `npx playwright test && pytest tests/ -x --tb=short` |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run `npx playwright test --project=api`
- **After every plan wave:** Run `npx playwright test`
- **Before `/gsd:verify-work`:** Full suite must be green (`npx playwright test && pytest tests/ -x --tb=short`)
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 21-01-01 | 01 | 1 | TEST-01 | E2E (config) | `npx playwright test --project=api` | ❌ W0 | ⬜ pending |
| 21-01-02 | 01 | 1 | TEST-01 | E2E (fixtures) | `npx playwright test e2e/api.spec.ts` | ❌ W0 | ⬜ pending |
| 21-02-01 | 02 | 1 | TEST-01 | E2E (API) | `npx playwright test e2e/api.spec.ts` | ❌ W0 | ⬜ pending |
| 21-02-02 | 02 | 1 | TEST-02 | E2E (browser) | `npx playwright test e2e/driver-pwa.spec.ts` | ❌ W0 | ⬜ pending |
| 21-02-03 | 02 | 1 | TEST-03 | E2E (browser) | `npx playwright test e2e/dashboard.spec.ts` | ❌ W0 | ⬜ pending |
| 21-02-04 | 02 | 1 | TEST-04 | E2E (API) | `npx playwright test e2e/license.spec.ts` | ❌ W0 | ⬜ pending |
| 21-02-05 | 02 | 1 | TEST-05 | unit (Python) | `pytest tests/ -x --tb=short` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `playwright.config.ts` — Playwright configuration at project root
- [ ] `e2e/fixtures/test-orders.csv` — Test data in CDCMS format with real Vatakara addresses
- [ ] `e2e/helpers/setup.ts` — Shared upload helper, API key validation, cleanup utilities
- [ ] `e2e/api.spec.ts` — API endpoint test stubs (TEST-01)
- [ ] `e2e/driver-pwa.spec.ts` — Driver PWA flow test stubs (TEST-02)
- [ ] `e2e/dashboard.spec.ts` — Dashboard display test stubs (TEST-03)
- [ ] `e2e/license.spec.ts` — License validation test stubs (TEST-04)
- [ ] `package.json` update — Add `"test:e2e"` script

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
