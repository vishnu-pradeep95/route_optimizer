---
phase: 07
slug: enforcement-module
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-10
---

# Phase 07 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (with pytest-asyncio, asyncio_mode=auto) |
| **Config file** | `pytest.ini` (exists, minimal: asyncio_mode = auto) |
| **Quick run command** | `python3 -m pytest tests/core/licensing/ -x -q` |
| **Full suite command** | `python3 -m pytest tests/ -x -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/core/licensing/ tests/apps/kerala_delivery/api/test_api.py -x -q`
- **After every plan wave:** Run `python3 -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | ENF-03 | unit + integration | `python3 -m pytest tests/core/licensing/test_enforcement.py -x -q` | ❌ W0 | ⬜ pending |
| 07-01-02 | 01 | 1 | ENF-03 | static analysis | `grep -c "license_enforcement_middleware\|validate_license\|LicenseStatus" apps/kerala_delivery/api/main.py` | N/A | ⬜ pending |
| 07-02-01 | 02 | 1 | RTP-01 | unit | `python3 -m pytest tests/core/licensing/test_enforcement.py::test_verify_integrity -x -q` | ❌ W0 | ⬜ pending |
| 07-02-02 | 02 | 1 | RTP-01 | unit | `python3 -m pytest tests/core/licensing/test_enforcement.py::test_integrity_failure -x -q` | ❌ W0 | ⬜ pending |
| 07-03-01 | 03 | 2 | ENF-03 | regression | `python3 -m pytest tests/apps/kerala_delivery/api/test_api.py -x -q` | ✅ | ⬜ pending |
| 07-03-02 | 03 | 2 | RTP-01 | integration | `./scripts/build-dist.sh v-test 2>&1 \| tail -20` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/core/licensing/test_enforcement.py` — stubs for ENF-03 (enforce() behavior, middleware registration) and RTP-01 (integrity verification, tampered file detection)
- [ ] Test for `get_license_status()` and `set_license_state()` — can be added to existing `tests/core/licensing/test_license_manager.py`

*Existing infrastructure covers regression requirements (39 licensing tests + 115 API tests already passing).*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
