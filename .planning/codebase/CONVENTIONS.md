# Coding Conventions

**Analysis Date:** 2026-03-01

## Naming Patterns

**Files:**
- Lowercase with underscores: `csv_importer.py`, `osrm_adapter.py`, `qr_helpers.py`
- Test files prefixed with `test_`: `test_api.py`, `test_qr_helpers.py`
- No camelCase in filenames — use snake_case exclusively

**Functions:**
- snake_case: `build_google_maps_url()`, `generate_qr_base64_png()`, `get_travel_time()`
- Descriptive verbs: `split_route_into_segments()` not `route_split()`
- Private functions prefixed with underscore: `_row_to_order()`, `_validate_columns()`

**Variables:**
- snake_case: `vehicle_id`, `max_weight_kg`, `depot_location`
- Abbreviations avoided: use `vehicle_id` not `veh_id`
- Boolean variables are explicit: `is_geocoded`, `has_window`, `enable_rate_limit`
- Collection names are plural: `orders`, `vehicles`, `locations`

**Types/Classes:**
- PascalCase: `Location`, `Order`, `Vehicle`, `Route`, `RouteAssignment`
- Data models inherit `BaseModel` from Pydantic: see `core/models/*.py`
- Interface/abstract classes explicitly named: `RoutingEngine`, `OptimizerInterface`, `GeocoderInterface`

## Code Style

**Formatting:**
- No explicit linter configured (ruff, black, flake8 not found)
- Code follows PEP 8 conventions by convention
- Line length appears to be ~88 characters (implicit black standard)

**Docstrings:**
- Google-style docstrings with triple quotes
- Every module starts with a docstring explaining its purpose and design decisions
- Every class has a docstring with Attributes section
- Every function has a docstring with Args, Returns, and optional Raises sections

**Example:**
```python
def build_google_maps_url(stops: list[dict]) -> str:
    """Build a Google Maps Directions URL from an ordered list of stops.

    Args:
        stops: List of dicts with 'latitude' and 'longitude' keys,
               ordered by delivery sequence.

    Returns:
        Google Maps URL that opens navigation with all stops as waypoints.
        Empty string if stops is empty.
    """
```

## Import Organization

**Order:**
1. Standard library imports (logging, os, pathlib, etc.)
2. Third-party imports (fastapi, pydantic, sqlalchemy, pandas, etc.)
3. Blank line
4. Core module imports (from core.*)
5. Business-specific imports (from apps.*)

**Example from `apps/kerala_delivery/api/main.py`:**
```python
import hmac
import html as html_module
import logging
import os
import pathlib

from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.kerala_delivery import config
from apps.kerala_delivery.api.qr_helpers import build_google_maps_url
```

**TYPE_CHECKING blocks:**
- Circular imports avoided with conditional imports inside `if TYPE_CHECKING:` blocks
- Example: `core/database/models.py` uses TYPE_CHECKING to import `VehicleDB`

**Path Aliases:**
- No path aliases configured (no `jsconfig.json` or `tsconfig.json` with paths)
- Absolute imports from project root: `from core.models.location import Location`

## Error Handling

**Patterns:**
- Explicit exception handling — do not catch `Exception` broadly
- Specific exceptions: `ValueError`, `FileNotFoundError`, `KeyError`, `TypeError`
- Logging warnings for expected failures (e.g., malformed CSV rows)
- Re-raising unexpected exceptions to propagate up stack

**Example from `csv_importer.py`:**
```python
try:
    order = self._row_to_order(row, idx)
    orders.append(order)
except (ValueError, KeyError, TypeError) as e:
    # Log bad rows but don't fail the entire import
    logger.warning("Skipping row %s: %s", idx, e)
    continue
```

**HTTP Error Responses:**
- FastAPI `HTTPException` for API errors
- Standard HTTP status codes: 200, 400, 404, 422, 429, 500
- Meaningful error messages in response body

## Logging

**Framework:** `logging` (Python standard library)

**Setup:**
- Module-level logger: `logger = logging.getLogger(__name__)`
- One logger per module, initialized at module level

**Patterns:**
- `logger.debug()`: Cache hits, minor operations
- `logger.info()`: Process milestones (import complete, optimization started)
- `logger.warning()`: Expected failures (bad row in CSV, geocoding miss)
- `logger.error()`: Unexpected failures (API timeout, database error)

**Example from `cache.py`:**
```python
logger.debug("Cache HIT for address: %s", address[:50])
logger.warning("Geocoding cache collision — different coords for same address")
logger.error("Upstream geocoding failed for '%s': %s", address[:50], e)
```

## Comments

**When to Comment:**
- Explain WHY, not WHAT (code already says what it does)
- High-level design decisions: why OSRM over Google Maps, why 30% safety buffer
- Non-obvious business logic: "MVD directive: no instant delivery", "Conservative estimate — adjust after real testing"
- Complex algorithms: e.g., route splitting with overlapping segments

**Example from `qr_helpers.py`:**
```python
# Advance by (max - 1) so the last stop of this segment becomes
# the first stop of the next segment (overlap for continuity)
i += max_stops_per_segment - 1
```

**JSDoc/TSDoc:**
- Not used — project is Python-only
- Google-style docstrings serve this purpose

## Function Design

**Size:**
- Small, focused functions: 20–40 lines typical
- Break logic into named helper functions: see `_row_to_order()`, `_parse_weight()`, `_validate_columns()`

**Parameters:**
- Use type hints: `def get_travel_time(self, origin: Location, destination: Location) -> TravelTime:`
- Use Pydantic models for complex parameter groups (not raw dicts/tuples)
- Default parameters rare — instead use dependency injection (FastAPI patterns)

**Return Values:**
- Explicit type hints on all functions
- Return Pydantic models or dataclasses, not raw dicts
- None is explicit when no return value needed

## Module Design

**Exports:**
- No `__all__` explicitly defined (but imports are clear from usage)
- Public functions/classes are the API — private helpers prefixed with `_`

**Barrel Files:**
- `__init__.py` files are minimal, usually empty or with brief imports
- Direct imports from modules: `from core.models.location import Location` (not `from core.models import Location`)

**Separation of Concerns:**
- `core/` contains business-agnostic logic (Location, Order, Vehicle models, routing/geocoding interfaces)
- `apps/kerala_delivery/` contains business-specific configuration and API routes
- `config.py` is the single source of truth for Kerala LPG constants (fleet size, cylinder weights, etc.)

**Pydantic Models:**
- All domain models use Pydantic `BaseModel` with Field descriptors
- Validation rules encoded in Field constraints: `ge=0`, `le=100`, custom validators
- Example: `Location` validates lat/lon ranges (-90..90, -180..180)

---

*Convention analysis: 2026-03-01*
