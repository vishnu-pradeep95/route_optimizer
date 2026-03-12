---
phase: 15
slug: csv-documentation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | `pytest.ini` (asyncio_mode=auto, custom markers) |
| **Quick run command** | `python3 -m pytest tests/integration/test_address_pipeline.py -x -v` |
| **Full suite command** | `python3 -m pytest tests/ -x -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/integration/test_address_pipeline.py -x -v`
- **After every plan wave:** Run `python3 -m pytest tests/ -x -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 15-01-01 | 01 | 1 | TEST-01 | integration | `python3 -m pytest tests/integration/test_address_pipeline.py::TestFullPipeline -x` | ❌ W0 | ⬜ pending |
| 15-01-02 | 01 | 1 | TEST-02 | integration | `python3 -m pytest tests/integration/test_address_pipeline.py::TestHdfcErgoBug -x` | ❌ W0 | ⬜ pending |
| 15-02-01 | 02 | 1 | TEST-03 | manual-only | N/A — one-time measurement documented in METRICS.md | N/A | ⬜ pending |
| 15-02-02 | 02 | 1 | TEST-04 | manual-only | N/A — documentation in METRICS.md | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/integration/test_address_pipeline.py` — stubs for TEST-01, TEST-02
- [ ] `.planning/milestones/v2.2-phases/METRICS.md` — covers TEST-03, TEST-04

*Existing `tests/conftest.py` provides shared fixtures (Vatakara depot coords, sample locations).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Accuracy metrics meet targets | TEST-03 | User decided: "one-time snapshot, not repeatable pytest assertion" | Process sample CDCMS CSV through pipeline, record metrics in METRICS.md |
| NER upgrade criteria documented | TEST-04 | Documentation artifact, not testable behavior | Verify METRICS.md contains thresholds + implementation sketch |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
