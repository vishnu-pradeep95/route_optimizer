# Routing Optimization Project — Copilot Context

> This file is automatically injected into every Copilot interaction in this repo.
> Keep it short and factual. Detailed guidance lives in the agent files.

## Project

Smart delivery-route optimization for a Kerala cargo three-wheeler business.
40–50 deliveries/day, 5 km radius, Piaggio Ape Xtra LDX fleet.

## Key Files

| File | Purpose |
|---|---|
| `plan/kerala_delivery_route_system_design.md` | Authoritative design document (450 lines) |
| `plan/session-journal.md` | Cross-session memory log — read at start, append at end |
| `.github/agents/kerala-delivery-route-architect.agent.md` | Main architect agent |
| `.github/agents/session-journal.agent.md` | Agent for saving/loading session context |

## Current State

- **Phase:** Pre-Phase 0 (planning and setup)
- **Stack (tentative):** VROOM + OSRM + PostgreSQL/PostGIS + FastAPI + PWA-first driver app
- **Mobile:** No native mobile experience on team — using PWA or guided cross-platform approach
- **Budget:** Flexible — prefer managed services where they save significant dev time

## Non-Negotiable Constraints

1. **No countdown timers** in any UI — Kerala MVD directive
2. **Minimum 30-minute delivery windows** — no "10-minute delivery" promises
3. **Speed alerts at 40 km/h urban** — driver safety
4. **1.3× safety multiplier** on all travel time estimates
5. **Offline-capable driver interface** — patchy Kerala mobile data
6. **Data privacy** — PII stays in source spreadsheet, optimizer uses only coordinates + weights

## Developer Context

- Solo developer building the system; others may contribute later via git
- Code must be well-documented and use mainstream tech (Python, PostgreSQL, Docker)
- When writing code: prefer clarity over cleverness, add docstrings, use type hints
- When creating files: follow the layout in the design document's file structure section
