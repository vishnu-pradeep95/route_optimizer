---
phase: 13
slug: geocode-validation-fallback-chain
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest with pytest-asyncio |
| **Config file** | `pytest.ini` |
| **Quick run command** | `pytest tests/core/geocoding/test_validator.py -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/core/geocoding/test_validator.py -x`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 13-01-01 | 01 | 1 | GVAL-01 | unit | `pytest tests/core/geocoding/test_validator.py::TestZoneCheck -x` | ❌ W0 | ⬜ pending |
| 13-01-02 | 01 | 1 | GVAL-02 | unit | `pytest tests/core/geocoding/test_validator.py::TestAreaRetry -x` | ❌ W0 | ⬜ pending |
| 13-01-03 | 01 | 1 | GVAL-03 | unit | `pytest tests/core/geocoding/test_validator.py::TestCentroidFallback -x` | ❌ W0 | ⬜ pending |
| 13-01-04 | 01 | 1 | GVAL-04 | unit | `pytest tests/core/geocoding/test_validator.py::TestConfidenceScoring -x` | ❌ W0 | ⬜ pending |
| 13-01-05 | 01 | 1 | CB | unit | `pytest tests/core/geocoding/test_validator.py::TestCircuitBreaker -x` | ❌ W0 | ⬜ pending |
| 13-02-01 | 02 | 2 | COMPAT | unit | `pytest tests/core/geocoding/test_cache.py -x` | ✅ | ⬜ pending |
| 13-02-02 | 02 | 2 | PIPELINE | integration | `pytest tests/core/geocoding/test_validator.py::TestPipelineIntegration -x` | ❌ W0 | ⬜ pending |
| 13-02-03 | 02 | 2 | MIGRATION | integration | `alembic upgrade head` + verify column | Manual | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/core/geocoding/test_validator.py` — stubs for GVAL-01 through GVAL-04, circuit breaker, depot fallback
- [ ] Alembic migration for geocode_method column
- [ ] Existing `tests/core/geocoding/test_cache.py` tests must pass unchanged (backward compatibility)

*Wave 0 creates test stubs that initially fail, then implementation makes them pass.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Alembic migration runs cleanly | MIGRATION | Requires running database + Docker | `docker compose exec api alembic upgrade head`, verify `geocode_method` column exists |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
