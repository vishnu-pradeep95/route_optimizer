---
phase: 13
slug: bootstrap-installation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-05
---

# Phase 13 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | bash + shellcheck + manual verification |
| **Config file** | none — shell scripts tested via execution |
| **Quick run command** | `bash -n scripts/bootstrap.sh` |
| **Full suite command** | Manual: run bootstrap.sh on fresh WSL2 Ubuntu |
| **Estimated runtime** | ~5 seconds (syntax check); ~10 min (full manual) |

---

## Sampling Rate

- **After every task commit:** Run `bash -n scripts/bootstrap.sh`
- **After every plan wave:** Syntax check + shellcheck (if available)
- **Before `/gsd:verify-work`:** Manual execution on test WSL2 environment
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 13-01-01 | 01 | 1 | INST-03 | smoke | `cd /mnt/c && bash bootstrap.sh; echo $?` | N/A | ⬜ pending |
| 13-01-02 | 01 | 1 | INST-05 | smoke | Mock `/proc/version` and test guard function | N/A | ⬜ pending |
| 13-01-03 | 01 | 1 | INST-04 | smoke | Check `/proc/meminfo` parsing in isolation | N/A | ⬜ pending |
| 13-01-04 | 01 | 1 | INST-01 | manual-only | Run on fresh WSL2 Ubuntu without Docker | N/A | ⬜ pending |
| 13-01-05 | 01 | 1 | INST-02 | manual-only | Reboot WSL, check `systemctl is-active docker` | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `bash -n scripts/bootstrap.sh` — syntax validation passes
- [ ] `shellcheck scripts/bootstrap.sh` — optional linting (if shellcheck installed)

*Existing infrastructure covers most requirements. Shell scripts are primarily validated via manual execution.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Docker CE auto-install | INST-01 | Requires fresh WSL2 Ubuntu without Docker installed | Run bootstrap.sh on clean Ubuntu, verify `docker --version` afterwards |
| Docker auto-start after reboot | INST-02 | Requires WSL reboot cycle | Run bootstrap.sh, close/reopen WSL, verify `systemctl is-active docker` |
| WSL1 detection and fail | INST-05 | Requires WSL1 environment or kernel mock | Run on WSL1 or mock `/proc/version` with WSL1 kernel string |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
