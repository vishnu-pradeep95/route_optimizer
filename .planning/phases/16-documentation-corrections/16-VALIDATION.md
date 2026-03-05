---
phase: 16
slug: documentation-corrections
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-05
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Manual verification (documentation-only phase — no automated tests) |
| **Config file** | N/A |
| **Quick run command** | `grep -rn 'routing-db\|routeopt\|<REPO_URL>\|alembic upgrade' README.md DEPLOY.md SETUP.md` |
| **Full suite command** | `grep -rn 'routing-db\|routeopt\|<REPO_URL>\|alembic upgrade' README.md DEPLOY.md SETUP.md` |
| **Estimated runtime** | ~1 second |

---

## Sampling Rate

- **After every task commit:** Run quick grep verification
- **After every plan wave:** Visual read-through of all three documents
- **Before `/gsd:verify-work`:** Full grep suite must show zero violations + manual read-through
- **Max feedback latency:** 1 second

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 16-01-01 | 01 | 1 | DOCS-01 | smoke | `grep -c 'routing-db' README.md` should return 0 | N/A | pending |
| 16-01-02 | 01 | 1 | DOCS-01 | smoke | `grep 'lpg-db' README.md` should match | N/A | pending |
| 16-01-03 | 01 | 1 | DOCS-02 | smoke | `grep -n 'alembic' README.md` — verify annotated | N/A | pending |
| 16-01-04 | 01 | 1 | DOCS-03 | smoke | `grep -c '<REPO_URL>' DEPLOY.md` should return 0 | N/A | pending |
| 16-01-05 | 01 | 1 | DOCS-04 | smoke | `grep 'scripts/start.sh' DEPLOY.md` should match | N/A | pending |
| 16-01-06 | 01 | 1 | DOCS-04 | smoke | `grep 'scripts/bootstrap.sh' DEPLOY.md` should match | N/A | pending |
| 16-01-07 | 01 | 1 | DOCS-04 | smoke | `grep 'CSV_FORMAT.md' DEPLOY.md` should match | N/A | pending |
| 16-01-08 | 01 | 1 | DOCS-04 | smoke | `grep -i 'powershell' DEPLOY.md` should match warning | N/A | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

*Existing infrastructure covers all phase requirements. No test framework needed for documentation-only phase.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| DEPLOY.md daily section fits one printed page | DOCS-04 | Line count is an approximation of printed output | Count lines in Section 3 — target under 50 lines |
| DEPLOY.md is coherent for non-technical reader | DOCS-04 | Requires human judgment on readability | Read Section 2 and 3 as a non-technical user |
| README employee callout is visible | DOCS-02 | Requires visual judgment | Verify callout appears prominently before Quick Start |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 1s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
