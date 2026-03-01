# Architecture Research

**Domain:** Kerala LPG Delivery Route Optimizer — UI polish + error hardening milestone
**Researched:** 2026-03-01
**Confidence:** HIGH (Tailwind/DaisyUI installation from official docs; error propagation from codebase analysis + FastAPI docs; code cleanup from static analysis tooling docs)

---

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND LAYER                               │
│                                                                      │
│  ┌──────────────────────────────┐   ┌────────────────────────────┐  │
│  │   React Dashboard (Vite)     │   │   Driver PWA (no-build)    │  │
│  │   apps/kerala_delivery/      │   │   apps/kerala_delivery/    │  │
│  │   dashboard/src/             │   │   driver_app/index.html    │  │
│  │                              │   │                            │  │
│  │  Tailwind v4 + DaisyUI v5    │   │  Pre-compiled Tailwind     │  │
│  │  via @tailwindcss/vite       │   │  CSS (via standalone CLI)  │  │
│  │  plugin → build-time CSS     │   │  + Leaflet CDN             │  │
│  │                              │   │                            │  │
│  │  Toast: React state +        │   │  Toast: vanilla JS DOM     │  │
│  │  DaisyUI alert classes       │   │  + DaisyUI alert classes   │  │
│  └───────────────┬──────────────┘   └──────────────┬─────────────┘  │
└──────────────────┼─────────────────────────────────┼────────────────┘
                   │  fetch() + X-API-Key             │ fetch()
                   ▼                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                       FastAPI API LAYER                              │
│                   apps/kerala_delivery/api/main.py                   │
│                                                                      │
│  Middleware stack (order matters):                                   │
│  1. Rate limiter (slowapi) — outermost                               │
│  2. CORS (fastapi CORSMiddleware)                                    │
│  3. License enforcement middleware                                   │
│  4. Endpoint handlers                                                │
│                                                                      │
│  POST /api/upload-orders → structured error payload with            │
│  geocoding_failures[] list (not just a string message)              │
└──────────────────────────────────┬──────────────────────────────────┘
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
┌─────────────────┐   ┌─────────────────────┐   ┌──────────────────┐
│   core/ domain  │   │  core/geocoding/    │   │ core/database/   │
│   models +      │   │  google_adapter +   │   │ repository.py    │
│   optimizer +   │   │  cache.py           │   │ PostgreSQL/      │
│   routing       │   │  (failures tracked) │   │ PostGIS          │
└─────────────────┘   └─────────────────────┘   └──────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Current State | Change in This Milestone |
|-----------|---------------|---------------|--------------------------|
| `dashboard/src/` | React ops UI for dispatchers | CSS custom properties + class-based styles | Add Tailwind + DaisyUI via Vite plugin; keep CSS custom properties as design tokens |
| `driver_app/index.html` | Vanilla JS PWA for drivers in the field | Inline `<style>` block, Leaflet CDN | Pre-compile Tailwind CSS via standalone CLI; replace inline styles with utility classes |
| `api/main.py` | FastAPI endpoints | String error messages in `detail` field | Structured error objects with `geocoding_failures[]` list in `detail` |
| `api/main.py` middleware | CORS, rate limit, license | Already in place | Add Content-Security-Policy header, tighten CORS validation |
| `core/geocoding/` | Google Geocoding + DB cache | Failures silently logged, not surfaced | Track failures, return them to caller |

---

## Tailwind + DaisyUI Integration Architecture

### Dashboard (React + Vite) — HIGH Confidence

**Install method:** `@tailwindcss/vite` plugin — the canonical, fastest approach for Vite projects.

```
npm install tailwindcss @tailwindcss/vite daisyui
```

**vite.config.ts change (additive — add tailwindcss alongside existing react plugin):**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),   // <-- add this
  ],
  server: {
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } }
  }
})
```

**CSS entry point (`src/index.css` — add at top, keep custom properties below):**

```css
@import "tailwindcss";
@plugin "daisyui";

/* Existing custom properties remain — Tailwind does not conflict with :root vars */
:root {
  --color-accent: #D97706;  /* Keep — used in components that reference vars */
  /* ... */
}
```

**Why this works with the existing architecture:**
- No `tailwind.config.js` needed in v4 — configuration lives in CSS (`@theme` blocks)
- Vite handles the CSS compilation at build time; no runtime overhead
- The existing per-component `.css` files (`App.css`, `UploadRoutes.css`, etc.) continue to work alongside Tailwind classes — they are not replaced in one shot
- DaisyUI v5 is purely CSS; it adds no JavaScript to the React bundle

**Migration strategy:** Keep existing CSS files intact initially. Add Tailwind classes progressively per component. Delete component CSS files only after full conversion.

### Driver PWA (Vanilla JS, no build step) — MEDIUM Confidence

**Problem:** The driver PWA (`driver_app/index.html`) has no build pipeline. The Tailwind v4 Play CDN (`@tailwindcss/browser@4` script) is explicitly labeled "not for production" by Tailwind Labs — it scans and compiles at runtime in the browser, burning CPU on every page load. This is unacceptable on low-end Android phones in the Kerala field.

**Solution: Tailwind Standalone CLI (pre-compile at author time)**

The standalone CLI is a self-contained binary (no Node.js required at runtime) that compiles a `tailwind.css` file from scanning the HTML template. The compiled CSS is committed as a static asset.

```bash
# Download once (Linux x64 example — adjust for dev OS):
curl -sLo tailwindcss https://github.com/tailwindlabs/tailwindcss/releases/latest/download/tailwindcss-linux-x64
chmod +x tailwindcss

# Generate compiled CSS from driver_app/index.html:
./tailwindcss -i driver_app/input.css -o driver_app/tailwind.css --minify
```

**driver_app/input.css (source, not served):**
```css
@import "tailwindcss";
@plugin "daisyui";
```

**driver_app/index.html (reference compiled output):**
```html
<link rel="stylesheet" href="tailwind.css">
<!-- Remove existing <style> block contents after migration -->
```

**Workflow:** Re-run the standalone CLI when modifying PWA HTML. The compiled `tailwind.css` is committed. Service worker caches it. No build step required for deployment.

**Why not full CDN approach:** Offline capability requires cached assets. The service worker (`sw.js`) caches `tailwind.css` as a static file. A runtime-compilation CDN script cannot be meaningfully cached for offline use because it must scan the DOM dynamically.

**Separation of concerns — driver PWA dark theme vs dashboard light theme:**
- Dashboard: DaisyUI `corporate` or custom light theme (amber accent, stone palette)
- Driver PWA: DaisyUI `dark` theme or `business` theme configured via `@plugin "daisyui" { themes: ["dark"] }` in `input.css`
- Themes are resolved at compile time, so each output CSS contains only its theme's variables

---

## Error Propagation Architecture

### Current Problem

The geocoding failure path in `api/main.py` (lines 638–703) logs failures to the console but returns only a count of geocoded orders. The frontend receives `total_orders: N` and `orders_assigned: M` with no explanation of why `N - M` orders are missing. The critical bug is: orders that fail geocoding are filtered out at line 728 (`optimizer.optimize(geocoded, fleet)`) without the caller knowing which ones or why.

### Target Architecture: Structured Partial-Success Response

**Pattern:** Return a 200 OK with `geocoding_failures` embedded in the response body. HTTP 207 Multi-Status is technically correct but introduces complexity in the existing Pydantic response model and confuses standard fetch error handling. A 200 with a structured warnings list is the dominant pattern for partial-batch operations (used by Google Cloud Batch, Stripe, AWS SQS).

**Updated `OptimizationSummary` Pydantic model:**

```python
class GeocodingFailure(BaseModel):
    order_id: str
    address_raw: str
    reason: str  # "no_geocoder", "api_error", "zero_results", "low_confidence"

class OptimizationSummary(BaseModel):
    run_id: str
    assignment_id: str
    total_orders: int           # from CSV (all rows)
    orders_geocoded: int        # successfully geocoded
    orders_assigned: int        # placed on routes
    orders_unassigned: int      # geocoded but VROOM couldn't route
    geocoding_failures: list[GeocodingFailure] = []  # NEW: failed geocoding
    vehicles_used: int
    optimization_time_ms: float
    created_at: datetime
```

**Geocoding loop change (collect failures instead of silently logging):**

```python
geocoding_failures: list[dict] = []

for order in orders:
    if not order.is_geocoded:
        cached = await repo.get_cached_geocode(session, order.address_raw)
        if cached:
            order.location = cached
        elif geocoder:
            result = geocoder.geocode(order.address_raw)
            if result.success and result.location:
                order.location = result.location
                await repo.save_geocode_cache(...)
            else:
                raw = getattr(result, "raw_response", {})
                geocoding_failures.append({
                    "order_id": order.order_id,
                    "address_raw": order.address_raw,
                    "reason": _classify_geocode_failure(raw),
                })
        else:
            geocoding_failures.append({
                "order_id": order.order_id,
                "address_raw": order.address_raw,
                "reason": "no_geocoder",
            })
```

**Helper to classify failures (makes frontend messaging specific):**

```python
def _classify_geocode_failure(raw: dict) -> str:
    status = raw.get("status", "")
    if status == "ZERO_RESULTS":
        return "zero_results"
    elif status == "REQUEST_DENIED":
        return "api_key_error"
    elif status == "OVER_QUERY_LIMIT":
        return "quota_exceeded"
    elif status == "INVALID_REQUEST":
        return "invalid_address"
    return "api_error"
```

### Error Flow: geocoding → API response → frontend toast

```
Geocoder.geocode(address)
    → success=False
    ↓
Upload handler collects GeocodingFailure record
    ↓
OptimizationSummary.geocoding_failures = [...]
    ↓
HTTP 200 response (partial success — some orders routed)
    ↓
Dashboard fetch() → parses response.geocoding_failures
    ↓
If geocoding_failures.length > 0:
    Toast: "N addresses could not be geocoded — see details"
    Expandable list: order_id + address + reason per failure
    ↓
Drivers only see geocoded stops — but dispatcher sees the gap
```

**Fatal error path (zero geocoded orders) stays as HTTP 400:**
```python
if not geocoded:
    raise HTTPException(
        status_code=400,
        detail={
            "message": "No orders could be geocoded.",
            "failures": geocoding_failures,  # structured list
            "hint": api_hint,
        }
    )
```

### Frontend Toast Architecture

**Dashboard (React):** Implement a lightweight `useToast` hook + `ToastContainer` component using DaisyUI `alert` + `toast` CSS classes. No external toast library needed — DaisyUI provides positioning and visual styles.

```typescript
// src/hooks/useToast.ts
type ToastType = "success" | "error" | "warning" | "info";
interface Toast { id: string; type: ToastType; message: string; detail?: string[] }

// ToastContainer renders DaisyUI .toast > .alert structure
// Toasts auto-dismiss after 5s (error stays until dismissed)
```

**Component structure:**
```
<div class="toast toast-top toast-end">
  <div class="alert alert-warning">
    <span>3 addresses could not be geocoded</span>
    <button>Details</button>
  </div>
</div>
```

**Driver PWA (Vanilla JS):** A 30-line vanilla JS `showToast(message, type)` function that creates/removes DaisyUI alert elements. No framework needed.

```javascript
function showToast(message, type = "info", duration = 4000) {
    const container = document.getElementById("toast-container");
    const el = document.createElement("div");
    el.className = `alert alert-${type} shadow-lg`;
    el.innerHTML = `<span>${message}</span>`;
    container.appendChild(el);
    setTimeout(() => el.remove(), duration);
}
```

---

## Code Cleanup Architecture

### Identifying AI Slop — Patterns to Audit

AI-generated code in this codebase has four recognizable slop patterns:

| Pattern | Detection | Action |
|---------|-----------|--------|
| Over-commenting | Comments explaining what the code does (not why) | Delete the comment, keep the code |
| Redundant try/except | `try: x = foo() except: x = None` when `foo()` never raises | Remove the try/except |
| Defensive None-checks | `if x is not None and x is not None:` (double check) | Simplify to `if x:` |
| Unused imports | `import` at top, never referenced | Remove (use `ruff --select F401`) |
| Dead branches | `if False:` / `# TODO: remove this` blocks | Delete |
| Abstraction inversion | A function that wraps one line of stdlib | Inline the call |

### Safe Cleanup Order (build order implications)

**Do not refactor and change behavior in the same commit.** The safe order is:

1. **Remove unused imports first** — no behavior change, easy to verify (`ruff --select F401 --fix`)
2. **Delete commented-out code** — no behavior change, grep for `# .*TODO.*remove` and stale blocks
3. **Simplify redundant guards** — small behavior-safe changes; run existing test suite after each file
4. **Remove dead functions** — use `vulture` to find unused functions; verify against test imports before deleting
5. **Inline trivial wrappers** — only if the wrapper has no tests targeting it directly

**Tooling:**
```bash
# Find unused code (Python):
pip install vulture ruff
ruff check . --select F401,F841  # unused imports, unused variables
vulture core/ apps/ --min-confidence 80

# Find dead TypeScript code (dashboard):
npx tsc --noEmit  # surfaces unused variables if strict: true in tsconfig
```

**For `main.py` specifically:** The file is 70+ KB with 25+ endpoints. The primary slop risks are:
- Inline imports inside functions (e.g., `from datetime import time as dt_time` at line 624 — should be at top)
- Phase-comment noise ("Phase 2", "Phase 3+" references that are now past)
- Repeated `getattr(result, "raw_response", {})` calls that belong in a helper

### Test Safety Net

Before any cleanup: verify `pytest tests/ -x` passes. After each file cleanup: re-run tests. The existing 351+ tests provide a meaningful regression net. If a cleanup breaks a test, the cleanup was not behavior-safe.

---

## Architectural Patterns to Follow

### Pattern 1: CSS-First Configuration (Tailwind v4)

**What:** All Tailwind customization lives in `index.css` using `@theme {}` blocks, not in `tailwind.config.js`. DaisyUI v5 is configured with `@plugin "daisyui" { themes: [...] }` in the same CSS file.

**When to use:** Always in this codebase — v4 has no config file.

**Example:**
```css
@import "tailwindcss";
@plugin "daisyui";

@theme {
  --color-accent: oklch(62.8% 0.17 63);  /* amber */
  --font-sans: "DM Sans", sans-serif;
}
```

**Trade-off:** Design tokens defined as `@theme` variables are available as Tailwind classes (`text-accent`, `bg-accent`). Existing CSS custom property references (`var(--color-accent)`) still work but need to be migrated to use `@theme` equivalents to be Tailwind-aware.

### Pattern 2: Structured Error Body (FastAPI)

**What:** `HTTPException.detail` accepts any JSON-serializable value — pass a `dict` not a string for errors where the frontend needs to act on specific fields.

**When to use:** Any endpoint where the frontend must distinguish between error subtypes (geocoding failures vs. file format errors vs. API key errors).

**Example:**
```python
raise HTTPException(
    status_code=400,
    detail={
        "code": "geocoding_failed",
        "message": "Human-readable summary",
        "failures": [{"order_id": ..., "address": ..., "reason": ...}]
    }
)
```

**Trade-off:** Slightly more work to document in OpenAPI schema, but the frontend can show specific guidance rather than a generic "Something went wrong" toast.

### Pattern 3: Additive CSS Migration (no big-bang rewrite)

**What:** Do not delete all existing `.css` files and rewrite in Tailwind at once. Add Tailwind classes to components progressively; remove the corresponding CSS rule only after verifying the visual result.

**When to use:** This migration pattern.

**Trade-off:** Temporary duplication of styles is acceptable — a component can use both Tailwind classes and a `.css` file simultaneously. Completion means the `.css` file is empty and deleted.

### Pattern 4: Service Worker Cache Versioning for Static CSS

**What:** When the pre-compiled `tailwind.css` for the driver PWA changes, the service worker's `CACHE_VERSION` constant must be bumped so browsers fetch the new file.

**When to use:** Every time PWA HTML or styling changes.

**Example (sw.js already has this pattern — maintain it):**
```javascript
const CACHE_VERSION = "v2";  // bump this when tailwind.css changes
const CACHE_NAME = `lpg-driver-${CACHE_VERSION}`;
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Tailwind Play CDN in Production PWA

**What people do:** Add `<script src="https://cdn.jsdelivr.net/npm/@tailwindcss/browser@4">` to `driver_app/index.html` for zero-config Tailwind.

**Why it's wrong:** The Play CDN compiles CSS at runtime by scanning the DOM — it ships ~350 KB of JavaScript, burns CPU on every page load, cannot be meaningfully cached by the service worker, and Tailwind explicitly documents it as "not for production."

**Do this instead:** Pre-compile with the standalone Tailwind CLI. The output `tailwind.css` is a static file that the service worker caches correctly.

### Anti-Pattern 2: Replacing DaisyUI Themes with Custom CSS Variables Wholesale

**What people do:** Define all colors as CSS custom properties (`:root { --color-x }`) and not use DaisyUI's theme system, then wonder why DaisyUI components look wrong.

**Why it's wrong:** DaisyUI v5 uses its own `oklch`-based CSS variables (`--p`, `--s`, `--a` for primary/secondary/accent). Components like `.btn-primary` reference `--p`, not `--color-accent`. If you bypass DaisyUI themes, you break component coloring.

**Do this instead:** Set DaisyUI theme variables to match the design. Use `@plugin "daisyui" { themes: [{ "kerala": { "primary": "#D97706" } }] }` or map the existing amber color into DaisyUI's theme slot. Keep `--color-accent` as an alias for components that reference it directly.

### Anti-Pattern 3: Silently Eating Geocoding Failures

**What people do:** Log geocoding failures at WARNING level and proceed with the geocoded subset. The API returns 200 OK with fewer stops than expected, and the frontend shows a map with missing pins but no explanation.

**Why it's wrong:** The dispatcher uploaded 47 orders and sees only 41 on the map. Without a failure list, there is no way to fix addresses or know which customers were skipped.

**Do this instead:** Return `geocoding_failures` as a structured list in the response body. The frontend shows a warning toast with the exact count and an expandable list of failed addresses.

### Anti-Pattern 4: One Giant CSS Cleanup Commit

**What people do:** Delete all the `.css` files in one commit, rewrite everything in Tailwind, and submit.

**Why it's wrong:** The existing 351+ tests don't cover visual output — regression is invisible. A component-by-component migration allows visual verification at each step.

**Do this instead:** One component per commit. Remove the component's `.css` file only after confirming the Tailwind classes produce the correct visual.

### Anti-Pattern 5: Refactoring + Feature Work in the Same Commit

**What people do:** While cleaning up slop in `main.py`, also fix the geocoding error propagation bug in the same commit.

**Why it's wrong:** If tests break, it is ambiguous whether the refactor or the bug fix caused it. Also makes code review much harder.

**Do this instead:** Cleanup commits are separate from behavior-change commits. Commit message discipline: `refactor:` prefix means no behavior change.

---

## Build Order Implications

**This milestone has a strict dependency order.** Phase structure must follow this sequence:

```
1. Tailwind + DaisyUI scaffolding (vite.config.ts + index.css changes)
   → Dashboard build must succeed with Tailwind before any component work

2. Design token mapping (existing CSS vars → DaisyUI theme)
   → Must happen before components use .btn-primary etc.
   → Otherwise component colors are wrong during migration

3. Error propagation backend (GeocodingFailure model + structured response)
   → Must happen before frontend toast work
   → Frontend needs the response shape to parse failures

4. Frontend toast infrastructure (useToast hook + ToastContainer)
   → Must happen before per-page error handling
   → Pages call useToast() — hook must exist

5. Per-component UI migration (one component at a time)
   → Can proceed in parallel after steps 1-4

6. Driver PWA Tailwind (standalone CLI pre-compile)
   → Independent of dashboard after Tailwind installation
   → Service worker cache version bump required

7. Security middleware hardening (CSP header, CORS tightening)
   → Independent — can happen any time
   → Does not block UI work

8. Code cleanup (slop removal)
   → Must come LAST — do not mix with behavior changes
   → Requires full test suite green before starting
```

**Critical dependency:** Do NOT start per-component Tailwind migration until `@tailwindcss/vite` is installed and the dashboard builds successfully. A broken build mid-migration is much harder to debug.

---

## Integration Points

### External Services

| Service | Integration Pattern | Notes for This Milestone |
|---------|---------------------|--------------------------|
| Google Geocoding API | `core/geocoding/google_adapter.py` → HTTP | Add failure classification; return structured failure list |
| Vite dev server | `@tailwindcss/vite` plugin | Plugin added to `vite.config.ts`; no other config |
| DaisyUI | CSS plugin via `@plugin "daisyui"` in `index.css` | Theme configured in same CSS file; no JS import |
| Tailwind Standalone CLI | Binary download, run locally | Pre-compiles `driver_app/tailwind.css` for PWA |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `api/main.py` ↔ `core/geocoding/` | Direct Python function calls | Add return type to surface failures back to caller |
| `OptimizationSummary` ↔ Dashboard | JSON over HTTP | Add `geocoding_failures: GeocodingFailure[]` field |
| Dashboard `lib/api.ts` ↔ React components | Module exports | `uploadAndOptimize()` return type must include `geocoding_failures` |
| Service Worker ↔ `tailwind.css` | Cache list in `sw.js` | `tailwind.css` added to precache list; CACHE_VERSION bumped on change |

---

## Scalability Considerations

This is a single-office tool (1 dispatcher, 13 drivers). Scalability is not a concern. The relevant concern is **reliability on the edge:**

| Concern | Current | After This Milestone |
|---------|---------|----------------------|
| PWA offline | Service worker caches Leaflet + stops JSON | Add `tailwind.css` to service worker precache list |
| Geocoding failures | Silent — dispatcher has no visibility | Structured list surfaced in UI |
| Security headers | CORS + API key | Add CSP header to block XSS vectors |

---

## Sources

- Tailwind CSS v4 Vite installation (official docs): https://tailwindcss.com/docs/installation
- Tailwind CSS Play CDN production limitations: https://tailwindcss.com/docs/installation/play-cdn
- DaisyUI v5 release notes + Tailwind v4 integration: https://daisyui.com/docs/v5/
- DaisyUI v5 install: https://daisyui.com/docs/install/
- Tailwind CSS Standalone CLI: https://tailwindcss.com/blog/standalone-cli
- FastAPI error handling (official): https://fastapi.tiangolo.com/tutorial/handling-errors/
- FastAPI structured error detail (dict in HTTPException.detail): https://fastapi.tiangolo.com/tutorial/handling-errors/
- HTTP 207 Multi-Status for batch partial success: https://apidog.com/blog/status-code-207-multi-status/
- vulture (Python dead code detection): https://github.com/jendrikseipp/vulture
- ruff (unused import detection, F401): https://github.com/astral-sh/ruff
- DaisyUI toast + alert components: https://daisyui.com/components/toast/

---

*Architecture research for: Kerala LPG Delivery — UI polish + error hardening milestone*
*Researched: 2026-03-01*
