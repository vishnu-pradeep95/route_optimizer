# Phase 4 Feature Pack — Plan

**Created:** 2026-02-28
**Phase:** 4 (Post-production enhancements)
**Status:** Draft — awaiting user review

---

## Summary

Four independent workstreams covering UI redesign, QR code route sharing, software licensing/protection, and simplified installation. All can run in parallel but recommended solo-dev order: D → B → C → A.

**Total estimated effort:** 7–10 days

---

## Phase A: Dashboard & Driver App UI Redesign (3–4 days)

**Aesthetic direction:** Industrial-utilitarian meets logistics precision. Dark charcoal sidebar, warm amber accent, cool slate content. Typography: **DM Sans** (headings) + **IBM Plex Mono** (data/numbers). Purpose-built command center, not generic SaaS.

<task id="A1">
  <name>Install design system dependencies</name>
  <files>apps/kerala_delivery/dashboard/package.json, apps/kerala_delivery/dashboard/src/index.css</files>
  <action>
    Add @fontsource/dm-sans, @fontsource/ibm-plex-mono, framer-motion to package.json.
    Replace CSS custom properties in index.css:
    - --color-surface-dark: #1C1917 (Stone 900, sidebar/header)
    - --color-surface: #FAFAF9 (Stone 50, content bg)
    - --color-accent: #D97706 (amber 600)
    - --color-accent-light: #FDE68A (amber 200, hover states)
    - --color-text-primary: #1C1917 (Stone 900)
    - --color-text-muted: #78716C (Stone 500)
    - --color-success: #16A34A (green 600)
    - --color-danger: #DC2626 (red 600)
    - --color-info: #0284C7 (sky 600)
  </action>
  <verify>npm run build succeeds with 0 TS errors</verify>
  <done>true</done>
</task>

<task id="A2">
  <name>Redesign App shell — sidebar navigation</name>
  <files>apps/kerala_delivery/dashboard/src/App.tsx, apps/kerala_delivery/dashboard/src/App.css</files>
  <action>
    Convert horizontal tab nav to left sidebar (64px collapsed, 220px on hover).
    Logo/brand at top. Nav items as icon + label. Health indicator at sidebar bottom.
    Entry animation: sidebar slides in 300ms with framer-motion AnimatePresence.
  </action>
  <verify>Dashboard loads, nav switches pages, sidebar hover-expands</verify>
  <done>true</done>
</task>

<task id="A3">
  <name>Redesign StatsBar — elevated metric tiles</name>
  <files>apps/kerala_delivery/dashboard/src/components/StatsBar.tsx, StatsBar.css</files>
  <action>
    Replace flat cards with elevated tiles. 4px left-border accent by status.
    Large DM Sans numbers, IBM Plex Mono labels. Pulsing dot on "Vehicles Active".
    Motion layoutId for smooth number transitions.
  </action>
  <verify>Stats display correctly, numbers animate on data change</verify>
  <done>true</done>
</task>

<task id="A4">
  <name>Redesign VehicleList — progress bars + efficiency</name>
  <files>apps/kerala_delivery/dashboard/src/components/VehicleList.tsx, VehicleList.css</files>
  <action>
    Mini progress bar per vehicle (delivered/total). Amber fill in-progress, green 100%.
    Selected vehicle gets left amber border. Speed alert badge pulses.
    Add route efficiency indicator (km/delivery) in small text.
  </action>
  <verify>Vehicle list shows progress, selection highlights correctly</verify>
  <done>true</done>
</task>

<task id="A5">
  <name>Redesign RouteMap — dark basemap + SVG markers</name>
  <files>apps/kerala_delivery/dashboard/src/components/RouteMap.tsx, RouteMap.css</files>
  <action>
    Add dark/light toggle. Dark = CARTO Dark Matter basemap.
    Stop markers: SVG circles with drop shadow and sequence number.
    Live vehicle markers: larger pulsing ring animation.
  </action>
  <verify>Map renders on both themes, markers legible, toggle works</verify>
  <done>true</done>
</task>

<task id="A6">
  <name>Redesign FleetManagement — styled data grid</name>
  <files>apps/kerala_delivery/dashboard/src/pages/FleetManagement.tsx, FleetManagement.css</files>
  <action>
    Alternating row shading (Stone 100/Stone 50). Amber focus ring on edit fields.
    Vehicle type badges as colored chips (diesel=slate, CNG=teal, electric=sky).
    Card view toggle for mobile.
  </action>
  <verify>CRUD operations work, inline edit fields styled, type badges render</verify>
  <done>true</done>
</task>

<task id="A7">
  <name>Redesign RunHistory — expandable rows + sparklines</name>
  <files>apps/kerala_delivery/dashboard/src/pages/RunHistory.tsx, RunHistory.css</files>
  <action>
    Expandable rows with smooth height animation via framer-motion.
    Mini bar showing orders_assigned vs total_orders. Status pills with colored backgrounds.
  </action>
  <verify>Rows expand/collapse smoothly, data displays correctly</verify>
  <done>true</done>
</task>

<task id="A8">
  <name>Redesign Driver PWA — sunlight-readable, big touch targets</name>
  <files>apps/kerala_delivery/driver_app/index.html</files>
  <action>
    Complete visual overhaul:
    - Font: DM Sans from Google Fonts CDN
    - Header: deep charcoal #1C1917, amber accent for progress counter
    - Stop cards: 18px padding, 48px min touch targets, left-border color by status
    - Navigate button: full-width, 56px tall, amber #D97706, compass icon
    - Delivered/Failed buttons: 48px tall, green/red, CSS active scale transform
    - Summary bar: black bg, large white numbers in IBM Plex Mono
    - WCAG AAA contrast (7:1). No low-contrast gray-on-gray.
    - Offline banner: amber bg with high contrast
  </action>
  <verify>Open on mobile viewport in DevTools, check touch targets, Lighthouse contrast audit</verify>
  <done>true</done>
</task>

---

## Phase B: QR Code for Google Maps Route (1–2 days)

**Key constraint:** Google Maps URLs support max 9 waypoints (+ origin + destination = 11 stops total). Routes >11 stops are split into multiple segments.

<task id="B1">
  <name>Add QR code generation API endpoint</name>
  <files>apps/kerala_delivery/api/main.py, requirements.txt</files>
  <action>
    Install: pip install qrcode[pil], add to requirements.txt.
    New endpoint: GET /api/routes/{vehicle_id}/google-maps-url
    
    Google Maps URL format:
    https://www.google.com/maps/dir/?api=1
      &origin={lat},{lng}
      &destination={last_lat},{last_lng}
      &waypoints={lat1},{lng1}|{lat2},{lng2}|...
      &travelmode=driving

    If >11 stops: split into segments of 11, return array of URLs.
    Generate QR as SVG string via qrcode lib (no image files needed).
    Return JSON: { urls: [...], qr_svgs: [...], segments: [{start_stop, end_stop, url, qr_svg}] }
  </action>
  <verify>curl endpoint → valid JSON with QR SVG. Scan QR → Google Maps opens with correct waypoints.</verify>
  <done>false</done>
</task>

<task id="B2">
  <name>Add QR / Google Maps button to driver PWA</name>
  <files>apps/kerala_delivery/driver_app/index.html</files>
  <action>
    Add "📱 Open in Google Maps" button that:
    - Fetches GET /api/routes/{vehicle_id}/google-maps-url
    - Route ≤11 stops: opens URL directly
    - Route >11 stops: shows segment buttons ("Part 1: Stops 1-11", "Part 2: Stops 12-22")
    - Also shows QR code SVG so dispatcher can scan it
  </action>
  <verify>Button works on mobile viewport, URL opens Google Maps correctly</verify>
  <done>false</done>
</task>

<task id="B3">
  <name>Add QR display to dashboard LiveMap</name>
  <files>apps/kerala_delivery/dashboard/src/pages/LiveMap.tsx, apps/kerala_delivery/dashboard/src/lib/api.ts, apps/kerala_delivery/dashboard/src/types.ts</files>
  <action>
    When vehicle selected, show "QR Code" button in vehicle detail panel.
    Click → modal with QR SVG at scannable size (200×200px min).
    Add "Print" button → print-friendly view with vehicle ID + QR code.
  </action>
  <verify>Select vehicle → QR modal → scan with phone → Google Maps opens</verify>
  <done>false</done>
</task>

<task id="B4">
  <name>Add printable QR sheet endpoint</name>
  <files>apps/kerala_delivery/api/main.py</files>
  <action>
    New endpoint: GET /api/routes/qr-sheet
    Returns HTML page with one QR code per vehicle, formatted for A4 printing.
    Each card: vehicle ID, driver name, total stops, QR code.
    Dispatcher prints all QR codes at once in the morning.
  </action>
  <verify>Open in browser → print to PDF → QR codes are scannable from printout</verify>
  <done>false</done>
</task>

---

## Phase C: Software Licensing & Protection (1–2 days)

**Approach:** Hardware-bound license key, offline validation. Stops casual copying, not determined reverse engineering.

<task id="C1">
  <name>Create license manager module</name>
  <files>core/licensing/__init__.py, core/licensing/license_manager.py</files>
  <action>
    Machine fingerprint: SHA256(Docker container ID + hostname + MAC address hash).
    License key format: LPG-XXXX-XXXX-XXXX-XXXX (base32, encodes customer ID + expiry + fingerprint + HMAC).
    Validation on FastAPI startup (lifespan): read LICENSE_KEY env or license.key file.
    Invalid → API returns 503 "License expired or invalid. Contact support." on all endpoints.
    Grace period: 7-day grace after expiry with X-License-Warning header.
    HMAC secret derived via PBKDF2 from a seemingly innocuous constant (not plain string).
  </action>
  <verify>Start with valid key → API works. Change machine → 503. Expired key → grace period.</verify>
  <done>false</done>
</task>

<task id="C2">
  <name>Create license generation CLI (stays on YOUR machine)</name>
  <files>scripts/generate_license.py</files>
  <action>
    Takes: customer name, machine fingerprint, duration (months), secret salt.
    Outputs: license key string.
    NOT shipped with product.
  </action>
  <verify>Generate key → decode → fields match input</verify>
  <done>false</done>
</task>

<task id="C3">
  <name>Create machine fingerprint reporter (shipped to customer)</name>
  <files>scripts/get_machine_id.py</files>
  <action>
    Customer runs this and sends output.
    Outputs: machine fingerprint hash.
  </action>
  <verify>Run on two different machines → different fingerprints</verify>
  <done>false</done>
</task>

<task id="C4">
  <name>Wire license check into Docker Compose</name>
  <files>docker-compose.prod.yml, apps/kerala_delivery/api/main.py</files>
  <action>
    Mount license.key as read-only volume: ./license.key:/app/license.key:ro
    API checks on startup. Without valid key → stack starts but returns 503.
    Add Makefile target: make dist → compiles licensing module to .pyc only (no .py source).
  </action>
  <verify>docker compose up with/without license.key → correct behavior</verify>
  <done>false</done>
</task>

---

## Phase D: Easy Installation / Packaging (1–2 days)

**Approach:** All-in-one Docker Compose with self-initializing init containers + bash installer script. Target: non-developer installs in <15 minutes.

<task id="D1">
  <name>Create OSRM init container</name>
  <files>docker-compose.yml, docker-compose.prod.yml</files>
  <action>
    New service osrm-init: checks if OSRM data exists, if not downloads Kerala PBF and preprocesses.
    Idempotent: exits immediately if data already exists.
    OSRM service depends_on osrm-init: condition: service_completed_successfully.
  </action>
  <verify>Remove OSRM data → docker compose up → data auto-downloads and preprocesses</verify>
  <done>false</done>
</task>

<task id="D2">
  <name>Create database init container</name>
  <files>docker-compose.yml, docker-compose.prod.yml</files>
  <action>
    New service db-init: runs alembic upgrade head.
    Depends on db: condition: service_healthy.
    API depends on db-init: condition: service_completed_successfully.
    Eliminates manual alembic step.
  </action>
  <verify>Fresh database → docker compose up → schema created automatically</verify>
  <done>false</done>
</task>

<task id="D3">
  <name>Create smart installer script</name>
  <files>scripts/install.sh</files>
  <action>
    curl -sSL https://your-repo/install.sh | bash
    - Checks for (installs if missing): Docker, Docker Compose, git
    - Clones repo (or pulls if existing)
    - Creates .env from .env.example with prompted values
    - Generates random secure passwords if user presses Enter
    - Runs docker compose up -d
    - Polls health endpoint every 5s for up to 5 minutes with progress bar
    - Prints success message with URL
  </action>
  <verify>Fresh Ubuntu VM → run script → system up in <15 min</verify>
  <done>false</done>
</task>

<task id="D4">
  <name>Simplify DEPLOY.md to 3 steps</name>
  <files>DEPLOY.md</files>
  <action>
    Step 1: Install WSL/Ubuntu (link to Microsoft guide)
    Step 2: Run curl -sSL URL | bash
    Step 3: Open http://localhost:8000/driver/
    Keep detailed manual steps as "Advanced" section at bottom.
  </action>
  <verify>Non-developer can follow the 3 steps</verify>
  <done>false</done>
</task>

---

## Dependencies & Recommended Order

```
Phase A (UI Redesign)     ─── independent ───┐
Phase B (QR Codes)        ─── independent ───┤──→ Integration testing
Phase C (Licensing)       ─── independent ───┤
Phase D (Easy Install)    ─── independent ───┘
```

**Recommended solo-dev order:**
1. **Phase D** (1–2 days) — reduces friction immediately
2. **Phase B** (1–2 days) — quick win, high driver impact
3. **Phase C** (1–2 days) — protection before distributing
4. **Phase A** (3–4 days) — largest scope, cosmetic, doesn't block functionality

---

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| QR generation location | Backend (Python) | Keeps driver PWA lightweight, single source of truth |
| License validation | Offline hardware-bound key | Matches offline-capable constraint, no license server |
| Packaging format | Docker Compose + bash installer | Multi-service apps need Docker, not Snap/Flatpak |
| Dashboard typography | DM Sans + IBM Plex Mono | Distinctive, logistics-appropriate, not generic AI look |
| Dashboard nav | Left sidebar | Better horizontal space for map-heavy LiveMap |
| Google Maps URL limit | 9 waypoints → split into segments | Google limitation, no workaround |
