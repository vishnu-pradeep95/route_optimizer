---
phase: 22
slug: ci-cd-pipeline-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-08
---

# Phase 22 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x + Playwright |
| **Config file** | `playwright.config.ts`, `pytest.ini` (implicit) |
| **Quick run command** | `npx playwright test --project=api` |
| **Full suite command** | `python -m pytest tests/ -q --tb=short && npx playwright test` |
| **Estimated runtime** | ~45 seconds (pytest ~20s + playwright ~22s) |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -q --tb=short` or `npx playwright test` as relevant
- **After every plan wave:** Run full suite command
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 45 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 22-01-01 | 01 | 1 | CICD-01 | integration | `python -m pytest tests/ -q --tb=short` | ✅ | ⬜ pending |
| 22-01-02 | 01 | 1 | CICD-02 | integration | `npx playwright test` | ✅ | ⬜ pending |
| 22-02-01 | 02 | 2 | CICD-03 | integration | CI artifact upload verification | ❌ manual | ⬜ pending |
| 22-02-02 | 02 | 2 | CICD-04 | visual | `grep -q 'badge' README.md` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. Playwright and pytest already installed and configured.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| CI artifact download | CICD-03 | GitHub Actions artifact upload can only be verified by pushing to remote and checking the Actions UI | Push a failing test, verify artifact appears in Actions run |
| CI badge renders | CICD-04 | Badge URL requires GitHub remote repo context | Check README.md after push, verify badge image loads |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 45s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
