---
phase: 18
slug: address-preprocessing-fixes
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-13
---

# Phase 18 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 (Python) + Playwright (E2E) |
| **Config file** | pytest: `pyproject.toml`; Playwright: `playwright.config.ts` |
| **Quick run command** | `pytest tests/core/data_import/test_cdcms_preprocessor.py tests/core/geocoding/ -x` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/core/data_import/test_cdcms_preprocessor.py tests/core/geocoding/ -x`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 18-01-01 | 01 | 1 | ADDR-01 | unit | `pytest tests/core/data_import/test_cdcms_preprocessor.py -k "muttungal" -x` | Partial | pending |
| 18-01-02 | 01 | 1 | ADDR-02 | unit | `pytest tests/core/data_import/test_cdcms_preprocessor.py -k "house or ho" -x` | Plan 18-01 creates | pending |
| 18-01-03 | 01 | 1 | ADDR-03 | unit | `pytest tests/core/data_import/test_cdcms_preprocessor.py -k "po" -x` | Plan 18-01 creates | pending |
| 18-02-01 | 02 | 1 | ADDR-04 | unit | `pytest tests/core/geocoding/test_interfaces_method.py -x` | Needs update 30->20 | pending |
| 18-02-02 | 02 | 1 | ADDR-05 | unit | `pytest tests/core/geocoding/test_validator.py -x` | Needs env var test + out-of-zone test | pending |
| 18-03-01 | 03 | 2 | ADDR-04 | unit+build | `pytest tests/apps/kerala_delivery/api/test_api.py -k "config" -x && cd apps/kerala_delivery/dashboard && npx tsc --noEmit` | Exists | pending |
| 18-04-01 | 04 | 3 | ADDR-01..03 | integration | `pytest tests/apps/kerala_delivery/api/test_address_cleaning.py -x` | Plan 18-04 creates | pending |
| 18-04-02 | 04 | 3 | ADDR-01..05 | E2E | `npx playwright test --project=dashboard --grep "Address Cleaning"` | Plan 18-04 creates | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [x] `tests/core/data_import/test_cdcms_preprocessor.py` — Plan 18-01 Task 1 creates (HO), (PO), Refill.xlsx regression tests (TDD: tests written first)
- [x] `tests/core/geocoding/test_interfaces_method.py:70` — Plan 18-02 Task 1 updates `== 30` to `== 20`
- [x] `tests/core/geocoding/test_validator.py:83` — Plan 18-02 Task 2 updates `30_000` to `20_000` and adds out-of-zone confidence 0.0 test
- [x] `tests/integration/test_address_pipeline.py` — Plan 18-02 Task 2 updates 30km references to 20km
- [x] `tests/apps/kerala_delivery/api/test_address_cleaning.py` — Plan 18-04 Task 1 creates API-level tests with Refill.xlsx
- [x] `e2e/dashboard-address-cleaning.spec.ts` — Plan 18-04 Task 2 creates Playwright E2E spec

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Zone circle renders on map | ADDR-04 | Visual rendering check | Open dashboard live map, verify dashed 20km circle around depot |
| Address display in driver PWA | ADDR-01..03 | Visual readability | Upload Refill.xlsx, check addresses in route view |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** ready
