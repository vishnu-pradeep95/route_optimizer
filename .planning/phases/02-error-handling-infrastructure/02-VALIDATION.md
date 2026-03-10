---
phase: 02
slug: error-handling-infrastructure
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-09
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| **Config file** | `pytest.ini` (asyncio_mode = auto) |
| **Quick run command** | `pytest tests/apps/kerala_delivery/api/ -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~30 seconds |
| **E2E framework** | Playwright (npx playwright test) |
| **E2E config** | `playwright.config.ts` |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/apps/kerala_delivery/api/ -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **After Plan 04:** Run `npx playwright test --project=dashboard e2e/dashboard-errors.spec.ts`
- **Before `/gsd:verify-work`:** Full suite must be green + Playwright E2E pass
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-T1 | 01 | 1 | ERR-01, ERR-02 | unit + integration | `pytest tests/apps/kerala_delivery/api/test_errors.py tests/apps/kerala_delivery/api/test_middleware.py -x` | W0 (created by task) | pending |
| 02-01-T2 | 01 | 1 | ERR-03 | integration | `pytest tests/apps/kerala_delivery/api/test_api.py -x` | partial (existing) | pending |
| 02-02-T1 | 02 | 2 | ERR-04, ERR-06 | unit | `pytest tests/apps/kerala_delivery/api/test_health.py tests/apps/kerala_delivery/api/test_retry.py -x` | W0 (created by task) | pending |
| 02-02-T2 | 02 | 2 | ERR-05 | integration | `pytest tests/apps/kerala_delivery/api/ -x` | partial (existing) | pending |
| 02-03-T1 | 03 | 3 | ERR-07, ERR-08 | build | `cd apps/kerala_delivery/dashboard && npx tsc --noEmit` | N/A | pending |
| 02-03-T2 | 03 | 3 | ERR-07, ERR-09 | build | `cd apps/kerala_delivery/dashboard && npm run build` | N/A | pending |
| 02-03-T3 | 03 | 3 | ERR-07, ERR-08, ERR-09 | manual | Human visual verification | N/A | pending |
| 02-04-T1 | 04 | 4 | ERR-07, ERR-08, ERR-09 | e2e | `npx playwright test --project=dashboard e2e/dashboard-errors.spec.ts` | W0 (created by task) | pending |

*Status: pending -- green -- red -- flaky*

---

## Wave 0 Requirements

- [ ] `tests/apps/kerala_delivery/api/test_errors.py` -- created by Plan 01 Task 1 (TDD: tests first)
- [ ] `tests/apps/kerala_delivery/api/test_middleware.py` -- created by Plan 01 Task 1 (TDD: tests first)
- [ ] `tests/apps/kerala_delivery/api/test_health.py` -- created by Plan 02 Task 1 (TDD: tests first)
- [ ] `tests/apps/kerala_delivery/api/test_retry.py` -- created by Plan 02 Task 1 (TDD: tests first)
- [ ] `e2e/dashboard-errors.spec.ts` -- created by Plan 04 Task 1

*Existing `test_api.py` covers ERR-03 and ERR-05 partially -- will need updates.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Error banner auto-dismiss on reconnect | ERR-07 | Requires network interruption simulation | Disconnect WiFi, verify banner appears, reconnect, verify banner dismisses |
| Error detail spacing/alignment | ERR-08 | Visual verification | Screenshot at 393x851 viewport, verify alignment |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
