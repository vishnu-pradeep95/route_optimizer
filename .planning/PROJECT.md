# Kerala LPG Delivery Route Optimizer

## What This Is

A route optimization system for LPG cylinder delivery in Kerala's Vatakara region. An office employee uploads CDCMS export CSVs, the system geocodes addresses, optimizes delivery routes across a 13-vehicle fleet (Piaggio Ape Xtra LDX), and generates QR codes/links that drivers open on their phones via a PWA for turn-by-turn navigation. The dashboard provides a professional logistics SaaS interface with skeleton loading, status badges, and responsive layout; the driver PWA is optimized for outdoor readability with WCAG AAA contrast and large touch targets.

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
- ✓ Geocoding cache normalization — single address key across all cache layers — v1.1
- ✓ DB-only geocoding cache — file-based JSON cache deprecated — v1.1
- ✓ Duplicate location detection — warnings for orders within 15m proximity — v1.1
- ✓ Geocoding cost tracking — cache hits vs API calls with estimated cost — v1.1
- ✓ Dashboard UI overhaul — DaisyUI components, lucide-react icons, responsive sidebar — v1.1
- ✓ Skeleton loading and empty states on all dashboard pages — v1.1
- ✓ Tabular-number font variant for numeric column alignment — v1.1
- ✓ Color-coded status badges (green/amber/red) — v1.1
- ✓ QR sheet print optimization (210px codes, cross-browser CSS fragmentation) — v1.1
- ✓ Driver PWA hero card next-stop architecture — v1.1
- ✓ Delivery progress bar with header stats — v1.1
- ✓ Refresh button with "Last updated" timestamp — v1.1
- ✓ 60px+ touch targets for all primary driver actions — v1.1
- ✓ WCAG AAA contrast ratio for outdoor readability — v1.1
- ✓ Offline route data persistence — v1.1
- ✓ API dead code removal (_build_fleet, unused imports, stale OSRM_URL, incorrect docstrings) — v1.2
- ✓ Typed PostGIS geometry helpers eliminating type:ignore suppressions — v1.2
- ✓ Single /api/config endpoint for depot coords, safety multiplier, office phone — v1.2
- ✓ Driver PWA safety: real phone from API, GPS leak fix, styled offline dialog — v1.2
- ✓ PWA installability: proper PNG icons, SW pre-cache for tailwind.css, debug logging gate — v1.2
- ✓ Dashboard cleanup: dead CSS removal, design token consistency, TypeScript type safety — v1.2
- ✓ Exhaustive StatusBadge switch with compile-time safety — v1.2
- ✓ Batch route loading (GET /api/routes?include_stops=true) replacing N+1 — v1.2
- ✓ Driver-verified geocode wiring into delivery status endpoint — v1.2
- ✓ Duplicate detection thresholds validated against production data — v1.2
- ✓ One-command WSL bootstrap with Docker CE auto-install and environment guards — v1.3
- ✓ Daily startup script with health polling and failure diagnosis — v1.3
- ✓ CSV format reference with error glossary and address cleaning pipeline — v1.3
- ✓ README/DEPLOY.md accuracy and non-technical audience restructure — v1.3
- ✓ Plain-English error messages for upload validation and geocoding — v1.3
- ✓ Distribution build with compiled licensing module (.pyc) — v1.3
- ✓ OSRM Docker image pinned to v5.27.1 for deployment resilience — v1.3
- ✓ Error message documentation synced with code (25 messages traced) — v1.3
- ✓ Playwright E2E test suite (38 tests: API, Driver PWA, Dashboard, License) — v1.4
- ✓ CI/CD pipeline with E2E tests on push to main, failure artifacts, status badge — v1.4
- ✓ Graceful shutdown script with --gc garbage collection mode — v1.4
- ✓ Distribution tarball verification (automated endpoint checks in isolated stack) — v1.4

### Active

#### Current Milestone: v1.4 Ship-Ready QA

**Goal:** Verify the full customer delivery pipeline works end-to-end — automated E2E tests, CI/CD health, clean install verification, distribution documentation, and operational scripts for graceful shutdown.

**Target features:**
- [x] Automated Playwright E2E tests (upload flow, driver PWA, dashboard)
- [x] CI/CD pipeline fix and Playwright integration
- [x] Stop script with garbage collection (containers, images, logs)
- [x] Clean install verification from tarball
- [ ] Distribution documentation (build-dist.sh workflow, .pyc licensing, customer delivery)
- [ ] Production vs development environment documentation
- [ ] License lifecycle documentation (generate → deliver → activate → renew → troubleshoot)
- [ ] Google API key troubleshooting guide

### Out of Scope

- Mobile native apps — PWA is sufficient for driver use case
- Real-time chat/messaging — not needed for delivery workflow
- Multi-tenant/multi-region — Vatakara-only for now
- Payment processing — handled outside this system
- Customer-facing tracking — drivers and office staff only
- Drag-and-drop route reordering — undermines VROOM optimizer
- Turn-by-turn navigation in-app — Google Maps handles this
- Photo proof-of-delivery — camera API complexity, upload on spotty Kerala networks
- Countdown timers for delivery windows — prohibited for Kerala MVD compliance
- Pre-cached map tiles — 50-100MB+ storage, unpredictable on low-memory Android
- Fuzzy address matching (Levenshtein) — false positives assign wrong coordinates
- Multiple geocoding provider fallback — mixing providers creates inconsistency
- Reverse geocoding for telemetry pings — $45K/year at scale

## Context

- **Domain**: LPG cylinder delivery in Kerala, India (Vatakara region)
- **Fleet**: 13 Piaggio Ape Xtra LDX vehicles, 446 kg max / 30 cylinders each
- **Data source**: CDCMS (Centralized Distribution Customer Management System) CSV exports
- **Infrastructure**: Docker Compose with OSRM (Kerala OSM data), VROOM solver, PostgreSQL/PostGIS
- **Current state**: v1.4 in progress — Phase 23 complete (E2E tests, CI/CD, stop.sh, verify-dist.sh). 2.7k Python LOC, 3.7k TypeScript LOC, 2.0k HTML/JS LOC, 1.9k Shell LOC, ~1k test LOC (~11.3k total). Remaining v1.4: documentation consolidation.
- **Known tech debt**: Physical Android device testing for outdoor contrast; 8 GB laptop testing for install script OSRM OOM validation.
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
| Tailwind CSS + DaisyUI for UI | Clean logistics SaaS look without React component library lock-in | ✓ Good — consistent across dashboard and PWA |
| Playwright + Context7 MCPs installed | Visual feedback during UI development + live docs | ✓ Good — caught bugs in visual verification |
| Fix geocoding before UI overhaul | Silent order drops are data-integrity bugs; UI polish on broken data is wasted effort | ✓ Good — clean data foundation before cosmetics |
| normalize_address() stdlib-only (unicodedata, re) | No external dependencies for cache key normalization | ✓ Good — pure function, 15 tests, zero dependencies |
| DB-only caching, deprecate file cache | Single source of truth eliminates cache key mismatch | ✓ Good — eliminated duplicate map pins |
| lucide-react for SVG nav icons | Consistent stroke width, tree-shakeable, React-native components | ✓ Good — unified icon system across all pages |
| CSS-only responsive sidebar | No JS matchMedia; mobile-first min-width breakpoints at 768px and 1280px | ✓ Good — simpler than JS-based approach |
| DaisyUI drawer for mobile nav | Native checkbox toggle, zero JS state management | ✓ Good — works without framework overhead |
| WCAG AAA contrast for driver PWA | Outdoor readability in Kerala sunlight conditions | ✓ Good — two-tier text hierarchy, saffron accents |
| Hero card + compact list architecture | Only next pending stop gets action buttons; rest are read-only | ✓ Good — reduces cognitive load for drivers |
| Native `<dialog>` for fail confirmation | Dark-themed, accessible, replaces browser confirm() | ✓ Good — consistent with PWA aesthetic |
| Public `/api/config` endpoint | Serve depot coords, safety multiplier, phone number from single source | ✓ Good — eliminates frontend hardcoding |
| `QR_SHEET_DURATION_BUFFER` named constant | Replace magic 1.2 multiplier in QR sheet generation | ✓ Good — single source of truth in config.py |
| `console.log` override for debug gating | No-op override vs wrapping call sites | ✓ Good — zero call-site changes needed |
| Pure Python PNG icon generation | struct+zlib instead of Pillow/image library | ✓ Good — zero new dependencies |
| Exhaustive switch for StatusBadge | TypeScript never-typed default ensures compile-time safety | ✓ Good — catches missing status values at build |
| Optional `include_stops` query param | Batch route data via existing endpoint, backward compatible | ✓ Good — no breaking changes for existing consumers |
| Direct `repo.save_geocode_cache` call | Skip CachedGeocoder instantiation for driver-verified saves | ✓ Good — simpler, avoids unnecessary Google API key validation |
| Two-phase resume with marker file | Docker group membership requires session restart | ✓ Good — seamless bootstrap flow across reboot |
| Guard-first architecture in bootstrap.sh | All environment checks (WSL version, filesystem, RAM) run before any installation | ✓ Good — fast-fail prevents partial installs |
| 60s health timeout for daily startup | Shorter than install.sh 300s; services warm in ~10s | ✓ Good — reasonable for daily use |
| "Problem -- fix action" error pattern | All user-facing errors follow consistent format | ✓ Good — office employees know what to do |
| Pin OSRM to v5.27.1 | latest tag dropped /bin/bash, breaking fresh deployments | ✓ Good — unblocked all deployments |
| /bin/sh instead of /bin/bash for OSRM | POSIX constructs only; resilient to base image changes | ✓ Good — works on both Debian and Alpine |
| ERROR-MAP.md traceability artifact | Maps 25 error messages to source code paths | ✓ Good — prevents documentation drift |
| Playwright 4-project config | Separate projects for api, driver-pwa, dashboard, license with different base URLs and viewports | ✓ Good — isolated test contexts, parallel-safe |
| Docker Compose override for license tests | Isolated production-mode container on port 8001 | ✓ Good — tests real license enforcement without affecting dev stack |
| Sequential story pattern for PWA tests | Shared BrowserContext across ordered tests with UI+API dual verification | ✓ Good — tests real user flow without artificial resets |
| Truncate logs before compose down | docker compose down removes containers and their log files | ✓ Good — GC captures log paths while containers exist |
| Standalone compose for verification | Docker Compose merges ports additively in overrides, causing conflicts | ✓ Good — isolated stack with no name/port collisions |
| Skip OSRM/VROOM in tarball verification | Endpoints don't require routing; saves 300+ MB download and minutes of init | ✓ Good — verification runs in ~30s instead of 10+ min |

---
*Last updated: 2026-03-08 after Phase 23*
