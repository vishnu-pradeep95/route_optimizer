---
phase: 14
slug: daily-startup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-05
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | bash + manual verification |
| **Config file** | none — shell scripts tested via execution |
| **Quick run command** | `bash -n scripts/start.sh` |
| **Full suite command** | Manual: run `scripts/start.sh` on WSL2 with services in various states |
| **Estimated runtime** | ~5 seconds (syntax check), ~90 seconds (full manual) |

---

## Sampling Rate

- **After every task commit:** Run `bash -n scripts/start.sh`
- **After every plan wave:** Run `scripts/start.sh` with services running (warm start)
- **Before `/gsd:verify-work`:** Cold start + warm start + simulated failure
- **Max feedback latency:** 5 seconds (syntax check)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 14-01-01 | 01 | 1 | DAILY-01 | syntax | `bash -n scripts/start.sh` | ❌ W0 | ⬜ pending |
| 14-01-02 | 01 | 1 | DAILY-01 | smoke | `./scripts/start.sh` (warm start) | ❌ W0 | ⬜ pending |
| 14-01-03 | 01 | 1 | DAILY-01 | manual-only | Simulated failure (stop API, run start.sh) | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `scripts/start.sh` — main script (created by plan tasks)

*Existing infrastructure covers all phase requirements. No test framework installation needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Timeout failure diagnosis | DAILY-01 | Requires deliberately stopping a service to trigger timeout path | 1. `docker compose stop api` 2. Run `./scripts/start.sh` 3. Wait 60s for timeout 4. Verify it names "API server" as failed and suggests `docker compose logs api` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
