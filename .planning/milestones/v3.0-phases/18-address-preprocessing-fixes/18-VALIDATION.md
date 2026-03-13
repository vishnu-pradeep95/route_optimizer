---
phase: 18
slug: address-preprocessing-fixes
status: draft
nyquist_compliant: false
wave_0_complete: false
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
| 18-01-01 | 01 | 1 | ADDR-01 | unit | `pytest tests/core/data_import/test_cdcms_preprocessor.py -k "muttungal" -x` | Partial | ⬜ pending |
| 18-01-02 | 01 | 1 | ADDR-02 | unit | `pytest tests/core/data_import/test_cdcms_preprocessor.py -k "house or ho" -x` | ❌ needs (HO) tests | ⬜ pending |
| 18-01-03 | 01 | 1 | ADDR-03 | unit | `pytest tests/core/data_import/test_cdcms_preprocessor.py -k "po" -x` | ❌ needs (PO) tests | ⬜ pending |
| 18-02-01 | 02 | 1 | ADDR-04 | unit | `pytest tests/core/geocoding/test_interfaces_method.py -x` | ✅ needs update 30→20 | ⬜ pending |
| 18-02-02 | 02 | 1 | ADDR-05 | unit | `pytest tests/core/geocoding/test_validator.py -x` | ✅ needs env var test | ⬜ pending |
| 18-03-01 | 03 | 2 | ADDR-01..05 | E2E | `npx playwright test --project=api` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/core/data_import/test_cdcms_preprocessor.py` — Add (HO) expansion tests, (PO) expansion tests, Refill.xlsx pattern regression tests
- [ ] `tests/core/geocoding/test_interfaces_method.py:70` — Update `== 30` to `== 20`
- [ ] `tests/core/geocoding/test_validator.py:83` — Update `30_000` to `20_000`
- [ ] `tests/integration/test_address_pipeline.py` — Update 30km references to 20km

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Zone circle renders on map | ADDR-04 | Visual rendering check | Open dashboard live map, verify dashed 20km circle around depot |
| Address display in driver PWA | ADDR-01..03 | Visual readability | Upload Refill.xlsx, check addresses in route view |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
