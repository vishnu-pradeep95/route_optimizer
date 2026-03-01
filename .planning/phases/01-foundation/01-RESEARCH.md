# Phase 1: Foundation - Research

**Researched:** 2026-03-01
**Domain:** Tailwind CSS v4 + DaisyUI v5 integration, Tailwind standalone CLI, pytest configuration
**Confidence:** HIGH

## Summary

Phase 1 is a foundation phase with five discrete tasks: (1) install Tailwind 4 + DaisyUI 5 into the existing React+Vite dashboard with a collision-safe prefix, (2) define a logistics SaaS design theme, (3) set up the Tailwind standalone CLI for the driver PWA's static CSS, (4) update all test fixtures from Kochi to Vatakara coordinates, and (5) configure pytest-asyncio's `asyncio_mode=auto`.

The dashboard is a React 19 + Vite 7 app with an extensive custom CSS variable system (`--color-accent`, `--color-surface`, `--color-text-primary`, etc.) in `index.css`. The critical risk is Tailwind v4's default behavior of emitting `--color-*` CSS variables onto `:root`, which would collide with these existing tokens. The `prefix(tw)` feature namespaces both utility classes (as `tw:flex`, `tw:bg-red-500`) and CSS variables (as `--tw-color-*`), preventing collision. This must be verified in DevTools before any utility classes are written.

The driver PWA (`driver_app/index.html`) is a standalone HTML/JS app with no build step. It needs pre-compiled Tailwind CSS via the `tailwind-cli-extra` standalone binary, which bundles both Tailwind v4.2.1 and DaisyUI v5.5.19. This avoids CDN dependency and supports offline operation. The test infrastructure changes are straightforward: replace Kochi coordinates (9.97N) with Vatakara (11.52N) in 12 test files, and add `asyncio_mode = auto` to a new `pytest.ini`.

**Primary recommendation:** Install `@tailwindcss/vite` plugin + `daisyui` package, use `@import "tailwindcss" prefix(tw); @plugin "daisyui";` in CSS, verify zero collision in DevTools `:root` before writing any utility classes, then use `tailwind-cli-extra` binary for PWA CSS generation.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DASH-01 | Install Tailwind 4 + DaisyUI 5 with collision-safe prefix (`tw`) in Vite pipeline | Tailwind `@tailwindcss/vite` plugin + `@import "tailwindcss" prefix(tw)` + `@plugin "daisyui"` -- verified syntax from official docs. `prefix(tw)` namespaces both classes and CSS variables to `--tw-*` preventing collision with existing `--color-*` tokens. |
| DASH-02 | Define logistics SaaS theme (clean colors, professional typography, consistent spacing) | DaisyUI 5 custom theme via `@plugin "daisyui/theme" { ... }` with oklch colors. Map existing design tokens from `index.css` to DaisyUI semantic colors (primary, secondary, accent, neutral, base-100/200/300, success/warning/error/info). |
| PWA-01 | Pre-compiled Tailwind CSS via standalone CLI (no CDN, offline-capable) | `tailwind-cli-extra` binary (v2.8.1) bundles Tailwind 4.2.1 + DaisyUI 5.5.19. Download Linux x64 binary, create `pwa-input.css` with `@import "tailwindcss" prefix(tw); @plugin "daisyui";`, compile to static `tailwind.css`, reference via `<link>` in PWA `index.html`. |
| TEST-01 | Fix E2E test coordinates -- use Vatakara (11.52N) instead of Kochi (9.97N) | 12 test files reference Kochi (lat ~9.97). Replace with Vatakara depot (lat 11.624, lon 75.580 from `config.py`) and Vatakara-area delivery landmarks. Add assertion that test depot matches `config.DEPOT_LOCATION`. |
| TEST-06 | Async test configuration -- set `asyncio_mode=auto` in `pytest.ini` | Create `pytest.ini` at project root with `[pytest]\nasyncio_mode = auto`. pytest-asyncio 1.3.0 (already in requirements.txt) supports this. Removes need for `@pytest.mark.asyncio` on every async test. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| tailwindcss | 4.2.1 | Utility-first CSS framework | Current stable; CSS-variable theming, no JS config needed. Already committed to in PROJECT.md. |
| @tailwindcss/vite | 4.2.1 | First-party Vite integration | Tight Vite integration, automatic content detection, maximum performance. Required for Tailwind v4 + Vite. |
| daisyui | 5.5.19 | Semantic component classes on Tailwind | v5 is Tailwind v4-native, zero deps, 34 kB CSS. Ships Card, Table, Badge, Stats, Navbar -- all needed for logistics SaaS. |
| tailwind-cli-extra | 2.8.1 | Standalone CLI with DaisyUI bundled | Pre-built binary bundles Tailwind 4.2.1 + DaisyUI 5.5.19. Generates static CSS without Node.js -- needed for PWA offline CSS. |
| pytest-asyncio | 1.3.0 | Async test support for pytest | Already in requirements.txt. Supports `asyncio_mode=auto` to auto-detect async tests. |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| @fontsource/dm-sans | 5.2.8 | DM Sans font (already installed) | Dashboard headings/UI text -- already the project's chosen font |
| @fontsource/ibm-plex-mono | 5.2.7 | IBM Plex Mono font (already installed) | Dashboard data/numbers -- already the project's chosen monospace font |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| @tailwindcss/vite | @tailwindcss/postcss | PostCSS path is slower, less integrated with Vite. Only needed if Vite plugin causes issues with existing plugins. |
| tailwind-cli-extra | Official tailwindcss standalone CLI + separate daisyui install | Official CLI does not bundle DaisyUI. Would need a node_modules setup or complex manual bundling. tailwind-cli-extra solves this cleanly. |
| DaisyUI custom theme | Raw Tailwind config | DaisyUI themes provide semantic color names and component defaults with less CSS. Raw Tailwind gives more control but more work for same result. |

**Installation:**
```bash
# Dashboard (from apps/kerala_delivery/dashboard/)
npm install tailwindcss@4.2.1 @tailwindcss/vite@4.2.1 daisyui@5.5.19

# PWA standalone CLI (project root or scripts/)
curl -sLO https://github.com/dobicinaitis/tailwind-cli-extra/releases/latest/download/tailwindcss-extra-linux-x64
chmod +x tailwindcss-extra-linux-x64
```

## Architecture Patterns

### Recommended Changes to Project Structure
```
apps/kerala_delivery/dashboard/
  src/
    index.css          # ADD: @import "tailwindcss" prefix(tw); @plugin "daisyui";
    App.css            # KEEP: existing layout CSS unchanged
    App.tsx            # KEEP: no changes in this phase
    components/        # KEEP: existing component CSS files unchanged
    pages/             # KEEP: existing page CSS files unchanged
  vite.config.ts       # MODIFY: add @tailwindcss/vite plugin

apps/kerala_delivery/driver_app/
  pwa-input.css        # NEW: Tailwind input for CLI compilation
  tailwind.css         # NEW: compiled output (committed, served statically)
  index.html           # MODIFY: add <link> to tailwind.css

tools/
  tailwindcss-extra    # NEW: standalone CLI binary (gitignored, downloaded in setup)

pytest.ini             # NEW: asyncio_mode = auto
```

### Pattern 1: Tailwind v4 Prefix Integration in Existing CSS
**What:** Add Tailwind to an existing project without breaking current styles
**When to use:** When the project has custom CSS variables on `:root` that conflict with Tailwind's generated variables
**Example:**
```css
/* src/index.css -- ADD at the TOP, before existing styles */
@import "tailwindcss" prefix(tw);
@plugin "daisyui";

/* All existing CSS variables below remain UNCHANGED */
:root {
  --color-surface-dark: #1C1917;
  --color-surface: #FAFAF9;
  --color-accent: #D97706;
  /* ... existing tokens stay as-is ... */
}
```
After this: Tailwind classes use `tw:` prefix (e.g., `tw:flex`, `tw:bg-amber-600`), Tailwind CSS variables are namespaced as `--tw-color-*`, and existing `--color-*` variables are untouched.

### Pattern 2: DaisyUI Custom Theme Definition
**What:** Define a custom logistics SaaS theme using DaisyUI 5's `@plugin "daisyui/theme"` syntax
**When to use:** When DaisyUI's built-in themes don't match the project's design language
**Example:**
```css
/* src/index.css -- after @plugin "daisyui" */
@plugin "daisyui/theme" {
  name: "logistics";
  default: true;
  color-scheme: light;
  --color-base-100: oklch(98% 0.02 60);      /* Light warm background */
  --color-base-200: oklch(96% 0.02 60);      /* Slightly darker */
  --color-base-300: oklch(93% 0.03 60);      /* Stone-tinted */
  --color-base-content: oklch(22% 0.02 60);  /* Near-black text */
  --color-primary: oklch(60% 0.18 70);       /* Amber 600 -- matches --color-accent */
  --color-primary-content: oklch(98% 0.01 60);
  --color-secondary: oklch(45% 0.06 60);     /* Stone 600 */
  --color-secondary-content: oklch(98% 0.01 60);
  --color-accent: oklch(60% 0.18 70);        /* Same as primary for this project */
  --color-accent-content: oklch(98% 0.01 60);
  --color-neutral: oklch(25% 0.02 60);       /* Dark stone */
  --color-neutral-content: oklch(96% 0.01 60);
  --color-success: oklch(55% 0.2 145);       /* Green 600 */
  --color-success-content: oklch(98% 0.01 145);
  --color-warning: oklch(70% 0.18 70);       /* Amber warm */
  --color-warning-content: oklch(22% 0.02 70);
  --color-error: oklch(55% 0.22 25);         /* Red 600 */
  --color-error-content: oklch(98% 0.01 25);
  --color-info: oklch(55% 0.17 230);         /* Sky 600 */
  --color-info-content: oklch(98% 0.01 230);
}
```

### Pattern 3: Vite Config with Tailwind Plugin
**What:** Add the `@tailwindcss/vite` plugin to the existing Vite config
**When to use:** Always for Tailwind v4 + Vite projects
**Example:**
```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    tailwindcss(),  // Must be before react() for optimal performance
    react(),
  ],
  server: {
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/health': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
```

### Pattern 4: PWA Static CSS via Standalone CLI
**What:** Compile Tailwind CSS for a no-build-step PWA using the standalone binary
**When to use:** When the target app has no Node.js/npm build pipeline (like the driver PWA)
**Example:**
```bash
# Create input CSS file for PWA
cat > apps/kerala_delivery/driver_app/pwa-input.css << 'EOF'
@import "tailwindcss" prefix(tw);
@plugin "daisyui";
EOF

# Compile to static CSS (from project root)
./tools/tailwindcss-extra \
  --input apps/kerala_delivery/driver_app/pwa-input.css \
  --output apps/kerala_delivery/driver_app/tailwind.css \
  --cwd apps/kerala_delivery/driver_app \
  --minify
```

### Pattern 5: Vatakara Test Fixtures
**What:** Replace all Kochi coordinates with Vatakara coordinates that match production config
**When to use:** Every test that creates depot locations or delivery coordinates
**Example:**
```python
# tests/conftest.py -- REPLACE kochi_depot with vatakara_depot
from apps.kerala_delivery.config import DEPOT_LOCATION

@pytest.fixture
def vatakara_depot():
    """Production depot location -- Vatakara, Kozhikode district."""
    return Location(
        latitude=11.624443730714066,
        longitude=75.57964507762223,
        address_text="LPG Godown (Main Depot)",
    )

@pytest.fixture(autouse=True)
def _verify_depot_matches_config(vatakara_depot):
    """Guard: test depot must always match production config."""
    assert vatakara_depot.latitude == pytest.approx(DEPOT_LOCATION.latitude, abs=0.001)
    assert vatakara_depot.longitude == pytest.approx(DEPOT_LOCATION.longitude, abs=0.001)

@pytest.fixture
def sample_locations():
    """5 delivery locations within ~10km of Vatakara depot.
    Real public landmarks near Vatakara, Kozhikode district.
    """
    return [
        Location(latitude=11.5950, longitude=75.5700, address_text="Vatakara Bus Stand"),
        Location(latitude=11.6100, longitude=75.5650, address_text="Vatakara Railway Station"),
        Location(latitude=11.6350, longitude=75.5900, address_text="Chorode Junction"),
        Location(latitude=11.5800, longitude=75.5850, address_text="Memunda"),
        Location(latitude=11.6200, longitude=75.5500, address_text="Edakkad"),
    ]
```

### Anti-Patterns to Avoid
- **Mixing Tailwind v3 and v4 patterns:** Do NOT use `tailwind.config.js` with `@import "tailwindcss"`. Tailwind v4 is CSS-first; the JS config file is a v3 pattern. Using both causes double-processing.
- **Unprefixed Tailwind classes alongside existing CSS:** Without `prefix(tw)`, classes like `bg-red-500` are ambiguous and Tailwind's `:root` variables will collide with existing `--color-*` tokens.
- **DaisyUI CDN in production PWA:** The CDN bundle excludes interactive variant classes and creates a network dependency. Use pre-compiled static CSS instead.
- **Writing utility classes before verifying no collision:** Always check DevTools `:root` first. If `--color-surface` changed after Tailwind install, the prefix is not working correctly.
- **Using `@tailwindcss/browser` in production:** Explicitly marked "development and prototypes only" in official docs. Adds runtime JS overhead and CDN dependency.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| CSS component library | Custom button/card/table CSS classes | DaisyUI 5 component classes (`tw:btn`, `tw:card`, `tw:table`) | DaisyUI handles responsive variants, dark mode, focus states, and accessible markup patterns across 50+ components |
| CSS prefix/namespace system | Manual CSS variable renaming or PostCSS plugin | `@import "tailwindcss" prefix(tw)` | Built into Tailwind v4, handles both class names and CSS variable namespacing automatically |
| Static CSS for no-build PWA | Custom build script with postcss-cli | `tailwind-cli-extra` standalone binary | Single binary, no Node.js dependency, bundles DaisyUI, same command as official CLI |
| oklch color conversion | Manual hex-to-oklch conversion | DaisyUI theme generator or oklch.com | oklch is the required format for DaisyUI v5 themes; hand-converting gets hue angles wrong |
| Design token mapping | Manual CSS variable mapping between systems | DaisyUI custom theme `@plugin "daisyui/theme"` | Maps semantic names (primary, base-100) to actual colors; DaisyUI components reference these names automatically |

**Key insight:** This phase is about installing and configuring existing tools, not building anything custom. Every "build" impulse should be redirected to a configuration option in Tailwind v4 or DaisyUI v5.

## Common Pitfalls

### Pitfall 1: Tailwind v4 CSS Variable Collision
**What goes wrong:** Tailwind v4 emits `--color-*` CSS variables on `:root` that collide with the dashboard's existing tokens (`--color-accent`, `--color-surface`, `--color-text-primary`, etc. defined in `src/index.css`). Colors break silently -- header turns wrong color, fonts revert to system default.
**Why it happens:** Tailwind v4 uses CSS variables for all theme tokens by default. Without prefix, names like `--color-red-500` overlap with the project's `--color-*` namespace.
**How to avoid:** Use `@import "tailwindcss" prefix(tw)` which namespaces ALL Tailwind variables as `--tw-color-*`, `--tw-font-*`, etc. Verify by inspecting `:root` in DevTools after install -- you should see BOTH `--color-accent` (project, value #D97706) AND `--tw-color-amber-600` (Tailwind) without conflict.
**Warning signs:** Colors shift on any page immediately after npm install (before writing any utility classes). `--color-surface` in DevTools shows a different value than defined in `index.css`.

### Pitfall 2: DaisyUI Class Names Require Tailwind Prefix
**What goes wrong:** After enabling `prefix(tw)`, writing `class="btn btn-primary"` does nothing because DaisyUI classes also require the `tw:` prefix when Tailwind prefix is active.
**Why it happens:** DaisyUI injects its classes through Tailwind's plugin system. When Tailwind has a prefix, ALL generated classes (including DaisyUI's) require the prefix.
**How to avoid:** Use `tw:btn tw:btn-primary` in JSX. This is confirmed behavior -- the DaisyUI maintainer (saadeghi) confirmed in issue #3810 (resolved April 2025). Verified working at play.tailwindcss.com/t9nRRiE3JZ.
**Warning signs:** DaisyUI component class names have no visual effect in the browser.

### Pitfall 3: Tailwind Preflight Resetting Existing Styles
**What goes wrong:** Tailwind's Preflight (normalize layer) adds `border-style: solid` to all elements, changes `line-height`, removes default margins. Existing dashboard components that relied on specific browser defaults shift layout.
**Why it happens:** Preflight is included by default with `@import "tailwindcss"`. The dashboard's `index.css` already explicitly resets most of these properties, but there may be components that depend on pre-Tailwind browser defaults.
**How to avoid:** After installing Tailwind, visually check every page in the dashboard BEFORE writing any utility classes. Any layout shift is a Preflight conflict, not a utility bug. The existing `index.css` resets (box-sizing, h* margin, table border-collapse, button font) should override Preflight, but verify. If Preflight causes unresolvable conflicts, it can be disabled with `@layer base { /* override */ }`.
**Warning signs:** Buttons look different, table spacing changes, heading margins disappear -- all before any Tailwind classes are added to JSX.

### Pitfall 4: Standalone CLI Source Detection
**What goes wrong:** Running `tailwindcss-extra --input pwa-input.css --output tailwind.css` from the wrong directory or without `--cwd` causes Tailwind to scan the wrong files for class names, producing a CSS file that's either massive (scanning everything) or empty (scanning nothing).
**Why it happens:** Tailwind v4's CLI auto-detects content files from the working directory. If run from project root, it may scan the entire repo including `node_modules`.
**How to avoid:** Use `--cwd` flag to point to the driver_app directory, OR use `@source` directive in the input CSS to explicitly list paths. Example: `@import "tailwindcss" source(".") prefix(tw);`
**Warning signs:** Compiled CSS is >500KB (scanning too much) or <5KB (scanning too little for DaisyUI components used in the PWA).

### Pitfall 5: pytest-asyncio Mode Warning on Old Default
**What goes wrong:** Without explicit `asyncio_mode` configuration, pytest-asyncio 1.3.0 defaults to `strict` mode, requiring `@pytest.mark.asyncio` on every async test. The project has ~40 async tests all decorated with `@pytest.mark.asyncio` -- removing the decorator only works when `auto` mode is configured.
**Why it happens:** The requirement says to set `asyncio_mode=auto`, but if this is done without simultaneously removing the `@pytest.mark.asyncio` decorators, existing tests still work fine. The pitfall is if someone removes decorators BEFORE adding the config -- tests silently stop running as async.
**How to avoid:** Step 1: Create `pytest.ini` with `asyncio_mode = auto`. Step 2: Verify all 40+ async tests still pass. Step 3 (optional, future): Remove `@pytest.mark.asyncio` decorators from individual test files. The decorators are harmless in `auto` mode, so step 3 is not required for this phase.
**Warning signs:** `PytestUnraisableExceptionWarning` or tests that should be async running synchronously.

### Pitfall 6: Incomplete Kochi-to-Vatakara Coordinate Replacement
**What goes wrong:** Replacing the depot fixture but missing delivery location coordinates that are still in the Kochi area (lat ~9.93-9.98). Tests pass because VROOM accepts any valid lat/lon, but the test suite validates the wrong geography.
**Why it happens:** Kochi coordinates appear in 12 files across fixtures, inline constants, and mock data. Easy to miss inline definitions like `KOCHI_DEPOT = Location(latitude=9.9716, ...)` in `test_e2e_pipeline.py`.
**How to avoid:** Search ALL test files for latitude values in the 9.9-10.0 range. The grep pattern `9\.9[0-9]` catches all Kochi-area coordinates. Replace systematically: depot fixtures get exact `config.DEPOT_LOCATION` values, delivery locations get real Vatakara-area landmarks within 10km radius.
**Warning signs:** Any fixture with latitude ~9.9x still present after the migration.

## Code Examples

Verified patterns from official sources:

### Vite Config with Tailwind Plugin
```typescript
// Source: https://tailwindcss.com/docs (official install guide)
// apps/kerala_delivery/dashboard/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    tailwindcss(),
    react(),
  ],
  server: {
    proxy: {
      '/api': { target: 'http://localhost:8000', changeOrigin: true },
      '/health': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
})
```

### CSS Entry Point with Prefix and DaisyUI
```css
/* Source: https://tailwindcss.com/docs + https://daisyui.com/docs/install/react/ */
/* apps/kerala_delivery/dashboard/src/index.css */

/* Tailwind with prefix to prevent CSS variable collision */
@import "tailwindcss" prefix(tw);

/* DaisyUI component library */
@plugin "daisyui";

/* Custom logistics theme */
@plugin "daisyui/theme" {
  name: "logistics";
  default: true;
  color-scheme: light;
  --color-base-100: oklch(98% 0.02 60);
  --color-base-200: oklch(96% 0.02 60);
  --color-base-300: oklch(93% 0.03 60);
  --color-base-content: oklch(22% 0.02 60);
  --color-primary: oklch(60% 0.18 70);
  --color-primary-content: oklch(98% 0.01 60);
  /* ... */
}

/* === Existing project styles below === */
/* These remain COMPLETELY UNCHANGED */

*,
*::before,
*::after {
  box-sizing: border-box;
}

:root {
  --color-surface-dark: #1C1917;
  --color-surface: #FAFAF9;
  --color-accent: #D97706;
  /* ... all existing tokens preserved ... */
}
```

### Using Prefixed DaisyUI Classes in JSX
```tsx
// Source: https://github.com/saadeghi/daisyui/issues/3810 (confirmed working)
// After prefix(tw) is configured, ALL Tailwind and DaisyUI classes use tw: prefix

// DaisyUI button
<button className="tw:btn tw:btn-primary">Upload CSV</button>

// Mixed Tailwind utilities + DaisyUI components
<div className="tw:card tw:bg-base-100 tw:shadow-md">
  <div className="tw:card-body">
    <h2 className="tw:card-title tw:text-lg tw:font-semibold">Route Summary</h2>
    <p className="tw:text-base-content/70">5 stops, 12.3 km total</p>
  </div>
</div>

// Tailwind utilities alongside existing CSS classes
<aside className={`app-sidebar ${expanded ? "expanded" : ""} tw:transition-all`}>
  {/* existing CSS classes work alongside tw: prefixed utilities */}
</aside>
```

### pytest.ini Configuration
```ini
# Source: https://pytest-asyncio.readthedocs.io/en/stable/reference/configuration.html
# pytest.ini (project root)
[pytest]
asyncio_mode = auto
```

### PWA Standalone CLI Build Command
```bash
# Source: https://github.com/dobicinaitis/tailwind-cli-extra
# Download binary (one-time setup)
curl -sLO https://github.com/dobicinaitis/tailwind-cli-extra/releases/latest/download/tailwindcss-extra-linux-x64
chmod +x tailwindcss-extra-linux-x64

# Compile CSS for driver PWA
./tailwindcss-extra-linux-x64 \
  --input apps/kerala_delivery/driver_app/pwa-input.css \
  --output apps/kerala_delivery/driver_app/tailwind.css \
  --cwd apps/kerala_delivery/driver_app \
  --minify
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `tailwind.config.js` + PostCSS | `@import "tailwindcss"` in CSS + `@tailwindcss/vite` plugin | Tailwind v4.0 (Jan 2026) | No JS config file needed; CSS-first configuration |
| `@tailwind base; @tailwind components; @tailwind utilities;` | `@import "tailwindcss";` | Tailwind v4.0 | Single import replaces three directives |
| DaisyUI `plugins: [require('daisyui')]` in config.js | `@plugin "daisyui";` in CSS | DaisyUI v5.0 | Plugin registered in CSS, not JS |
| `prefix: 'tw-'` in config.js producing `tw-flex` | `prefix(tw)` in CSS producing `tw:flex` | Tailwind v4.0 | Prefix uses colon syntax, not hyphen |
| DaisyUI v4 (requires Tailwind v3) | DaisyUI v5 (requires Tailwind v4) | DaisyUI 5.0 (2025) | Not interchangeable; version pairing is mandatory |
| `@pytest.mark.asyncio` on every test | `asyncio_mode = auto` in config | pytest-asyncio ~0.21+ | Auto mode detects async tests without markers |
| pytest-asyncio `legacy` mode | `strict` or `auto` mode | pytest-asyncio 1.0+ | Legacy mode removed; must explicitly choose |

**Deprecated/outdated:**
- `tailwind.config.js`: Still supported via `@config` compat directive, but the CSS-first `@import + @theme` approach is the v4 standard
- `@tailwindcss/browser` CDN: Explicitly "development and prototypes only" -- never use in production
- DaisyUI v4: Requires Tailwind v3; cannot be used with Tailwind v4
- pytest-asyncio `legacy` mode: Removed in 1.x; must use `strict` or `auto`

## Open Questions

1. **DaisyUI oklch color accuracy for existing design tokens**
   - What we know: The dashboard uses hex colors (`#D97706` for accent, `#1C1917` for dark surface). DaisyUI v5 themes require oklch values.
   - What's unclear: The exact oklch equivalents that produce visually identical colors. oklch conversion from hex is not 1:1 perceptually.
   - Recommendation: Use a converter (oklch.com) for initial values, then fine-tune in browser DevTools. The theme colors in the Code Examples section above are approximations that should be refined during implementation.

2. **tailwind-cli-extra binary availability for CI/CD**
   - What we know: The binary is available on GitHub releases. v2.8.1 bundles Tailwind 4.2.1 + DaisyUI 5.5.19.
   - What's unclear: Whether the binary should be committed to the repo or downloaded in CI. The binary is ~60MB.
   - Recommendation: Add it to `.gitignore` and download it in CI/setup scripts. Include a `scripts/setup-tailwind-cli.sh` that downloads the correct version.

3. **Vatakara landmark coordinates for test fixtures**
   - What we know: The depot is at lat 11.624, lon 75.580 (from `config.py`). Delivery locations should be within ~10km.
   - What's unclear: Exact coordinates of real public landmarks near Vatakara for realistic test fixtures.
   - Recommendation: Use Google Maps to find 5-8 public landmarks (bus stand, railway station, junctions) within 10km of the depot. The sample_locations fixture in the Code Examples section uses approximate coordinates that should be validated.

## Sources

### Primary (HIGH confidence)
- [Tailwind CSS v4 official docs -- installation](https://tailwindcss.com/docs) -- Vite plugin setup, `@import "tailwindcss"` syntax
- [Tailwind CSS v4.0 announcement](https://tailwindcss.com/blog/tailwindcss-v4) -- prefix(tw) feature, CSS-first configuration
- [DaisyUI official install for React](https://daisyui.com/docs/install/react/) -- `@plugin "daisyui"` syntax, Vite setup
- [DaisyUI themes docs](https://daisyui.com/docs/themes/) -- `@plugin "daisyui/theme"` custom theme syntax with oklch colors
- [DaisyUI config docs](https://daisyui.com/docs/config/) -- DaisyUI prefix option, theme configuration
- [DaisyUI issue #3810](https://github.com/saadeghi/daisyui/issues/3810) -- confirmed prefix(tw) works with DaisyUI v5 (resolved April 2025)
- [Tailwind CSS GitHub #15754](https://github.com/tailwindlabs/tailwindcss/issues/15754) -- CSS variable collision issue, prefix as solution
- [Tailwind CSS GitHub discussion #16273](https://github.com/tailwindlabs/tailwindcss/discussions/16273) -- prefix(tw) confirmed to prefix both classes and variables
- [pytest-asyncio configuration docs](https://pytest-asyncio.readthedocs.io/en/stable/reference/configuration.html) -- asyncio_mode options
- [tailwind-cli-extra GitHub](https://github.com/dobicinaitis/tailwind-cli-extra) -- standalone CLI with DaisyUI, v2.8.1 bundles TW 4.2.1 + DaisyUI 5.5.19
- [Tailwind standalone CLI discussion #15855](https://github.com/tailwindlabs/tailwindcss/discussions/15855) -- v4 standalone CLI setup tutorial

### Secondary (MEDIUM confidence)
- [Project research: .planning/research/STACK.md](../..) -- stack research from project initialization, versions verified on npm/PyPI
- [Project research: .planning/research/PITFALLS.md](../..) -- pitfall documentation from project initialization

### Tertiary (LOW confidence)
- oklch color values in the custom theme example are approximations of existing hex colors -- need visual verification in browser

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all versions verified on npm/PyPI, install patterns verified from official docs
- Architecture (prefix, Vite plugin, CSS structure): HIGH -- confirmed working via DaisyUI issue #3810 and Tailwind GitHub discussions
- Architecture (DaisyUI theme oklch values): MEDIUM -- color format is correct, specific values are approximations
- Pitfalls: HIGH -- CSS variable collision is a documented known issue (#15754), prefix is the official solution
- Test changes (Vatakara coordinates): HIGH -- fixtures and file list identified from codebase grep
- pytest-asyncio configuration: HIGH -- documented in official pytest-asyncio docs, version 1.3.0 supports auto mode

**Research date:** 2026-03-01
**Valid until:** 2026-03-31 (stable libraries, unlikely to change in 30 days)
