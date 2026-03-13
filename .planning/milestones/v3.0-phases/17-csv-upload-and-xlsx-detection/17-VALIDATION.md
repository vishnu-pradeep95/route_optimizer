---
phase: 17
slug: csv-upload-and-xlsx-detection
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-13
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + asyncio_mode=auto |
| **Config file** | `pytest.ini` |
| **Quick run command** | `pytest tests/core/data_import/test_cdcms_preprocessor.py tests/apps/kerala_delivery/api/test_api.py -x -v` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~45 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/core/data_import/test_cdcms_preprocessor.py tests/apps/kerala_delivery/api/test_api.py -x -v`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 17-01-01 | 01 | 1 | CSV-01 | unit | `pytest tests/apps/kerala_delivery/api/test_api.py -k "xlsx_cdcms_detect" -x` | ❌ W0 | ⬜ pending |
| 17-01-02 | 01 | 1 | CSV-04 | unit | `pytest tests/core/data_import/test_cdcms_preprocessor.py -k "allocated_printed" -x` | ✅ | ⬜ pending |
| 17-01-03 | 01 | 1 | CSV-05 | unit | `pytest tests/core/data_import/test_cdcms_preprocessor.py -k "column_order" -x` | ❌ W0 | ⬜ pending |
| 17-02-01 | 02 | 1 | CSV-02 | unit | `pytest tests/apps/kerala_delivery/api/test_api.py -k "parse_upload_preview" -x` | ❌ W0 | ⬜ pending |
| 17-02-02 | 02 | 1 | CSV-03 | unit | `pytest tests/apps/kerala_delivery/api/test_api.py -k "selected_drivers" -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/apps/kerala_delivery/api/test_api.py` — stubs for CSV-01 (XLSX detection)
- [ ] `tests/apps/kerala_delivery/api/test_api.py` — stubs for CSV-02 (parse-upload preview)
- [ ] `tests/apps/kerala_delivery/api/test_api.py` — stubs for CSV-03 (selected drivers filtering)
- [ ] `tests/core/data_import/test_cdcms_preprocessor.py` — stubs for CSV-05 (column order independence)
- No new framework install needed — pytest infrastructure complete

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Driver preview UI renders correctly | CSV-02 | Visual layout/styling | Upload multi-driver file, verify driver list with checkboxes and order counts |
| Select/deselect drivers UX | CSV-03 | Interactive UX flow | Toggle driver checkboxes, verify visual feedback and button state |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
