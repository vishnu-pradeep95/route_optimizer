# Phase Verification Report — Phase [N]: [Phase Name]

**Date:** [YYYY-MM-DD]
**Result:** PASS | FAIL
**Mode:** initial | re-verification

---

## Phase Goal

> [Goal statement from design doc]

## Must-Haves

### Observable Truths

<!-- What must be TRUE for the goal to be achieved? (User perspective) -->

1. [Truth statement — user-observable behavior]
2. [Truth statement]

### Required Artifacts

<!-- What files must EXIST? -->

| Artifact | Path | Status |
|---|---|---|
| [Name] | `path/to/file.py` | VERIFIED / STUB / MISSING |

### Key Links (Wiring)

<!-- What must be CONNECTED? -->

| From | To | Via | Status |
|---|---|---|---|
| [Component A] | [Component B] | [Mechanism] | WIRED / BROKEN / ORPHANED |

---

## Three-Level Verification Results

### Level 1: Existence

| Artifact | Exists? | Notes |
|---|---|---|
| `path/to/file.py` | YES / NO | |

### Level 2: Substantive

| Artifact | Lines | Stub Patterns | Exports | Status |
|---|---|---|---|---|
| `path/to/file.py` | [N] | [N found] | YES/NO | SUBSTANTIVE / STUB / PARTIAL |

**Python-specific stub checks:**
- `pass` in function bodies
- `raise NotImplementedError`
- `return {}` / `return None` placeholders
- SQLAlchemy models with only `id` column
- FastAPI routes returning hardcoded responses
- Adapter classes not implementing ABC methods
- `# TODO` / `# FIXME` / `# HACK` comments

### Level 3: Wired

| Artifact | Imported By | Used By | Status |
|---|---|---|---|
| `path/to/file.py` | [N] files | [N] calls | WIRED / ORPHANED / PARTIAL |

**Python-specific wiring checks:**
- Adapter implements its ABC/Protocol interface
- `core/` modules never import from `apps/`
- Tests import and exercise the right fixtures
- Docker services can reach each other (OSRM ↔ VROOM ↔ PostGIS ↔ FastAPI)
- Config values are injected, not hardcoded

---

## Nyquist Validation (Test Coverage)

| Requirement | Test File | Test Command | Status |
|---|---|---|---|
| [Requirement] | `tests/path/test_file.py` | `pytest tests/path/test_file.py -k "test_name"` | PASS / FAIL / MISSING |

---

## Gaps

<!-- Items that failed verification. Feed into fix planning. -->

| # | Level | Artifact/Truth | Issue | Severity |
|---|---|---|---|---|
| 1 | [existence/substantive/wired] | [What failed] | [Why] | blocker / warning |

## Anti-Pattern Scan

```bash
# Run these checks against the phase's files
grep -rn "TODO\|FIXME\|HACK\|XXX" [phase_files]
grep -rn "pass$" [phase_files] --include="*.py"
grep -rn "raise NotImplementedError" [phase_files] --include="*.py"
grep -rn "return {}\|return None\|return \[\]" [phase_files] --include="*.py"
```

**Results:** [N] anti-patterns found | [Details if any]
