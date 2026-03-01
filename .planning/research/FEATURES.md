# Feature Research

**Domain:** Logistics SaaS — Delivery Route Optimization Dashboard + Driver PWA
**Researched:** 2026-03-01
**Confidence:** MEDIUM (UI patterns and CSV import UX are well-established; security headers are HIGH from OWASP docs; driver PWA patterns are MEDIUM from industry guides)

---

## Context: What Already Exists

This is an improvement milestone on a working system. The app already has:
- CSV file upload with drag-and-drop, file type validation, and size limit checks
- Upload workflow state machine (idle → selected → uploading → success → error)
- Route results cards per vehicle with stop counts, distance, duration, weight
- QR code generation and print sheet
- StatsBar with six KPI tiles (total, completed, pending, failed, active vehicles, unassigned)
- Leaflet map (LiveMap page), run history page, fleet management page
- API key authentication with `hmac.compare_digest()`, rate limiting via slowapi
- Driver PWA (dark-first, 48px touch targets, offline via service worker)

The gap: the UI looks prototype-quality, geocoding failures are silent (orders disappear), error details never reach the user, and security headers are missing.

---

## Feature Landscape

### Table Stakes — UI/UX (Users Expect These)

Features any logistics SaaS operator dashboard has. Missing = product feels like a hackathon demo.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Consistent design system** | Every professional SaaS tool has visual coherence: same spacing, color tokens, type scale. Mixing ad-hoc CSS with different button styles signals "not production." | LOW | Tailwind + DaisyUI already decided. Apply systematically, not piecemeal. |
| **Clear status hierarchy** | Colors must mean the same thing everywhere: green=good, amber=warning, red=error, blue=info. Operators scan dashboards visually — inconsistency causes errors. | LOW | Design tokens already partially in StatsBar (`--color-success`, `--color-danger`). Must propagate to all components. |
| **Import success/failure summary** | After CSV upload, user must immediately know: how many rows processed, how many succeeded, how many failed, and why. The current "No valid orders" single-string error is not acceptable in any logistics tool. | MEDIUM | This is the critical missing feature. Every import SaaS (HubSpot, Salesforce, Routific) shows a per-row breakdown. |
| **Geocoding failure reporting** | When an address can't be geocoded, the order silently disappears. Users must see a list of failed addresses with the reason, not a smaller number of pins. | MEDIUM | Root cause: `GoogleGeocoder.batch()` drops failed results; UI never receives the drop count. Backend must track and surface this. |
| **Actionable error messages** | Errors like "Upload failed. Please try again." or "Invalid CSV format" leave users guessing. Messages must say what went wrong, which row, and what to do next. | LOW | Pattern from OWASP/UX research: specificity over brevity. |
| **Loading state with progress steps** | Multi-step processing (upload → geocode → optimize → persist) needs per-step progress, not just a spinner. 3-5 second operations feel broken without feedback. | LOW | The `uploadProgress` string already exists in UploadRoutes.tsx; needs to map to step indicators, not free-form text. |
| **Toast/notification system** | Non-blocking feedback for actions: "Routes generated", "Vehicle updated", "Fleet saved". Modal dialogs for minor confirmations are outdated logistics UX. | LOW | DaisyUI `toast` + `alert` components. One global notification provider. |
| **Empty states** | All pages need meaningful empty states (not blank). "No routes yet — upload a CDCMS file to begin" with a CTA is standard. | LOW | Maps page with no data, run history with no runs, fleet with no vehicles. |
| **Keyboard and screen reader basics** | ARIA labels on icon-only buttons, focus rings visible, form labels associated with inputs. Not full WCAG 2.1 AA, but enough that a keyboard user can navigate. | LOW | Applies especially to the upload zone and vehicle CRUD forms. |
| **Responsive layout (breakpoints)** | Dashboard runs on office desktops and laptops. Must not break below 1280px. The driver PWA already handles mobile. | LOW | Sidebar collapse at 1024px, card grid wrapping. |

### Table Stakes — Security (Expected in Any Production Web App)

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **HTTP security headers** | OWASP requires: `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `Content-Security-Policy`, `Strict-Transport-Security` (HTTPS), `Permissions-Policy`. Missing = instant fail on any security scan. | LOW | Add as FastAPI middleware. One-time setup. Source: [OWASP HTTP Headers Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html) |
| **CORS origin whitelist** | `CORSMiddleware` currently likely uses a broad origin. Production must whitelist known dashboard origin(s) only. Wildcard `*` with credentials is broken behavior. | LOW | Update env var to list allowed origins explicitly. |
| **Remove information-disclosure headers** | `Server`, `X-Powered-By` headers expose stack details. FastAPI/uvicorn often send these by default. | LOW | Middleware to strip. |
| **Input validation on file upload** | File extension check exists in frontend. Backend must also validate: MIME type, max size, CSV column schema. Never trust client validation. | LOW | Backend already has a 10MB limit. Add column-presence check before geocoding. |
| **XSS prevention on address rendering** | Driver PWA Leaflet popups render address text. Raw address strings from database could contain injected content if input wasn't escaped at storage time. | LOW | Already partially fixed (commit ad4f52e). Audit all innerHTML usages. |
| **Dependency security scan** | Production apps must know if any dependency has known CVEs. | LOW | `pip-audit` for Python, `npm audit` for dashboard. Run in CI. |
| **API docs locked in production** | FastAPI auto-generates `/docs` and `/redoc`. These should be disabled or auth-gated in production. | LOW | Env-flag: `if not settings.DEBUG: app.openapi_url = None` |

### Table Stakes — Developer Experience

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **One-command setup** | `docker-compose up` with working OSRM data, seeded DB, and working API. Missing = onboarding friction, support burden. | MEDIUM | Requires downloading Kerala OSM data automatically or providing in repo. |
| **Environment variable validation** | App should fail loudly on startup if `GOOGLE_MAPS_API_KEY` or `API_KEY` is missing, not silently fail at first use. | LOW | Pydantic `BaseSettings` with required fields and helpful error messages. |
| **Test coverage for edge cases** | Tests that cover: geocoding failure paths, VROOM timeout, unassigned orders, malformed CSV rows. Currently coverage may be shallow on failure paths. | MEDIUM | Write tests for the failure paths, not just happy paths. |

---

### Differentiators — CSV Import Quality

Features that distinguish a well-engineered import from a basic upload.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Row-level import report** | After processing, show a table: `Row | Address | Status | Reason` — green for geocoded, amber for partial match, red for failed. Users can see exactly which deliveries won't happen today. | MEDIUM | Backend must accumulate per-row geocoding results and return them in the upload response. New `geocoding_report` field in `OptimizationSummary`. |
| **Geocoding confidence display** | Show geocoding confidence score per stop (HIGH/MEDIUM/LOW). Operators can spot low-confidence geocodes before drivers head out to wrong locations. | MEDIUM | `GeocodeCacheDB` already stores confidence. Surface it in the route stop card. |
| **Failed row download** | "Download failed rows as CSV" button — users can fix addresses offline and re-upload just the failures. Saves time on large CSV batches. | LOW | Subset of original CSV rows filtered by failed status. Pure frontend if backend returns row data. |
| **Partial import with confirmation** | If 3 of 150 orders fail geocoding, ask "Proceed with 147 orders?" instead of failing silently or blocking. User explicitly acknowledges the gap. | MEDIUM | Two-step API call: first returns preview with failures, second confirms and optimizes. Or simpler: immediate optimization + prominent warning. |

### Differentiators — Dashboard Operational Quality

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Per-vehicle capacity utilization bar** | Show weight used vs 446 kg max as a horizontal bar on each route card. Operators see at a glance if loads are balanced. | LOW | Data already in `route.total_weight_kg`. Simple CSS width calculation. |
| **Unassigned order detail** | When unassigned count > 0, show which orders weren't assigned and why (over capacity, no geocode). Currently just a number. | MEDIUM | Requires backend to return unassigned order IDs + reason. `RouteAssignment.unassigned_orders` already exists. |
| **Driver PWA dark mode outdoor readability** | Existing dark-first design is good. Add high-contrast mode toggle for very bright outdoor conditions (white background, black text). | LOW | CSS `prefers-contrast` media query + manual toggle. Important for Kerala sun. |
| **ETA display in driver list view** | Driver app shows sequence numbers but not ETAs. Showing estimated arrival time per stop lets drivers explain delays to customers. | LOW | `route_stop.duration_from_prev_minutes` is already computed. Sum from depot departure to display running ETA. |

---

### Anti-Features — Do NOT Build in This Milestone

Features that seem logical but are out of scope, create risk, or should be deliberately deferred.

| Anti-Feature | Why Requested | Why Problematic | What to Do Instead |
|--------------|---------------|-----------------|-------------------|
| **Real-time driver location tracking on dispatch map** | LiveMap exists; showing live GPS seems obvious | Requires persistent WebSocket or polling; telemetry data is already ingested but building a smooth live map layer is a week of work. Out of scope for this milestone. | Keep existing Leaflet map. Show last-known position from telemetry on page load. |
| **Customer-facing delivery tracking page** | "Where is my cylinder?" is a common request | Multi-tenant auth, privacy concerns, SMS/notification system — entirely new vertical. PROJECT.md marks this as out of scope. | Explicitly out of scope. Not this milestone. |
| **AI/ML address suggestions for failed geocodes** | "Just suggest the right address automatically" | Would require a secondary geocoding provider, fuzzy matching, manual review UI, and operator training. 3x scope of the actual fix. | Show failure reason clearly. Let the operator correct the CSV manually and re-upload. |
| **Automated re-geocoding queue** | "Retry failed addresses with fallback providers" | Multiple geocoding provider integration adds API key management, billing risk, and code complexity. Not needed — the real fix is surfacing failures so humans can correct them. | Show which rows failed. Human corrects address. Re-upload. Simple. |
| **Drag-and-drop route reordering in UI** | Dispatchers might want to manually reorder stops | VROOM's output is already optimal. Manual override introduces errors. Complex drag-and-drop with persist-to-DB is high effort for low value. | Trust the optimizer. Provide a notes field for stop-level overrides at most. |
| **Multi-file batch upload** | "Upload multiple days at once" | Batching logic, run tagging, date filtering, result merging — significant scope increase. | One CSV per day. The CDCMS workflow already produces one daily export. |
| **Browser push notifications** | "Alert me when optimization completes" | Current optimization is synchronous (under 30s). Push requires service worker notification permission, backend subscription management. | Progress steps in-UI are sufficient. The operation is fast. |
| **Dark mode for dispatch dashboard** | "Make it dark like the driver app" | Cosmetic scope that risks destabilizing CSS during the UI overhaul. Driver PWA is dark because outdoor readability requires it; office dispatchers work indoors. | Light mode only for dashboard. Add to future backlog if requested. |

---

## Feature Dependencies

```
[Geocoding failure reporting — backend]
    └──requires──> [Per-row geocoding result accumulation in batch()]
                       └──requires──> [New API response field: geocoding_report]
                                          └──enables──> [Import summary UI]
                                                            └──enables──> [Failed row download]

[Security headers]
    └──no dependencies — standalone middleware

[Consistent design system (Tailwind + DaisyUI)]
    └──enables──> [Toast system]
    └──enables──> [Empty states]
    └──enables──> [Status badge consistency]

[Input validation — backend]
    └──required before──> [Import summary UI]
    (backend must return structured errors for UI to display them)

[Unassigned order detail]
    └──requires──> [RouteAssignment.unassigned_orders data returned to frontend]
    (already in Pydantic model, may not be in API response JSON)
```

### Dependency Notes

- **Geocoding failure reporting requires backend changes first:** The UI cannot show what the backend doesn't return. Backend must accumulate per-row results in `GoogleGeocoder.batch()`, then surface them through the `POST /api/upload-orders` response. The UI change is straightforward once that data exists.
- **Design system before components:** Applying Tailwind + DaisyUI must happen before building individual UI improvements, or you end up mixing two CSS approaches in the same component.
- **Security headers are independent:** Can be added as a middleware in one PR with no other dependencies. Should be first security item tackled.
- **Failed row download enhances import summary:** Only valuable after the import summary shows which rows failed. Build in sequence, not parallel.

---

## MVP Definition for This Milestone

This is a polish and hardening milestone on an existing working system, not a greenfield MVP. The framing is: "What's the minimum set of changes that takes this from prototype to professional?"

### Must Ship (P1 — Blocking professional use)

- [ ] **Geocoding failure reporting** — the core data integrity bug. Silent drops must become visible failures with address + reason. This is the stated "Core Value" in PROJECT.md.
- [ ] **Import summary screen** — after upload, show rows processed, geocoded, failed, unassigned. Replace the current generic error string.
- [ ] **HTTP security headers** — `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `CSP`, `Permissions-Policy`. OWASP table stakes for any production API.
- [ ] **Actionable error messages** — replace "Upload failed. Please try again." with specific errors (geocoding failed for N addresses, optimization service unavailable, etc.).
- [ ] **Consistent UI design system** — Tailwind + DaisyUI applied uniformly. No mixed CSS approaches. Visual coherence across all pages.

### Add After Core (P2 — Significantly improves quality)

- [ ] **Row-level import report table** — `Row | Address | Status | Reason` table after upload, beyond just counts.
- [ ] **CORS origin whitelist** — production env must restrict allowed origins.
- [ ] **Empty states for all pages** — meaningful placeholder content instead of blank pages.
- [ ] **Toast notification system** — non-blocking feedback for all user actions.
- [ ] **Failed row download** — "Download unprocessed rows as CSV" for correction and re-upload.
- [ ] **Unassigned order detail** — show which specific orders weren't assigned, not just the count.
- [ ] **API docs gating** — disable `/docs` and `/redoc` in production mode.
- [ ] **Env var validation at startup** — crash loudly with helpful message if required env vars are missing.
- [ ] **One-command docker setup** — `docker-compose up` works without manual steps.

### Defer to Future (P3 — Nice to have, not this milestone)

- [ ] **Geocoding confidence display per stop** — valuable but needs UX design work.
- [ ] **Capacity utilization bars on route cards** — cosmetic improvement, low priority.
- [ ] **ETA display in driver list view** — requires summing durations client-side; low complexity but not blocking.
- [ ] **Driver PWA high-contrast mode** — valuable for outdoor use; not in current milestone scope.
- [ ] **Dependency security scan in CI** — important but infrastructure work.

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Geocoding failure reporting (backend) | HIGH | MEDIUM | P1 |
| Import summary screen (UI) | HIGH | LOW | P1 |
| HTTP security headers | HIGH | LOW | P1 |
| Actionable error messages | HIGH | LOW | P1 |
| Consistent design system | HIGH | MEDIUM | P1 |
| Row-level import report table | HIGH | MEDIUM | P2 |
| CORS whitelist | MEDIUM | LOW | P2 |
| Empty states | MEDIUM | LOW | P2 |
| Toast system | MEDIUM | LOW | P2 |
| Failed row download | MEDIUM | LOW | P2 |
| Unassigned order detail | MEDIUM | MEDIUM | P2 |
| API docs gating | MEDIUM | LOW | P2 |
| Env var validation | MEDIUM | LOW | P2 |
| One-command setup | HIGH | MEDIUM | P2 |
| Geocoding confidence display | LOW | MEDIUM | P3 |
| Capacity utilization bars | LOW | LOW | P3 |
| ETA in driver list | LOW | LOW | P3 |
| High-contrast driver mode | LOW | LOW | P3 |

---

## Competitor Feature Analysis

| Feature | Onfleet | Routific | Our Approach |
|---------|---------|---------|--------------|
| Import failure visibility | Per-task status with reason codes; failed imports shown in task list | Shows unmatched addresses before optimization; user fixes then proceeds | Backend must return per-row geocoding status; show in summary screen |
| Driver status indicators | Color-coded (blue=in-transit, green=idle) with map pin state | Driver list with completion percentage per route | Existing status model (Pending/Assigned/InTransit/Delivered/Failed) — surface in UI with color badges |
| Dispatch KPI tiles | On-time rate, completion rate, driver capacity — live refresh | Stops completed, time savings vs unoptimized, fuel estimates | StatsBar already has 6 tiles; add geocoding failure count as 7th tile |
| CSV import flow | Drag-drop with column mapping wizard, validation preview | Upload → automatic matching → review screen | Current: no review screen. Add: upload → geocoding report → confirm → proceed |
| Security | Enterprise SSO, role-based access, audit logs | Similar enterprise posture | This app: API key auth is appropriate for single-operator use; add security headers, harden CORS |
| Mobile driver app | Native iOS/Android app | Native apps | PWA is appropriate for this use case; focus on readability and offline reliability |

---

## Sources

- [Onfleet Route Optimization](https://onfleet.com/route-optimization) — feature capabilities (MEDIUM confidence, marketing page)
- [Onfleet Q4 2025 Product Update](https://onfleet.com/blog/onfleet-product-update-q4-2025/) — Command Center map view, Analytics Dashboard (MEDIUM confidence)
- [Onfleet Driver Status Docs](https://support.onfleet.com/hc/en-us/articles/10228905705876-Driver-Status) — driver status color conventions (HIGH confidence, official docs)
- [Data import UX: designing spreadsheet imports users don't hate](https://www.importcsv.com/blog/data-import-ux) — five-stage import flow, error patterns (MEDIUM confidence)
- [Dromo CSV Import Best Practices](https://dromo.io/blog/ultimate-guide-to-csv-imports) — row-level error reporting, pre-import validation (MEDIUM confidence)
- [OWASP HTTP Headers Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html) — required security headers and values (HIGH confidence, official OWASP)
- [How to Secure FastAPI Against OWASP Top 10](https://oneuptime.com/blog/post/2025-01-06-fastapi-owasp-security/view) — FastAPI-specific security patterns (MEDIUM confidence)
- [FastAPI CORS / Trusted Hosts 2025](https://johal.in/fastapi-cors-starlette-trusted-hosts-origins-2025-2/) — CORS origin whitelist patterns (MEDIUM confidence)
- [Logistics KPIs 2025 — Locus Blog](https://blog.locus.sh/logistics-kpi/) — delivery completion rate, on-time rate as expected dashboard metrics (MEDIUM confidence)
- [PWA UX Best Practices](https://www.grazitti.com/blog/top-7-tips-to-build-a-great-ux-for-pwa/) — offline mode, touch target sizing, gesture navigation (MEDIUM confidence)
- [DaisyUI Component Docs](https://daisyui.com/components/) — badge, status, toast, alert components (HIGH confidence, official docs)

---

*Feature research for: Kerala LPG Delivery Route Optimizer — UI/UX, Error Handling, Security milestone*
*Researched: 2026-03-01*
