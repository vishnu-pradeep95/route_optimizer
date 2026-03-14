---
phase: 20
slug: ui-terminology-rename
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-14
---

# Phase 20 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (API), Playwright (E2E), vitest (dashboard) |
| **Config file** | `pytest.ini`, `playwright.config.ts`, `dashboard/vite.config.ts` |
| **Quick run command** | `pytest tests/apps/ -v --timeout=30` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/apps/ -v --timeout=30`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 20-01-01 | 01 | 1 | UI-01 | grep | `grep -r "Vehicle" dashboard/src/ --include="*.tsx"` | ✅ | ⬜ pending |
| 20-01-02 | 01 | 1 | UI-01 | import | `grep "VehicleList" dashboard/src/ -r` | ✅ | ⬜ pending |
| 20-01-03 | 01 | 1 | UI-03 | import | `grep "FleetManagement" dashboard/src/ -r` | ✅ | ⬜ pending |
| 20-02-01 | 02 | 2 | UI-01 | unit | `pytest tests/apps/ -v -k "test_api"` | ✅ | ⬜ pending |
| 20-02-02 | 02 | 2 | UI-02 | unit | `pytest tests/apps/ -v -k "vehicle"` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dashboard labels show "Driver" not "Vehicle" | UI-01 | Visual inspection | Open dashboard, check all pages for "Vehicle" text |
| QR sheet still works with driver names | UI-02 | Visual inspection | Print QR sheet, scan QR code, verify PWA loads |
| Duplicate warnings are collapsible | UI-01 | Visual/UX | Upload file with duplicates, verify collapsed display |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
