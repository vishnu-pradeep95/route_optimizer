# Validation Architecture — Phase [N]: [Phase Name]

**Date:** [YYYY-MM-DD]
**Test Infrastructure:** pytest + Docker Compose
**Coverage Target:** Every requirement has at least one automated test

> **Nyquist Principle:** Map automated test coverage to each requirement BEFORE
> any code is written. This ensures that when a task is committed, a feedback
> mechanism already exists to verify it within seconds.

---

## Requirement → Test Mapping

| Req ID | Requirement | Test File | Test Function | Command | Status |
|---|---|---|---|---|---|
| R1 | [Requirement description] | `tests/path/test_file.py` | `test_function_name` | `pytest tests/path/test_file.py::test_function_name` | PLANNED / EXISTS / PASS / FAIL |
| R2 | [Requirement description] | ... | ... | ... | ... |

## Test Scaffolding Needed (Wave 0)

<!-- Tests or fixtures that must be created BEFORE implementation begins -->

| Test File | Purpose | Dependencies |
|---|---|---|
| `tests/path/test_file.py` | [What it validates] | [Fixtures, mocks, services needed] |

## Existing Test Infrastructure

- **Test runner:** pytest
- **Test directory:** `tests/` (mirrors `core/` and `apps/` structure)
- **Fixtures:** `tests/conftest.py`
- **Integration tests:** `tests/integration/`
- **Coverage:** [current count] tests, [N] passing

## Verification Commands

```bash
# Run all tests for this phase
pytest tests/[relevant_path]/ -v

# Run with coverage
pytest tests/[relevant_path]/ --cov=[module_path] --cov-report=term-missing

# Quick smoke test
pytest tests/[relevant_path]/ -x --tb=short
```

## Gaps

<!-- Requirements with no test mapping — must be resolved before plan approval -->

| Req ID | Requirement | Reason No Test | Resolution |
|---|---|---|---|
| ... | ... | [Why no test exists] | [How to add one] |
