---
phase: 23
slug: distribution-verification-operational-scripts
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-08
---

# Phase 23 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Bash scripts (self-verifying) |
| **Config file** | none — scripts are the tests |
| **Quick run command** | `./scripts/stop.sh && docker compose ps` |
| **Full suite command** | `./scripts/verify-dist.sh dist/kerala-delivery-v*.tar.gz` |
| **Estimated runtime** | ~120 seconds (verify-dist.sh), ~5 seconds (stop.sh) |

---

## Sampling Rate

- **After every task commit:** Run `./scripts/stop.sh && docker compose ps`
- **After every plan wave:** Run `./scripts/verify-dist.sh dist/kerala-delivery-v*.tar.gz`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 120 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 23-01-01 | 01 | 1 | OPS-01 | smoke | `./scripts/stop.sh && docker compose ps` | ❌ W0 | ⬜ pending |
| 23-01-02 | 01 | 1 | OPS-02 | smoke | `./scripts/stop.sh --gc` | ❌ W0 | ⬜ pending |
| 23-02-01 | 02 | 2 | OPS-03 | integration | `./scripts/verify-dist.sh dist/kerala-delivery-v*.tar.gz` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `scripts/stop.sh` — new file, covers OPS-01 and OPS-02
- [ ] `scripts/verify-dist.sh` — new file, covers OPS-03
- [ ] Build a fresh tarball: `./scripts/build-dist.sh v1.4` (verify-dist.sh needs input)

*Scripts ARE the deliverables — creation satisfies both Wave 0 and production requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Data volumes preserved after stop | OPS-01 | Requires inspecting Docker volumes and restarting services | After `stop.sh`, run `docker volume ls`, verify `lpg_pgdata` still exists, then `start.sh` and confirm data persists |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 120s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
