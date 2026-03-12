---
phase: 12
slug: data-wiring-validation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 with pytest-asyncio 1.3.0 |
| **Config file** | `pytest.ini` |
| **Quick run command** | `python -m pytest tests/core/data_import/test_address_splitter.py -x` |
| **Full suite command** | `python -m pytest tests/core/data_import/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/core/data_import/test_address_splitter.py -x`
- **After every plan wave:** Run `python -m pytest tests/core/data_import/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 12-01-01 | 01 | 1 | ADDR-04 | unit | `python -m pytest tests/core/data_import/test_address_splitter.py::test_dictionary_exists -x` | ❌ W0 | ⬜ pending |
| 12-01-02 | 01 | 1 | ADDR-04 | integration | `python scripts/build_place_dictionary.py --dry-run` | ❌ W0 | ⬜ pending |
| 12-01-03 | 01 | 1 | ADDR-04 | unit | `python -m pytest tests/core/data_import/test_address_splitter.py::test_dictionary_coverage -x` | ❌ W0 | ⬜ pending |
| 12-02-01 | 02 | 2 | ADDR-05 | unit | `python -m pytest tests/core/data_import/test_address_splitter.py::TestSplitter -x` | ❌ W0 | ⬜ pending |
| 12-02-02 | 02 | 2 | ADDR-05 | unit | `python -m pytest tests/core/data_import/test_address_splitter.py::test_passthrough_unknown -x` | ❌ W0 | ⬜ pending |
| 12-03-01 | 03 | 2 | ADDR-06 | unit | `python -m pytest tests/core/data_import/test_address_splitter.py::TestFuzzyMatching -x` | ❌ W0 | ⬜ pending |
| 12-03-02 | 03 | 2 | ADDR-06 | unit | `python -m pytest tests/core/data_import/test_address_splitter.py::test_no_false_positives -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/core/data_import/test_address_splitter.py` — stubs for ADDR-04, ADDR-05, ADDR-06
- [ ] `rapidfuzz==3.14.3` added to `requirements.txt`

*Existing infrastructure covers test framework (pytest already configured).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Build script fetches from live OSM/India Post APIs | ADDR-04 | External API availability | Run `python scripts/build_place_dictionary.py` and verify JSON output |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
