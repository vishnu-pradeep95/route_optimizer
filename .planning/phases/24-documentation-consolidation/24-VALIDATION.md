---
phase: 24
slug: documentation-consolidation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-08
---

# Phase 24 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Manual verification (documentation phase — no test framework) |
| **Config file** | N/A |
| **Quick run command** | `ls -la DISTRIBUTION.md ENV-COMPARISON.md GOOGLE-MAPS.md ATTRIBUTION.md LICENSING.md` |
| **Full suite command** | Check each file exists, has content, and contains expected sections via grep |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** `ls -la DISTRIBUTION.md ENV-COMPARISON.md GOOGLE-MAPS.md ATTRIBUTION.md && wc -l LICENSING.md`
- **After every plan wave:** All 5 files exist with expected content; LICENSING.md line count > 266 (original); README.md updated with doc index
- **Before `/gsd:verify-work`:** All files created, build-dist.sh includes ATTRIBUTION.md in tarball
- **Max feedback latency:** 2 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 24-01-01 | 01 | 1 | DOCS-01 | smoke | `grep -c "build-dist.sh\|verify-dist.sh\|generate_license" DISTRIBUTION.md` | ❌ W0 | ⬜ pending |
| 24-01-02 | 01 | 1 | DOCS-02 | smoke | `grep -c "Grace Period\|Renewal\|503\|Lifecycle" LICENSING.md` | ✅ (extend) | ⬜ pending |
| 24-02-01 | 02 | 1 | DOCS-03 | smoke | `grep -c "ENVIRONMENT\|API_KEY\|POSTGRES_PASSWORD" ENV-COMPARISON.md` | ❌ W0 | ⬜ pending |
| 24-02-02 | 02 | 1 | DOCS-04 | smoke | `grep -c "REQUEST_DENIED\|OVER_QUERY_LIMIT\|INVALID_REQUEST" GOOGLE-MAPS.md` | ❌ W0 | ⬜ pending |
| 24-03-01 | 03 | 1 | DOCS-05 | smoke | `grep -c "ODbL\|BSD-2\|LGPL\|MPL" ATTRIBUTION.md` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `DISTRIBUTION.md` — new file for DOCS-01
- [ ] `ENV-COMPARISON.md` — new file for DOCS-03
- [ ] `GOOGLE-MAPS.md` — new file for DOCS-04
- [ ] `ATTRIBUTION.md` — new file for DOCS-05
- [ ] `LICENSING.md` extension — append lifecycle/grace/renewal/503 sections for DOCS-02

*Existing infrastructure covers all phase requirements (no test framework needed — documentation verified by content checks).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Distribution workflow is followable end-to-end | DOCS-01 | Human readability | Read DISTRIBUTION.md, verify each step makes sense and commands are correct |
| License lifecycle is complete and accurate | DOCS-02 | Domain accuracy | Compare LICENSING.md lifecycle stages against license_manager.py logic |
| Env comparison is accurate | DOCS-03 | Config audit | Compare ENV-COMPARISON.md against docker-compose.yml and docker-compose.prod.yml |
| Google Maps troubleshooting covers real errors | DOCS-04 | Domain accuracy | Verify error codes and fixes against Google Maps API documentation |
| Attribution is legally complete | DOCS-05 | Legal compliance | Verify all copyleft/restrictive licenses are documented with correct obligations |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 2s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
