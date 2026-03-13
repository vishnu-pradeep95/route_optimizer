# Phase 16: Driver Database Foundation - Context

**Gathered:** 2026-03-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Drivers become first-class entities with full CRUD, fuzzy name matching for deduplication, auto-creation from CSV DeliveryMan column, and a Driver Management page replacing FleetManagement. The system starts with zero drivers and grows organically from CSV uploads and manual additions.

</domain>

<decisions>
## Implementation Decisions

### Driver Schema Evolution
- Drop the vehicle_id FK from DriverDB entirely — drivers are standalone entities, not vehicle accessories
- Drop the phone field — CDCMS doesn't provide it and there's no current use case
- Add a `name_normalized` column (uppercase, trimmed, collapsed spaces) for fast fuzzy matching lookups and indexing
- Add a `driver_id` FK (nullable, UUID) on RouteDB pointing to the drivers table for proper relational integrity
- Keep `driver_name` string on RouteDB for display purposes alongside `driver_id` FK — populate both on route creation
- Store driver names title-cased (e.g., "Suresh Kumar") — `name_normalized` stays uppercase for matching

### Fuzzy Matching Behavior
- Use RapidFuzz (already in project) for driver name deduplication
- Claude's discretion on exact similarity threshold — tune based on CDCMS name variation patterns
- Auto-merge with report: fuzzy matches merge automatically, but the upload response includes a summary of what was matched (e.g., "SURESH K → Suresh Kumar")
- Within a single CSV upload: do NOT merge intra-CSV name variations — create both as separate drivers, let user merge manually on the Driver Management page
- Deactivated drivers ARE eligible for fuzzy matching — if matched, reactivate them automatically and include in the report ("Reactivated: Suresh Kumar")
- Manual add (via dashboard) triggers fuzzy check: warn user if similar driver exists before creating
- Name edits (PUT) also trigger fuzzy check: warn if new name matches another existing driver
- Dedicated check endpoint: GET /api/drivers/check-name?name=X returns similar matches for the dashboard to display warnings before create/edit

### Driver Management Page
- Replace FleetManagement entirely — "Drivers" takes the FleetManagement sidebar slot
- Sidebar order becomes: Upload Routes, Live Map, Run History, Drivers
- Table columns: driver name, active/inactive status badge, route count (requires join query)
- CRUD: add, edit name, deactivate/reactivate — same inline pattern as FleetManagement
- Add form: Claude's discretion on simple inline input vs. form container (only one field: name)

### Auto-creation Flow
- Auto-creation happens during the parse step (early in pipeline), before geocoding begins
- If CSV has no DeliveryMan column, fall back to current vehicle-based behavior — backward compatible
- Upload response includes a `drivers` summary section: { new_drivers: [...], matched_drivers: [{csv_name, matched_to}], reactivated_drivers: [...], existing_drivers: [...] }

### Claude's Discretion
- Exact fuzzy matching threshold (tune based on representative CDCMS name data)
- Add driver form style (simple inline input vs. form container)
- Exact Alembic migration strategy for schema changes

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DriverDB` (core/database/models.py:99): Existing ORM model — needs reshaping (drop vehicle FK, drop phone, add name_normalized)
- `FleetManagement.tsx`: Full CRUD page pattern with inline forms, skeleton loading, DaisyUI components, error/success banners — replace with DriverManagement
- `FleetManagement.css`: Existing styles for the management page layout
- RapidFuzz: Already installed and used in `core/data_import/address_splitter.py` for fuzzy place name matching — reuse for driver name matching
- `EmptyState` component: Reusable empty state with icon, title, description, action button
- `ErrorBanner` component: Structured error display with retry and dismiss
- `lib/api.ts`: API client with fetchVehicles, createVehicle, etc. — add driver equivalents
- `lib/errors.ts`: Error type utilities (isApiError, ApiError type)

### Established Patterns
- Repository pattern: All CRUD in `core/database/repository.py` — add driver CRUD methods following same async pattern
- ORM models in `core/database/models.py` — DriverDB reshape follows existing mapped_column style
- API endpoints in `apps/kerala_delivery/api/main.py` — add driver endpoints following vehicle endpoint patterns
- Dashboard pages: useState/useCallback/useEffect hooks, DaisyUI components with `tw:` prefix
- Alembic migrations in `infra/alembic/versions/` — schema changes require new migration

### Integration Points
- `POST /api/upload-orders`: Needs driver extraction + auto-creation logic added to parse step
- `RouteDB` model: Add nullable `driver_id` FK column
- Dashboard `App.tsx`: Replace FleetManagement page import with DriverManagement, update sidebar nav
- Dashboard `types.ts`: Add Driver interface, DriversResponse, DriverCheckResponse types
- `infra/postgres/init.sql`: Update drivers table schema (source of truth for initial creation)

</code_context>

<specifics>
## Specific Ideas

- Driver names stored as title case ("Suresh Kumar") for clean dashboard display, but normalized to uppercase for matching
- Upload response should clearly distinguish new vs. matched vs. reactivated drivers so office staff knows what happened
- Route count column in driver table gives operational context — "this driver has been assigned 15 routes"
- The system should feel zero-config: first CSV upload with DeliveryMan column automatically bootstraps the driver list

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 16-driver-database-foundation*
*Context gathered: 2026-03-12*
