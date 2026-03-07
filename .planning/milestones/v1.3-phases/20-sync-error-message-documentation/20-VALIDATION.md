---
phase: 20
slug: sync-error-message-documentation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-07
---

# Phase 20 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Manual verification (documentation-only phase) |
| **Config file** | N/A |
| **Quick run command** | `grep -n` comparison of documented messages vs source code strings |
| **Full suite command** | Line-by-line audit of all error message entries in CSV_FORMAT.md and DEPLOY.md |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Verify changed lines against source code strings
- **After every plan wave:** Full audit of all error message entries
- **Before `/gsd:verify-work`:** Full suite must confirm every documented message matches code
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 20-01-01 | 01 | 1 | CSV-04 | manual | `grep` CSV_FORMAT.md geocoding table vs GEOCODING_REASON_MAP | N/A (doc) | pending |
| 20-01-02 | 01 | 1 | ERR-01 | manual | `grep -n "{'\\|'}" CSV_FORMAT.md DEPLOY.md` (expect 0 matches) | N/A (doc) | pending |
| 20-01-03 | 01 | 1 | ERR-02 | manual | Compare CSV_FORMAT.md geocoding rows vs main.py:82-89 | N/A (doc) | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. This is a documentation-only phase — no test framework needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| All CSV_FORMAT.md error strings match code output | CSV-04 | Documentation content, not executable code | Compare each "What You See" cell against source code string verbatim |
| No Python set notation in docs | ERR-01 | Pattern matching in markdown | `grep -n "{'\\|'}" CSV_FORMAT.md DEPLOY.md` should return 0 matches |
| Geocoding messages are office-friendly | ERR-02 | Subjective tone check + string match | Verify each geocoding row matches GEOCODING_REASON_MAP entry |
| Every message traces to code path | SC-3 | Cross-reference audit | ERROR-MAP.md has every CSV_FORMAT.md message with file:line |

---

## Validation Sign-Off

- [ ] All tasks have manual verify instructions
- [ ] Sampling continuity: every task verified against source code
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
