# Phase 6: Dashboard UI Overhaul - Research

**Researched:** 2026-03-01
**Domain:** Frontend UI -- DaisyUI 5, Tailwind CSS 4, lucide-react, responsive layouts, print CSS
**Confidence:** HIGH

## Summary

Phase 6 transforms all 4 dashboard pages (Upload, Live Map, Run History, Fleet Management) from mixed raw-CSS/DaisyUI into a consistent professional logistics SaaS UI. The project already has DaisyUI 5.5.19 installed with a custom "logistics" theme and `tw-` prefix. Tailwind CSS 4 is configured via CSS-first setup (`@import "tailwindcss" prefix(tw)` in `index.css`). The UploadRoutes page already partially uses DaisyUI components (`tw-alert`, `tw-collapse`, `tw-table`, `tw-stats`) and serves as the migration reference pattern.

The primary work is: (1) replace the hover-expand sidebar with a responsive sidebar using CSS media queries + DaisyUI drawer for mobile, replacing emoji icons with lucide-react SVGs; (2) add skeleton loading states and meaningful empty states to all 4 pages; (3) rewrite route cards using DaisyUI card components with color-coded status badges; (4) apply `font-variant-numeric: tabular-nums` with `--font-mono` across all numeric surfaces; and (5) enhance the backend QR print sheet with larger QR codes, `break-inside: avoid`, and full route summary metadata.

**Primary recommendation:** Migrate component-by-component, starting with App.tsx sidebar (affects all pages), then page-by-page. Use DaisyUI's built-in `tw-skeleton` utility for loading states, lucide-react for all icons, and CSS `@media` queries for responsive breakpoints (no JS matchMedia needed since Tailwind/DaisyUI handle responsive classes).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

#### Sidebar & Navigation
- At >= 1280px: full 220px sidebar always visible (no hover-expand interaction needed)
- At < 1280px (tablet): collapsed to 64px icon-only strip
- At < 768px (mobile): sidebar hidden entirely; DaisyUI drawer component opens from left via hamburger icon in top-left corner
- Replace all emoji icons with lucide-react SVG icons
- Brand area also gets a lucide SVG icon replacement

#### Loading & Empty States
- Use DaisyUI's built-in `tw-skeleton` utility classes for loading placeholders
- Skeleton loading shown on initial page load only -- when refreshing, keep existing data visible with subtle loading indicator (spinner in button, or disabled state)
- Every page gets a meaningful empty state: lucide icon + descriptive message + primary action button

#### Route Cards & Status Badges
- Rewrite route cards using DaisyUI card components (`tw-card`, `tw-card-body`, `tw-card-title`)
- Keep all 4 metrics (stops, km, min, kg) visible in card header row
- All numeric table cells and stat values use IBM Plex Mono (`--font-mono`) with `font-variant-numeric: tabular-nums`
- Apply tabular-number treatment across all 4 pages

#### QR Print Layout
- QR labels include full route summary: vehicle ID, driver name, stop count, total distance, total weight
- Page break strategy: pack as many vehicle QR blocks per page as possible, never split a single vehicle's QR codes across a page boundary (`break-inside: avoid`)

### Claude's Discretion
- Lucide icon selection for brand area and nav items (optimize for readability at 32px)
- Lucide icon style (outlined vs filled) -- pick most readable for narrow sidebar
- Status badge design for route cards -- determine from available API data whether 3-state or 2-state makes sense
- Live Map loading state design
- QR code physical size on print sheet (optimize for scanning from arm's length in three-wheeler cab)
- Which surfaces get `@media print` styles

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DASH-01 | All 4 dashboard pages use DaisyUI component vocabulary consistently (no mixed raw CSS + DaisyUI) | DaisyUI 5.5.19 with `tw-` prefix already configured; UploadRoutes has partial migration as reference pattern; standard component classes documented (card, table, badge, alert, collapse, stat, skeleton, drawer) |
| DASH-02 | Sidebar uses SVG icons (lucide-react) instead of emoji for navigation items | lucide-react provides tree-shakable React components; 14 emoji locations identified across codebase; recommended icon mappings provided |
| DASH-03 | Every page shows skeleton loading state while data loads and meaningful empty state when no data exists | DaisyUI `tw-skeleton` utility creates animated loading placeholders; each page's loading/empty branches identified; skeleton pattern and empty state pattern documented |
| DASH-04 | Numeric values use tabular-number font variant for column alignment | `.numeric` class pattern already exists in RunHistory.css and FleetManagement.css (`font-family: var(--font-mono); font-variant-numeric: tabular-nums`); needs extension to UploadRoutes and LiveMap/StatsBar |
| DASH-05 | Route cards display color-coded status badges (green=complete, amber=in-progress, red=issues) | DaisyUI badge classes (`tw-badge-success`, `tw-badge-warning`, `tw-badge-error`); status data available via `RouteStop.status` field (pending/delivered/failed); 3-state mapping recommended |
| DASH-06 | Sidebar collapses to icon-only below 1280px and uses DaisyUI drawer on mobile | DaisyUI drawer component with `tw-drawer-toggle` + checkbox pattern; 3-tier responsive layout (>=1280: full, <1280: icon-only, <768: drawer); CSS media queries handle breakpoints |
| DASH-07 | QR sheet prints cleanly with large QR codes, vehicle name, and driver name via @media print | Backend QR sheet already has basic print styles; needs `break-inside: avoid`, larger QR image size (200-220px), and full route summary metadata |
</phase_requirements>

## Standard Stack

### Core (already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| DaisyUI | 5.5.19 | UI component classes | Already configured with custom "logistics" theme and `tw-` prefix |
| Tailwind CSS | 4.2.1 | Utility-first CSS framework | CSS-first config via `@import "tailwindcss" prefix(tw)` |
| React | 19.2.0 | UI framework | Already the project framework |
| framer-motion | 12.34.3 | Animations (expand/collapse) | Already used in RunHistory for animated table rows |

### To Install
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| lucide-react | latest | SVG icon components | Replace all emoji icons (14 locations); tree-shakable, each icon is ~200B |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| lucide-react | heroicons/react | Lucide has more icons (1500+), already referenced in CONTEXT.md as the decision |
| DaisyUI skeleton | custom skeleton CSS | DaisyUI's built-in skeleton handles animation and theming automatically |
| CSS media queries for responsive | JS matchMedia hook | CSS handles this natively with Tailwind responsive prefixes; no JS needed |

**Installation:**
```bash
cd apps/kerala_delivery/dashboard
npm install lucide-react
```

## Architecture Patterns

### Recommended File Structure Changes
```
src/
├── App.tsx              # Sidebar overhaul: responsive + drawer + lucide icons
├── App.css              # Sidebar CSS: 3-tier responsive breakpoints
├── index.css            # Global: .numeric class, @media print utilities
├── hooks/
│   └── useMediaQuery.ts # Optional: only if JS-level breakpoint detection needed
├── components/
│   ├── Skeleton.tsx      # Reusable skeleton loader shapes (table, card, stats)
│   ├── EmptyState.tsx    # Reusable empty state (icon + message + CTA)
│   ├── StatusBadge.tsx   # Color-coded badge component wrapping DaisyUI
│   ├── StatsBar.tsx      # Migrate to DaisyUI stat component
│   ├── VehicleList.tsx   # Replace emoji with lucide icons
│   └── RouteMap.tsx      # Minor: replace theme toggle emoji
├── pages/
│   ├── UploadRoutes.tsx  # Rewrite route cards → DaisyUI card; add skeleton/empty
│   ├── LiveMap.tsx       # Add skeleton loading state; empty state for no routes
│   ├── RunHistory.tsx    # Migrate table to DaisyUI table; add skeleton/empty
│   └── FleetManagement.tsx  # Migrate table to DaisyUI table; add skeleton/empty
```

### Pattern 1: DaisyUI Class Prefixing (`tw-` prefix)
**What:** All DaisyUI and Tailwind classes use the `tw-` prefix to prevent CSS variable collision with existing design tokens.
**When to use:** Every DaisyUI/Tailwind class in JSX.
**Example:**
```tsx
// Source: Verified from project's index.css and existing UploadRoutes.tsx
// CORRECT: tw- prefix on all DaisyUI classes
<div className="tw-card tw-bg-base-100 tw-shadow-sm">
  <div className="tw-card-body">
    <h2 className="tw-card-title">Route VEH-01</h2>
    <div className="tw-badge tw-badge-success">Complete</div>
  </div>
</div>

// WRONG: missing prefix
<div className="card bg-base-100">
```

### Pattern 2: Responsive Sidebar with DaisyUI Drawer
**What:** Three-tier responsive sidebar: full (>=1280px), icon-only (<1280px), hidden+drawer (<768px).
**When to use:** App.tsx root layout.
**Example:**
```tsx
// Source: DaisyUI drawer docs + project CONTEXT.md decisions
// The sidebar is always rendered via CSS — no JS matchMedia needed
// DaisyUI drawer handles the mobile overlay behavior

// In App.tsx:
<div className="tw-drawer">
  <input id="mobile-drawer" type="checkbox" className="tw-drawer-toggle" />
  <div className="tw-drawer-content">
    {/* Desktop/tablet sidebar is a fixed aside, not inside drawer-content */}
    <aside className="app-sidebar">
      {/* Brand + Nav + Health — same as current, but with lucide icons */}
    </aside>
    {/* Mobile hamburger — only visible below 768px */}
    <label htmlFor="mobile-drawer" className="mobile-menu-btn">
      <Menu size={24} />
    </label>
    <main className="app-main">
      {/* Page content */}
    </main>
  </div>
  <div className="tw-drawer-side">
    <label htmlFor="mobile-drawer" className="tw-drawer-overlay" />
    {/* Mobile nav — full sidebar content */}
    <nav className="tw-menu tw-bg-base-200 tw-min-h-full tw-w-64 tw-p-4">
      {NAV_ITEMS.map(item => (
        <li key={item.page}><button onClick={...}>{item.icon} {item.label}</button></li>
      ))}
    </nav>
  </div>
</div>
```

**CSS approach for 3-tier sidebar:**
```css
/* Full sidebar at >= 1280px */
.app-sidebar {
  width: var(--sidebar-expanded); /* 220px */
  /* Labels visible, icons visible */
}

/* Icon-only at < 1280px */
@media (max-width: 1279px) {
  .app-sidebar {
    width: var(--sidebar-collapsed); /* 64px */
  }
  .sidebar-nav-label,
  .sidebar-brand-text,
  .sidebar-health-label {
    display: none;
  }
}

/* Hidden at < 768px — DaisyUI drawer takes over */
@media (max-width: 767px) {
  .app-sidebar {
    display: none;
  }
  .mobile-menu-btn {
    display: flex;
  }
}
```

### Pattern 3: Skeleton Loading States
**What:** Show skeleton placeholders that match the shape of the actual content, not a generic spinner.
**When to use:** Initial page load only (not on refresh with existing data).
**Example:**
```tsx
// Source: DaisyUI skeleton docs + project CONTEXT.md

// Table skeleton (for RunHistory, FleetManagement)
function TableSkeleton({ rows = 5, cols = 6 }: { rows?: number; cols?: number }) {
  return (
    <table className="tw-table">
      <thead>
        <tr>
          {Array.from({ length: cols }).map((_, i) => (
            <th key={i}><div className="tw-skeleton tw-h-4 tw-w-20" /></th>
          ))}
        </tr>
      </thead>
      <tbody>
        {Array.from({ length: rows }).map((_, r) => (
          <tr key={r}>
            {Array.from({ length: cols }).map((_, c) => (
              <td key={c}><div className="tw-skeleton tw-h-4 tw-w-full" /></td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

// Card skeleton (for UploadRoutes route cards)
function CardSkeleton() {
  return (
    <div className="tw-card tw-bg-base-100 tw-shadow-sm">
      <div className="tw-card-body">
        <div className="tw-skeleton tw-h-6 tw-w-32" />
        <div className="tw-flex tw-gap-4">
          <div className="tw-skeleton tw-h-4 tw-w-16" />
          <div className="tw-skeleton tw-h-4 tw-w-16" />
          <div className="tw-skeleton tw-h-4 tw-w-16" />
        </div>
      </div>
    </div>
  );
}
```

### Pattern 4: Meaningful Empty States
**What:** When data is empty, show a helpful illustration (lucide icon) + message + primary action.
**When to use:** Every page when no data exists.
**Example:**
```tsx
// Source: CONTEXT.md decisions
import { Truck, Upload, ClipboardList, MapPin } from 'lucide-react';

function EmptyState({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction,
}: {
  icon: React.ComponentType<{ size?: number; className?: string }>;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className="tw-flex tw-flex-col tw-items-center tw-justify-center tw-py-16 tw-text-center">
      <Icon size={48} className="tw-text-base-content/30 tw-mb-4" />
      <h3 className="tw-text-lg tw-font-semibold tw-text-base-content/70">{title}</h3>
      <p className="tw-text-sm tw-text-base-content/50 tw-mt-1 tw-max-w-sm">{description}</p>
      {actionLabel && onAction && (
        <button className="tw-btn tw-btn-primary tw-mt-4" onClick={onAction}>
          {actionLabel}
        </button>
      )}
    </div>
  );
}

// Usage in FleetManagement:
<EmptyState
  icon={Truck}
  title="No vehicles yet"
  description="Add a vehicle to start assigning delivery routes."
  actionLabel="Add Vehicle"
  onAction={() => setShowAddForm(true)}
/>
```

### Pattern 5: Status Badges
**What:** Color-coded DaisyUI badges for route/delivery status.
**When to use:** Route cards, run history table, anywhere status is displayed.
**Example:**
```tsx
// Status badge using DaisyUI semantic colors
function StatusBadge({ status }: { status: 'pending' | 'delivered' | 'failed' | 'completed' | 'running' }) {
  const badgeClass = {
    delivered: 'tw-badge-success',
    completed: 'tw-badge-success',
    pending: 'tw-badge-warning',
    running: 'tw-badge-warning',
    failed: 'tw-badge-error',
  }[status] ?? 'tw-badge-ghost';

  return (
    <span className={`tw-badge tw-badge-sm ${badgeClass}`}>
      {status}
    </span>
  );
}
```

### Anti-Patterns to Avoid
- **Mixing raw CSS colors with DaisyUI theme colors:** Use DaisyUI semantic classes (`tw-text-success`, `tw-bg-error`) instead of inline `style={{ color: '#16A34A' }}`. The DaisyUI theme handles color consistency.
- **Using `onMouseEnter`/`onMouseLeave` for sidebar expand:** The current hover-expand behavior is being replaced with CSS media queries. Remove the JS hover state entirely.
- **Creating new CSS files for skeleton/empty components:** Use DaisyUI utility classes inline in JSX. These components are simple enough to not need dedicated CSS files.
- **Using JS `window.matchMedia()` for responsive layout:** Tailwind/CSS media queries handle responsive breakpoints. JS-based breakpoint detection adds unnecessary complexity and causes layout flicker.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SVG icons | Custom SVG sprite or inline SVGs | lucide-react components | Tree-shakable, consistent sizing, TypeScript props for color/size/strokeWidth |
| Loading skeletons | Custom CSS animation + placeholder divs | DaisyUI `tw-skeleton` class | Already themed, handles animation, pulse timing, border-radius matching |
| Mobile sidebar drawer | Custom JS overlay + backdrop + animation | DaisyUI `tw-drawer` + `tw-drawer-toggle` | Handles overlay, scroll lock, close-on-click, accessibility (aria labels) |
| Status badge colors | Inline style with hex colors | DaisyUI `tw-badge-success/warning/error` | Stays consistent with theme, handles contrast automatically |
| Responsive breakpoints | JS `matchMedia` hook + state | CSS `@media` queries + Tailwind responsive prefixes | Zero JS cost, no layout flicker, SSR-safe |

**Key insight:** DaisyUI 5 provides all the component primitives this phase needs. The work is migration (rewriting existing raw CSS to use DaisyUI classes), not building new components from scratch.

## Common Pitfalls

### Pitfall 1: Forgetting `tw-` Prefix on DaisyUI Classes
**What goes wrong:** Classes like `card`, `badge`, `skeleton` render nothing -- no styles applied.
**Why it happens:** The project uses `prefix(tw)` in Tailwind config, so ALL Tailwind/DaisyUI classes need the `tw-` prefix.
**How to avoid:** Every DaisyUI class in JSX must start with `tw-`. Search for bare DaisyUI class names in PR review.
**Warning signs:** Components render but have no styling; dev tools show no matching CSS rules.

### Pitfall 2: Breaking the Grid Layout When Restructuring Sidebar
**What goes wrong:** Main content area shifts, overlaps, or doesn't fill viewport after sidebar changes.
**Why it happens:** Current layout uses CSS Grid with `grid-template-columns: var(--sidebar-collapsed) 1fr`. Changing the sidebar from fixed-position to drawer-based requires updating the grid.
**How to avoid:** Test all three responsive tiers (>=1280, <1280, <768) after every sidebar change. The grid column for the sidebar must match the sidebar's actual width at each breakpoint.
**Warning signs:** Content area has horizontal gap on mobile; sidebar overlaps content on tablet.

### Pitfall 3: Skeleton Shapes Not Matching Actual Content
**What goes wrong:** Skeleton shows wrong proportions, causing jarring layout shift when real data loads.
**Why it happens:** Skeleton placeholders are generic boxes instead of matching the actual component dimensions.
**How to avoid:** Make skeleton match the real component's height, width, and grid structure. Use the same container layout (card, table, flex row) for both skeleton and real content.
**Warning signs:** Visible "jump" when data loads, elements shifting position.

### Pitfall 4: Print Styles Not Tested with Actual Printers
**What goes wrong:** QR codes print too small to scan, or card boundaries get cut off at page breaks.
**Why it happens:** Browser print preview != actual printer output. Margins, scaling, and DPI differ.
**How to avoid:** Use `@page { size: A4; margin: 10mm; }` (already in backend). Set QR code size to 200-220px for arm-length scanning. Use `break-inside: avoid` on card containers. Test with Chrome print preview at minimum.
**Warning signs:** QR code scanning failures in the field; drivers reporting unreadable codes.

### Pitfall 5: Removing Existing CSS Design Tokens Prematurely
**What goes wrong:** Components that haven't been migrated yet lose their styling.
**Why it happens:** Eagerly deleting CSS custom properties (`--color-surface-*`, `--color-text-*`) that are still referenced by unmigrated CSS.
**How to avoid:** Keep ALL existing CSS custom properties in `index.css` during migration. Only remove deprecated tokens after ALL pages have been fully migrated and verified. The `index.css` comment "Legacy aliases" already marks safe-to-remove tokens.
**Warning signs:** Unmigrated components suddenly have wrong colors or missing backgrounds.

### Pitfall 6: Inconsistent Numeric Alignment Across Pages
**What goes wrong:** Numbers in one table align correctly but another table's numbers jump around.
**Why it happens:** Missing `font-variant-numeric: tabular-nums` on some numeric elements. Or mixing `--font-heading` (DM Sans, proportional) with `--font-mono` (IBM Plex Mono, monospaced) for numbers.
**How to avoid:** Create a single `.numeric` utility class in `index.css` and apply it consistently. Verify every `<td>` and `<span>` showing numbers uses this class.
**Warning signs:** Numbers in columns don't line up vertically; different widths for the digit "1" vs "0".

## Code Examples

### Lucide-React Icon Usage (with `tw-` Prefix Tailwind Classes)
```tsx
// Source: Context7 /websites/lucide_dev_guide_packages
import { Upload, Map, ClipboardList, Truck, Fuel, Menu, Package, Ruler, Scale } from 'lucide-react';

// NAV_ITEMS with lucide-react components instead of emoji strings
const NAV_ITEMS: { page: Page; icon: React.ComponentType<{ size?: number }>; label: string }[] = [
  { page: "upload", icon: Upload, label: "Upload & Routes" },
  { page: "live-map", icon: Map, label: "Live Map" },
  { page: "run-history", icon: ClipboardList, label: "Run History" },
  { page: "fleet", icon: Truck, label: "Fleet" },
];

// Rendering in sidebar:
{NAV_ITEMS.map(({ page, icon: Icon, label }) => (
  <button key={page} className={`sidebar-nav-item ${activePage === page ? "active" : ""}`}>
    <Icon size={20} />
    <span className="sidebar-nav-label">{label}</span>
  </button>
))}
```

### DaisyUI Route Card with Status Badge
```tsx
// Source: DaisyUI card + badge docs, adapted for tw- prefix
<div className="tw-card tw-bg-base-100 tw-shadow-sm">
  <div className="tw-card-body tw-p-4">
    <div className="tw-flex tw-items-center tw-justify-between">
      <h2 className="tw-card-title tw-text-sm">
        <span className="tw-badge tw-badge-neutral tw-font-mono">{route.vehicle_id}</span>
        <span className="tw-text-base-content/60">{route.driver_name}</span>
      </h2>
      <StatusBadge status={routeStatus} />
    </div>
    <div className="tw-flex tw-gap-4 tw-mt-2">
      <span className="numeric"><strong>{route.total_stops}</strong> stops</span>
      <span className="numeric"><strong>{route.total_distance_km}</strong> km</span>
      <span className="numeric"><strong>{Math.round(route.total_duration_minutes)}</strong> min</span>
      <span className="numeric"><strong>{route.total_weight_kg}</strong> kg</span>
    </div>
  </div>
</div>
```

### Global `.numeric` Utility Class
```css
/* Add to index.css -- applies tabular-nums consistently */
.numeric {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}
```

### QR Print Sheet Improvements (Backend)
```css
/* Enhanced print styles for apps/kerala_delivery/api/main.py QR sheet */
.card {
  break-inside: avoid;      /* Never split a vehicle's card across pages */
  page-break-inside: avoid; /* Legacy browser support */
}

.qr-img {
  width: 220px;   /* Larger for arm-length scanning in three-wheeler cab */
  height: 220px;
}

/* Full route summary in card header */
.card-stats {
  display: flex;
  gap: 12px;
  margin-bottom: 10px;
  font-variant-numeric: tabular-nums;
}
```

## Emoji-to-Lucide Icon Mapping

Based on codebase analysis, these 14 emoji locations need replacement:

| File | Current Emoji | Recommended Lucide Icon | Rationale |
|------|---------------|------------------------|-----------|
| App.tsx (nav) | `📤` Upload & Routes | `Upload` | Standard upload icon |
| App.tsx (nav) | `🗺️` Live Map | `Map` | Standard map icon |
| App.tsx (nav) | `📋` Run History | `ClipboardList` | Clipboard with list items |
| App.tsx (nav) | `🚛` Fleet | `Truck` | Vehicle/fleet icon |
| App.tsx (brand) | `⛽` Kerala LPG | `Fuel` | Fuel/gas pump icon |
| UploadRoutes | `📄` file icon | `FileText` | File with content |
| UploadRoutes | `⚠️` error icon | `AlertTriangle` | Warning triangle |
| UploadRoutes | `🖨️` Print QR Sheet | `Printer` | Print icon |
| FleetManagement | `✏️` Edit | `Pencil` | Edit/pencil icon |
| VehicleList | `📦` stops | `Package` | Package/delivery icon |
| VehicleList | `📏` distance | `Ruler` | Measurement icon |
| VehicleList | `⚖️` weight | `Scale` | Weight/scale icon |
| RouteMap | `🌙`/`☀️` theme | `Moon`/`Sun` | Theme toggle icons |

## Current State Audit

### What Already Uses DaisyUI (tw- prefix)
- **UploadRoutes.tsx**: `tw-alert`, `tw-alert-success/warning/error`, `tw-collapse`, `tw-collapse-arrow`, `tw-collapse-title`, `tw-collapse-content`, `tw-table`, `tw-table-sm`, `tw-stats`, `tw-stat`, `tw-stat-title`, `tw-stat-value`, `tw-stat-desc`, `tw-overflow-x-auto`
- **index.css**: Full DaisyUI theme configuration with `@plugin "daisyui"` and custom "logistics" theme

### What Uses Raw CSS (needs migration to DaisyUI)
- **App.tsx/App.css**: Entire sidebar (brand, nav, health indicator) -- raw CSS with design tokens
- **LiveMap.tsx/LiveMap.css**: Loading spinner, error banner, layout -- raw CSS
- **RunHistory.tsx/RunHistory.css**: Table, status badges, loading state -- raw CSS with `.numeric` class
- **FleetManagement.tsx/FleetManagement.css**: Table, buttons, forms, loading state -- raw CSS with `.numeric` class
- **StatsBar.tsx/StatsBar.css**: Stat cards -- raw CSS (should become `tw-stat`)
- **VehicleList.tsx/VehicleList.css**: Vehicle items, progress bars -- raw CSS

### Pages with Existing Loading States (need skeleton replacement)
| Page | Current Loading State | Current Empty State |
|------|----------------------|---------------------|
| LiveMap | Custom spinner div (`loading-spinner` CSS class) | "No active routes" text-only |
| RunHistory | Custom spinner div (`loading-spinner` CSS class) | "No optimization runs yet" text in `<td>` |
| FleetManagement | Custom spinner div (`loading-spinner` CSS class) | "No vehicles found" text in `<td>` |
| UploadRoutes | Custom spinner with progress text | None (starts in "idle" workflow state) |

### Responsive State
| Current | Target |
|---------|--------|
| Sidebar: hover-expand (64px -> 220px via JS `onMouseEnter`) | Sidebar: CSS media query (>=1280: 220px, <1280: 64px, <768: hidden + drawer) |
| Grid: `grid-template-columns: var(--sidebar-collapsed) 1fr` | Grid: responsive columns matching sidebar width at each breakpoint |
| Only UploadRoutes has `@media (max-width: 768px)` | All pages responsive at 768px and 1280px breakpoints |

## Status Badge Design Decision

**Recommendation: 3-state badges for route cards.**

The API data supports 3 states via `RouteStop.status`:
- `"delivered"` -> `tw-badge-success` (green) -- delivery completed
- `"pending"` -> `tw-badge-warning` (amber) -- awaiting delivery
- `"failed"` -> `tw-badge-error` (red) -- delivery attempt failed

For route-level badges (on the card header), derive from stop-level data:
- All stops delivered -> "Complete" (green)
- Some stops pending + some delivered -> "In Progress" (amber)
- Any stops failed -> "Issues" (red) -- red takes priority

For optimization run status (`OptimizationRun.status`):
- `"completed"` -> `tw-badge-success` (green)
- `"running"` -> `tw-badge-warning` (amber)
- `"failed"` -> `tw-badge-error` (red)

## QR Sheet Enhancement Details

The backend QR sheet (`/api/qr-sheet` in `main.py`) already has:
- A4 page sizing with 10mm margins
- 2-column grid layout for vehicle cards
- `page-break-inside: avoid` on cards (using old property name)
- PNG QR codes (base64 inline) at 150x150px
- Vehicle ID, driver name, stops, distance, duration, weight

**What needs changing for DASH-07:**
1. Increase QR image size from 150px to 200-220px (optimize for arm-length scanning in three-wheeler cab)
2. Add `break-inside: avoid` (modern property) alongside existing `page-break-inside: avoid`
3. Verify full route summary is already present (it is -- vehicle ID, driver name, stop count, distance, duration, weight are all included)
4. Consider increasing font sizes in card header for readability from arm's length

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Tailwind CSS 3 config file | Tailwind CSS 4 CSS-first config | Tailwind v4 (2024) | No `tailwind.config.js` needed; config in `index.css` via `@import` and `@plugin` |
| DaisyUI 4 `@tailwindcss/plugin` | DaisyUI 5 `@plugin "daisyui"` | DaisyUI v5 (2025) | Theme defined via `@plugin "daisyui/theme"` in CSS |
| `page-break-inside: avoid` | `break-inside: avoid` | CSS Fragmentation Level 3 | Modern browsers support both; use both for compatibility |
| Custom icon sprites/fonts | Tree-shakable icon components (lucide-react) | ~2022+ | Per-icon imports, ~200B per icon, full TypeScript support |

**Deprecated/outdated:**
- `page-break-inside`: Use `break-inside` (CSS Fragmentation Level 3) as the primary, with `page-break-inside` as fallback
- `onMouseEnter`/`onMouseLeave` for sidebar: Being replaced by CSS-only responsive behavior (per CONTEXT.md decision)

## Open Questions

1. **Route-level status derivation logic**
   - What we know: Individual stop statuses are `pending`, `delivered`, `failed`. The `RouteSummary` type does not include a status field.
   - What's unclear: Whether to compute route-level status client-side (from stop data) or add a field to the backend API.
   - Recommendation: Compute client-side from `RouteDetail.stops` -- the data is already fetched. No backend change needed.

2. **Live Map skeleton design**
   - What we know: The Live Map has a unique 3-panel layout (stats bar + vehicle list + map canvas). A generic table skeleton won't work.
   - What's unclear: What skeleton shape makes sense for a map area.
   - Recommendation: Show skeleton for stats bar (horizontal skeleton blocks matching stat card layout) and vehicle list (list of skeleton rows). For the map canvas, show a solid gray placeholder with a subtle "Loading map..." text center-aligned. Maps don't have a natural skeleton shape.

3. **Sidebar CSS vs DaisyUI drawer integration**
   - What we know: Desktop/tablet sidebar uses raw CSS (brand, nav items, health dot). Mobile uses DaisyUI drawer.
   - What's unclear: Whether the desktop sidebar should also use DaisyUI menu classes or stay with raw CSS.
   - Recommendation: Keep the desktop sidebar with raw CSS (it's already well-styled with design tokens) and only use DaisyUI drawer for the mobile overlay. The two don't need to share the same component classes -- they serve different responsive contexts.

## Sources

### Primary (HIGH confidence)
- Context7 `/saadeghi/daisyui` - Drawer component, skeleton utility, badge component, card component
- Context7 `/websites/lucide_dev_guide_packages` - lucide-react usage, tree-shaking, props API
- Project codebase: `apps/kerala_delivery/dashboard/` - all .tsx, .css files, package.json, vite.config.ts

### Secondary (MEDIUM confidence)
- DaisyUI v5 `@plugin` syntax verified in project's own `index.css` (confirmed working)
- CSS `break-inside: avoid` support verified via project's existing `page-break-inside: avoid` in QR sheet

### Tertiary (LOW confidence)
- QR code scanning distance (200-220px optimal) -- based on general QR scanning guidance, not tested with specific three-wheeler cab environment. Validate during implementation.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already installed/verified except lucide-react (straightforward npm install)
- Architecture: HIGH - Patterns verified from existing codebase (UploadRoutes DaisyUI migration) and DaisyUI docs
- Pitfalls: HIGH - Derived from actual codebase analysis (prefix requirements, grid layout, design token dependencies)

**Research date:** 2026-03-01
**Valid until:** 2026-03-31 (stable libraries, no fast-moving changes expected)
