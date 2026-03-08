---
description: "Verification patterns for checking implementations are real, not stubs or placeholders"
applyTo: "**/VERIFICATION.md,**/*.py"
---

# Verification Patterns

How to verify artifacts are real implementations, not stubs or placeholders.

## Core Principle

**Existence ≠ Implementation**

A file existing does not mean the feature works. Verification must check:

1. **Exists** — File is present at expected path
2. **Substantive** — Content is real implementation, not placeholder
3. **Wired** — Connected to the rest of the system
4. **Functional** — Actually works when invoked (tests pass)

Levels 1-3 can be checked programmatically. Level 4 requires running tests or the application.

## Python Stub Detection

### Universal Patterns

```bash
# Comment-based stubs
grep -E "(TODO|FIXME|XXX|HACK|PLACEHOLDER)" "$file"
grep -E "implement|add later|coming soon|will be" "$file" -i

# Empty or trivial implementations
grep -E "pass$|raise NotImplementedError|return \{\}|return None$|return \[\]" "$file"

# Placeholder text
grep -E "placeholder|lorem ipsum|coming soon|sample data|dummy" "$file" -i
```

### ABC Interface Stubs

```python
# RED FLAG — ABC with no abstract methods:
class RoutingEngine(ABC):
    pass  # No @abstractmethod defined

# RED FLAG — Abstract method with trivial default:
class RoutingEngine(ABC):
    @abstractmethod
    def get_route(self, start, end):
        return {}  # Should have no body or raise NotImplementedError
```

**Substantive check:**

```bash
# ABC should have @abstractmethod decorators
grep -c "@abstractmethod" "$interface_file"
# Should be > 0

# Each abstract method should have a docstring
grep -A2 "@abstractmethod" "$interface_file" | grep -c '"""'
```

### Adapter/Implementation Stubs

```python
# RED FLAG — Method exists but does nothing:
def get_distance_matrix(self, locations):
    pass

# RED FLAG — Returns empty/hardcoded data:
def get_distance_matrix(self, locations):
    return [[0] * len(locations)] * len(locations)

# RED FLAG — Only logs:
def optimize(self, orders, vehicles):
    logger.info("Optimizing routes...")
    return []
```

**Substantive check:**

```bash
# Implementation should have HTTP calls (for adapters)
grep -c -E "requests\.(get|post)|httpx\.(get|post)|self\.session\." "$adapter_file"
# Should be > 0 for adapters that call external services

# Implementation should use its constructor params
grep -E "self\.\w+" "$adapter_file" | head -10
```

### FastAPI Route Stubs

```python
# RED FLAG — Route returns static response:
@router.get("/orders")
async def list_orders():
    return {"orders": []}

# RED FLAG — Route ignores request body:
@router.post("/orders")
async def create_order(order: OrderCreate):
    return {"status": "ok"}

# RED FLAG — No database interaction:
@router.get("/orders/{order_id}")
async def get_order(order_id: int):
    return {"id": order_id, "status": "placeholder"}
```

**Substantive check:**

```bash
# Route should use repository/database
grep -c -E "repository\.|session\.|db\." "$route_file"

# Route should validate/use request data
grep -c -E "request\.|body\.|order\." "$route_file"
```

### SQLAlchemy Model Stubs

```python
# RED FLAG — Model with only id:
class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    # TODO: add fields

# RED FLAG — Model with no relationships:
class Route(Base):
    __tablename__ = "routes"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    # Missing: orders relationship, vehicle FK, etc.
```

**Substantive check:**

```bash
# Model should have multiple columns
grep -c "Column\|mapped_column\|relationship" "$model_file"
# Should be > 2 for real models

# Model should have appropriate types
grep -E "Integer|String|Float|DateTime|Boolean|ForeignKey|JSON" "$model_file"
```

### Pydantic Model Stubs

```python
# RED FLAG — Empty model:
class OrderCreate(BaseModel):
    pass

# RED FLAG — All Optional with no validators:
class OrderCreate(BaseModel):
    address: Optional[str] = None
    weight: Optional[float] = None
    # Nothing required, no validation
```

**Substantive check:**

```bash
# Pydantic model should have typed fields
grep -c -E ":\s*(str|int|float|bool|list|dict|Optional|List|Dict)" "$model_file"

# Should have validators for business rules
grep -c -E "@validator|@field_validator|@model_validator" "$model_file"
```

## Wiring Verification

### Pattern: Interface → Implementation

```bash
# Implementation imports and inherits from interface
grep -E "from.*interfaces import" "$impl_file"
grep -E "class.*\(.*ABC\|Protocol\)" "$impl_file"

# All abstract methods are implemented (no NotImplementedError)
grep -c "raise NotImplementedError" "$impl_file"
# Should be 0
```

### Pattern: Module → Module (core/ only)

```bash
# Check architecture boundary: core/ NEVER imports apps/
grep -rn "from apps\.\|import apps\." core/ --include="*.py" 2>/dev/null
# Must return 0 results

# Check modules import via interfaces, not implementations
grep -rn "from core\.routing\.osrm_adapter import" core/ --include="*.py" 2>/dev/null | grep -v "core/routing/"
# Other modules should import from interfaces, not directly from adapter
```

### Pattern: Script → Core Module

```bash
# Script imports from core/
grep -E "from core\." "$script_file"

# Script has entry point
grep -E 'if __name__.*==.*"__main__"' "$script_file"

# Script uses argparse or click for CLI
grep -E "argparse\|click\|typer" "$script_file"
```

### Pattern: Test → Implementation

```bash
# Test imports the module under test
grep -E "from core\.|from apps\." "$test_file"

# Test has assertions
grep -c "assert" "$test_file"
# Should be > 0

# Test uses fixtures (not hardcoded setup)
grep -E "@pytest.fixture\|def test_.*\(.*\w" "$test_file"
```

## Quick Verification Checklist

### Interface Checklist
- [ ] File exists at `core/{module}/interfaces.py`
- [ ] Has ≥1 ABC/Protocol class
- [ ] Each class has ≥1 `@abstractmethod`
- [ ] Each method has a docstring
- [ ] Type hints on all parameters and return types

### Adapter Checklist
- [ ] File exists at `core/{module}/{name}_adapter.py`
- [ ] Imports and inherits from interface
- [ ] Implements all abstract methods
- [ ] No `raise NotImplementedError` or `pass` in method bodies
- [ ] Has HTTP client calls (for external service adapters)
- [ ] Has error handling (try/except for network errors)
- [ ] Constructor accepts configuration (URL, timeouts, etc.)

### Model Checklist
- [ ] File exists at `core/models/{name}.py`
- [ ] Has typed fields (not all Optional)
- [ ] Has validators for business rules
- [ ] Exported from `core/models/__init__.py`

### Test Checklist
- [ ] File exists at `tests/core/{module}/test_{name}.py`
- [ ] Has ≥1 test function
- [ ] Tests behavior, not implementation
- [ ] External services mocked (no real HTTP calls)
- [ ] Uses fixtures from conftest.py
- [ ] Descriptive test names

### Non-Negotiable Constraint Checklist
- [ ] No countdown timer code anywhere
- [ ] Time windows enforce ≥30 minutes
- [ ] Speed threshold is 40 km/h for urban
- [ ] Safety multiplier of 1.3 is applied
- [ ] PII fields not stored in optimizer data structures
