---
phase: 21
slug: dashboard-settings-and-cache-management
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-14
---

# Phase 21 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (asyncio_mode = auto) |
| **Config file** | `pytest.ini` |
| **Quick run command** | `pytest tests/apps/kerala_delivery/api/test_settings.py -x -v` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds (settings tests only), ~120 seconds (full suite) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/apps/kerala_delivery/api/test_settings.py -x -v`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 21-01-01 | 01 | 1 | SET-01, SET-02 | unit | `pytest tests/apps/kerala_delivery/api/test_settings.py::test_update_api_key -x` | ❌ W0 | ⬜ pending |
| 21-01-02 | 01 | 1 | SET-02 | unit | `pytest tests/apps/kerala_delivery/api/test_settings.py::test_get_settings_masked_key -x` | ❌ W0 | ⬜ pending |
| 21-01-03 | 01 | 1 | SET-04 | unit | `pytest tests/apps/kerala_delivery/api/test_settings.py::test_geocode_cache_stats -x` | ❌ W0 | ⬜ pending |
| 21-01-04 | 01 | 1 | SET-05 | unit | `pytest tests/apps/kerala_delivery/api/test_settings.py::test_cache_export -x` | ❌ W0 | ⬜ pending |
| 21-01-05 | 01 | 1 | SET-06 | unit | `pytest tests/apps/kerala_delivery/api/test_settings.py::test_cache_import -x` | ❌ W0 | ⬜ pending |
| 21-01-06 | 01 | 1 | SET-01 | unit | `pytest tests/apps/kerala_delivery/api/test_settings.py::test_validate_api_key -x` | ❌ W0 | ⬜ pending |
| 21-01-07 | 01 | 1 | SET-01 | unit | `pytest tests/apps/kerala_delivery/api/test_settings.py::test_api_key_db_overrides_env -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/apps/kerala_delivery/api/test_settings.py` — stubs for SET-01 through SET-06 + validation + fallback tests
- [ ] Alembic migration file for `settings` table
- [ ] `SettingsDB` model added to `core/database/models.py` (imported by `env.py` for autogenerate)

*Existing test infrastructure (`conftest.py`, `pytest.ini`, test DB fixtures) covers all shared requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Settings page renders correctly in dashboard | SET-01-SET-06 | Visual layout, CSS styling | Navigate to Settings page, verify sections visible |
| Masked key display is readable | SET-02 | Visual UX | Enter API key, verify masked display |
| Cache export downloads valid JSON file | SET-05 | Browser file download behavior | Click Export, verify downloaded file |
| Cache import file picker works | SET-06 | Browser file input behavior | Select JSON file, verify import summary |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
