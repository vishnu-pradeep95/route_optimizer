# Stack Research

**Domain:** Logistics SaaS — LPG delivery route optimization dashboard + driver PWA (Kerala, India)
**Researched:** 2026-03-01
**Confidence:** MEDIUM-HIGH (most versions verified via PyPI/npm; see per-item notes)
**Scope:** Subsequent milestone additions — UI polish, security hardening, test improvements. No framework changes.

---

## Context: What Already Exists (Do Not Re-research)

The base stack (FastAPI 0.129, React 19 + Vite 7, PostgreSQL 16 + PostGIS, OSRM, VROOM, SQLAlchemy 2, asyncpg, Alembic, pytest 9, pytest-asyncio 1.3) is already in place and must not change. This document covers **additive** libraries only.

---

## Recommended Stack

### UI Layer — Professional Logistics Dashboard

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Tailwind CSS | 4.2.1 | Utility-first CSS for dashboard and PWA | v4 is current stable (released ~Feb 2026); CSS-variable-based theming, no JS config file, 34 kB install footprint. The project already committed to Tailwind in PROJECT.md. |
| DaisyUI | 5.5.19 | Semantic component classes on top of Tailwind | v5 is Tailwind v4-native with zero deps, 34 kB compressed CSS (down from 137 kB in v4). Ships Table, Badge, Stats, Card, Navbar, Drawer, Modal — all needed for a logistics SaaS look. |
| Leaflet | 1.9.4 | Interactive map for dashboard and driver PWA | Stay on 1.9.4 (stable). Leaflet 2.0 is alpha (released Aug 2025) with breaking API changes (module imports replace global `L`); upgrading during a UI polish phase adds risk with no user benefit. |
| Leaflet.markercluster | 1.5.3 | Cluster 100–500 delivery pins into manageable groups | Purpose-built, maintained by Leaflet org, handles 10 k markers in Chrome. Critical for readability when 300+ orders are on map. |

**Confidence:** HIGH — Tailwind 4.2.1 and DaisyUI 5.5.19 versions verified on npm (2026-03-01). Leaflet 1.9.4 confirmed stable; 2.0 confirmed alpha-only per official blog. Leaflet.markercluster 1.5.3 widely used, maintained by Leaflet org.

### Security Hardening Libraries

| Library | Version | Purpose | Why Recommended |
|---------|---------|---------|-----------------|
| PyJWT | 2.11.0 | JWT encode/decode for API auth tokens | FastAPI docs updated in 2025 to recommend PyJWT over python-jose (python-jose is abandoned, last release ~3 years ago). PyJWT 2.11.0 released Jan 30, 2026 — actively maintained. |
| pwdlib | 0.3.0 | Password hashing (bcrypt/argon2 backends) | passlib is abandoned (last release 2020, breaks on Python 3.13). FastAPI docs now use pwdlib in examples. pwdlib 0.3.0 released Oct 2025 supports bcrypt and argon2. Install with `pip install "pwdlib[bcrypt]"`. |
| Secweb | 1.11.0 | HTTP security headers middleware for Starlette/FastAPI | Applies CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy in one `SecWeb(app=app)` call. Lightweight, no external deps. Use instead of rolling headers manually. |

**Confidence:** HIGH for PyJWT (verified PyPI, FastAPI GitHub discussion #11345 confirms switch). HIGH for pwdlib (verified PyPI, FastAPI GitHub discussion #11773). MEDIUM for Secweb (version confirmed via libraries.io; last release cadence not fully verified — monitor GitHub for freshness).

### Testing Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest-cov | 7.0.0 | Coverage measurement integrated with pytest | Always — add to CI to gate coverage regression. Note: v7 removes `.pth`-based subprocess measurement; use `coverage`'s native patch for subprocess coverage if needed. |
| hypothesis | 6.151.9 | Property-based testing (auto-generates edge cases) | Use for geocoding coordinate validators, route weight calculations, CSV parsing edge cases. Verifies properties across all valid inputs, not just hand-picked examples. |
| factory_boy | 3.3.3 | Test fixture factories (replaces hard-coded dicts) | Use to build `Order`, `Route`, `Vehicle` objects in tests without duplicating fixture boilerplate. Integrate with pytest via `pytest-factoryboy`. |
| respx | 0.22.0 | Mock httpx calls in tests | Use to mock Google Geocoding API, OSRM, and VROOM HTTP calls in unit tests without making real network requests. Works with both sync and async httpx. |

**Confidence:** HIGH — all four versions verified directly on PyPI (hypothesis 6.151.9 released Feb 2026; factory_boy 3.3.3 Feb 2025; pytest-cov 7.0.0 Sep 2025; respx 0.22.0 Dec 2024).

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| pytest-asyncio 1.3.0 | Async test support (already in stack) | Set `asyncio_mode = "auto"` in `pyproject.toml` or `pytest.ini` to avoid per-test `@pytest.mark.asyncio` decorators. Already installed — just configure mode. |
| Playwright (already planned) | Visual regression and E2E testing of dashboard | PROJECT.md notes it is planned. Use `@playwright/test` with Vite dev server for visual checks of Tailwind/DaisyUI components. |

---

## Installation

### Python (add to requirements.txt)

```bash
# Security hardening
pip install "PyJWT==2.11.0" "pwdlib[bcrypt]==0.3.0" "Secweb==1.11.0"

# Testing improvements
pip install "pytest-cov==7.0.0" "hypothesis==6.151.9" "factory-boy==3.3.3" "respx==0.22.0"
```

### Node / Frontend

```bash
# Core UI
npm install tailwindcss@4.2.1 daisyui@5.5.19

# Leaflet clustering (for dashboard map)
npm install leaflet.markercluster@1.5.3
npm install -D @types/leaflet.markercluster
```

### Driver PWA (no build step — CDN links)

```html
<!-- Tailwind v4 browser build (development only; use CLI build for production) -->
<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4"></script>

<!-- DaisyUI v5 (requires Tailwind v4) -->
<link href="https://cdn.jsdelivr.net/npm/daisyui@5/dist/full.min.css" rel="stylesheet"/>

<!-- Leaflet stable -->
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>

<!-- Marker clustering -->
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css"/>
<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
```

**Note:** Tailwind `@tailwindcss/browser` CDN is explicitly marked "development/prototypes only" in official docs. The driver PWA needs a production-ready CSS solution. Options: (a) pre-build a `driver.css` artifact via Tailwind CLI during Docker build, or (b) use DaisyUI's standalone CDN CSS which does not require Tailwind at runtime. Recommendation: pre-build and serve static CSS — keeps the PWA's no-build-step constraint while avoiding CDN dependency in production.

### pytest.ini / pyproject.toml configuration

```ini
[pytest]
asyncio_mode = auto
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| DaisyUI 5 + Tailwind 4 | shadcn/ui + Tailwind | If the project were a new greenfield React app with full build pipeline control. shadcn requires per-component copy-paste into src; incompatible with no-build-step PWA constraint. |
| DaisyUI 5 + Tailwind 4 | Ant Design / MUI | If desktop-app feel and comprehensive pre-built React components were needed. Adds large bundle, opinionated theming, and is overkill for a single-team logistics tool. |
| Leaflet 1.9.4 | Leaflet 2.0 alpha | Do not use 2.0 until stable — breaking API (no global `L`), all plugins must be updated to ESM imports, and existing driver PWA code would break. Re-evaluate when 2.0.0 stable ships. |
| PyJWT 2.11.0 | python-jose | Do not use python-jose — abandoned, 3-year-old codebase, security patches not being applied. FastAPI's own documentation deprecated it in 2025. |
| pwdlib 0.3.0 | passlib | Do not use passlib on Python 3.12+. It raises deprecation warnings on 3.12 and will break on 3.13. pwdlib is passlib's spiritual successor for bcrypt/argon2. |
| pwdlib 0.3.0 | argon2-cffi directly | argon2-cffi works but lacks the convenience wrapper. Use pwdlib[argon2] to get the same backend with a unified API. Only use argon2-cffi directly if pwdlib's API becomes a blocker. |
| Secweb | secure.py (TypeError/secure) | secure.py is more flexible for custom header policies. Use it instead of Secweb if CSP needs fine-grained per-route control. Both are valid; Secweb is simpler for an internal tool. |
| respx | pytest-httpx | Either works. respx has slightly better documentation and a more ergonomic fixture API. pytest-httpx is a fine alternative if respx causes friction. |
| hypothesis | manual parametrize | Use hypothesis for coordinate validators and weight calculations where the input space is large and continuous. Use plain `@pytest.mark.parametrize` for discrete enumerable cases (e.g., CSV column permutations). |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| python-jose | Abandoned ~2022; no security patches; FastAPI docs explicitly dropped it in 2025 | PyJWT 2.11.0 |
| passlib | Last released 2020; triggers deprecation warnings on Python 3.12; breaks on 3.13 | pwdlib 0.3.0 with bcrypt backend |
| Leaflet 2.0.0-alpha | Alpha stage, breaking API changes, all plugins (markercluster etc.) not yet ported to ESM | Leaflet 1.9.4 (stable) |
| @tailwindcss/browser CDN in production | Official docs say "development and prototypes only"; adds runtime JS overhead | Pre-build CSS with Tailwind CLI during Docker image build |
| Ant Design / MUI / Chakra | Heavy bundle, opinionated theming clashes with DaisyUI, unnecessary for internal logistics tool | DaisyUI 5 components |
| Wildcard CORS (`allow_origins=["*"]`) | Breaks `allow_credentials=True`; exposes API to any origin | Explicit origin list from `CORS_ALLOWED_ORIGINS` env var (already in config) |

---

## Stack Patterns by Context

**Tailwind in React dashboard (has build step):**
- Install `tailwindcss` + `@tailwindcss/vite` plugin, configure `vite.config.ts`
- Tailwind v4 uses CSS `@import "tailwindcss"` in place of v3's `@tailwind base/components/utilities`
- DaisyUI v5 is a Tailwind plugin: `plugins: [daisyui]` in CSS or JS config

**Tailwind in driver PWA (no build step):**
- Pre-build a static `driver.css` during Docker image build using `npx tailwindcss --input driver.css --output dist/driver.css --minify`
- Reference pre-built CSS via `<link>` in `index.html`
- Do NOT use `@tailwindcss/browser` in production

**Security headers — where to put them:**
- Add `SecWeb(app=app)` before any route handlers in `main.py` lifespan setup
- Tune CSP to allow Leaflet tile URLs (`unpkg.com`, OSM tile servers) and inline script nonces if needed
- Keep CORS config driven from `CORS_ALLOWED_ORIGINS` env var (already exists — do not hardcode)

**Property-based testing with hypothesis for geospatial code:**
- Use `hypothesis.strategies.floats(min_value=-90, max_value=90)` for lat, `floats(min_value=-180, max_value=180)` for lon
- Target functions: `haversine_distance()`, `is_within_delivery_radius()`, CSV geocode normalization
- Mark slow hypothesis tests with `@settings(max_examples=50)` to keep CI fast

**Factory_boy for delivery domain objects:**
```python
import factory
from apps.kerala_delivery.models import Order

class OrderFactory(factory.Factory):
    class Meta:
        model = Order
    customer_id = factory.Sequence(lambda n: f"CUST{n:04d}")
    lat = factory.Faker("latitude")
    lon = factory.Faker("longitude")
    cylinders = factory.Faker("pyint", min_value=1, max_value=5)
```

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| tailwindcss@4.2.1 | daisyui@5.5.19 | DaisyUI v5 requires Tailwind v4. DaisyUI v4 requires Tailwind v3. Do not mix versions. |
| daisyui@5.5.19 | React 19 | DaisyUI is CSS-only; works with any JS framework or vanilla JS. No React peer dep issues. |
| Leaflet@1.9.4 | leaflet.markercluster@1.5.3 | Compatible. Do NOT use Leaflet 2.0 alpha with markercluster — plugins not ported yet. |
| PyJWT@2.11.0 | FastAPI@0.129.1 | No conflicts. PyJWT has no FastAPI peer dependency. |
| pwdlib@0.3.0 | Python 3.12.3 | Works. Python 3.13 support confirmed by pwdlib's design intent. |
| pytest-asyncio@1.3.0 | pytest@9.0.2 | Already installed together; confirmed compatible. Set `asyncio_mode = auto`. |
| hypothesis@6.151.9 | pytest@9.0.2 | Works. hypothesis integrates with pytest natively via plugin discovery. |
| respx@0.22.0 | httpx@0.28.1 | respx 0.22.0 requires httpx>=0.25.0. Project has httpx 0.28.1. |

---

## Sources

- [DaisyUI npm](https://www.npmjs.com/package/daisyui) — v5.5.19 current as of 2026-03-01 (verified)
- [DaisyUI v5 release notes](https://daisyui.com/docs/v5/?lang=en) — Tailwind 4 compatibility, zero deps, 34 kB (verified)
- [Tailwind CSS v4.0 blog](https://tailwindcss.com/blog/tailwindcss-v4) — v4 release, CSS-variable architecture (official)
- [tailwindcss npm](https://www.npmjs.com/package/tailwindcss) — v4.2.1 current (verified)
- [Leaflet 2.0 alpha blog](https://leafletjs.com/2025/05/18/leaflet-2.0.0-alpha.html) — alpha status confirmed (official)
- [PyJWT PyPI](https://pypi.org/project/PyJWT/) — v2.11.0 released Jan 30, 2026 (verified)
- [FastAPI discussion #11345](https://github.com/fastapi/fastapi/discussions/11345) — python-jose abandonment, PyJWT recommendation (official FastAPI team)
- [pwdlib PyPI](https://pypi.org/project/pwdlib/) — v0.3.0 released Oct 2025, bcrypt+argon2 backends (verified)
- [FastAPI discussion #11773](https://github.com/fastapi/fastapi/discussions/11773) — passlib abandonment, pwdlib recommendation (official FastAPI team)
- [pytest-cov PyPI](https://pypi.org/project/pytest-cov/) — v7.0.0 released Sep 2025 (verified)
- [hypothesis PyPI](https://pypi.org/project/hypothesis/) — v6.151.9 released Feb 2026 (verified)
- [factory-boy PyPI](https://pypi.org/project/factory-boy/) — v3.3.3 released Feb 2025 (verified)
- [respx PyPI](https://pypi.org/project/respx/) — v0.22.0 released Dec 2024, httpx>=0.25 required (verified)
- [pytest-asyncio PyPI](https://pypi.org/project/pytest-asyncio/) — v1.3.0 released Nov 2025 (verified)
- [Secweb libraries.io](https://libraries.io/pypi/Secweb) — v1.11.0 (MEDIUM confidence; release date not pinned)
- [OWASP REST Security Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html) — security headers checklist
- [FastAPI OWASP hardening guide](https://oneuptime.com/blog/post/2025-01-06-fastapi-owasp-security/view) — MEDIUM confidence (single source, 2025)
- [FastAPI async tests docs](https://fastapi.tiangolo.com/advanced/async-tests/) — asyncio_mode=auto pattern (official)

---

*Stack research for: Kerala LPG Delivery Route Optimizer — UI + Security + Testing milestone*
*Researched: 2026-03-01*
