# Phase 22: Google Routes Validation - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can manually compare a generated route against Google Routes API to assess OSRM routing accuracy. Each route card gets a "Validate with Google" button that shows a cost warning before calling the API, then displays an inline side-by-side comparison with a confidence indicator. Results persist in the database. Google Routes validation is never triggered automatically.

</domain>

<decisions>
## Implementation Decisions

### Comparison display
- Inline in route card — no modal or separate panel. Validation results expand within the existing RouteList card after the current stats
- "Validate with Google" button visible on every route card (not just selected)
- One-at-a-time only — no "Validate All" batch button
- Display: OSRM distance, Google distance, delta %. Same for time. Plus a colored confidence badge

### Confidence indicator
- Based on distance delta only (time varies with traffic, distance is stable and reflects route quality)
- Google re-optimizes stop order — comparison measures both road-network accuracy and optimization quality
- Claude decides exact thresholds for green/amber/red
- Claude decides badge style (dot+text vs percentage badge) based on existing dashboard patterns

### Cost warning
- Show per-request estimated cost AND cumulative tracker (validations count + total estimated cost)
- Always warn on every validation click — no "don't ask again" option
- If Google Maps API key is not configured: show message with link/button to Settings page (button still visible)
- Claude decides modal vs inline popover for the confirmation UX

### Result persistence
- Validation results stored in database (not session-only) — needs DB migration
- Previously-validated routes show cached result inline with a "Re-validate" button (no re-calling Google)
- Cumulative validation count and cost persist in DB for budgeting
- Validation history card added to Settings page (total validations, total cost, recent validations with results)

### Claude's Discretion
- Confidence thresholds (green/amber/red delta percentages)
- Badge visual style (dot+text vs percentage badge)
- Cost warning confirmation UX (modal vs popover)
- Google Routes API vs Directions API choice
- DB schema for validation results and cost tracking
- How to handle Google API errors (timeout, quota exceeded, invalid key)
- Whether to store per-stop comparison or route-level only

</decisions>

<specifics>
## Specific Ideas

- Google should re-optimize stop order (not follow VROOM sequence) — this measures total routing quality, not just road-network accuracy
- Cost tracker shows something like "₹0.42 per validation (12 validations today, ~₹5.04 total)"
- When no API key configured, button click shows "Google API key required" with a link to Settings page
- Cached validation results should show the date they were validated, so user knows how fresh the comparison is

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `RouteList.tsx`: Route cards with distance/time/stops — add validate button and inline result section here
- `lib/api.ts`: Already has `fetchGoogleMapsRoute()` stub and `apiFetch`/`apiWrite` wrappers
- `Settings.tsx`: Card-based layout — add Validation History card here
- `core/geocoding/google_adapter.py`: httpx pattern for Google API calls — reference for Routes API adapter
- `_validate_google_api_key()` in main.py: Pattern for testing API key validity
- `SettingsDB` model: Key-value schema for storing cumulative validation stats

### Established Patterns
- httpx for Google API calls (sync, with 10s timeout)
- DaisyUI modal for destructive confirmations (cache clear in Settings.tsx)
- Color-coded status badges (green/amber/red) throughout dashboard
- `tw:` prefix for all Tailwind/DaisyUI classes
- lucide-react for icons

### Integration Points
- `RouteList.tsx` — Add validate button and inline comparison display to each route card
- `lib/api.ts` — Add validation endpoint client function (update existing stub)
- `apps/kerala_delivery/api/main.py` — New validation endpoint
- `core/database/models.py` — New RouteValidation model for persisting results
- `core/database/repository.py` — CRUD for validation results and cost tracking
- `Settings.tsx` — Add Validation History card
- Alembic migration for new validation table

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 22-google-routes-validation*
*Context gathered: 2026-03-14*
