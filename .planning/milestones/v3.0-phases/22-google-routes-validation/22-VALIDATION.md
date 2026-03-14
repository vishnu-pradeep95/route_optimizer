---
phase: 22
slug: google-routes-validation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-14
---

# Phase 22 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + FastAPI TestClient |
| **Config file** | `pytest.ini` |
| **Quick run command** | `pytest tests/apps/kerala_delivery/api/test_validation.py -x` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/apps/kerala_delivery/api/test_validation.py -x`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 22-01-01 | 01 | 1 | VAL-01 | unit | `pytest tests/apps/kerala_delivery/api/test_validation.py::test_validate_route -x` | ❌ W0 | ⬜ pending |
| 22-01-02 | 01 | 1 | VAL-01 | unit | `pytest tests/apps/kerala_delivery/api/test_validation.py::test_validate_response_format -x` | ❌ W0 | ⬜ pending |
| 22-01-03 | 01 | 1 | VAL-02 | unit | `pytest tests/apps/kerala_delivery/api/test_validation.py::test_confidence_levels -x` | ❌ W0 | ⬜ pending |
| 22-01-04 | 01 | 1 | VAL-03 | unit | `pytest tests/apps/kerala_delivery/api/test_validation.py::test_cost_estimate -x` | ❌ W0 | ⬜ pending |
| 22-01-05 | 01 | 1 | VAL-01 | unit | `pytest tests/apps/kerala_delivery/api/test_validation.py::test_cached_validation -x` | ❌ W0 | ⬜ pending |
| 22-01-06 | 01 | 1 | VAL-01 | unit | `pytest tests/apps/kerala_delivery/api/test_validation.py::test_no_api_key -x` | ❌ W0 | ⬜ pending |
| 22-02-01 | 02 | 1 | VAL-04 | manual | Verify no automatic API calls in code | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/apps/kerala_delivery/api/test_validation.py` — stubs for VAL-01, VAL-02, VAL-03
- [ ] Mock Google Routes API responses (follow pattern from test_settings.py)

*Existing infrastructure covers framework install — pytest already configured.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| No automatic validation triggered | VAL-04 | Code review — verify no scheduled/background API calls | Search codebase for any periodic/automatic invocation of validation endpoint |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
