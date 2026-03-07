---
phase: 19
slug: pin-osrm-docker-image
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-07
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Manual Docker verification (compose config validation + container smoke tests) |
| **Config file** | docker-compose.yml, docker-compose.prod.yml |
| **Quick run command** | `docker compose config --quiet` |
| **Full suite command** | `docker compose up -d && docker compose ps` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `docker compose config --quiet`
- **After every plan wave:** Run `docker compose up -d && docker compose ps`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 19-01-01 | 01 | 1 | INST-01 | smoke | `docker compose config --quiet` | N/A | pending |
| 19-01-02 | 01 | 1 | INST-01 | smoke | `grep 'v5.27.1' docker-compose.yml` | N/A | pending |
| 19-01-03 | 01 | 1 | INST-01 | smoke | `grep '/bin/sh' docker-compose.yml` | N/A | pending |
| 19-01-04 | 01 | 1 | DAILY-01 | smoke | `grep '/bin/sh' docker-compose.prod.yml` | N/A | pending |
| 19-01-05 | 01 | 1 | INST-01 | smoke | `grep 'v5.27.1' scripts/osrm_setup.sh` | N/A | pending |
| 19-01-06 | 01 | 1 | INST-01 | smoke | `grep 'v5.27.1' SETUP.md` | N/A | pending |

*Status: pending · green · red · flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. This is a configuration-only fix — no test framework installation needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| osrm-init container starts without exit 127 | INST-01 | Requires Docker daemon running | `docker compose up osrm-init 2>&1` — verify exit code 0 |
| Full stack comes up after compose up | DAILY-01 | Requires Docker daemon + network | `docker compose up -d && docker compose ps` — verify all services running |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
