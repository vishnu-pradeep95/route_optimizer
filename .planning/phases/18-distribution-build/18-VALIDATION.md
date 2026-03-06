---
phase: 18
slug: distribution-build
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-06
---

# Phase 18 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Manual shell script validation (no automated test framework for shell scripts) |
| **Config file** | None — this is a build script, not application code |
| **Quick run command** | `./scripts/build-dist.sh v0.0-test` |
| **Full suite command** | `./scripts/build-dist.sh v0.0-test && tar tzf dist/kerala-delivery-v0.0-test.tar.gz \| head -20` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `./scripts/build-dist.sh v0.0-test`
- **After every plan wave:** Run full suite: build + tar content inspection + import test
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 18-01-01 | 01 | 1 | DIST-01 | smoke | `./scripts/build-dist.sh v0.0-test` | ❌ W0 | ⬜ pending |
| 18-01-02 | 01 | 1 | DIST-01a | smoke | `tar tzf dist/kerala-delivery-v0.0-test.tar.gz \| grep 'licensing.*\.pyc'` | ❌ W0 | ⬜ pending |
| 18-01-03 | 01 | 1 | DIST-01b | smoke | `tar tzf dist/kerala-delivery-v0.0-test.tar.gz \| grep 'licensing.*\.py$' \| grep -v '.pyc' && echo FAIL \|\| echo PASS` | ❌ W0 | ⬜ pending |
| 18-01-04 | 01 | 1 | DIST-01c | smoke | Built into build-dist.sh (import validation test) | ❌ W0 | ⬜ pending |
| 18-01-05 | 01 | 1 | DIST-01d | smoke | `tar tzf dist/kerala-delivery-v0.0-test.tar.gz \| grep generate_license && echo FAIL \|\| echo PASS` | ❌ W0 | ⬜ pending |
| 18-01-06 | 01 | 1 | DIST-01e | smoke | `tar tzf dist/kerala-delivery-v0.0-test.tar.gz \| grep '\.git/' && echo FAIL \|\| echo PASS` | ❌ W0 | ⬜ pending |
| 18-01-07 | 01 | 1 | DIST-01f | smoke | `tar tzf dist/kerala-delivery-v0.0-test.tar.gz \| grep -E '(README\|DEPLOY\|CSV_FORMAT\|SETUP)\.md'` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `scripts/build-dist.sh` — the entire deliverable (does not exist yet)
- [ ] `dist/` directory creation handled by the script itself
- [ ] No framework install needed — uses bash + python3 stdlib only

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Tarball extracts cleanly on fresh WSL | DIST-01 | Requires clean environment | Extract on fresh WSL, run `bootstrap.sh` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
