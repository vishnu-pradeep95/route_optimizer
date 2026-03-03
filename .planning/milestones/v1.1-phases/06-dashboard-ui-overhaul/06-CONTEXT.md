# Phase 6: Dashboard UI Overhaul - Context

**Gathered:** 2026-03-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Make all 4 dashboard pages (Upload, Live Map, Run History, Fleet Management) look and behave like a professional logistics SaaS product. Consistent DaisyUI component vocabulary, proper loading/empty states, responsive sidebar with SVG icons, tabular-number alignment, color-coded status badges, and print-ready QR sheets.

Requirements: DASH-01 through DASH-07.

</domain>

<decisions>
## Implementation Decisions

### Sidebar & Navigation
- At >= 1280px: full 220px sidebar always visible (no hover-expand interaction needed)
- At < 1280px (tablet): collapsed to 64px icon-only strip
- At < 768px (mobile): sidebar hidden entirely; DaisyUI drawer component opens from left via hamburger icon in top-left corner
- Replace all emoji icons (📤, 🗺️, 📋, 🚛) with lucide-react SVG icons
- Brand area (⛽ Kerala LPG) also gets a lucide SVG icon replacement

### Loading & Empty States
- Use DaisyUI's built-in `tw-skeleton` utility classes for loading placeholders
- Skeleton loading shown on initial page load only — when refreshing (e.g., clicking Refresh button), keep existing data visible with a subtle loading indicator (spinner in the button, or disabled state)
- Every page gets a meaningful empty state: lucide icon + descriptive message + primary action button
  - Example: Fleet page → truck icon + "No vehicles yet" + "Add Vehicle" button
  - Example: Run History → clipboard icon + "No optimization runs yet. Upload orders to get started." + link/button to Upload page

### Route Cards & Status Badges
- Rewrite route cards using DaisyUI card components (`tw-card`, `tw-card-body`, `tw-card-title`)
- Keep all 4 metrics (stops, km, min, kg) visible in card header row — operators need at-a-glance view
- All numeric table cells and stat values use IBM Plex Mono (`--font-mono`) with `font-variant-numeric: tabular-nums` for column alignment
- Apply tabular-number treatment across all 4 pages (RunHistory table, Fleet table, UploadRoutes stats, route cards)

### QR Print Layout
- QR labels include full route summary: vehicle ID, driver name, stop count, total distance, total weight
- Page break strategy: pack as many vehicle QR blocks per page as possible, but never split a single vehicle's QR codes across a page boundary (`break-inside: avoid`)

### Claude's Discretion
- Lucide icon selection for brand area and nav items (optimize for readability at 32px)
- Lucide icon style (outlined vs filled) — pick most readable for narrow sidebar
- Status badge design for route cards — determine from available API data whether 3-state (complete/in-progress/issues) or 2-state (assigned/unassigned) makes sense
- Live Map loading state design
- QR code physical size on print sheet (optimize for scanning from arm's length in a three-wheeler cab)
- Which surfaces get `@media print` styles (backend QR sheet endpoint, in-page, or both)

</decisions>

<specifics>
## Specific Ideas

- Sidebar should feel like a standard SaaS ops dashboard — not a mobile app
- The DaisyUI "logistics" theme is already configured in `index.css` with `tw-` prefix — all DaisyUI classes use this prefix
- IBM Plex Mono already loaded as `--font-mono` — gives numbers a technical, high-precision look matching the logistics identity
- QR print sheet is for the morning workflow: office prints one sheet, drivers identify their section and scan their QR codes with their phones

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- DaisyUI 5 with custom "logistics" theme already configured in `index.css` with `tw-` prefix
- CSS design tokens well-established: `--color-surface-*`, `--color-accent`, `--color-text-*`, `--color-success/danger/info/warning`, spacing scale, radii, shadows
- `--font-mono` (IBM Plex Mono) already loaded for technical/numeric use
- `--sidebar-collapsed` (64px) and `--sidebar-expanded` (220px) CSS variables defined
- UploadRoutes already partially uses DaisyUI components (`tw-alert`, `tw-collapse`, `tw-table`, `tw-stats`) — serves as the migration pattern reference
- `framer-motion` available (used in RunHistory for animated expand/collapse)

### Established Patterns
- State-based "routing" in App.tsx (`type Page = "upload" | "live-map" | "run-history" | "fleet"`)
- Data-driven nav items array (`NAV_ITEMS`) — easy to update icons
- API health polling every 30s with health dot indicator in sidebar footer
- Each page is a standalone component with its own `.css` file
- Inline editing pattern in FleetManagement (edit row replaces display row)

### Integration Points
- `App.tsx` sidebar: NAV_ITEMS array needs icon property changed from string emoji to React component (lucide-react)
- `App.tsx` sidebar: responsive breakpoints need CSS media queries + conditional rendering for mobile drawer
- Each page component: add skeleton/empty states at the loading/empty render branches
- `index.css`: may need global `.numeric` class for tabular-nums
- Backend QR sheet endpoint (`getQrSheetUrl()` in `lib/api.ts`): print styles applied there

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 06-dashboard-ui-overhaul*
*Context gathered: 2026-03-01*
