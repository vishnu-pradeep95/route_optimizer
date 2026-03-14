# Phase 21: Dashboard Settings and Cache Management - Context

**Gathered:** 2026-03-14
**Status:** Ready for planning

<domain>
## Phase Boundary

Office staff can manage the Google Maps API key, view upload history, and inspect/export/import the geocode cache — all from a new Settings page in the dashboard. No new capabilities beyond SET-01 through SET-06.

</domain>

<decisions>
## Implementation Decisions

### API Key Storage & Update Flow
- Store the API key in a new `settings` database table (not .env rewrite) — immediately available without server restart
- DB overrides .env: if a key exists in the DB settings table, use it; otherwise fall back to GOOGLE_MAPS_API_KEY from .env. Existing deployments keep working
- Validate the key before saving: make a single test geocoding request to Google Maps API with a known address (Vatakara depot). Show success/failure feedback to the user immediately
- Key displayed masked in the UI (SET-02) — exact masking pattern is Claude's discretion

### Settings Page Layout & Navigation
- Single scrollable page with stacked card/sections: API Key, Geocode Cache, Upload History
- Sidebar position: bottom of nav list (after Drivers) — Upload, Live Map, Run History, Drivers, Settings
- Geocode cache stats section shows estimated cost savings: "X cached addresses · Y API calls saved · ~$Z saved" using $5/1000 Google rate

### Upload History
- Relabel `vehicles_used` as "Drivers" in the UI — no DB schema change needed, the field already stores the correct count
- Claude's discretion on whether to show as a compact summary card in Settings or enhance the existing RunHistory page (avoid duplicating the same data in two places)

### Cache Export/Import
- Export: single "Export Cache" button triggers browser JSON file download with all cached addresses, coordinates, sources, confidence scores
- Import: file picker → immediate import → show summary after ("Added 142 entries, skipped 38 duplicates")
- Import strategy: Claude's discretion on merge vs replace behavior (safest approach)
- "Clear Cache" button available with confirmation dialog showing entry count before deletion

### Claude's Discretion
- Exact API key masking pattern (first 4 + last 4, or just last 4, etc.)
- Settings icon (gear vs wrench from lucide-react)
- Upload history approach (compact card in Settings vs enhancing RunHistory page)
- Cache import merge strategy (skip duplicates vs update duplicates)
- Settings table schema design (key-value pairs vs typed columns)
- New API endpoint design for geocode stats, cache export/import, and API key management

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `RunHistory.tsx`: Data-fetching page pattern (useState → useCallback → useEffect → JSX) — follow same pattern for Settings
- `DriverManagement.tsx`: Mutation page pattern with inline forms, save/cancel, re-fetch on success
- `EmptyState`, `ErrorBanner`, `StatusBadge` components: Reusable across Settings sections
- `apiFetch<T>()` and `apiWrite<T>()` in lib/api.ts: HTTP client with API key headers and error handling
- `isApiError()` type guard from lib/errors.ts: Error classification for ErrorBanner
- `lucide-react`: Icon library already in use (Settings icon available)
- DaisyUI `tw:card`, `tw:stat`, `tw:btn` components: Use for Settings sections

### Established Patterns
- State-based page switching in App.tsx: `activePage` state + conditional rendering (no router)
- Navigation: `NAV_ITEMS` array with `{ page, icon, label }` objects
- API client: `apiFetch<T>(path)` for GET, `apiWrite<T>(path, method, body)` for mutations
- Repository pattern: All CRUD in `core/database/repository.py` — add settings + cache stats methods
- Health endpoint already checks `google_api.status` — can be enhanced with DB key check

### Integration Points
- `App.tsx` NAV_ITEMS: Add "settings" entry, extend `Page` type union
- `lib/api.ts`: Add fetchSettings, updateApiKey, fetchGeocodeStats, exportGeocodeCache, importGeocodeCache, clearGeocodeCache functions
- `types.ts`: Add Settings, GeocodeStats, CacheExportEntry interfaces
- `main.py`: New endpoints for settings CRUD, geocode cache stats/export/import
- `core/database/models.py`: New SettingsDB model for key-value or typed settings table
- `core/database/repository.py`: New methods for settings get/set, cache stats aggregation, cache export/import
- `_get_geocoder()` in main.py: Modify to check DB settings table before .env fallback
- `health.py`: Update `check_google_api()` to also check DB-stored key

</code_context>

<specifics>
## Specific Ideas

- The Settings page should feel like a natural extension of the dashboard — same industrial-utilitarian aesthetic, card-based sections
- Cost savings display gives office staff tangible evidence that the geocode cache is saving money
- API key validation via test geocode call gives immediate confidence the key works — no "save and hope" pattern
- Cache export is primarily for migration between machines (development → production, or office laptop replacement)
- Clear Cache with confirmation prevents accidental data loss — dialog should show how many entries will be deleted

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 21-dashboard-settings-and-cache-management*
*Context gathered: 2026-03-14*
