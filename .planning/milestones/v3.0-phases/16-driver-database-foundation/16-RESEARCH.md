# Phase 16: Driver Database Foundation - Research

**Researched:** 2026-03-12
**Domain:** Database schema evolution, CRUD API, fuzzy name matching, React dashboard page
**Confidence:** HIGH

## Summary

Phase 16 reshapes the existing `DriverDB` model into a standalone entity (dropping vehicle FK and phone), adds a `name_normalized` column for fuzzy matching, builds full CRUD API endpoints following the vehicle endpoint pattern, replaces the FleetManagement dashboard page with DriverManagement, and wires driver auto-creation into the CSV upload pipeline. All decisions are locked in CONTEXT.md -- no alternatives need exploring.

The implementation is well-constrained by existing patterns. The vehicle CRUD flow (model, repository, API endpoint, dashboard page) provides a direct template. RapidFuzz 3.14.3 is already installed and used in `address_splitter.py` for fuzzy place name matching -- the same library is used for driver name deduplication. The Alembic migration pattern is established with idempotent `ALTER TABLE ... IF NOT EXISTS` for safe deployment.

**Primary recommendation:** Follow the vehicle CRUD pattern exactly (model -> repository -> API endpoints -> dashboard page), reshaping DriverDB rather than creating a new model. Use `fuzz.ratio` from RapidFuzz with a threshold of ~85 for driver name matching, tuned for CDCMS name patterns (all-caps abbreviations vs title-case full names).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Drop the vehicle_id FK from DriverDB entirely -- drivers are standalone entities, not vehicle accessories
- Drop the phone field -- CDCMS doesn't provide it and there's no current use case
- Add a `name_normalized` column (uppercase, trimmed, collapsed spaces) for fast fuzzy matching lookups and indexing
- Add a `driver_id` FK (nullable, UUID) on RouteDB pointing to the drivers table for proper relational integrity
- Keep `driver_name` string on RouteDB for display purposes alongside `driver_id` FK -- populate both on route creation
- Store driver names title-cased (e.g., "Suresh Kumar") -- `name_normalized` stays uppercase for matching
- Use RapidFuzz (already in project) for driver name deduplication
- Auto-merge with report: fuzzy matches merge automatically, upload response includes summary
- Within a single CSV upload: do NOT merge intra-CSV name variations -- create both as separate drivers
- Deactivated drivers ARE eligible for fuzzy matching -- if matched, reactivate automatically
- Manual add (via dashboard) triggers fuzzy check: warn user if similar driver exists before creating
- Name edits (PUT) also trigger fuzzy check: warn if new name matches another existing driver
- Dedicated check endpoint: GET /api/drivers/check-name?name=X returns similar matches
- Replace FleetManagement entirely -- "Drivers" takes the FleetManagement sidebar slot
- Sidebar order: Upload Routes, Live Map, Run History, Drivers
- Table columns: driver name, active/inactive status badge, route count (requires join query)
- CRUD: add, edit name, deactivate/reactivate -- same inline pattern as FleetManagement
- Auto-creation happens during the parse step (early in pipeline), before geocoding begins
- If CSV has no DeliveryMan column, fall back to current vehicle-based behavior -- backward compatible
- Upload response includes a `drivers` summary section: { new_drivers, matched_drivers, reactivated_drivers, existing_drivers }

### Claude's Discretion
- Exact fuzzy matching threshold (tune based on representative CDCMS name data)
- Add driver form style (simple inline input vs. form container)
- Exact Alembic migration strategy for schema changes

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DRV-01 | User can view a list of all drivers with name and active status | Dashboard DriverManagement page with DaisyUI table, following FleetManagement.tsx pattern |
| DRV-02 | User can manually add a new driver by entering a name | POST /api/drivers endpoint + inline add form, with fuzzy check warning via GET /api/drivers/check-name |
| DRV-03 | User can edit an existing driver's name | PUT /api/drivers/{id} endpoint + inline edit row, with fuzzy check on new name |
| DRV-04 | User can deactivate a driver (soft delete) | DELETE /api/drivers/{id} sets is_active=false, same pattern as vehicle deactivation |
| DRV-05 | System auto-creates new drivers from CSV DeliveryMan column on upload | Extract delivery_man from preprocessed_df, fuzzy-match against existing drivers, create new DriverDB rows |
| DRV-06 | System uses fuzzy name matching (RapidFuzz) to avoid creating duplicate drivers | RapidFuzz fuzz.ratio with ~85 threshold on name_normalized column, including deactivated drivers |
| DRV-07 | System starts with zero drivers (no pre-loaded fleet) | No driver seed data in init.sql, unlike vehicles which have 13 seeded rows |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| SQLAlchemy | 2.0 | ORM model for DriverDB, async queries | Already used for all models, mapped_column style |
| Alembic | (project version) | Schema migration for driver table changes | Established async migration pattern in infra/alembic/ |
| RapidFuzz | 3.14.3 | Fuzzy driver name matching | Already installed, used in address_splitter.py |
| FastAPI | (project version) | Driver CRUD API endpoints | Existing API framework, Pydantic models for validation |
| React 19 | 19 | DriverManagement dashboard page | Dashboard framework |
| DaisyUI | v5 | Table, badge, button, form components | Design system used across all dashboard pages |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| lucide-react | (project version) | Icons for sidebar nav and page UI | Replace Truck icon with Users/UserPlus for Drivers |
| Pydantic | v2 | Request/response body validation | DriverCreate, DriverUpdate, DriverCheckResponse models |

### Alternatives Considered
None -- all decisions are locked in CONTEXT.md. Stack is entirely existing project tooling.

**Installation:**
No new packages needed. RapidFuzz 3.14.3, SQLAlchemy 2.0, Alembic, FastAPI, React 19, DaisyUI v5 are all already installed.

## Architecture Patterns

### Database Schema Changes

**DriverDB reshape (core/database/models.py:99):**
```python
class DriverDB(Base):
    __tablename__ = "drivers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_normalized: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
```

Changes from current:
- DROP: `phone` column
- DROP: `vehicle_id` FK column
- DROP: `vehicle` relationship
- ADD: `name_normalized` (uppercase, trimmed, collapsed spaces)
- ADD: `updated_at` column (for tracking edits)

**RouteDB addition:**
```python
# Add to RouteDB (alongside existing driver_name string)
driver_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True), ForeignKey("drivers.id"), nullable=True
)
```

**VehicleDB cleanup:**
- DROP: `drivers` relationship (back_populates="vehicle") since DriverDB no longer has vehicle_id

### Recommended File Structure

Files that need changes (not new directories -- follows existing structure):
```
core/database/models.py          # Reshape DriverDB, add driver_id to RouteDB
core/database/repository.py      # Add driver CRUD + fuzzy match methods
infra/postgres/init.sql           # Update drivers table schema
infra/alembic/versions/           # New migration for schema changes
apps/kerala_delivery/api/main.py  # Add driver API endpoints
apps/kerala_delivery/api/errors.py # Add DRIVER_* error codes
apps/kerala_delivery/dashboard/src/
  pages/DriverManagement.tsx      # New page (replaces FleetManagement)
  pages/DriverManagement.css      # New styles (based on FleetManagement.css)
  lib/api.ts                      # Add driver API client functions
  types.ts                        # Add Driver, DriversResponse types
  App.tsx                         # Replace FleetManagement with DriverManagement
tests/core/database/              # Driver model + repo tests
tests/apps/kerala_delivery/api/   # Driver API endpoint tests
```

### Pattern 1: Name Normalization

**What:** Convert driver names to a canonical form for matching
**When to use:** Every time a name is stored or compared

```python
def normalize_driver_name(name: str) -> str:
    """Normalize a driver name for fuzzy matching.

    Converts to uppercase, strips whitespace, collapses multiple spaces.
    This is stored in name_normalized column for indexed lookups.
    """
    import re
    return re.sub(r'\s+', ' ', name.strip().upper())
```

### Pattern 2: Fuzzy Name Matching with RapidFuzz

**What:** Find existing drivers whose names are similar to a new name
**When to use:** CSV upload auto-creation, manual add, name edit

```python
from rapidfuzz import fuzz

DRIVER_MATCH_THRESHOLD = 85  # Claude's discretion to tune

async def find_similar_drivers(
    session: AsyncSession,
    name: str,
    exclude_id: uuid.UUID | None = None,
) -> list[tuple[DriverDB, float]]:
    """Find existing drivers with similar names.

    Checks ALL drivers (including deactivated) because deactivated
    drivers should be reactivated rather than duplicated.
    """
    normalized = normalize_driver_name(name)

    # Fetch all drivers for fuzzy comparison
    result = await session.execute(select(DriverDB))
    all_drivers = list(result.scalars().all())

    matches = []
    for driver in all_drivers:
        if exclude_id and driver.id == exclude_id:
            continue
        score = fuzz.ratio(normalized, driver.name_normalized)
        if score >= DRIVER_MATCH_THRESHOLD:
            matches.append((driver, score))

    # Sort by score descending
    matches.sort(key=lambda x: x[1], reverse=True)
    return matches
```

**Why fuzz.ratio over fuzz.token_sort_ratio:** CDCMS driver names are typically short (2-3 words, first name + surname/initial). `fuzz.ratio` handles the common variations:
- "SURESH K" vs "SURESH KUMAR" (partial surname) -- ratio ~75-80
- "RAJESH" vs "RAJESH P" (missing initial) -- ratio ~80-85
- "SURESH KUMAR K" vs "SURESH K" -- ratio ~70

For the threshold, consider that CDCMS names are typically:
- ALL CAPS with abbreviations: "SURESH K", "RAJMOHAN P"
- Sometimes full names: "SURESH KUMAR", "RAJMOHAN PILLAI"
- Occasionally with middle initials: "SURESH K NAIR"

A threshold of ~85 catches "SURESH K" vs "SURESH KUMAR K" while avoiding false merges between genuinely different drivers like "SURESH" vs "SUDHESH".

**Performance note:** With <50 drivers in a typical operation, scanning all drivers and computing fuzzy scores is negligible (<1ms). No need for optimized search algorithms at this scale.

### Pattern 3: Auto-Creation Flow in Upload Pipeline

**What:** Extract DeliveryMan from CSV, match against existing drivers, create new ones
**When to use:** During upload_and_optimize(), after CDCMS preprocessing, before geocoding

The preprocessed DataFrame already contains a `delivery_man` column (line 295 of cdcms_preprocessor.py). The auto-creation step:

1. Extract unique delivery_man values from preprocessed_df
2. For each unique name, fuzzy-match against all existing drivers (including inactive)
3. If match found and driver is active: record as "existing"
4. If match found and driver is inactive: reactivate, record as "reactivated"
5. If no match: create new driver with title-cased name, record as "new"
6. Include driver summary in upload response

**Critical:** Do NOT merge intra-CSV name variations. If the CSV has both "SURESH K" and "SURESH KUMAR", create both as separate drivers.

### Pattern 4: Repository Layer (following vehicle CRUD pattern)

```python
# New repository methods needed:
async def get_all_drivers(session, active_only=False) -> list[DriverDB]
async def get_driver_by_id(session, driver_id: uuid.UUID) -> DriverDB | None
async def create_driver(session, name: str) -> DriverDB
async def update_driver_name(session, driver_id: uuid.UUID, new_name: str) -> bool
async def deactivate_driver(session, driver_id: uuid.UUID) -> bool
async def reactivate_driver(session, driver_id: uuid.UUID) -> bool
async def get_driver_route_counts(session) -> dict[uuid.UUID, int]
async def find_similar_drivers(session, name: str, exclude_id=None) -> list[tuple[DriverDB, float]]
```

### Pattern 5: API Endpoints (following vehicle endpoint pattern)

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | /api/drivers | verify_read_key | List all drivers with route counts |
| GET | /api/drivers/check-name | verify_read_key | Check for similar driver names |
| POST | /api/drivers | verify_api_key | Create a new driver |
| PUT | /api/drivers/{id} | verify_api_key | Update driver name |
| DELETE | /api/drivers/{id} | verify_api_key | Deactivate driver (soft delete) |

### Pattern 6: Dashboard Page (following FleetManagement pattern)

The DriverManagement page is structurally simpler than FleetManagement because there's only one field (name) instead of eight. Key differences:
- Table columns: Name, Status (badge), Route Count, Actions
- Add form: single name input (vs 8-field grid for vehicles)
- Edit row: single name input inline
- Warning banner: shown when fuzzy check returns similar matches
- No filter toggle needed initially (can add "active only" later)

### Anti-Patterns to Avoid
- **Storing normalized name only:** Keep both `name` (title-case for display) and `name_normalized` (uppercase for matching). Don't compute normalized on-the-fly -- it should be indexed.
- **Hard-deleting drivers:** Routes reference driver_id FK. Soft-delete (is_active=false) preserves referential integrity and audit trail.
- **Merging intra-CSV names:** If one CSV has "SURESH K" and "SURESH KUMAR", creating both separately is intentional. Let the user merge manually on the management page.
- **Ignoring deactivated drivers in fuzzy matching:** A deactivated "Suresh Kumar" should match and be reactivated, not create a duplicate.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fuzzy string matching | Custom edit-distance algorithm | `rapidfuzz.fuzz.ratio()` | RapidFuzz is C-optimized, handles Unicode, already installed |
| Name normalization | Manual string manipulation | `re.sub(r'\s+', ' ', name.strip().upper())` | Simple and correct for CDCMS name patterns |
| Schema migration | Manual ALTER TABLE in code | Alembic migration with `IF NOT EXISTS` | Established project pattern, handles rollbacks |
| Inline CRUD forms | Custom modal dialogs | FleetManagement inline form pattern | Proven UX pattern already in the project |

**Key insight:** This phase is 95% pattern-following from existing vehicle CRUD. The only novel part is fuzzy name matching, which RapidFuzz handles trivially.

## Common Pitfalls

### Pitfall 1: Alembic Migration Ordering for FK Changes
**What goes wrong:** Adding `driver_id` FK to RouteDB while also dropping `vehicle_id` FK from DriverDB in the same migration can cause constraint issues.
**Why it happens:** PostgreSQL evaluates constraints in order. Dropping a FK that other tables depend on (via relationship) before cleaning up those references causes errors.
**How to avoid:** Use a single well-ordered migration: (1) add `name_normalized` to drivers, (2) drop `phone` and `vehicle_id` from drivers, (3) add `driver_id` to routes, (4) add `updated_at` to drivers. Use `IF NOT EXISTS` / `IF EXISTS` for idempotency.
**Warning signs:** Migration fails on `docker compose up` for fresh databases that already have the updated init.sql schema.

### Pitfall 2: VehicleDB Relationship Cleanup
**What goes wrong:** Dropping `vehicle_id` from DriverDB without removing the `drivers` relationship from VehicleDB causes SQLAlchemy errors on startup.
**Why it happens:** SQLAlchemy tries to configure the back_populates relationship and fails when the FK column doesn't exist.
**How to avoid:** Remove `drivers: Mapped[list["DriverDB"]] = relationship(back_populates="vehicle")` from VehicleDB in the same commit that removes `vehicle_id` from DriverDB.
**Warning signs:** `sqlalchemy.exc.ArgumentError` or `InvalidRequestError` on app startup.

### Pitfall 3: init.sql / ORM Model Drift
**What goes wrong:** Updating the ORM model but forgetting init.sql (or vice versa). Fresh Docker installs use init.sql; existing installs use Alembic migrations.
**Why it happens:** Two sources of truth for schema.
**How to avoid:** Update init.sql and ORM model in the same commit. The migration bridges the gap for existing databases.
**Warning signs:** Tests pass (use mocks) but `docker compose up` fails on a fresh database.

### Pitfall 4: Fuzzy Match Threshold Too Aggressive
**What goes wrong:** Setting threshold too low (e.g., 70) causes false merges between different drivers ("SURESH" matches "SUDESH").
**Why it happens:** Short Indian names have high similarity scores even when they're different people.
**How to avoid:** Start with threshold ~85, log all fuzzy matches in the upload response so operators can verify. Include the match score in the response for debugging.
**Warning signs:** Office staff reports that different drivers are being merged.

### Pitfall 5: Missing Backward Compatibility for CSV Without DeliveryMan
**What goes wrong:** Upload fails for CSVs that don't have a DeliveryMan column.
**Why it happens:** Auto-creation code assumes delivery_man column always exists in preprocessed_df.
**How to avoid:** Check if `delivery_man` column exists in preprocessed_df. If not, skip driver auto-creation entirely (fall back to current vehicle-based flow). This is specified in CONTEXT.md.
**Warning signs:** Standard CSV uploads (non-CDCMS) crash with KeyError.

### Pitfall 6: Race Condition on Concurrent Uploads
**What goes wrong:** Two simultaneous CSV uploads both try to create the same driver, resulting in duplicate entries.
**Why it happens:** Fuzzy check and insert are not atomic.
**How to avoid:** Add a UNIQUE index on `name_normalized` to prevent exact duplicates at the database level. Fuzzy duplicates are handled at the application level and are acceptable to have temporarily -- the driver management page lets users merge.
**Warning signs:** Duplicate driver names appear in the driver list after busy upload periods.

## Code Examples

### Alembic Migration Pattern
```python
# Based on existing migration pattern (54c27825e8df)
def upgrade() -> None:
    # Add name_normalized column
    op.execute(
        "ALTER TABLE drivers ADD COLUMN IF NOT EXISTS "
        "name_normalized VARCHAR(100)"
    )
    # Add updated_at column
    op.execute(
        "ALTER TABLE drivers ADD COLUMN IF NOT EXISTS "
        "updated_at TIMESTAMPTZ DEFAULT NOW()"
    )
    # Drop phone column
    op.execute(
        "ALTER TABLE drivers DROP COLUMN IF EXISTS phone"
    )
    # Drop vehicle_id FK column
    op.execute(
        "ALTER TABLE drivers DROP COLUMN IF EXISTS vehicle_id"
    )
    # Add driver_id FK to routes
    op.execute(
        "ALTER TABLE routes ADD COLUMN IF NOT EXISTS "
        "driver_id UUID REFERENCES drivers(id)"
    )
    # Backfill name_normalized for any existing drivers
    op.execute(
        "UPDATE drivers SET name_normalized = UPPER(TRIM(name)) "
        "WHERE name_normalized IS NULL"
    )
    # Make name_normalized NOT NULL after backfill
    op.execute(
        "ALTER TABLE drivers ALTER COLUMN name_normalized SET NOT NULL"
    )
    # Index for fast name lookups
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_drivers_name_normalized "
        "ON drivers(name_normalized)"
    )
```

### API Pydantic Models
```python
class DriverCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100,
                      description="Driver's full name")

class DriverUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = Field(default=None)

class DriverCheckResponse(BaseModel):
    similar_drivers: list[dict]  # [{id, name, score, is_active}]
```

### Dashboard TypeScript Types
```typescript
export interface Driver {
  id: string;
  name: string;
  is_active: boolean;
  route_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface DriversResponse {
  count: number;
  drivers: Driver[];
}

export interface DriverCheckResponse {
  similar_drivers: Array<{
    id: string;
    name: string;
    score: number;
    is_active: boolean;
  }>;
}
```

### Upload Response Driver Summary
```python
# Added to upload response (alongside existing fields)
"drivers": {
    "new_drivers": ["Suresh Kumar", "Rajesh P"],
    "matched_drivers": [
        {"csv_name": "SURESH K", "matched_to": "Suresh Kumar", "score": 88}
    ],
    "reactivated_drivers": ["Mohan Lal"],
    "existing_drivers": ["Rajesh P"],
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| DriverDB linked to VehicleDB via FK | Standalone DriverDB entity | Phase 16 | Drivers are not vehicle accessories |
| FleetManagement page for vehicles | DriverManagement replaces it | Phase 16 | Sidebar nav changes |
| vehicle_id only on RouteDB | driver_id FK + driver_name string | Phase 16 | Proper relational integrity |
| Manual driver creation only | Auto-creation from CSV DeliveryMan | Phase 16 | Zero-config bootstrapping |

**Deprecated/outdated:**
- `DriverDB.vehicle_id` FK: Removed, drivers are standalone
- `DriverDB.phone`: Removed, no current use case
- `VehicleDB.drivers` relationship: Removed, no FK to back-populate
- FleetManagement page: Replaced by DriverManagement

## Open Questions

1. **Fuzzy threshold tuning**
   - What we know: `fuzz.ratio` with ~85 works for "SURESH K" vs "SURESH KUMAR" patterns
   - What's unclear: Exact CDCMS name variation patterns across all drivers
   - Recommendation: Start with 85, log all matches with scores in upload response. Tune based on operator feedback after first few uploads. This is Claude's discretion per CONTEXT.md.

2. **Route count query performance**
   - What we know: Route count requires a JOIN between drivers and routes tables
   - What's unclear: Whether to precompute or query on each page load
   - Recommendation: Query on each page load with a simple `COUNT` subquery or LEFT JOIN. At <50 drivers and <1000 routes, this is negligible. No caching needed.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (asyncio_mode = auto) |
| Config file | pytest.ini |
| Quick run command | `pytest tests/core/database/ tests/apps/kerala_delivery/api/ -x -q` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DRV-01 | GET /api/drivers returns driver list | unit | `pytest tests/apps/kerala_delivery/api/test_api.py -k "test_list_drivers" -x` | Wave 0 |
| DRV-02 | POST /api/drivers creates driver | unit | `pytest tests/apps/kerala_delivery/api/test_api.py -k "test_create_driver" -x` | Wave 0 |
| DRV-03 | PUT /api/drivers/{id} updates name | unit | `pytest tests/apps/kerala_delivery/api/test_api.py -k "test_update_driver" -x` | Wave 0 |
| DRV-04 | DELETE /api/drivers/{id} deactivates | unit | `pytest tests/apps/kerala_delivery/api/test_api.py -k "test_deactivate_driver" -x` | Wave 0 |
| DRV-05 | Upload creates drivers from CSV | unit | `pytest tests/apps/kerala_delivery/api/test_api.py -k "test_upload_auto_creates_drivers" -x` | Wave 0 |
| DRV-06 | Fuzzy matching prevents duplicates | unit | `pytest tests/core/database/test_driver_matching.py -x` | Wave 0 |
| DRV-07 | No pre-loaded drivers on fresh start | unit | `pytest tests/core/database/test_database.py -k "test_no_seeded_drivers" -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/core/database/ tests/apps/kerala_delivery/api/ -x -q`
- **Per wave merge:** `pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/core/database/test_driver_matching.py` -- covers DRV-06 fuzzy matching logic
- [ ] Driver CRUD test methods in `tests/apps/kerala_delivery/api/test_api.py` -- covers DRV-01 through DRV-05
- [ ] Update existing `test_driver_table_name` test for new schema (DRV-07 no-seed verification)

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `core/database/models.py` -- current DriverDB model (lines 99-121)
- Codebase inspection: `core/database/repository.py` -- vehicle CRUD pattern (lines 574-726)
- Codebase inspection: `apps/kerala_delivery/api/main.py` -- vehicle API endpoints (lines 2369-2515)
- Codebase inspection: `apps/kerala_delivery/dashboard/src/pages/FleetManagement.tsx` -- full CRUD page pattern (784 lines)
- Codebase inspection: `core/data_import/cdcms_preprocessor.py` -- delivery_man column in preprocessed DataFrame (line 295)
- Codebase inspection: `core/data_import/address_splitter.py` -- RapidFuzz fuzz.ratio usage pattern (line 234)
- Codebase inspection: `infra/alembic/versions/54c27825e8df_*.py` -- migration pattern with IF NOT EXISTS
- RapidFuzz 3.14.3 installed (`pip show rapidfuzz`)

### Secondary (MEDIUM confidence)
- RapidFuzz `fuzz.ratio` scoring behavior for short name strings -- based on project's existing usage in address_splitter.py with similar threshold tuning

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all libraries already in project, no new dependencies
- Architecture: HIGH -- direct pattern-following from vehicle CRUD flow
- Pitfalls: HIGH -- identified from codebase analysis (FK relationships, init.sql drift, migration ordering)
- Fuzzy matching threshold: MEDIUM -- 85 is a reasonable starting point but needs real-world tuning

**Research date:** 2026-03-12
**Valid until:** 2026-04-12 (stable -- all internal project patterns, no external dependencies changing)
