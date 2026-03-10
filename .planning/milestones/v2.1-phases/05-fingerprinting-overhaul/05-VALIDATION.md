---
phase: 5
slug: fingerprinting-overhaul
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-10
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing, 426 unit tests) |
| **Config file** | `pytest.ini` (asyncio_mode = auto) |
| **Quick run command** | `python3 -m pytest tests/core/licensing/test_license_manager.py -x -q` |
| **Full suite command** | `python3 -m pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/core/licensing/test_license_manager.py -x -q`
- **After every plan wave:** Run `python3 -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | FPR-01 | unit | `python3 -m pytest tests/core/licensing/test_license_manager.py::TestMachineFingerprint -x` | Exists (needs update) | ⬜ pending |
| 05-01-02 | 01 | 1 | FPR-01 | unit | `python3 -m pytest tests/core/licensing/test_license_manager.py -k "read_machine_id" -x` | ❌ W0 | ⬜ pending |
| 05-01-03 | 01 | 1 | FPR-01 | unit | `python3 -m pytest tests/core/licensing/test_license_manager.py -k "read_cpu_model" -x` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 1 | FPR-02 | smoke | `docker exec lpg-api cat /etc/machine-id` | ❌ W0 | ⬜ pending |
| 05-02-02 | 02 | 1 | FPR-03 | unit | `python3 -m pytest tests/core/licensing/test_license_manager.py -k "get_machine_id_script" -x` | ❌ W0 | ⬜ pending |
| 05-03-01 | 03 | 2 | FPR-01 | integration | Manual: compare host vs container fingerprint | New | ⬜ pending |

---

## Wave 0 Requirements

- [ ] Update `tests/core/licensing/test_license_manager.py::TestMachineFingerprint` — tests must mock `/etc/machine-id` and `/proc/cpuinfo` reads
- [ ] Add test for `_read_machine_id()` fallback behavior (file missing, permission denied)
- [ ] Add test for `_read_cpu_model()` fallback behavior (file missing, no matching line)
- [ ] Add test that fingerprint is deterministic with mocked filesystem reads
- [ ] Add test that old signals (hostname, container_id) are NOT used

*Existing test infrastructure (pytest, conftest.py) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Host and container produce same fingerprint | FPR-01, FPR-02 | Requires running Docker container with bind mount | Run `python3 scripts/get_machine_id.py` on host, `docker exec lpg-api python3 scripts/get_machine_id.py` in container, compare |
| Fingerprint survives container recreate | FPR-01 | Requires Docker lifecycle operations | Run `docker compose up -d --force-recreate api`, compare fingerprint before and after |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
