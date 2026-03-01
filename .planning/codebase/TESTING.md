# Testing Patterns

**Analysis Date:** 2026-03-01

## Test Framework

**Runner:**
- pytest 9.0.2
- Config: No explicit `pytest.ini` — uses defaults
- Async support: `pytest-asyncio` 1.3.0 for async test functions

**Assertion Library:**
- pytest built-in assertions (no pytest-cov in requirements, coverage via pytest)

**Run Commands:**
```bash
pytest                           # Run all tests
pytest -v                        # Verbose output
pytest tests/apps/kerala_delivery/  # Run specific directory
pytest tests/test_e2e_pipeline.py  # Run specific file
pytest -k "test_health"         # Run tests matching pattern
```

## Test File Organization

**Location:**
- Tests co-located with source code under `tests/` directory mirror
- `src/core/models/location.py` → `tests/core/models/test_models.py`
- `src/apps/kerala_delivery/api/main.py` → `tests/apps/kerala_delivery/api/test_api.py`

**Naming:**
- Test modules prefixed with `test_`: `test_api.py`, `test_qr_helpers.py`
- Test functions prefixed with `test_`: `test_health_returns_ok()`, `test_empty_stops_returns_empty_string()`
- Test classes use `Test` prefix for organization: `TestBuildGoogleMapsUrl`, `TestHealthEndpoint`

**Structure:**
```
tests/
├── conftest.py                    # Shared fixtures (kochi_depot, sample_orders, etc.)
├── test_e2e_pipeline.py           # End-to-end workflow tests
├── apps/
│   └── kerala_delivery/
│       └── api/
│           ├── test_api.py        # API endpoint tests
│           └── test_qr_helpers.py # QR/Google Maps helper tests
├── core/
│   ├── models/
│   │   └── test_models.py         # Location, Order, Vehicle, Route validation
│   ├── routing/
│   │   └── test_osrm_adapter.py   # OSRM routing adapter tests
│   ├── data_import/
│   │   ├── test_csv_importer.py
│   │   └── test_cdcms_preprocessor.py
│   ├── geocoding/
│   │   ├── test_cache.py
│   │   └── test_google_adapter.py
│   ├── database/
│   │   └── test_database.py
│   ├── optimizer/
│   │   └── test_vroom_adapter.py
│   └── licensing/
│       └── test_license_manager.py
├── integration/
│   └── test_osrm_vroom_pipeline.py
└── scripts/
    ├── test_geocode_batch.py
    └── test_import_orders.py
```

## Test Structure

**Suite Organization:**

Tests are grouped into classes for logical organization. Classes group related test cases and share common setup/teardown through class-scoped or function-scoped fixtures.

```python
class TestBuildGoogleMapsUrl:
    """Test Google Maps Directions URL construction."""

    def test_empty_stops_returns_empty_string(self):
        """No stops → empty URL (guard clause)."""
        assert build_google_maps_url([]) == ""

    def test_two_stops_no_waypoints(self, two_stops):
        """Two stops → origin + destination, no waypoints."""
        url = build_google_maps_url(two_stops)
        assert "origin=9.97,76.28" in url
        assert "destination=9.98,76.29" in url
```

**Patterns:**

1. **Descriptive test names:** Test name describes the scenario and expected outcome
   - `test_empty_stops_returns_empty_string()` not `test_1()`
   - `test_max_weight_kg_is_90_percent_of_rated()` explains the business rule

2. **One assertion focus:** Each test verifies one behavior (multiple assertions on same object OK)
   ```python
   def test_location_returns_correct_tuple(self):
       loc = Location(latitude=9.9716, longitude=76.2846)
       assert loc.to_lon_lat_tuple() == (76.2846, 9.9716)  # OK: same operation
   ```

3. **Fixtures for reusable data:** Pytest fixtures provide test inputs
   ```python
   @pytest.fixture
   def two_stops():
       """Minimal route: origin + destination (no waypoints)."""
       return [
           {"latitude": 9.97, "longitude": 76.28},
           {"latitude": 9.98, "longitude": 76.29},
       ]
   ```

4. **Descriptive comments:** Each test has a docstring explaining what and why
   ```python
   def test_monsoon_multiplier_greater_than_safety(self):
       """Monsoon multiplier (1.5×) should exceed base safety multiplier (1.3×).

       During monsoon, roads flood and travel times increase 30-50%.
       The monsoon multiplier REPLACES (not stacks on top of) the
       base safety multiplier in the upload-and-optimize endpoint.
       """
   ```

## Mocking

**Framework:** `unittest.mock` (Python standard library)

**Common mocking patterns:**

1. **AsyncMock for database sessions:**
   ```python
   @pytest.fixture
   def mock_session():
       """Create a mock AsyncSession for dependency override."""
       session = AsyncMock()
       session.commit = AsyncMock()
       session.rollback = AsyncMock()
       session.close = AsyncMock()
       return session
   ```

2. **Dependency override for FastAPI:**
   ```python
   @pytest.fixture
   def client(mock_session):
       """FastAPI TestClient with DB session overridden to a mock."""
       async def override_get_session():
           yield mock_session

       app.dependency_overrides[get_session] = override_get_session
       yield TestClient(app)
       app.dependency_overrides.clear()
   ```

3. **Mocking httpx for external API calls:**
   ```python
   @patch('httpx.get')
   def test_osrm_applies_safety_multiplier(self, mock_get, osrm):
       """Verify safety multiplier is applied to OSRM travel times."""
       mock_get.return_value = MagicMock(
           json=lambda: {"code": "Ok", "routes": [{"duration": 300.0}]},
           status_code=200
       )
       result = osrm.get_travel_time(origin, destination)
       assert result.duration_seconds == 390  # 300 * 1.3 (safety multiplier)
   ```

**What to Mock:**
- External APIs (OSRM, Google Maps, VROOM) — use `@patch` or `MagicMock`
- Database connections — use `AsyncMock()` for SQLAlchemy sessions
- File I/O in unit tests — but not in integration tests that verify real CSV parsing
- Rate limiters — disabled via environment variable in test fixtures

**What NOT to Mock:**
- Pydantic models — validate directly with test instances
- Pure business logic (ordering, weight calculations) — test with real values
- CSV parsing — test with real CSV fixtures to catch format issues
- Google Maps URL building — test the actual URL formatting, not the browser

## Fixtures and Factories

**Test Data:**

Shared fixtures are defined in `tests/conftest.py` with real Kerala coordinates:

```python
@pytest.fixture
def kochi_depot():
    """Central Kochi depot location (near MG Road area)."""
    return Location(
        latitude=9.9716,
        longitude=76.2846,
        address_text="LPG Godown - Main Depot",
    )

@pytest.fixture
def sample_locations():
    """5 delivery locations within ~5km of Kochi depot.
    These are real public landmarks in Kochi.
    """
    return [
        Location(latitude=9.9816, longitude=76.2996, address_text="Edappally Junction"),
        Location(latitude=9.9567, longitude=76.2998, address_text="Palarivattom"),
        # ... more locations
    ]

@pytest.fixture
def sample_orders(sample_locations):
    """5 sample LPG delivery orders with geocoded locations."""
    orders = []
    for i, loc in enumerate(sample_locations):
        orders.append(
            Order(
                order_id=f"TEST-{i+1:03d}",
                location=loc,
                address_raw=loc.address_text or f"Test Address {i+1}",
                customer_ref=f"CUST-{i+1:03d}",
                weight_kg=14.2 * (1 + i % 2),
            )
        )
    return orders
```

**Location:**
- Shared fixtures: `tests/conftest.py`
- Module-specific fixtures: Top of test file (e.g., `test_qr_helpers.py` defines `two_stops`, `three_stops`, `eleven_stops`)
- API response fixtures: In test modules with `mock_vroom_2_orders`, `osrm_route_response`

**Fixture Design:**
- Real Kerala coordinates validate actual OSM/geocoding behavior (not (0,0) mocks)
- Fixture dependencies chain: `sample_orders(sample_locations)`, `sample_fleet(kochi_depot)`
- Minimal fixtures: Only populate fields needed for the test

## Coverage

**Requirements:** No explicit coverage requirement enforced

**Observation:** 351 tests passing (from recent commit message) suggests comprehensive coverage

**View Coverage:**
```bash
pytest --cov=core --cov=apps --cov-report=html
# or
pytest --cov=core --cov=apps --cov-report=term-missing
```

## Test Types

**Unit Tests:**
- Scope: Single function or method
- Dependencies: Mocked (external APIs, database)
- Example: `test_build_google_maps_url()` in `test_qr_helpers.py`
- Approach: Direct function call with test inputs, assert on return value

**Integration Tests:**
- Scope: Multiple components working together
- Dependencies: Real services where feasible (or well-mocked)
- Example: `test_csv_produces_geocoded_orders()` in `test_e2e_pipeline.py`
- Approach: Full CSV→Orders→Optimization workflow with mocked VROOM/OSRM

**E2E Tests:**
- Scope: Complete API workflow
- Example: `test_upload_creates_routes()` in `test_e2e_pipeline.py`
- Approach: POST /upload endpoint with CSV, assert response shape and data

**API Tests:**
- Framework: FastAPI's `TestClient` (not a real HTTP server)
- Example: `TestHealthEndpoint.test_health_returns_ok()` in `test_api.py`
- Pattern: Create client fixture, make request, assert status/response

## Common Patterns

**Async Testing:**

Tests using async functions are marked with `@pytest.mark.asyncio`:

```python
@pytest.mark.asyncio
async def test_repository_saves_order(self, mock_session):
    """Async repository method saves order to database."""
    from core.database.repository import OrderRepository
    repo = OrderRepository(mock_session)
    order = Order(...)
    await repo.save_order(order)
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()
```

**Error Testing:**

Validation errors and exceptions are tested with `pytest.raises()`:

```python
def test_invalid_latitude_rejected(self):
    """Latitude outside -90..90 is rejected by Pydantic validation."""
    with pytest.raises(ValidationError):
        Location(latitude=91.0, longitude=76.0)

def test_missing_csv_columns_raises_value_error(self):
    """CSV without required columns raises ValueError."""
    with pytest.raises(ValueError):
        importer.import_orders("bad_columns.csv")
```

**Parametrized Tests:**

For testing multiple inputs with same logic, use `@pytest.mark.parametrize()`:

```python
@pytest.mark.parametrize("cylinder_type,expected_weight", [
    ("domestic", 14.2),
    ("14.2kg", 14.2),
    ("commercial", 19.0),
    ("19", 19.0),
])
def test_cylinder_weight_lookup(self, cylinder_type, expected_weight):
    """CYLINDER_WEIGHTS lookup resolves all known types."""
    assert config.CYLINDER_WEIGHTS[cylinder_type] == expected_weight
```

**Config Testing:**

Business rules are verified as tests to catch accidental changes:

```python
class TestSafetyConstraints:
    """Non-negotiable safety and regulatory parameters."""

    def test_speed_limit_40_kmh(self):
        """Urban Kerala speed limit for three-wheelers = 40 km/h.

        This is a Kerala MVD directive. Changing this value would
        violate regulatory compliance.
        """
        assert config.SPEED_LIMIT_KMH == 40.0

    def test_min_delivery_window_at_least_30_minutes(self):
        """Delivery windows must be >= 30 minutes.

        Kerala MVD directive: no "instant" or "10-minute" delivery promises.
        Windows shorter than this are forcibly widened by the API.
        """
        assert config.MIN_DELIVERY_WINDOW_MINUTES >= 30
```

---

*Testing analysis: 2026-03-01*
