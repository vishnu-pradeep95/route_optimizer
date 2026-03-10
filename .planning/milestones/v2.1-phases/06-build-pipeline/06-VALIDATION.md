---
phase: 06
slug: build-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-10
---

# Phase 06 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| **Config file** | `pytest.ini` (asyncio_mode = auto) |
| **Quick run command** | `python -m pytest tests/core/licensing/ tests/apps/kerala_delivery/api/test_api.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/core/licensing/ tests/apps/kerala_delivery/api/test_api.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green + `./scripts/build-dist.sh v-test` succeeds
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 0 | ENF-04 | unit | `python -m pytest tests/core/licensing/test_license_manager.py -x -q` | Exists -- needs fixture update | ⬜ pending |
| 06-01-02 | 01 | 1 | ENF-01 | unit | `python -m pytest tests/apps/kerala_delivery/api/test_api.py -x -q` | Partial -- needs update | ⬜ pending |
| 06-01-03 | 01 | 1 | ENF-01 | integration | `grep -r "ENVIRONMENT" --include="*.py" dist/ \| wc -l` | No -- Wave 0 | ⬜ pending |
| 06-02-01 | 02 | 1 | ENF-02, BLD-03 | integration | `docker build -f infra/Dockerfile.build .` | No -- Wave 0 | ⬜ pending |
| 06-02-02 | 02 | 1 | BLD-01, BLD-02 | integration | `./scripts/build-dist.sh v-test` | Exists -- needs upgrade | ⬜ pending |
| 06-02-03 | 02 | 1 | ENF-02 | integration | `docker run --rm img python -c "from core.licensing.license_manager import get_machine_fingerprint"` | No -- Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/core/licensing/test_license_manager.py` — update HMAC test fixtures for new seed values
- [ ] `tests/apps/kerala_delivery/api/test_api.py` — update test_docs_gated_in_production for inverted ENVIRONMENT logic
- [ ] Build pipeline integration test stubs: tarball .so verification, ENVIRONMENT grep, Docker import validation

*Existing test infrastructure covers licensing and API tests; build pipeline integration tests are new.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| HMAC seed differs from shipped .pyc | ENF-04 | Requires inspecting old .pyc and new .so binary | `strings dist/*.so \| grep -c "kerala-logistics"` should be 0 |
| Tarball extracts and runs on fresh Docker | BLD-01 | Full end-to-end deployment verification | Extract tarball, `docker compose up`, verify API responds |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
