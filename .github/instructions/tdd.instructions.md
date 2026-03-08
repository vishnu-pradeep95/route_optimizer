---
description: "TDD guidelines — when to use test-driven development and how to structure TDD tasks"
applyTo: "**/PLAN.md,**/test_*,**/conftest.py"
---

# Test-Driven Development

TDD is about design quality, not coverage metrics. The red-green-refactor cycle forces you to think about behavior before implementation, producing cleaner interfaces and more testable code.

## When to Use TDD

**TDD candidates (use `type="tdd"` tasks):**

- Business logic with defined inputs/outputs (route optimization constraints)
- API endpoints with request/response contracts (FastAPI routes)
- Data transformations, parsing, formatting (CSV import → Order models)
- Validation rules and constraints (30-min windows, speed limits, capacity)
- Algorithms with testable behavior (distance matrix, time estimation)
- Interface compliance (adapter implements all ABC methods)

**Skip TDD (use standard tasks, add tests after):**

- Configuration changes (Docker compose, .env)
- Glue code connecting existing modules
- One-off scripts and migrations
- Simple CRUD with no business logic
- Exploratory prototyping
- UI layout and styling (dashboard, PWA)

**Heuristic:** Can you write `assert func(input) == expected` before writing `func`?
→ Yes: Use TDD
→ No: Write tests after implementation

## TDD in This Project

### Test Infrastructure

```
tests/
├── conftest.py          # Shared fixtures (mock OSRM, mock VROOM, test DB)
├── core/
│   ├── routing/
│   │   └── test_osrm_adapter.py
│   ├── optimizer/
│   │   └── test_vroom_adapter.py
│   ├── geocoding/
│   │   └── test_google_adapter.py
│   ├── data_import/
│   │   └── test_csv_importer.py
│   └── database/
│       └── test_repository.py
├── apps/
│   └── kerala_delivery/
│       └── test_config.py
├── integration/
│   └── test_pipeline.py
└── scripts/
    └── test_import_orders.py
```

### Running Tests

```bash
# Activate venv
source .venv/bin/activate

# Full suite
pytest

# Specific module
pytest tests/core/routing/ -v

# With coverage
pytest --cov=core --cov-report=term-missing

# Specific test
pytest tests/core/routing/test_osrm_adapter.py::test_distance_matrix -v
```

## Red-Green-Refactor Cycle

### RED — Write Failing Test

1. Create test file in `tests/` mirroring source structure
2. Write test describing expected behavior
3. Run test — it MUST fail
4. If test passes: feature already exists or test is wrong. Investigate.
5. Commit: `test({module}): add failing test for {feature}`

**Example — RED:**

```python
# tests/core/routing/test_osrm_adapter.py

import pytest
from core.routing.osrm_adapter import OSRMAdapter

def test_distance_matrix_returns_correct_shape():
    """Distance matrix for N locations should be NxN."""
    adapter = OSRMAdapter(base_url="http://localhost:5000")
    locations = [
        (76.2673, 9.9312),  # Kochi point 1
        (76.2733, 9.9352),  # Kochi point 2
        (76.2800, 9.9400),  # Kochi point 3
    ]
    matrix = adapter.get_distance_matrix(locations)
    assert len(matrix) == 3
    assert all(len(row) == 3 for row in matrix)

def test_safety_multiplier_applied():
    """All durations must include 1.3x safety multiplier."""
    adapter = OSRMAdapter(base_url="http://localhost:5000", safety_multiplier=1.3)
    # ... test that returned durations are 1.3x raw OSRM values
```

### GREEN — Implement to Pass

1. Write minimal code to make test pass
2. No cleverness, no optimization — just make it work
3. Run test — it MUST pass
4. Commit: `feat({module}): implement {feature}`

### REFACTOR (if needed)

1. Clean up implementation (extract methods, improve naming)
2. Run tests — MUST still pass
3. Commit only if changes made: `refactor({module}): clean up {feature}`

## Test Quality Guidelines

### Test Behavior, Not Implementation

```python
# Good — tests observable behavior
def test_optimizer_respects_vehicle_capacity():
    """No route should exceed the vehicle's weight capacity."""
    result = optimizer.optimize(orders, vehicle)
    for route in result.routes:
        assert route.total_weight <= vehicle.capacity_kg

# Bad — tests internal implementation
def test_optimizer_calls_vroom_api():
    """Checks that VROOM HTTP client is called."""
    # This test breaks on any internal refactor
```

### One Concept Per Test

```python
# Good — separate tests for each behavior
def test_rejects_time_window_under_30_minutes(): ...
def test_accepts_time_window_at_30_minutes(): ...
def test_accepts_time_window_over_30_minutes(): ...

# Bad — multiple behaviors in one test
def test_time_windows():
    # tests under 30, at 30, and over 30 all in one
```

### Descriptive Names

```python
# Good
def test_csv_import_skips_rows_with_missing_coordinates(): ...
def test_geocoder_returns_cached_result_on_second_call(): ...
def test_route_duration_includes_safety_multiplier(): ...

# Bad
def test_import(): ...
def test_cache(): ...
def test_multiplier(): ...
```

### Mock External Services

```python
# Good — mock OSRM HTTP response
@pytest.fixture
def mock_osrm(responses):
    """Mock OSRM table endpoint returning a 3x3 distance matrix."""
    responses.add(
        responses.GET,
        "http://localhost:5000/table/v1/driving/76.2673,9.9312;76.2733,9.9352;76.2800,9.9400",
        json={"durations": [[0, 120, 300], [120, 0, 200], [300, 200, 0]]},
        status=200,
    )

def test_distance_matrix_with_mock(mock_osrm):
    adapter = OSRMAdapter(base_url="http://localhost:5000")
    matrix = adapter.get_distance_matrix(locations)
    assert matrix[0][1] == pytest.approx(120 * 1.3)  # with safety multiplier
```

## Non-Negotiable Constraint Tests

Every non-negotiable constraint from the project MUST have an enforcement test:

```python
# tests/core/test_constraints.py

def test_no_delivery_window_under_30_minutes():
    """Kerala MVD directive: minimum 30-minute delivery windows."""
    with pytest.raises(ValueError, match="30 minutes"):
        create_time_window(start="09:00", end="09:20")

def test_safety_multiplier_always_applied():
    """All travel time estimates get 1.3x safety multiplier."""
    raw_duration = 600  # 10 minutes
    estimated = apply_safety_multiplier(raw_duration)
    assert estimated == pytest.approx(780)  # 13 minutes

def test_speed_alert_threshold():
    """Urban speed alert at 40 km/h."""
    assert should_alert(speed_kmh=41, zone="urban") is True
    assert should_alert(speed_kmh=39, zone="urban") is False
```
