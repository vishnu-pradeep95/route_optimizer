---
phase: 09
slug: license-management
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 09 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pytest.ini (existing) |
| **Quick run command** | `pytest tests/core/licensing/ -x -q` |
| **Full suite command** | `pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/core/licensing/ -x -q`
- **After every plan wave:** Run `pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | LIC-01 | unit | `pytest tests/core/licensing/test_license_manager.py -x -q` | ❌ W0 | ⬜ pending |
| 09-01-02 | 01 | 1 | LIC-01 | unit | `pytest tests/core/licensing/test_license_manager.py -x -q` | ❌ W0 | ⬜ pending |
| 09-02-01 | 02 | 2 | LIC-02, LIC-03 | unit | `pytest tests/core/licensing/test_enforcement.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/core/licensing/test_license_manager.py` — extend with renewal validation tests
- [ ] `tests/core/licensing/test_enforcement.py` — extend with header and health license tests

*Existing infrastructure covers framework and fixtures.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Docker renewal.key mount | LIC-01 | Requires running Docker stack | Drop renewal.key, restart, verify via /health |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
