# Routing Optimization Project — Copilot Context

> This file is automatically injected into every Copilot interaction in this repo.
> Keep it short and factual. Detailed guidance lives in the agent files.

## Project

Modular delivery-route optimization platform. First deployment: Kerala cargo
three-wheeler business (40–50 deliveries/day, 5 km radius, Piaggio Ape Xtra LDX).
Architecture is designed to be **reusable across any delivery business**.

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

## Architecture Principles

1. **Modular & reusable** — every component (optimizer, geocoder, routing engine adapter,
   data import) is a standalone module with a clean interface. The Kerala delivery app is
   the *first consumer*, not the only one. Other delivery businesses should be able to
   reuse core modules with different configs.
2. **Educational code** — this is a learning project. Every significant code block gets
   a comment explaining *why* it's written that way, not just *what* it does. Include
   links to docs/articles where a design decision came from.
3. **Test-driven confidence** — every module has unit tests. Every integration point has
   integration tests. Tests serve as living documentation and a safety net for future
   contributors. Target: `pytest` runs green before every commit.
4. **Interface-first design** — define abstract interfaces (Python ABCs or Protocols)
   before implementations. This allows swapping OSRM for Valhalla, or VROOM for OR-Tools,
   without changing calling code.

## Developer Context

- Solo developer building the system; others will contribute via git
- Code must be well-documented and use mainstream tech (Python, PostgreSQL, Docker)
- When writing code: prefer clarity over cleverness, add docstrings, use type hints
- Every function gets a docstring. Every non-trivial block gets an inline comment
  explaining the *design decision* (why), not just the mechanics (what).
- When creating files: follow the layout in the design document's file structure section
- New dev setup: follow `SETUP.md`

## Dev Environment

- **OS:** Ubuntu 24.04 LTS on WSL2 (Windows host)
- **Python:** 3.12, venv at `.venv/` — activate with `source .venv/bin/activate`
- **Node.js:** v24 (for dashboard/PWA tooling later)
- **Docker:** v29 + Compose v5 — run `sudo service docker start` if daemon not running
- **Hardware:** 32 cores, 30 GB RAM, ~950 GB disk — more than enough
- **Requirements:** `pip install -r requirements.txt` to restore packages
- **Env vars:** Copy `.env.example` → `.env` and fill in API keys
- **WSL note:** Docker daemon must be started manually: `sudo service docker start`
- **Testing:** `pytest` from project root. Tests live alongside code in `tests/` mirrors.
- **New developer?** Follow `SETUP.md` for complete environment setup.
