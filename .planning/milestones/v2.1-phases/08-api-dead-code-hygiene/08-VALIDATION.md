---
phase: 8
slug: api-dead-code-hygiene
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-10
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pytest.ini` (asyncio_mode = auto) |
| **Quick run command** | `pytest tests/core/licensing/ -x -q` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/core/licensing/ -x -q`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | RTP-02 | unit | `pytest tests/core/licensing/test_license_manager.py::TestMaybeRevalidate::test_triggers_at_500 -x` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 1 | RTP-02 | unit | `pytest tests/core/licensing/test_license_manager.py::TestMaybeRevalidate::test_integrity_failure_raises_system_exit -x` | ❌ W0 | ⬜ pending |
| 08-01-03 | 01 | 1 | RTP-02 | unit | `pytest tests/core/licensing/test_license_manager.py::TestMaybeRevalidate::test_skips_in_dev_mode -x` | ❌ W0 | ⬜ pending |
| 08-01-04 | 01 | 1 | RTP-03 | unit | `pytest tests/core/licensing/test_license_manager.py::TestMaybeRevalidate::test_counter_resets -x` | ❌ W0 | ⬜ pending |
| 08-01-05 | 01 | 1 | RTP-03 | unit | `pytest tests/core/licensing/test_license_manager.py::TestMaybeRevalidate::test_license_expiry_transition -x` | ❌ W0 | ⬜ pending |
| 08-01-06 | 01 | 1 | RTP-03 | unit | `pytest tests/core/licensing/test_license_manager.py::TestStateGuard -x` | ❌ W0 | ⬜ pending |
| 08-01-07 | 01 | 1 | RTP-03 | unit | `pytest tests/core/licensing/test_license_manager.py::TestStateGuard::test_allows_degradation -x` | ❌ W0 | ⬜ pending |
| 08-01-08 | 01 | 1 | RTP-03 | unit | `pytest tests/core/licensing/test_enforcement.py::TestRuntimeRevalidation -x` | ❌ W0 | ⬜ pending |
| 08-01-09 | 01 | 1 | RTP-03 | integration | `pytest tests/core/licensing/test_enforcement.py::TestRuntimeRevalidation::test_status_reread -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/core/licensing/test_license_manager.py::TestMaybeRevalidate` — new test class for maybe_revalidate()
- [ ] `tests/core/licensing/test_license_manager.py::TestStateGuard` — new test class for set_license_state() guard
- [ ] `tests/core/licensing/test_enforcement.py::TestRuntimeRevalidation` — new test class for middleware integration

*Existing infrastructure covers framework install — pytest 9.0.2 already configured.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
