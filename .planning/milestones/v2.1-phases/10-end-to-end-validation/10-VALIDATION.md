---
phase: 10
slug: end-to-end-validation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-11
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Playwright ^1.58.2 |
| **Config file** | `playwright.config.ts` |
| **Quick run command** | `npx playwright test e2e/security-pipeline.spec.ts --workers=1` |
| **Full suite command** | `npx playwright test --workers=1` |
| **Estimated runtime** | ~120 seconds |

---

## Sampling Rate

- **After every task commit:** Run `npx playwright test e2e/security-pipeline.spec.ts --workers=1`
- **After every plan wave:** Run `npx playwright test --workers=1`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 0 | DOC-01 | E2E setup | `npx playwright test e2e/security-pipeline.spec.ts` | ❌ W0 | ⬜ pending |
| 10-01-02 | 01 | 1 | DOC-01a | E2E (Docker) | `npx playwright test e2e/security-pipeline.spec.ts -g "integrity tamper"` | ❌ W0 | ⬜ pending |
| 10-01-03 | 01 | 1 | DOC-01b | E2E (Docker) | `npx playwright test e2e/security-pipeline.spec.ts -g "re-validation"` | ❌ W0 | ⬜ pending |
| 10-01-04 | 01 | 1 | DOC-01c | E2E (Docker) | `npx playwright test e2e/security-pipeline.spec.ts -g "renewal"` | ❌ W0 | ⬜ pending |
| 10-01-05 | 01 | 1 | DOC-01d | E2E (Docker) | `npx playwright test e2e/security-pipeline.spec.ts -g "fingerprint"` | ❌ W0 | ⬜ pending |
| 10-02-01 | 02 | 2 | DOC-02 | manual-only | Visual review of LICENSING.md | N/A | ⬜ pending |
| 10-02-02 | 02 | 2 | DOC-02 | manual-only | Visual review of SETUP.md, ERROR-MAP.md | N/A | ⬜ pending |
| 10-03-01 | 03 | 2 | DOC-03 | manual-only | Visual review of MIGRATION.md | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `e2e/security-pipeline.spec.ts` — stubs for DOC-01a through DOC-01d
- [ ] `docker-compose.license-test.yml` updates — new service configs for security test scenarios
- [ ] `REVALIDATION_INTERVAL` env var in `core/licensing/license_manager.py` — makes re-validation testable
- [ ] Test key generation helper (expired key, mismatched fingerprint key, valid renewal key)

*Wave 0 creates test infrastructure before implementation tasks begin.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| LICENSING.md accuracy | DOC-02 | Content review — no automated way to verify doc accuracy | Read LICENSING.md, cross-reference with codebase for fingerprint formula, renewal workflow, integrity checking, re-validation |
| SETUP.md completeness | DOC-02 | Content review — new config entries | Verify machine-id mount, renewal.key, REVALIDATION_INTERVAL documented |
| ERROR-MAP.md completeness | DOC-02 | Content review — new error messages | Verify all v2.1 error messages and headers present |
| MIGRATION.md instructions | DOC-03 | Content review — customer-facing | Verify step-by-step migration instructions are complete and accurate |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
