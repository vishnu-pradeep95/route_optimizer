# Phase 24: Documentation Consolidation - Research

**Researched:** 2026-03-08
**Domain:** Technical documentation (Markdown), dependency licensing, environment configuration
**Confidence:** HIGH

## Summary

Phase 24 creates 5 documentation artifacts covering distribution workflow, license lifecycle, environment comparison, Google Maps troubleshooting, and third-party attribution. This is a pure documentation phase -- no code changes except updating `scripts/build-dist.sh` to include ATTRIBUTION.md in the tarball and adding a documentation index to README.md.

The project already has 7 markdown docs at the root level (README.md, DEPLOY.md, SETUP.md, LICENSING.md, CSV_FORMAT.md, GUIDE.md, CLAUDE.md) with established patterns: code blocks for commands, tables for structured data, audience callout boxes, and ASCII diagrams. All existing docs use consistent formatting that the new docs must match.

**Primary recommendation:** Write each document by extracting information already present in source code, scripts, and compose files -- this phase is synthesis, not invention. The dependency audit requires scanning both `requirements.txt` (59 Python packages) and `package.json` (10 JS dependencies) for license types, with special attention to 4 copyleft-licensed packages that need flagging.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Create 4 new standalone files in project root: DISTRIBUTION.md, ENV-COMPARISON.md, GOOGLE-MAPS.md, ATTRIBUTION.md
- Extend existing LICENSING.md with grace period monitoring, renewal, and 503 troubleshooting sections (don't replace -- add to existing 266-line file)
- Add a "Documentation" section to README.md listing all doc files with one-line descriptions
- All docs live in project root alongside existing docs (README.md, DEPLOY.md, GUIDE.md, etc.)
- DISTRIBUTION.md: Developer-level. Assume CLI and Docker familiarity. Exact commands, explain flags, skip preamble.
- LICENSING.md extensions: Developer-level throughout. Consistent with existing LICENSING.md style.
- ENV-COMPARISON.md: Developer-level. Comparison table format for quick reference.
- GOOGLE-MAPS.md: Plain-English for office employees. Step-by-step text with "you should see..." expected outputs. No screenshots (go stale when Google updates UI).
- ATTRIBUTION.md: Developer-level. Table + required attribution text blocks.
- Full dependency audit: scan all Python and JS dependencies for license types, not just key infrastructure
- Flag any copyleft (GPL) or restrictive licenses
- Summary table (component, license type, obligation) at top, then full required attribution text blocks below
- ATTRIBUTION.md must be bundled in tarball -- update build-dist.sh to include it in the distribution
- Key infrastructure with specific obligations: OSM data (ODbL), OSRM (BSD-2), VROOM (BSD-2), Leaflet (BSD-2), MapLibre (BSD-3), Google Maps (ToS)
- Inline links at point of need: link where the reader needs it, e.g., "see [LICENSING.md](LICENSING.md#generating-keys)"
- No master index page beyond the README documentation section
- DISTRIBUTION.md includes exact commands inline (copy-pasteable full workflow)
- Exact commands with flag explanations, not just "run the script"

### Claude's Discretion
- Whether to add cross-references between LICENSING.md 503 troubleshooting and GOOGLE-MAPS.md (distinguishing license 503 from geocoding errors)
- Exact heading structure and section ordering within each document
- How to organize the full dependency audit (by category, alphabetical, by license type)
- Level of detail in ENV-COMPARISON.md comparison table

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DOCS-01 | Distribution workflow documented: build tarball -> generate license -> deliver to customer -> verify install | `scripts/build-dist.sh`, `scripts/verify-dist.sh`, `scripts/deploy.sh`, `LICENSING.md` sections on key generation -- all source material identified and read |
| DOCS-02 | License lifecycle documented: generate -> deliver -> activate -> monitor grace -> renew -> troubleshoot 503 | `core/licensing/license_manager.py` (GRACE_PERIOD_DAYS=7, LicenseStatus enum, validate_license flow), existing LICENSING.md (266 lines) -- extension points identified |
| DOCS-03 | Production vs development environment comparison documented | `docker-compose.yml` vs `docker-compose.prod.yml`, `.env.example` vs `.env.production.example`, existing LICENSING.md "Dev vs Production" section -- all sources read and diffed |
| DOCS-04 | Google API key troubleshooting guide | Google official docs on REQUEST_DENIED/OVER_QUERY_LIMIT/INVALID_REQUEST error codes researched; Phase 17 "Problem -> fix action" pattern identified in DEPLOY.md |
| DOCS-05 | Third-party license/attribution audit documented | Full dependency scan completed: 59 Python packages + 10 JS packages audited; 4 copyleft licenses flagged (psycopg LGPL-3.0, psycopg-binary LGPL-3.0, certifi MPL-2.0, Secweb MPL-2.0); PostGIS GPL-2.0 Docker image noted |
</phase_requirements>

## Standard Stack

This phase produces markdown files only. No libraries or frameworks needed.

### Core Tools
| Tool | Purpose | Why |
|------|---------|-----|
| Markdown | Document format | Matches all existing project docs |
| `pip show` / `importlib.metadata` | Python license audit | Extracts SPDX license expressions from installed packages |
| `package.json` inspection | JS license audit | Dependencies listed with versions |

### Existing Assets to Reference
| Asset | Lines | Purpose for This Phase |
|-------|-------|----------------------|
| `LICENSING.md` | 266 | Extend with lifecycle sections -- DO NOT restructure existing content |
| `README.md` | 529 | Add "Documentation" section at bottom |
| `scripts/build-dist.sh` | 172 | Source material for DISTRIBUTION.md + update to include ATTRIBUTION.md |
| `scripts/verify-dist.sh` | 369 | Source material for DISTRIBUTION.md verify step |
| `scripts/deploy.sh` | 272 | Source material for DISTRIBUTION.md deploy step |
| `docker-compose.yml` | 254 | Dev environment details for ENV-COMPARISON.md |
| `docker-compose.prod.yml` | 334 | Prod environment details for ENV-COMPARISON.md |
| `.env.example` | 40 | Dev env vars for ENV-COMPARISON.md |
| `.env.production.example` | 80 | Prod env vars for ENV-COMPARISON.md |
| `DEPLOY.md` | 343 | Audience/tone reference for GOOGLE-MAPS.md (office employee level) |
| `core/licensing/license_manager.py` | 449 | License lifecycle technical details |

## Architecture Patterns

### Document Structure Patterns (from existing docs)

**Pattern 1: Audience callout box (DEPLOY.md, SETUP.md)**
```markdown
> **Who this is for:** An employee at the office who needs to...
```
Use this for GOOGLE-MAPS.md.

**Pattern 2: Step-by-step with verification (LICENSING.md)**
```markdown
### Step 1: Get the customer's machine fingerprint
[command]
This outputs a 64-character hex string...
```
Use this for DISTRIBUTION.md.

**Pattern 3: ASCII flow diagrams (LICENSING.md)**
```
Customer machine                      Developer machine
─────────────────                     ──────────────────
get_machine_id.py                     generate_license.py
```
Use this for LICENSING.md lifecycle extension.

**Pattern 4: Comparison tables (LICENSING.md "Dev vs Production")**
```markdown
| Check | Development | Production |
|-------|-------------|------------|
```
Use this for ENV-COMPARISON.md (the whole document).

**Pattern 5: Problem -> fix action (Phase 17 / DEPLOY.md troubleshooting)**
```markdown
### "Error message here"
```
**Fix:** [action to take]
```
Use this for GOOGLE-MAPS.md error section.

### Document Placement
```
routing_opt/
├── ATTRIBUTION.md          # NEW (DOCS-05)
├── DISTRIBUTION.md         # NEW (DOCS-01)
├── ENV-COMPARISON.md       # NEW (DOCS-03)
├── GOOGLE-MAPS.md          # NEW (DOCS-04)
├── LICENSING.md            # EXTEND (DOCS-02)
├── README.md               # EXTEND (doc index)
├── scripts/build-dist.sh   # UPDATE (include ATTRIBUTION.md)
├── CSV_FORMAT.md           # existing
├── DEPLOY.md               # existing
├── GUIDE.md                # existing
└── SETUP.md                # existing
```

### Anti-Patterns to Avoid
- **Restructuring LICENSING.md:** CONTEXT.md explicitly says "add to existing 266-line file" -- append new sections after the existing Security Notes section
- **Screenshots in GOOGLE-MAPS.md:** Go stale when Google updates UI -- use text descriptions with "you should see..." phrasing instead
- **Bloating README doc index:** One line per doc, no multi-sentence descriptions
- **Duplicating content:** Use cross-references (`see [LICENSING.md](LICENSING.md#section)`) instead of copying content between docs

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| License audit | Manual license lookup | `importlib.metadata` + `package.json` | Automated extraction catches all 69 dependencies accurately |
| Env comparison | Reading compose files by hand | Side-by-side diff of docker-compose.yml vs docker-compose.prod.yml | Ensures nothing is missed |
| Google Maps error codes | Guessing from experience | Official Google Geocoding API docs | Error codes and messages change; official docs are authoritative |

## Common Pitfalls

### Pitfall 1: Missing copyleft license flags
**What goes wrong:** ATTRIBUTION.md lists only permissive licenses, misses LGPL/MPL packages
**Why it happens:** Most packages are MIT/BSD, easy to assume all are
**How to avoid:** The dependency audit has already identified 4 copyleft packages: psycopg (LGPL-3.0), psycopg-binary (LGPL-3.0), certifi (MPL-2.0), Secweb (MPL-2.0). PostGIS Docker image is GPL-2.0. All must be flagged with implications.
**Warning signs:** If ATTRIBUTION.md doesn't mention LGPL or MPL, something was missed

### Pitfall 2: Confusing license 503 with geocoding errors
**What goes wrong:** User sees 503 error and doesn't know if it's a license issue or a service issue
**Why it happens:** Both license expiry and service failures can produce HTTP errors
**How to avoid:** Add cross-reference between LICENSING.md 503 troubleshooting and GOOGLE-MAPS.md -- explain that license 503 affects ALL endpoints while geocoding errors affect only upload
**Warning signs:** Troubleshooting section doesn't distinguish between the two error sources

### Pitfall 3: DISTRIBUTION.md commands that don't work
**What goes wrong:** Copy-pasted commands fail because of missing context (wrong directory, missing venv, etc.)
**Why it happens:** Docs written from memory rather than from actual script source code
**How to avoid:** Extract every command from the actual scripts (build-dist.sh, verify-dist.sh, deploy.sh, generate_license.py) and test the narrative flow
**Warning signs:** Commands in docs don't match commands in scripts

### Pitfall 4: build-dist.sh not updated to include ATTRIBUTION.md
**What goes wrong:** Tarball ships without attribution file, violating license obligations
**Why it happens:** Easy to forget the script update among 5 documentation tasks
**How to avoid:** The rsync in build-dist.sh copies everything not explicitly excluded -- ATTRIBUTION.md at project root will be included by default. Verify by checking rsync exclude list.
**Warning signs:** ATTRIBUTION.md not mentioned in build-dist.sh or tarball contents

### Pitfall 5: ENV-COMPARISON.md missing variables or services
**What goes wrong:** Developer reads comparison, sets up prod, but misses a critical variable
**Why it happens:** Variables scattered across .env.example, .env.production.example, and compose files
**How to avoid:** Systematically diff all 4 files: .env.example, .env.production.example, docker-compose.yml, docker-compose.prod.yml
**Warning signs:** Comparison table has fewer rows than the actual env files

## Code Examples

### build-dist.sh update pattern (for ATTRIBUTION.md inclusion)
```bash
# ATTRIBUTION.md lives at project root, which is copied by the rsync command
# on line 67-97 of build-dist.sh. Since ATTRIBUTION.md is not in the exclude
# list, it will be automatically included. NO CHANGE NEEDED to the rsync.
#
# However, the "What's included in the distribution" table in LICENSING.md
# (line 229-240) should be updated to mention ATTRIBUTION.md.
```

Actually, reviewing build-dist.sh more carefully: the rsync copies `./` to staging with exclusions. Since ATTRIBUTION.md is a new file at the root and is not in the exclude list, it WILL be automatically included. The only change needed is to mention it in documentation tables that list tarball contents.

### LICENSING.md extension point
```markdown
# The existing file ends at line 266 with:
## Security Notes
- `generate_license.py` must **never** be shipped to customers...

# New sections should be appended AFTER Security Notes:

---

## License Lifecycle

### Stages
[ASCII diagram: Generate -> Deliver -> Activate -> Monitor -> Renew]

### Grace Period Monitoring
[X-License-Warning header details, 7-day window]

### Renewal Process
[Step-by-step with exact commands]

### Troubleshooting 503
[Problem -> fix pattern]
```

### README.md documentation index pattern
```markdown
## Documentation

| Document | Description |
|----------|-------------|
| [DEPLOY.md](DEPLOY.md) | Office employee setup and daily use guide |
| [SETUP.md](SETUP.md) | Developer environment setup |
| [LICENSING.md](LICENSING.md) | License generation, activation, and lifecycle |
| [DISTRIBUTION.md](DISTRIBUTION.md) | Build, deliver, and verify customer distributions |
| [ENV-COMPARISON.md](ENV-COMPARISON.md) | Development vs production environment comparison |
| [GOOGLE-MAPS.md](GOOGLE-MAPS.md) | Google Maps API key setup and troubleshooting |
| [ATTRIBUTION.md](ATTRIBUTION.md) | Third-party licenses and attribution requirements |
| [CSV_FORMAT.md](CSV_FORMAT.md) | Upload file format reference |
| [GUIDE.md](GUIDE.md) | Beginner's guide to the platform |
```

## Key Data: Dependency License Audit Results

### Python Dependencies (59 packages from requirements.txt)

**Copyleft/Restrictive (MUST FLAG):**

| Package | Version | License | Obligation |
|---------|---------|---------|------------|
| psycopg | 3.3.3 | LGPL-3.0-only | Must allow users to replace/relink; source modifications must be shared |
| psycopg-binary | 3.3.3 | LGPL-3.0-only | Same as psycopg (bundled C extension) |
| certifi | 2026.1.4 | MPL-2.0 | Modified source files must remain MPL-2.0; unmodified use is fine |
| Secweb | 1.30.10 | MPL-2.0 | Same as certifi (file-level copyleft) |

**Permissive (no special obligations beyond attribution):**

| License Type | Packages |
|-------------|----------|
| MIT | alembic, annotated-doc, annotated-types, anyio, charset-normalizer, click (BSD-3), Deprecated, et_xmlfile, fastapi, GeoAlchemy2, greenlet, h11, httptools, iniconfig, limits, Mako, MarkupSafe (BSD-3), openpyxl, pillow (MIT-CMU), pluggy, pydantic, pydantic_core, Pygments (BSD-2), pyogrio, pyproj, pytest, python-dotenv (BSD-3), PyYAML, shapely (BSD-3), six, slowapi, SQLAlchemy, typing-inspection, typing_extensions (PSF-2.0), urllib3, uvloop, watchfiles, websockets (BSD-3), wrapt (BSD-2) |
| BSD-3-Clause | httpcore, httpx, idna, numpy, pandas, geopandas, starlette, uvicorn |
| Apache-2.0 | asyncpg, python-multipart, pytest-asyncio, requests |

### JavaScript Dependencies (10 packages from package.json)

| Package | Version | License |
|---------|---------|---------|
| react | 19.2.0 | MIT |
| react-dom | 19.2.0 | MIT |
| maplibre-gl | 5.18.0 | BSD-3-Clause |
| react-map-gl | 8.1.0 | MIT |
| daisyui | 5.5.19 | MIT |
| tailwindcss | 4.2.1 | MIT |
| framer-motion | 12.34.3 | MIT |
| lucide-react | 0.575.0 | ISC |
| @fontsource/dm-sans | 5.2.8 | OFL-1.1 (font), MIT (package) |
| @fontsource/ibm-plex-mono | 5.2.7 | OFL-1.1 (font), MIT (package) |

### Infrastructure / Docker Images

| Component | License | Attribution Required |
|-----------|---------|---------------------|
| PostgreSQL 16 | PostgreSQL License (permissive) | Copyright notice in docs |
| PostGIS 3.5 | GPL-2.0 | Used as Docker image, not modified -- no source disclosure required |
| OSRM v5.26.0 | BSD-2-Clause | Copyright notice in docs |
| VROOM v1.14.0 | BSD-2-Clause | Copyright notice in docs |
| Caddy 2 | Apache-2.0 | Copyright notice in docs |
| Node 22 | MIT | Dev-only, not distributed |

### Data Sources

| Source | License | Required Attribution Text |
|--------|---------|--------------------------|
| OpenStreetMap | ODbL (Open Database License) | "Contains information from OpenStreetMap, which is made available here under the Open Database License (ODbL)" + link to openstreetmap.org/copyright |
| Google Maps Platform | Google ToS (proprietary) | "Google Maps" attribution must be displayed; cannot remove/modify Google-provided attribution |
| Google Fonts (Outfit, JetBrains Mono) | OFL-1.1 (SIL Open Font License) | Free to use, embed, redistribute; must include copyright notice if redistributing font files |

## Key Data: Environment Comparison Matrix

### Services Comparison
| Service | Dev (`docker-compose.yml`) | Prod (`docker-compose.prod.yml`) |
|---------|---------------------------|----------------------------------|
| db | Port 5432 exposed, default password | No exposed port, strong password required, shm_size=256mb, 1G memory limit |
| osrm | Port 5000 exposed | No exposed port, 1G memory limit |
| vroom | Port 3000 exposed | No exposed port, 512M memory limit, healthcheck added |
| api | Port 8000 exposed | No exposed port (behind Caddy), 1G memory limit, LICENSE_KEY required |
| caddy | N/A | Ports 80/443 exposed, auto-TLS, serves dashboard static files |
| dashboard-build | Builds to shared volume | Builds to shared volume (same) |
| dashboard-dev | Profile `dev`, port 5173 | N/A (not available in prod) |
| db-init | Runs migrations | Runs migrations (same) |

### Environment Variables Comparison
| Variable | Dev (`.env.example`) | Prod (`.env.production.example`) |
|----------|---------------------|----------------------------------|
| ENVIRONMENT | `development` | `production` |
| API_KEY | Empty (optional) | Required (error if unset) |
| POSTGRES_PASSWORD | `change-me-in-production` | Required (error if default) |
| GOOGLE_MAPS_API_KEY | `your-key-here` | Required for geocoding |
| CORS_ALLOWED_ORIGINS | `localhost:8000,localhost:5173` | `https://delivery.example.com` |
| RATE_LIMIT_ENABLED | `true` | `true` |
| DOMAIN | N/A | Required (for Caddy TLS) |
| BACKUP_DIR | N/A | `./backups` |
| RETAIN_COUNT | N/A | `7` |
| LICENSE_KEY | N/A | Required (or license.key file) |

### Key Behavioral Differences
| Behavior | Development | Production |
|----------|-------------|------------|
| License enforcement | Skipped (ENVIRONMENT=development) | Required (503 without valid key) |
| API docs (`/docs`) | Available | Disabled |
| CORS | Permissive | Strict (domain-specific) |
| TLS | None (HTTP) | Auto-TLS via Caddy (HTTPS) |
| Log rotation | None | 10m x 3 files per container |
| Resource limits | None | Per-container memory/CPU limits |
| Ports exposed | 8000, 5432, 5000, 3000 | 80, 443 only |

## Key Data: Google Maps API Error Reference

| Error Code | Meaning | Common Cause | Fix Action |
|------------|---------|-------------|------------|
| `REQUEST_DENIED` | API rejected the request | API key missing/invalid, Geocoding API not enabled, HTTP instead of HTTPS | Verify key in Cloud Console, enable Geocoding API, check GOOGLE_MAPS_API_KEY in .env |
| `OVER_QUERY_LIMIT` | Rate limit exceeded | Too many requests per second (limit: 50 req/s) or monthly quota exceeded | Check billing dashboard, add delays between batch requests, verify $200 free credit |
| `INVALID_REQUEST` | Malformed request | Missing address parameter, empty query string | Check CSV for empty address fields |
| `ZERO_RESULTS` | No results found | Address too vague or doesn't exist | Improve address quality in CDCMS |

## Key Data: LICENSING.md Extension Points

The existing LICENSING.md (266 lines) covers:
- Lines 1-30: Overview + ASCII flow diagram
- Lines 32-107: Developer guide (generate key)
- Lines 109-161: Customer guide (activate key)
- Lines 163-252: Dev vs Production comparison + build-dist.sh
- Lines 254-266: Security Notes

**New sections to add after line 266:**

1. **License Lifecycle** -- ASCII diagram of full lifecycle: Generate -> Deliver -> Activate -> Monitor Grace -> Renew -> (or) Troubleshoot 503
2. **Grace Period Monitoring** -- `X-License-Warning` header detection, 7-day countdown, what the API logs show, how to check remaining days
3. **Renewal Process** -- Step-by-step: get new fingerprint (may have changed if Docker container recreated), send to developer, receive new key, update .env or license.key, restart
4. **Troubleshooting License 503** -- Problem -> fix pattern: "All endpoints return 503" (expired), "Wrong machine" (fingerprint mismatch), "Invalid key format" (typo/corruption)

Source material: `core/licensing/license_manager.py` lines 75-88 (LicenseStatus enum), lines 120-122 (GRACE_PERIOD_DAYS=7), lines 364-439 (validate_license flow).

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| LICENSING.md covers generation/activation only | Must cover full lifecycle including grace period and troubleshooting | Extends existing doc, doesn't replace |
| No attribution documentation | Full dependency audit required | New ATTRIBUTION.md with 69+ packages |
| Env differences scattered across docs | Single comparison document | New ENV-COMPARISON.md centralizes info |
| Distribution workflow undocumented | End-to-end walkthrough | New DISTRIBUTION.md covers full workflow |
| Google Maps setup assumed | Plain-English troubleshooting guide | New GOOGLE-MAPS.md for office employees |

## Open Questions

1. **build-dist.sh and ATTRIBUTION.md inclusion**
   - What we know: The rsync in build-dist.sh copies everything from `./` that isn't in the exclude list. ATTRIBUTION.md at root will be included automatically.
   - What's unclear: Should the script explicitly `info "Including ATTRIBUTION.md"` for visibility, or is silent inclusion sufficient?
   - Recommendation: Add a comment in the script noting ATTRIBUTION.md is included, but no code change needed for the actual inclusion.

2. **psycopg LGPL-3.0 compliance in .pyc distribution**
   - What we know: psycopg is LGPL-3.0. The tarball distributes psycopg as a pip-installed package (not modified, not compiled to .pyc). The LGPL allows use in proprietary software when the library is kept as a separate, replaceable component.
   - What's unclear: Whether the Docker image constitutes "linking" under LGPL terms.
   - Recommendation: Document in ATTRIBUTION.md that psycopg is LGPL-3.0, note that it's used unmodified as a pip package, and that users can replace it with a newer version. This satisfies LGPL requirements.

3. **Cross-reference between LICENSING.md 503 and GOOGLE-MAPS.md errors**
   - What we know: Both license expiry (503 on ALL endpoints) and geocoding errors (REQUEST_DENIED on upload only) can confuse users.
   - Recommendation: Add cross-reference. LICENSING.md troubleshooting section should note "If only the upload endpoint fails but other endpoints work, the issue is likely a Google Maps API error -- see [GOOGLE-MAPS.md](GOOGLE-MAPS.md)". GOOGLE-MAPS.md should note "If ALL endpoints return 503, the issue is likely a license problem -- see [LICENSING.md](LICENSING.md#troubleshooting-license-503)".

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Manual verification (documentation phase) |
| Config file | N/A |
| Quick run command | `ls -la DISTRIBUTION.md ENV-COMPARISON.md GOOGLE-MAPS.md ATTRIBUTION.md LICENSING.md` |
| Full suite command | Check each file exists, has content, and contains expected sections |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DOCS-01 | DISTRIBUTION.md covers build->generate->deliver->verify | manual + smoke | `grep -c "build-dist.sh\|verify-dist.sh\|generate_license\|deploy.sh" DISTRIBUTION.md` | Wave 0 |
| DOCS-02 | LICENSING.md extended with lifecycle/grace/renewal/503 | manual + smoke | `grep -c "Grace Period\|Renewal\|503\|Lifecycle" LICENSING.md` | Exists (extend) |
| DOCS-03 | ENV-COMPARISON.md covers ports/volumes/env/services | manual + smoke | `grep -c "ENVIRONMENT\|API_KEY\|POSTGRES_PASSWORD\|DOMAIN" ENV-COMPARISON.md` | Wave 0 |
| DOCS-04 | GOOGLE-MAPS.md covers Cloud Console/errors/troubleshooting | manual + smoke | `grep -c "REQUEST_DENIED\|OVER_QUERY_LIMIT\|INVALID_REQUEST\|Cloud Console" GOOGLE-MAPS.md` | Wave 0 |
| DOCS-05 | ATTRIBUTION.md covers OSM/OSRM/VROOM/Leaflet/Google + full audit | manual + smoke | `grep -c "ODbL\|BSD-2\|LGPL\|MPL\|GPL" ATTRIBUTION.md` | Wave 0 |

### Sampling Rate
- **Per task commit:** `ls -la DISTRIBUTION.md ENV-COMPARISON.md GOOGLE-MAPS.md ATTRIBUTION.md && wc -l LICENSING.md`
- **Per wave merge:** All 5 files exist with expected content; LICENSING.md line count > 266 (original); build-dist.sh includes ATTRIBUTION.md in tarball
- **Phase gate:** All files created, README.md updated, build-dist.sh updated

### Wave 0 Gaps
- [ ] `DISTRIBUTION.md` -- new file, covers DOCS-01
- [ ] `ENV-COMPARISON.md` -- new file, covers DOCS-03
- [ ] `GOOGLE-MAPS.md` -- new file, covers DOCS-04
- [ ] `ATTRIBUTION.md` -- new file, covers DOCS-05
- [ ] `LICENSING.md` extension -- existing file, append sections for DOCS-02

## Sources

### Primary (HIGH confidence)
- `scripts/build-dist.sh` -- read directly, 172 lines, rsync exclude list and compilation steps
- `scripts/verify-dist.sh` -- read directly, 369 lines, verification workflow
- `scripts/deploy.sh` -- read directly, 272 lines, production deployment workflow
- `core/licensing/license_manager.py` -- read directly, 449 lines, license validation logic
- `docker-compose.yml` -- read directly, 254 lines, dev service configuration
- `docker-compose.prod.yml` -- read directly, 334 lines, prod service configuration
- `.env.example` -- read directly, 40 lines, dev environment variables
- `.env.production.example` -- read directly, 80 lines, prod environment variables
- `LICENSING.md` -- read directly, 266 lines, existing license documentation
- `requirements.txt` -- read directly, 59 packages with pinned versions
- `package.json` -- read directly, 10 JS dependencies
- `importlib.metadata` scan -- automated license extraction for all 59 Python packages

### Secondary (MEDIUM confidence)
- [Google Geocoding API docs](https://developers.google.com/maps/documentation/geocoding/requests-geocoding) -- error codes and status descriptions
- [Google Cloud Console API setup](https://developers.google.com/maps/documentation/geocoding/get-api-key) -- key creation steps
- [OpenStreetMap attribution guidelines](https://osmfoundation.org/wiki/Licence/Attribution_Guidelines) -- required ODbL attribution text
- [OSRM GitHub](https://github.com/Project-OSRM/osrm-backend) -- BSD-2-Clause license confirmed
- [VROOM GitHub](https://github.com/VROOM-Project/vroom) -- BSD-2-Clause license confirmed
- [MapLibre GL JS LICENSE](https://github.com/maplibre/maplibre-gl-js/blob/main/LICENSE.txt) -- BSD-3-Clause confirmed
- [PostGIS GPL FAQ](https://postgis.net/documentation/faq/gpl-license/) -- GPL-2.0, no source disclosure for using as Docker image
- [psycopg license page](https://www.psycopg.org/license/) -- LGPL-3.0 confirmed
- [Google Maps Platform ToS](https://cloud.google.com/maps-platform/terms) -- attribution requirements

### Tertiary (LOW confidence)
- None -- all findings verified with primary or secondary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - pure documentation phase, no libraries needed
- Architecture: HIGH - all source files read, existing doc patterns well-established
- Pitfalls: HIGH - dependency audit completed with automated tooling, all copyleft licenses identified
- Content accuracy: HIGH - all data extracted from actual source code and scripts, not from memory

**Research date:** 2026-03-08
**Valid until:** 2026-04-08 (stable -- documentation of existing system, unlikely to change)
