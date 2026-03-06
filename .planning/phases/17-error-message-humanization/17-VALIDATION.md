---
phase: 17
slug: error-message-humanization
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-05
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest with pytest-asyncio |
| **Config file** | `pytest.ini` (asyncio_mode = auto) |
| **Quick run command** | `python -m pytest tests/core/data_import/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/core/data_import/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 17-01-01 | 01 | 1 | ERR-01 | unit | `python -m pytest tests/core/data_import/test_cdcms_preprocessor.py -x -k "missing_required"` | Exists -- needs assertion update | ⬜ pending |
| 17-01-02 | 01 | 1 | ERR-01 | unit | `python -m pytest tests/core/data_import/test_csv_importer.py -x -k "missing"` | Needs new test | ⬜ pending |
| 17-01-03 | 01 | 1 | ERR-01 | unit | `python -m pytest tests/core/data_import/test_csv_importer.py -x -k "humanize"` | Needs new test | ⬜ pending |
| 17-01-04 | 01 | 1 | ERR-02 | unit | `python -m pytest tests/apps/kerala_delivery/api/test_api.py -x -k "geocod"` | Needs new test | ⬜ pending |
| 17-01-05 | 01 | 1 | ERR-02 | unit | `python -m pytest tests/apps/kerala_delivery/api/test_api.py -x -k "fallback"` | Needs new test | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/core/data_import/test_cdcms_preprocessor.py::TestValidation::test_missing_required_columns_raises` -- update assertion to verify new message format (no set notation, has " -- " fix action)
- [ ] `tests/core/data_import/test_csv_importer.py` -- add test for missing address column error message format (no list repr)
- [ ] `tests/core/data_import/test_csv_importer.py` -- add test for `_humanize_row_error()` helper
- [ ] No new framework install needed -- pytest already configured

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Upload CSV with wrong columns, verify UI error message | ERR-01 | End-to-end through browser | Upload a CSV missing OrderNo, check dashboard shows friendly error |
| Geocode a bad address, verify UI error message | ERR-02 | Requires Google API interaction | Upload CSV with nonsense address, check failure table shows friendly reason |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
