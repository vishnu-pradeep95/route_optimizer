---
phase: 3
slug: error-handling-polish
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-10
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (backend), Playwright (E2E) |
| **Config file** | `pytest.ini` / `playwright.config.ts` |
| **Quick run command** | `pytest tests/apps/kerala_delivery/api/test_errors.py tests/apps/kerala_delivery/api/test_health.py -x` |
| **Full suite command** | `pytest tests/ -x && npx playwright test --project=dashboard e2e/dashboard-errors.spec.ts` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/apps/kerala_delivery/api/test_errors.py tests/apps/kerala_delivery/api/test_health.py -x`
- **After every plan wave:** Run `pytest tests/ -x && cd apps/kerala_delivery/dashboard && npx tsc --noEmit`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | ERR-05, ERR-09 | integration | `pytest tests/apps/kerala_delivery/api/test_health.py -x` | ✅ | ⬜ pending |
| 03-01-02 | 01 | 1 | ERR-01 | unit | `pytest tests/apps/kerala_delivery/api/test_errors.py -x` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. No new test files or frameworks needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Health bar shows per-service breakdown on 503 | ERR-09 | Requires degraded service state | 1. Stop OSRM container 2. Refresh dashboard 3. Verify health bar shows per-service status not just "Unhealthy" |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
