# Kerala LPG Delivery Route Optimizer

## What This Is

A route optimization system for LPG cylinder delivery in Kerala's Vatakara region. An office employee uploads CDCMS export CSVs, the system geocodes addresses, optimizes delivery routes across a 13-vehicle fleet (Piaggio Ape Xtra LDX), and generates QR codes/links that drivers open on their phones via a PWA for turn-by-turn navigation.

## Core Value

Every delivery address uploaded must appear on the map and be assigned to an optimized route — no silent drops, no missing stops.

## Requirements

### Validated

- Route optimization via VROOM/OSRM for 13-vehicle fleet — existing
- CSV/CDCMS file upload and parsing — existing
- Google Geocoding with DB caching — existing
- Driver PWA with Leaflet maps and offline support — existing
- QR code generation for route sharing — existing
- PostgreSQL + PostGIS persistence with Alembic migrations — existing
- API key authentication and rate limiting — existing
- Docker Compose orchestration (API, OSRM, VROOM, PostgreSQL) — existing
- React/TypeScript dashboard with route upload, live map, fleet management — existing
- Telemetry ingestion from driver devices — existing

### Active

- [ ] Professional UI overhaul — clean logistics SaaS look (Onfleet/Routific style) for both dashboard and driver PWA
- [ ] Fix silent geocoding failures — orders that fail geocoding are silently dropped, causing locations to disappear from map after routing
- [ ] Audit preprocessing/depot logic — verify Vatakara depot config flows correctly through the entire pipeline, no Kozhikode coordinates leaking
- [ ] Security audit and hardening — address OWASP concerns, review auth, input validation, XSS, injection vectors
- [ ] Code quality cleanup — remove AI-generated slop, dead code, unnecessary abstractions
- [ ] Well-rounded unit tests — cover edge cases, improve coverage, remove shallow/redundant tests
- [ ] Streamlined installation and documentation — easy setup guide, clear README, docker-compose just works
- [ ] CSV import validation reporting — show users which rows failed and why (not just "No valid orders")

### Out of Scope

- Mobile native apps — PWA is sufficient for driver use case
- Real-time chat/messaging — not needed for delivery workflow
- Multi-tenant/multi-region — Vatakara-only for now
- Payment processing — handled outside this system
- Customer-facing tracking — drivers and office staff only

## Context

- **Domain**: LPG cylinder delivery in Kerala, India (Vatakara region)
- **Fleet**: 13 Piaggio Ape Xtra LDX vehicles, 446 kg max / 30 cylinders each
- **Data source**: CDCMS (Centralized Distribution Customer Management System) CSV exports
- **Infrastructure**: Docker Compose with OSRM (Kerala OSM data), VROOM solver, PostgreSQL/PostGIS
- **Current state**: Functional prototype with working optimization pipeline, but tacky UI, silent failures, and code quality issues from AI-assisted development
- **Known critical bug**: Geocoding failures silently drop orders — user sees fewer pins on map than CSV rows after routing runs
- **Codebase map**: `.planning/codebase/` (7 documents, 2047 lines of analysis)

## Constraints

- **Tech stack**: Python/FastAPI backend, React/TypeScript dashboard, vanilla JS driver PWA — no framework changes
- **CSS approach**: Tailwind CSS + DaisyUI for professional logistics SaaS look (no React component libraries requiring build changes)
- **Infrastructure**: Must work with existing Docker Compose setup (OSRM, VROOM, PostgreSQL)
- **Driver PWA**: Must remain a standalone HTML/JS app (no build step) — drivers install it as PWA on phones
- **Depot**: Vatakara coordinates from `config.py` are the single source of truth
- **Kerala-specific**: Monsoon safety multipliers, MVD compliance (no countdown timers), outdoor readability

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Tailwind CSS + DaisyUI for UI | Clean logistics SaaS look without React component library lock-in; works for both server-rendered and React pages | — Pending |
| Playwright + Context7 MCPs installed | Visual feedback during UI development + live docs for Leaflet/Tailwind APIs | — Pending |
| Fix geocoding before UI overhaul | Silent order drops are data-integrity bugs; UI polish on broken data is wasted effort | — Pending |

---
*Last updated: 2026-03-01 after initialization*
