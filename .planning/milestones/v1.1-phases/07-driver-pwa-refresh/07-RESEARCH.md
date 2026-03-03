# Phase 7: Driver PWA Refresh - Research

**Researched:** 2026-03-03
**Domain:** Vanilla JS PWA / UI overhaul / WCAG AAA contrast / Offline reliability
**Confidence:** HIGH

## Summary

Phase 7 is a UI/UX overhaul of an existing single-file vanilla JS PWA (`index.html`, ~1340 lines). No new API endpoints, no framework migration, no build step changes. The work decomposes into four clear areas: (1) restructure `renderStopList()` into hero card + compact list with auto-advance transitions, (2) replace the bottom summary bar with a segmented progress bar below the sticky header, (3) audit and fix all color values for WCAG AAA compliance, and (4) harden touch targets to 60px+ and add a Call Office FAB.

The existing codebase is well-structured with centralized CSS custom properties (`:root` variables), a mature offline queue (`queueOfflineUpdate`/`replayOfflineQueue`), and XSS-safe rendering via `escapeHtml()`. All changes are CSS + vanilla JS within the single `index.html` file. The `tailwind.css` file is compiled from `pwa-input.css` but the driver app uses almost entirely custom CSS (the Tailwind output is loaded but the app's inline `<style>` block does all the actual styling).

**Primary recommendation:** Implement in three sequential waves: (1) WCAG AAA color audit + touch target sizing, (2) segmented progress bar + refresh row + header stats, (3) hero card + compact list + auto-advance + fail modal + Call Office FAB.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Hero card design:** Full-width elevated card taking ~40% of viewport with saffron-accent border/glow, oversized text, huge Navigate button. Shows ALL stop info: address (large), distance from current location, customer name (if available), cylinder count, weight, notes, Navigate + Done + Fail buttons. Label: "NEXT DELIVERY · Stop X of Y". Remaining stops as compact list below. On delivery/fail: brief toast (~1.5s) then auto-advance with smooth slide. All-done banner when complete.
- **Progress & status display:** Segmented progress bar below sticky header (each stop = one segment). Colors: green (#00C853) delivered, red (#FF3B30) failed, saffron (#FF9410) current, dim for pending. Header text: "X of Y delivered". Below progress bar: "Last updated: HH:MM AM" left + "Refresh" button right. Bottom summary bar REMOVED.
- **Touch targets & actions:** Navigate button 60px+ (64-68px), full-width saffron, bold. Done and Fail at 60px. Call Office FAB in bottom-right corner (round, phone icon, always visible, `tel:` link). Fail triggers custom dark-themed modal (NOT `confirm()`), with "Yes, Failed" + "Cancel" buttons + optional reason dropdown. All interactive elements 60px+.
- **Outdoor readability (WCAG AAA):** Dark theme only, no light mode, no toggle. Eliminate muted text tier (#4E4D65). Only TWO text hierarchy levels: primary (#F0EFFB) and secondary (bumped to pass 7:1). 14px minimum font everywhere. Saffron for large elements only (buttons, progress segments, hero border). White for body-size text that would otherwise be saffron. All pairs audited for WCAG AAA: 7:1 body, 4.5:1 large (18px+ bold or 24px+ regular).

### Claude's Discretion
- Exact animation/transition approach for hero card auto-advance
- Toast notification styling and positioning
- Specific secondary text color value (must pass 7:1 against #0B0B0F)
- FAB size, shadow, and position offsets
- Fail reason dropdown options beyond the three specified (not home, refused, wrong address)
- Loading skeleton design during route fetch
- Exact spacing, padding, and gap values throughout

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PWA-01 | Next stop as prominent hero card at top of stop list with large address, distance, Navigate button | Hero card rendering: split `renderStopList()` into `renderHeroCard()` + `renderCompactList()`. Use existing stop data model (address, distance_from_prev_km, quantity, weight_kg, notes). Transition via CSS transform + opacity. |
| PWA-02 | Header shows "X of Y delivered" with visual progress bar | Segmented progress bar: replace `updateSummary()`. Each stop = one `<div>` segment colored by status. Header stats text format change. Progress bar row inserted below `.header`. |
| PWA-03 | Visible Refresh button with "Last updated" timestamp | Add refresh row below progress bar. `loadRoute()` records timestamp to localStorage. Refresh button calls `reloadCurrentRoute()`. Display formatted time. |
| PWA-04 | All primary action buttons 60px+ touch targets (Delivered, Failed, Navigate, Call Office) | CSS height changes: btn-navigate 64-68px, btn-deliver 60px, btn-fail 60px (currently 48px). New FAB element for Call Office with `tel:` href. |
| PWA-05 | WCAG AAA contrast: 7:1 body, 4.5:1 large text | Color audit findings below. Eliminate `--color-text-muted`. Bump `--color-text-secondary` from #9897B0 to #9F9DB8+. Fix 12px/10px font sizes to 14px minimum. |
| PWA-06 | Offline: loading, viewing stops, marking deliveries work without network | Already works via localStorage + offline queue. Verify `renderHeroCard()` and new progress bar work from cached `currentRoute`. No new API dependencies. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Vanilla JS | ES2020+ | All app logic | Single-file PWA, no build step, no framework. Matches existing architecture |
| CSS Custom Properties | -- | Color system, theming | Already in place via `:root` variables. Centralized audit/fix point for WCAG |
| HTML `<dialog>` | -- | Fail confirmation modal | Native, accessible, no dependencies. Supported on Chrome Android 37+, Samsung Internet 3.0+ |
| Service Worker | Cache API v1 | Offline app shell | Already implemented (`sw.js`). Cache version bump needed after changes |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Leaflet | 1.9.4 | Map view | Already loaded. No changes needed for Phase 7 |
| Google Fonts (Outfit + JetBrains Mono) | -- | Typography | Already loaded. No changes needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `<dialog>` for fail modal | Custom `<div>` overlay | `<dialog>` gives free accessibility (focus trap, Esc to close, inert backdrop) with zero custom code |
| CSS transitions for hero advance | Web Animations API | CSS transitions are simpler, more compatible, sufficient for slide/fade. WAAPI would add complexity with no benefit |
| localStorage for "last updated" | Service Worker message passing | localStorage is already the established pattern. Adding SW messaging would be overengineering for a single timestamp |

**Installation:** None. Zero dependencies to add. All changes are to `index.html` inline CSS and JS.

## Architecture Patterns

### Recommended Project Structure
```
apps/kerala_delivery/driver_app/
├── index.html        # ALL changes go here (CSS + JS inline)
├── sw.js             # Bump CACHE_VERSION after changes
├── manifest.json     # No changes needed
├── pwa-input.css     # No changes needed (Tailwind input, unused in practice)
└── tailwind.css      # No changes needed (compiled Tailwind, minimally used)
```

### Pattern 1: Hero Card + Compact List Rendering
**What:** Split the single `renderStopList()` function into three functions: `renderHeroCard()` for the next pending stop, `renderCompactList()` for remaining stops, and `renderStopList()` as the orchestrator.
**When to use:** When the first undelivered stop needs fundamentally different HTML/CSS than the rest.
**Example:**
```javascript
function renderStopList() {
    const container = document.getElementById('stop-list');
    const nextStop = currentRoute.stops.find(s => s.status === 'pending');
    const otherStops = currentRoute.stops.filter(s => s !== nextStop);

    container.innerHTML = [
        nextStop ? renderHeroCard(nextStop) : renderAllDoneBanner(),
        ...otherStops.map(s => renderCompactCard(s)),
    ].join('');

    updateProgressBar();
    updateHeaderStats();
}
```

### Pattern 2: Segmented Progress Bar
**What:** A row of `<div>` segments, one per stop, colored by status. Uses flexbox with `flex: 1` so segments auto-size regardless of stop count.
**When to use:** To replace the bottom summary bar with an inline visual indicator.
**Example:**
```javascript
function updateProgressBar() {
    const bar = document.getElementById('progress-bar');
    bar.innerHTML = currentRoute.stops.map((stop, i) => {
        const nextIdx = currentRoute.stops.findIndex(s => s.status === 'pending');
        let colorClass = 'progress-pending';
        if (stop.status === 'delivered') colorClass = 'progress-delivered';
        else if (stop.status === 'failed') colorClass = 'progress-failed';
        else if (i === nextIdx) colorClass = 'progress-current';
        return `<div class="progress-segment ${colorClass}"></div>`;
    }).join('');
}
```
```css
.progress-bar {
    display: flex;
    gap: 3px;
    height: 8px;
    padding: 0 16px;
    margin: 8px 0;
}
.progress-segment {
    flex: 1;
    border-radius: 4px;
    transition: background-color 0.3s;
}
.progress-delivered { background: #00C853; }
.progress-failed    { background: #FF3B30; }
.progress-current   { background: #FF9410; }
.progress-pending   { background: #1E1E2E; }
```

### Pattern 3: Hero Card Auto-Advance with CSS Transitions
**What:** When a stop is marked delivered/failed, show a brief toast, then smoothly transition the next stop into the hero position using CSS transform + opacity.
**When to use:** On every `updateStatus()` call that resolves a pending stop.
**Example:**
```javascript
async function updateStatus(vehicleId, orderId, status) {
    // ... existing optimistic update logic ...

    // Show toast
    showToast(status === 'delivered' ? 'Delivered!' : 'Marked failed', status);

    // Delay re-render for toast visibility
    setTimeout(() => {
        renderStopList();
    }, 1500);
}

function showToast(message, type) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    // Auto-remove after animation
    setTimeout(() => toast.remove(), 1500);
}
```
```css
.toast {
    position: fixed;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    padding: 16px 32px;
    border-radius: 12px;
    font-family: var(--font-ui);
    font-size: 18px;
    font-weight: 700;
    z-index: 2000;
    animation: toast-in 0.2s ease-out, toast-out 0.3s ease-in 1.2s forwards;
    pointer-events: none;
}
.toast-delivered { background: #00C853; color: #000; }
.toast-failed    { background: #FF3B30; color: #FFF; }

@keyframes toast-in  { from { opacity: 0; scale: 0.85; } to { opacity: 1; scale: 1; } }
@keyframes toast-out { from { opacity: 1; } to { opacity: 0; } }
```

### Pattern 4: Native `<dialog>` for Fail Modal
**What:** Replace `confirm('Mark this delivery as failed?')` with an HTML `<dialog>` element styled to match the dark theme. Includes large touch-target buttons and an optional reason dropdown.
**When to use:** When `markFailed()` is called.
**Example:**
```html
<dialog id="fail-dialog">
    <div class="fail-modal">
        <h3>Mark delivery as failed?</h3>
        <select id="fail-reason">
            <option value="">Reason (optional)</option>
            <option value="not_home">Not home</option>
            <option value="refused">Refused delivery</option>
            <option value="wrong_address">Wrong address</option>
            <option value="other">Other</option>
        </select>
        <div class="fail-actions">
            <button class="btn btn-fail-confirm" id="fail-confirm">Yes, Failed</button>
            <button class="btn btn-fail-cancel" id="fail-cancel">Cancel</button>
        </div>
    </div>
</dialog>
```
```javascript
let pendingFailOrderId = null;

function markFailed(vehicleId, orderId) {
    pendingFailOrderId = orderId;
    document.getElementById('fail-reason').value = '';
    document.getElementById('fail-dialog').showModal();
}

document.getElementById('fail-confirm').addEventListener('click', () => {
    document.getElementById('fail-dialog').close();
    if (pendingFailOrderId) {
        updateStatus(
            currentRoute.vehicle_id,
            pendingFailOrderId,
            'failed'
        );
        pendingFailOrderId = null;
    }
});

document.getElementById('fail-cancel').addEventListener('click', () => {
    document.getElementById('fail-dialog').close();
    pendingFailOrderId = null;
});
```

### Anti-Patterns to Avoid
- **Full re-render on every status change without visual feedback:** The current code does `renderStopList()` immediately. Phase 7 must add the 1.5s toast delay before re-render so drivers get confirmation feedback.
- **Using `confirm()` or `alert()` in a PWA:** Browser dialogs are ugly, tiny, and don't match the dark theme. Always use `<dialog>` elements.
- **Hardcoding color values in JS-generated HTML:** Keep all colors in CSS custom properties. The inline `style.cssText` for banners (offline, speed alert) should use variables, not hex literals.
- **Storing the office phone number in JS:** Use a `data-*` attribute or CSS custom property loaded from config, not a JS constant. Makes it deployable for different distributors.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Modal dialog | Custom div + overlay + focus trap + Esc handler | HTML `<dialog>` + `showModal()` | Free focus trapping, Esc key, `::backdrop`, inert page. 10 lines vs 80+ |
| Contrast ratio checking | Manual hex-to-luminance calculator | Pre-calculated values from research (below) | Ratios are static — calculate once, hardcode results |
| Offline persistence | IndexedDB wrapper | Existing localStorage helpers | Route data is <100KB. localStorage is sufficient and already works |
| Touch ripple/feedback | Custom touch event handler | CSS `:active` pseudo-class with `transform: scale(0.95)` | Already in place, works well on mobile Chrome |

**Key insight:** This is a UI-only overhaul of an existing working app. The offline layer, auth, telemetry, and data model are all stable. Every temptation to "improve" the infrastructure should be resisted — focus exclusively on the six PWA requirements.

## Common Pitfalls

### Pitfall 1: WCAG AAA Color Math Errors
**What goes wrong:** Picking colors that "look accessible" but don't actually pass 7:1 contrast ratio against both `#0B0B0F` (body background) AND `#13131A` (card/surface background).
**Why it happens:** Colors can pass against one background but fail against the other. The surface background is lighter, so contrast is lower.
**How to avoid:** Test every text color against BOTH backgrounds. Use the pre-calculated values in the Color Audit section below.
**Warning signs:** Any text appearing on a `.stop-card` (surface background) that wasn't tested against `#13131A`.

### Pitfall 2: Hero Card Height Consuming Too Much Viewport
**What goes wrong:** The hero card takes 40%+ of viewport as specified, but on small Android screens (5" displays at 360×640 logical pixels), this leaves almost no room for the compact list below.
**Why it happens:** 40% of 640px = 256px for the hero, plus ~57px header + ~40px progress bar + ~40px refresh row = 393px consumed. Only 247px left for the compact list.
**How to avoid:** Use `min-height` not fixed `height` for the hero card. Let content determine actual height. The "~40% of viewport" is a guideline for the visual prominence, not a CSS constraint.
**Warning signs:** Compact list showing fewer than 2 visible stops on a standard Android phone.

### Pitfall 3: Touch Target Overlap on Small Screens
**What goes wrong:** The hero card has Navigate (64-68px) + Done (60px) + Fail (60px) buttons in a row. On a 360px-wide screen with 12px padding each side, that's 336px available. Three buttons at their minimum widths may be too tight.
**Why it happens:** The current layout uses `flex: 1` for Navigate and Done with a fixed-width Fail button. At 60px minimum height, horizontal space becomes the constraint.
**How to avoid:** Stack Navigate full-width on its own row. Done + Fail side-by-side below. This gives Navigate maximum visual prominence (locked decision) and adequate sizing for all three.
**Warning signs:** Buttons smaller than 60px in any dimension on a 360px screen.

### Pitfall 4: CSS Transition Jank on Low-End Android
**What goes wrong:** Hero card auto-advance animation stutters or freezes on mid-range Android phones (Redmi, Realme — common in Kerala).
**Why it happens:** `height` and `top`/`bottom` animations trigger layout recalculation (reflow). Only `transform` and `opacity` are GPU-composited.
**How to avoid:** Animate ONLY `transform` (translateY) and `opacity`. Never animate `height`, `margin`, `padding`, or `top`. Use `will-change: transform` sparingly.
**Warning signs:** Any CSS transition on a property other than `transform` or `opacity`.

### Pitfall 5: Forgetting to Bump Service Worker Cache Version
**What goes wrong:** After deploying changes to `index.html`, drivers' phones serve the old cached version indefinitely.
**Why it happens:** The service worker caches `index.html` during install. Without a `CACHE_VERSION` bump in `sw.js`, the browser sees no change in the SW file and doesn't re-install.
**How to avoid:** Final step of implementation MUST bump `CACHE_VERSION` in `sw.js` (currently `'v3'` → `'v4'`).
**Warning signs:** Local testing works but deployed app shows old UI.

### Pitfall 6: Office Phone Number Source
**What goes wrong:** The Call Office FAB needs a phone number, but there is no `OFFICE_PHONE` constant in `config.py` or anywhere in the codebase.
**Why it happens:** The feature is new. No phone number has been configured yet.
**How to avoid:** Add the phone number as a configurable constant. For now, use a `data-tel` attribute on the FAB element with a placeholder that can be configured per deployment. In the API, expose it via the route response or a config endpoint. For v1.1, a hardcoded placeholder is acceptable since this is a single-distributor deployment.
**Warning signs:** Shipping with `tel:` pointing to an empty or placeholder number.

## Code Examples

Verified patterns from the existing codebase and web standards:

### Existing: Optimistic Status Update (reuse as-is)
```javascript
// Source: index.html lines 1123-1152
async function updateStatus(vehicleId, orderId, status) {
    const stop = currentRoute.stops.find(s => s.order_id === orderId);
    if (stop) stop.status = status;
    saveToStorage(STORAGE_KEYS.ROUTE_DATA, currentRoute);
    renderStopList();
    updateSummary();
    try {
        const resp = await authPost(
            `${API_BASE}/api/routes/${vehicleId}/stops/${orderId}/status`,
            { status },
        );
        if (!resp.ok) throw new Error('Server rejected update');
    } catch {
        queueOfflineUpdate(vehicleId, orderId, status);
    }
}
```

### Existing: XSS-Safe innerHTML (reuse for all new rendering)
```javascript
// Source: index.html lines 826-834
function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
```

### New: Call Office FAB with tel: link
```html
<!-- Source: MDN tel: protocol documentation -->
<a href="tel:+91XXXXXXXXXX" id="call-office-fab" class="call-fab" aria-label="Call Office">
    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07
                 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3
                 a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09
                 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0
                 2.81.7A2 2 0 0 1 22 16.92z"/>
    </svg>
</a>
```
```css
.call-fab {
    position: fixed;
    bottom: 24px;
    right: 16px;
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: var(--color-surface-2);
    border: 2px solid var(--color-border-bright);
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--color-accent);
    box-shadow: 0 4px 16px rgba(0,0,0,0.5);
    z-index: 999;
    text-decoration: none;
    transition: transform 0.15s, background 0.15s;
}
.call-fab:active {
    transform: scale(0.9);
    background: rgba(255,148,16,0.15);
}
```

### New: Last Updated Timestamp Storage
```javascript
const STORAGE_KEYS = {
    // ... existing keys ...
    LAST_UPDATED: 'lpg_last_updated',
};

async function loadRoute(vehicleId) {
    // ... existing logic ...
    // On successful fetch, record timestamp
    saveToStorage(STORAGE_KEYS.LAST_UPDATED, new Date().toISOString());
    updateRefreshRow();
}

function updateRefreshRow() {
    const ts = loadFromStorage(STORAGE_KEYS.LAST_UPDATED);
    const el = document.getElementById('last-updated');
    if (ts && el) {
        const d = new Date(ts);
        el.textContent = `Last updated: ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    }
}
```

## WCAG AAA Color Audit

Pre-calculated contrast ratios for the locked color system. All ratios verified with the WCAG 2.1 relative luminance formula.

### Current Colors — Audit Results

| Color | Hex | vs #0B0B0F (bg) | vs #13131A (surface) | AAA Body (7:1) | AAA Large (4.5:1) | Action |
|-------|-----|-----------------|----------------------|----------------|-------------------|--------|
| Primary text | #F0EFFB | 17.25:1 | 16.24:1 | PASS | PASS | Keep |
| Secondary text | #9897B0 | 6.91:1 | 6.51:1 | FAIL | PASS | Bump to #A3A2BC |
| Muted text | #4E4D65 | 2.41:1 | 2.27:1 | FAIL | FAIL | ELIMINATE |
| Saffron accent | #FF9410 | 8.88:1 | 8.36:1 | PASS | PASS | Keep for large elements; use #F0EFFB for body-size text |
| Success green | #00C853 | 8.78:1 | 8.26:1 | PASS | PASS | Keep |
| Danger red | #FF3B30 | 5.54:1 | 5.21:1 | FAIL | PASS | Keep for large elements (buttons, icons); use #F0EFFB for body-size red text |
| Accent dim | #CC7600 | 5.76:1 | 5.42:1 | FAIL | PASS | Large-only or bump |

### Recommended Secondary Text Color

The current `--color-text-secondary` (#9897B0) at 6.91:1 narrowly misses AAA body text (7:1). Recommended replacement:

| Candidate | vs #0B0B0F | vs #13131A | Notes |
|-----------|------------|------------|-------|
| #9F9DB8 | 7.47:1 | 7.03:1 | Minimum passing — barely clears on surface |
| #A3A2BC | 7.88:1 | 7.42:1 | Recommended — comfortable margin on both |
| #A8A7C0 | 8.38:1 | 7.88:1 | Generous margin — slightly brighter |

**Recommendation:** Use `#A3A2BC` as `--color-text-secondary`. It passes 7:1 against both backgrounds with margin, stays visibly distinct from primary #F0EFFB, and preserves the existing blue-purple tint.

### Font Size Violations to Fix

Current violations of the 14px minimum:
- `.header .stats` — `font-size: 12px` (header stat text)
- `.stop-meta` — `font-size: 12px` (cylinder/weight/distance info)
- `.stop-notes` — `font-size: 12px` (delivery notes)
- `.summary-item .label` — `font-size: 10px` (summary bar labels — being removed)
- `.upload-status` — `font-size: 13px` (upload feedback)
- `.tab` — `font-size: 14px` (OK, but tab text uses `--color-text-muted` which must change)

### Large Text Definition (WCAG 2.1)
- **18.66px (14pt) bold** or larger = "large text" (4.5:1 AAA threshold)
- **24px (18pt) regular** or larger = "large text" (4.5:1 AAA threshold)
- Everything else = "body text" (7:1 AAA threshold)

With the locked decision of 14px minimum font size, all text below 18.66px bold is body text requiring 7:1. Saffron (#FF9410) at 8.88:1 actually passes 7:1 for body text against `#0B0B0F`, but fails against card backgrounds at body sizes since #13131A yields only 8.36:1 — wait, that still passes 7:1. **Correction: Saffron passes AAA body text against both backgrounds.** The user decision to use white for body-size saffron text is a conservative choice for outdoor readability, which is still the right call for Kerala sunlight conditions.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `confirm()` / `alert()` dialogs | HTML `<dialog>` + `showModal()` | Chrome 37 (2014), universal ~2022 | Free accessibility (focus trap, Esc, backdrop). 97%+ browser coverage |
| jQuery `.slideUp()`/`.slideDown()` | CSS `transform: translateY()` + `opacity` transitions | ~2018 | GPU-composited, no JS dependency, smooth on low-end devices |
| Custom offline cache managers | Service Worker Cache API + localStorage | ~2018 | Already implemented in this app. Mature pattern |
| Pixel-based touch targets (44px) | 48px minimum (WCAG 2.2), 60px+ for field use | WCAG 2.2 (Oct 2023) | 48px is the web standard minimum; 60px is field-use best practice for gloves |

**Deprecated/outdated:**
- `window.confirm()` / `window.alert()`: Blocks main thread, unstyled, tiny text. Use `<dialog>`.
- jQuery animations: Dead weight. CSS transitions cover all needs for this app.
- `var()` fallbacks for CSS custom properties: 97%+ browser support. No need for fallback hex values in `var(--color-accent, #FF9410)` patterns.

## Open Questions

1. **Office Phone Number**
   - What we know: No phone number exists anywhere in the codebase. The Call Office FAB needs a `tel:` href value.
   - What's unclear: Whether the number should come from `config.py`, an API endpoint, or be hardcoded in `index.html`.
   - Recommendation: Add `OFFICE_PHONE = "+91XXXXXXXXXX"` to `config.py`. For now, hardcode in `index.html` with a `TODO` comment. The driver app is a single-distributor deployment (Vatakara HPCL), so a hardcoded number is acceptable for v1.1. Expose via the route API response in a future phase.

2. **Customer Name in Hero Card**
   - What we know: CONTEXT.md says hero card shows "customer name (if available)". But the API response for `/api/routes/{vehicle_id}` does NOT include `customer_name`. The data model has `customer_ref` (a pseudonymized reference, NOT a real name — per privacy rules in the design doc).
   - What's unclear: Whether the user wants to show `customer_ref` or if they expect a real customer name.
   - Recommendation: Show `customer_ref` if it exists in the stop data, labeled as "Ref" (not "Customer"). If the API response doesn't include it (it currently doesn't), skip this field. Do NOT add a new API field without explicit user approval — PII sensitivity.

3. **Tailwind CSS Usage**
   - What we know: `tailwind.css` is loaded but the app uses almost entirely custom inline CSS. The Tailwind output provides base resets and DaisyUI component classes, but no DaisyUI classes appear to be used in the driver app HTML.
   - What's unclear: Whether new UI elements should use DaisyUI classes (e.g., `tw:btn`, `tw:modal`) or continue with custom CSS.
   - Recommendation: Continue with custom CSS. The driver app's custom dark theme with specific hex values is purpose-built for outdoor readability. DaisyUI's theme system would conflict. The Tailwind/DaisyUI CSS is loaded but should remain unused.

## Sources

### Primary (HIGH confidence)
- Existing codebase: `apps/kerala_delivery/driver_app/index.html` (1343 lines) — full analysis of CSS, JS, HTML structure
- Existing codebase: `apps/kerala_delivery/driver_app/sw.js` — service worker cache strategy
- Existing codebase: `apps/kerala_delivery/api/main.py` lines 1132-1179 — route API response structure
- Existing codebase: `apps/kerala_delivery/config.py` — no office phone number found
- WCAG 2.1 contrast formula — calculated programmatically with Python (all ratios in Color Audit verified)

### Secondary (MEDIUM confidence)
- [MDN: HTML `<dialog>` element](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/dialog) — showModal(), ::backdrop, focus management
- [CanIUse: dialog element](https://caniuse.com/dialog) — Chrome Android 37+, Samsung Internet 3.0+ (97%+ global coverage)
- [MDN: Storage quotas](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria) — localStorage ~5MB limit (sufficient for route data)
- [WebAIM: Contrast Checker](https://webaim.org/resources/contrastchecker/) — WCAG AAA requirements: 7:1 body, 4.5:1 large text
- [WCAG 2.1 Understanding Contrast](https://www.w3.org/WAI/WCAG21/Understanding/contrast-minimum.html) — large text definition: 18.66px bold or 24px regular

### Tertiary (LOW confidence)
- None. All findings verified against primary sources or calculated directly.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new libraries, all changes to existing single-file architecture
- Architecture: HIGH — patterns derived from direct analysis of existing codebase
- Pitfalls: HIGH — contrast ratios calculated programmatically, not estimated; touch target math verified against CSS specs
- Color audit: HIGH — every ratio computed with WCAG 2.1 relative luminance formula

**Research date:** 2026-03-03
**Valid until:** 2026-04-03 (stable — no external dependency changes expected)
