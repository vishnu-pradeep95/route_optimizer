---
phase: 16
slug: driver-database-foundation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-12
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (asyncio_mode = auto) |
| **Config file** | pytest.ini |
| **Quick run command** | `pytest tests/core/database/ tests/apps/kerala_delivery/api/ -x -q` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/core/database/ tests/apps/kerala_delivery/api/ -x -q`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 16-01-01 | 01 | 1 | DRV-01 | unit | `pytest tests/apps/kerala_delivery/api/test_api.py -k "test_list_drivers" -x` | ❌ W0 | ⬜ pending |
| 16-01-02 | 01 | 1 | DRV-02 | unit | `pytest tests/apps/kerala_delivery/api/test_api.py -k "test_create_driver" -x` | ❌ W0 | ⬜ pending |
| 16-01-03 | 01 | 1 | DRV-03 | unit | `pytest tests/apps/kerala_delivery/api/test_api.py -k "test_update_driver" -x` | ❌ W0 | ⬜ pending |
| 16-01-04 | 01 | 1 | DRV-04 | unit | `pytest tests/apps/kerala_delivery/api/test_api.py -k "test_deactivate_driver" -x` | ❌ W0 | ⬜ pending |
| 16-02-01 | 02 | 2 | DRV-05 | unit | `pytest tests/apps/kerala_delivery/api/test_api.py -k "test_upload_auto_creates_drivers" -x` | ❌ W0 | ⬜ pending |
| 16-02-02 | 02 | 2 | DRV-06 | unit | `pytest tests/core/database/test_driver_matching.py -x` | ❌ W0 | ⬜ pending |
| 16-02-03 | 02 | 2 | DRV-07 | unit | `pytest tests/core/database/test_database.py -k "test_no_seeded_drivers" -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/core/database/test_driver_matching.py` — stubs for DRV-06 fuzzy matching logic
- [ ] Driver CRUD test methods in `tests/apps/kerala_delivery/api/test_api.py` — covers DRV-01 through DRV-05
- [ ] Update existing `test_driver_table_name` test for new schema (DRV-07 no-seed verification)

*Existing infrastructure (pytest, conftest.py, test fixtures) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Driver Management page layout/UX | DRV-01 | Visual/subjective | Open dashboard, navigate to Driver Management, verify table renders with name + status columns |
| Dashboard CRUD form usability | DRV-02, DRV-03, DRV-04 | Visual/subjective | Add/edit/deactivate a driver from dashboard, verify forms and feedback |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
