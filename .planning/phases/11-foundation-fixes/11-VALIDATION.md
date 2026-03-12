---
phase: 11
slug: foundation-fixes
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-10
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + pytest-asyncio |
| **Config file** | `pytest.ini` (`asyncio_mode = auto`) |
| **Quick run command** | `python -m pytest tests/core/data_import/test_cdcms_preprocessor.py -x` |
| **Full suite command** | `python -m pytest tests/ -x --timeout=60` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/core/data_import/test_cdcms_preprocessor.py -x`
- **After every plan wave:** Run `python -m pytest tests/ -x --timeout=60`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 1 | ADDR-01 | unit | `python -m pytest tests/core/database/test_database.py -x -k "address"` | ❌ W0 | ⬜ pending |
| 11-01-02 | 01 | 1 | ADDR-01 | unit | `python -m pytest tests/apps/kerala_delivery/api/test_api.py -x -k "address"` | ❌ W0 | ⬜ pending |
| 11-01-03 | 01 | 1 | ADDR-01 | integration | Playwright MCP E2E | Manual only | ⬜ pending |
| 11-02-01 | 02 | 1 | ADDR-02 | unit | `python -m pytest tests/core/data_import/test_cdcms_preprocessor.py -x -k "split"` | ❌ W0 | ⬜ pending |
| 11-02-02 | 02 | 1 | ADDR-02 | unit | `python -m pytest tests/core/data_import/test_cdcms_preprocessor.py -x -k "abbreviation_preserved"` | ❌ W0 | ⬜ pending |
| 11-02-03 | 02 | 1 | ADDR-03 | unit | `python -m pytest tests/core/data_import/test_cdcms_preprocessor.py -x -k "step_order"` | ❌ W0 | ⬜ pending |
| 11-02-04 | 02 | 1 | ADDR-03 | regression | `python -m pytest tests/core/data_import/test_cdcms_preprocessor.py -x` | ✅ (32 tests) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/core/data_import/test_cdcms_preprocessor.py` — add tests for ADDR-02 (word splitting) and ADDR-03 (step ordering)
- [ ] `tests/core/database/test_database.py` — add tests verifying address_display sourced from address_raw
- [ ] `tests/apps/kerala_delivery/api/test_api.py` — add tests for address_raw field in API response

*Existing infrastructure covers framework/fixture needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Navigate button opens Google Maps with coordinates | ADDR-01 | Requires real browser + Google Maps | Playwright: click Navigate, verify URL contains lat/lon |
| PWA hero card shows dual addresses | ADDR-01 | Visual layout verification | Playwright: snapshot hero card, verify both address lines |
| PWA compact card shows dual addresses | ADDR-01 | Visual layout verification | Playwright: snapshot compact card, verify both address lines |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
