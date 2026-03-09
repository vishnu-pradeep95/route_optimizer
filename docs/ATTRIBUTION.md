# Third-Party Attribution

> **Audience:** Developer

This document lists all third-party software used in this project, their licenses,
and required attribution text. It is included in customer distributions.

---

## Copyleft / Restrictive Licenses (MUST READ)

These packages have licenses that impose obligations beyond simple attribution.
Review the compliance notes before modifying or redistributing.

| Package | Version | License | Obligation | Compliance Notes |
|---------|---------|---------|------------|------------------|
| psycopg | 3.3.3 | LGPL-3.0-only | Users must be able to replace/relink the library; modifications to psycopg source must be shared | Used unmodified as pip package; users can replace with `pip install psycopg==newer` |
| psycopg-binary | 3.3.3 | LGPL-3.0-only | Same as psycopg (bundled C extension) | Same as psycopg |
| certifi | 2026.1.4 | MPL-2.0 | Modified source files must remain MPL-2.0; unmodified use requires no action | Used unmodified |
| Secweb | 1.30.10 | MPL-2.0 | Same as certifi (file-level copyleft) | Used unmodified |
| PostGIS 3.5 (Docker image) | GPL-2.0 | Source disclosure if modified and distributed | Used as unmodified Docker image -- no source disclosure required |

**Summary of compliance posture:** All copyleft packages are used unmodified as
standard pip packages or Docker images. No source modifications have been made.
The LGPL obligation to allow replacement is satisfied because users can
`pip install` a different version of psycopg at any time. The MPL obligation
applies only to modified source files, and no modifications have been made.

---

## Infrastructure & Data Sources

Components with specific licensing or attribution requirements:

| Component | License | Required Attribution |
|-----------|---------|---------------------|
| OpenStreetMap data | ODbL (Open Database License) | Required (see [attribution text](#openstreetmap) below) |
| OSRM v5.26.0 | BSD-2-Clause | Copyright notice (see [attribution text](#osrm) below) |
| VROOM v1.14.0 | BSD-2-Clause | Copyright notice (see [attribution text](#vroom) below) |
| PostgreSQL 16 | PostgreSQL License (permissive) | Copyright notice |
| Caddy 2 | Apache-2.0 | Copyright notice |
| MapLibre GL JS 5 | BSD-3-Clause | Copyright notice (see [attribution text](#maplibre-gl-js) below) |
| Google Maps Platform | Google ToS (proprietary) | Google attribution must be displayed; cannot remove Google-provided attribution (see [attribution text](#google-maps) below) |

---

## Python Dependencies

59 packages from `requirements.txt`, organized by license type.

### MIT License

| Package | Version |
|---------|---------|
| alembic | 1.18.4 |
| annotated-doc | 0.0.4 |
| annotated-types | 0.7.0 |
| anyio | 4.12.1 |
| charset-normalizer | 3.4.4 |
| Deprecated | 1.3.1 |
| et_xmlfile | 2.0.0 |
| fastapi | 0.129.1 |
| GeoAlchemy2 | 0.18.1 |
| greenlet | 3.3.2 |
| h11 | 0.16.0 |
| httptools | 0.7.1 |
| iniconfig | 2.3.0 |
| limits | 5.8.0 |
| Mako | 1.3.10 |
| openpyxl | 3.1.5 |
| packaging | 26.0 |
| pillow | 12.1.1 |
| pluggy | 1.6.0 |
| pydantic | 2.12.5 |
| pydantic_core | 2.41.5 |
| pyogrio | 0.12.1 |
| pyproj | 3.7.2 |
| pytest | 9.0.2 |
| python-dateutil | 2.9.0.post0 |
| PyYAML | 6.0.3 |
| qrcode | 8.2 |
| six | 1.17.0 |
| slowapi | 0.1.9 |
| SQLAlchemy | 2.0.46 |
| typing-inspection | 0.4.2 |
| uvloop | 0.22.1 |
| watchfiles | 1.1.1 |

### BSD-3-Clause

| Package | Version |
|---------|---------|
| click | 8.3.1 |
| httpcore | 1.0.9 |
| httpx | 0.28.1 |
| idna | 3.11 |
| MarkupSafe | 3.0.3 |
| numpy | 2.4.2 |
| pandas | 3.0.1 |
| geopandas | 1.1.2 |
| python-dotenv | 1.2.1 |
| shapely | 2.1.2 |
| starlette | 0.52.1 |
| uvicorn | 0.41.0 |
| websockets | 16.0 |

### BSD-2-Clause

| Package | Version |
|---------|---------|
| Pygments | 2.19.2 |
| wrapt | 2.1.1 |

### Apache-2.0

| Package | Version |
|---------|---------|
| asyncpg | 0.31.0 |
| python-multipart | 0.0.22 |
| pytest-asyncio | 1.3.0 |
| requests | 2.32.5 |

### PSF-2.0 (Python Software Foundation)

| Package | Version |
|---------|---------|
| typing_extensions | 4.15.0 |

### LGPL-3.0-only

See [Copyleft / Restrictive Licenses](#copyleft--restrictive-licenses-must-read) above.

| Package | Version |
|---------|---------|
| psycopg | 3.3.3 |
| psycopg-binary | 3.3.3 |

### MPL-2.0

See [Copyleft / Restrictive Licenses](#copyleft--restrictive-licenses-must-read) above.

| Package | Version |
|---------|---------|
| certifi | 2026.1.4 |
| Secweb | 1.30.10 |

### Other

| Package | Version | License |
|---------|---------|---------|
| urllib3 | 2.6.3 | MIT |

---

## JavaScript Dependencies

10 packages from `apps/kerala_delivery/dashboard/package.json` (production dependencies only):

| Package | Version | License |
|---------|---------|---------|
| react | 19.2.0 | MIT |
| react-dom | 19.2.0 | MIT |
| maplibre-gl | 5.18.0 | BSD-3-Clause |
| react-map-gl | 8.1.0 | MIT |
| daisyui | 5.5.19 | MIT |
| tailwindcss | 4.2.1 | MIT |
| @tailwindcss/vite | 4.2.1 | MIT |
| framer-motion | 12.34.3 | MIT |
| lucide-react | 0.575.0 | ISC |
| @fontsource/dm-sans | 5.2.8 | OFL-1.1 (font), MIT (package) |
| @fontsource/ibm-plex-mono | 5.2.7 | OFL-1.1 (font), MIT (package) |

---

## Fonts

All fonts used in this project are licensed under the **SIL Open Font License 1.1 (OFL-1.1)**, which allows free use, embedding, and redistribution. Include the copyright notice if redistributing font files.

| Font | Source | License |
|------|--------|---------|
| DM Sans | @fontsource/dm-sans npm package | OFL-1.1 |
| IBM Plex Mono | @fontsource/ibm-plex-mono npm package | OFL-1.1 |
| Outfit | Google Fonts (loaded via CDN) | OFL-1.1 |
| JetBrains Mono | Google Fonts (loaded via CDN) | OFL-1.1 |

---

## Required Attribution Text

The following attribution text blocks must be preserved in distributions.

### OpenStreetMap

> Contains information from OpenStreetMap (https://www.openstreetmap.org),
> which is made available here under the Open Database License (ODbL) by the
> OpenStreetMap Foundation (OSMF).
> https://www.openstreetmap.org/copyright

### OSRM

> Copyright (c) 2024, Project OSRM contributors. All rights reserved.
> Licensed under BSD-2-Clause.

### VROOM

> Copyright (c) 2015-2024, Julien Coupey. All rights reserved.
> Licensed under BSD-2-Clause.

### Google Maps

> This product uses the Google Maps Platform. Google Maps is a trademark of
> Google LLC. Use subject to the Google Maps Platform Terms of Service
> (https://cloud.google.com/maps-platform/terms).

### MapLibre GL JS

> Copyright (c) 2020-2024, MapLibre contributors. All rights reserved.
> Licensed under BSD-3-Clause.
