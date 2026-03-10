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

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/apps/kerala_delivery/api/ -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green + Playwright MCP E2E pass
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | ERR-01 | unit | `pytest tests/apps/kerala_delivery/api/test_errors.py -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | ERR-02 | integration | `pytest tests/apps/kerala_delivery/api/test_middleware.py -x` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | ERR-03 | integration | `pytest tests/apps/kerala_delivery/api/test_api.py -x` | ✅ partial | ⬜ pending |
| 02-01-04 | 01 | 1 | ERR-04 | unit | `pytest tests/apps/kerala_delivery/api/test_health.py -x` | ❌ W0 | ⬜ pending |
| 02-01-05 | 01 | 1 | ERR-05 | integration | `pytest tests/apps/kerala_delivery/api/test_api.py::test_health -x` | ✅ partial | ⬜ pending |
| 02-01-06 | 01 | 1 | ERR-06 | unit | `pytest tests/apps/kerala_delivery/api/test_retry.py -x` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 2 | ERR-07 | e2e | Playwright MCP | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 2 | ERR-08 | e2e | Playwright MCP | ❌ W0 | ⬜ pending |
| 02-02-03 | 02 | 2 | ERR-09 | e2e | Playwright MCP | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/apps/kerala_delivery/api/test_errors.py` — stubs for ERR-01 (ErrorResponse model validation)
- [ ] `tests/apps/kerala_delivery/api/test_middleware.py` — stubs for ERR-02 (RequestIDMiddleware)
- [ ] `tests/apps/kerala_delivery/api/test_health.py` — stubs for ERR-04 (startup health gates)
- [ ] `tests/apps/kerala_delivery/api/test_retry.py` — stubs for ERR-06 (retry logic)

*Existing `test_api.py` covers ERR-03 and ERR-05 partially — will need updates.*

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
