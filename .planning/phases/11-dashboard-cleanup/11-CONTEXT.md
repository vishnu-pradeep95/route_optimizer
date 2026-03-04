# Phase 11: Dashboard Cleanup - Context

**Gathered:** 2026-03-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Eliminate dead CSS, hardcoded colors, TypeScript type gaps, and N+1 route fetching in the dashboard. No new features — strictly cleanup. Requirements: DASH-01 through DASH-05.

</domain>

<decisions>
## Implementation Decisions

### Batch API endpoint (DASH-05)
- Extend existing `GET /api/routes` with `?include_stops=true` query parameter
- When `include_stops=true`: each route in the response includes `stops[]`, `total_weight_kg`, and `total_items` (unified response shape)
- Default is `false` — existing callers get the same response (non-breaking)
- Keep the old per-vehicle endpoint `GET /api/routes/{vehicle_id}` — driver PWA depends on it
- LiveMap switches to single batch call instead of N sequential `fetchRouteDetail` calls

### CSS token cleanup (DASH-01, DASH-02)
- Full CSS audit: check ALL `--color-*` tokens in `index.css` for dead declarations, not just the 3 legacy aliases
- Remove all dead tokens — any `--color-*` declared but never referenced gets deleted (clean sweep)
- `.text-muted-30` hardcoded hex replaced with a design token

### StatusBadge type alignment (DASH-04)
- Widen StatusBadge to accept a flat union type: `'pending' | 'delivered' | 'failed' | 'completed' | 'running'`
- Implement exhaustive switch inside StatusBadge for color/label mapping
- Remove the unsafe `as` cast in RunHistory.tsx line 244
- Also fix the inline hardcoded `#dc2626` color on RunHistory.tsx line 231 — use `var(--color-danger)` for consistency with token cleanup

### RouteDetail type gap (DASH-03)
- Add `total_weight_kg` and `total_items` to the `RouteDetail` TypeScript interface
- Aligns with the unified batch response shape decided above
- Remove any `as any` or `as unknown` casts for these fields

### Claude's Discretion
- Whether `.text-muted-30` maps to new `--color-text-faint` (stone 400, preserving current look) or existing `--color-text-muted` (stone 500, slightly darker)
- Exact exhaustive switch implementation in StatusBadge
- Plan splitting strategy (which requirements group into which plans)

</decisions>

<specifics>
## Specific Ideas

- The batch endpoint should be backward-compatible — `?include_stops=true` is opt-in
- RunHistory.tsx line 231 has a hardcoded `#dc2626` that should use `var(--color-danger)` as part of the cleanup
- Clean sweep on dead CSS tokens — don't leave partial debris

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `StatusBadge` component (`src/components/StatusBadge.tsx`): Already handles delivery statuses, needs widening for run statuses
- `types.ts`: Central type file — `RouteSummary` already has `total_weight_kg`/`total_items`, `RouteDetail` needs them added
- `index.css`: Design token system with `--color-*` naming, DaisyUI logistics theme, `.text-muted-*` utility classes

### Established Patterns
- Tailwind v4 with `tw:` prefix throughout dashboard
- DaisyUI components (`tw:table`, `tw:skeleton`, `tw:badge`)
- `fetchRoutes()`, `fetchRouteDetail()`, `fetchFleetTelemetry()` in `lib/api.ts` — fetch helpers for API calls
- `Promise.allSettled` pattern for parallel fetching in LiveMap (to be replaced)

### Integration Points
- `GET /api/routes` endpoint in `api/main.py` — needs `include_stops` query parameter
- `LiveMap.tsx` `loadRouteData()` function — replace N+1 with single batch call
- `RunHistory.tsx` StatusBadge usage — remove cast after widening component
- `index.css` `:root` block — token audit and cleanup

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 11-dashboard-cleanup*
*Context gathered: 2026-03-04*
