---
phase: 19
slug: per-driver-tsp-optimization
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-14
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (async, asyncio_mode=auto) |
| **Config file** | `pytest.ini` |
| **Quick run command** | `pytest tests/core/optimizer/test_tsp_orchestrator.py -v -x` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/core/optimizer/test_tsp_orchestrator.py -v -x`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 19-01-01 | 01 | 1 | OPT-01 | unit | `pytest tests/core/optimizer/test_tsp_orchestrator.py::test_single_driver_tsp -x` | No W0 | pending |
| 19-01-02 | 01 | 1 | OPT-02 | unit | `pytest tests/core/optimizer/test_tsp_orchestrator.py::test_order_grouping_by_driver -x` | No W0 | pending |
| 19-01-03 | 01 | 1 | OPT-03 | unit | `pytest tests/core/optimizer/test_tsp_orchestrator.py::test_merged_assignment_single_run -x` | No W0 | pending |
| 19-01-04 | 01 | 1 | OPT-04 | unit | `pytest tests/core/optimizer/test_tsp_orchestrator.py::test_no_overlap_validation -x` | No W0 | pending |
| 19-01-05 | 01 | 1 | OPT-05 | unit | `pytest tests/core/optimizer/test_tsp_orchestrator.py::test_geographic_anomaly_detection -x` | No W0 | pending |
| 19-02-01 | 02 | 2 | - | unit | `pytest tests/apps/kerala_delivery/test_parse_upload_deliveryman.py::test_missing_deliveryman_column -x` | No W0 | pending |
| 19-03-01 | 03 | 3 | - | e2e | `npx playwright test --project=driver-pwa -g "driver param"` | No W0 | pending |
| 19-03-02 | 03 | 3 | - | e2e | `npx playwright test --project=api -g "qr sheet"` | No W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/core/optimizer/test_tsp_orchestrator.py` — stubs for OPT-01 through OPT-05
- [ ] `tests/apps/kerala_delivery/test_parse_upload_deliveryman.py` — stub for DeliveryMan column validation
- [ ] Alembic migration for `routes.vehicle_id` VARCHAR(20) to VARCHAR(100) — prerequisite for storing driver names

*DB migration is a Wave 0 prerequisite because all route-saving tests will fail if driver names exceed 20 characters.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| QR code scans correctly on printed sheet | - | Physical QR printing/scanning | Print QR sheet, scan with phone camera, verify driver route loads |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
