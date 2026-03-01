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
- ✓ Tailwind 4 + DaisyUI 5 installed with collision-safe prefix — v1.0
- ✓ HTTP security headers (CSP, CORS hardening, Permissions-Policy) — v1.0
- ✓ Geocoding failure reporting with per-row reasons — v1.0
- ✓ Import summary UI (success/partial/zero states) — v1.0
- ✓ Depot coordinates audited (Vatakara 11.62°N throughout pipeline) — v1.0
- ✓ CSV row-level validation before geocoding — v1.0

### Active

- [ ] Professional UI redesign — sleek logistics dashboard aesthetic (research best themes)
- [ ] Geocoding cache normalization fix — inconsistent DB vs file cache causing duplicate locations
- [ ] Duplicate location detection — flag orders resolving to same GPS coordinates
- [ ] Geocoding cost tracking — cache hit vs API call indicator per address
- [ ] Elegant error handling across pipeline — structured errors, retries, graceful degradation
- [ ] Code quality cleanup — remove dead code, refactor main.py, fix driver names
- [ ] Well-rounded unit tests — property-based, factory fixtures, external API mocks, coverage gate
- [ ] Streamlined installation and documentation — easy setup guide, clear README

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
- **Current state**: v1.0 shipped — foundation, security, and data integrity complete. 380 tests passing. 16.6k Python LOC, 3.3k TypeScript LOC.
- **Known issues**: Geocoding cache normalization inconsistency causes duplicate map locations; UI needs professional redesign
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
*Last updated: 2026-03-01 after v1.0 milestone*
