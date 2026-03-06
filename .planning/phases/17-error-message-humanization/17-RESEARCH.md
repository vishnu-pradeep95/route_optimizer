# Phase 17: Error Message Humanization - Research

**Researched:** 2026-03-05
**Domain:** Python error message formatting, API error translation, user-facing error UX
**Confidence:** HIGH

## Summary

This phase is a pure string-formatting exercise across 4 specific code locations in the Python backend. No new libraries, no frontend changes, no architectural shifts. The existing data pipeline already has the right structure -- `RowError.message`, `ImportFailure.reason`, `GEOCODING_REASON_MAP` -- the problem is that raw Python representations (set notation, `str(e)`, raw API status codes) leak through those string fields to the office employee's screen.

The CDCMS column validator (`cdcms_preprocessor.py:347`) uses `{missing_required}` which renders as `{'OrderNo', 'ConsumerAddress'}` -- Python set literal notation. The CSV importer catch-all (`csv_importer.py:237`) uses `str(e)` which passes through raw Python exception messages. The geocoding fallback (`main.py:934`) uses `f"Geocoding failed ({status})"` which exposes raw API status codes. Additionally, the `preprocess_cdcms()` call in the upload endpoint has no try/except for `ValueError`, meaning column validation failures produce a 500 Internal Server Error with a Python traceback instead of a 400 with a friendly message.

**Primary recommendation:** Fix the 4 specific code locations identified in CONTEXT.md, add a `ValueError` catch in main.py around `preprocess_cdcms()`, and update `GEOCODING_REASON_MAP` entries to use the "problem -- fix action" pattern.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Every error message follows "Problem -- fix action" pattern
- Example: "Address not found -- check spelling in CDCMS"
- Example: "Google Maps quota exceeded -- contact IT"
- Missing column errors: Format "Required columns missing: OrderNo, ConsumerAddress -- make sure you're uploading the raw CDCMS export"
- Do NOT show "Found columns: [...]" in user-facing message -- that's noise for office staff
- Log found columns at WARNING level server-side for IT debugging
- Update all 6 entries in `GEOCODING_REASON_MAP` to match success criteria style
- ZERO_RESULTS: "Address not found -- check spelling in CDCMS"
- OVER_DAILY_LIMIT: "Google Maps quota exceeded -- contact IT"
- Extend same pattern to remaining 4 codes (REQUEST_DENIED, OVER_QUERY_LIMIT, INVALID_REQUEST, UNKNOWN_ERROR)
- Unknown error fallback: "Could not find this address -- try checking the spelling"
- No raw status codes exposed to user -- IT checks server logs
- Replace current fallback `f"Geocoding failed ({status})"` with the generic friendly message

### Claude's Discretion
- Exact contact phrasing per error context ("contact IT" vs "contact admin" -- Claude picks what fits)
- Which row-level error patterns to translate vs use generic fallback
- Whether to add a catch-all error wrapper in the upload endpoint for unexpected exceptions

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ERR-01 | Upload errors use plain English instead of Python set notation | Fix `cdcms_preprocessor.py:347-352` to join set items into comma-separated string; fix `csv_importer.py:270-272` to format list without brackets; fix `csv_importer.py:237` catch-all to translate common exception patterns; add ValueError catch in `main.py` around `preprocess_cdcms()` |
| ERR-02 | Geocoding errors translated to office-friendly descriptions | Update all 6 entries in `main.py:82-89` GEOCODING_REASON_MAP; replace fallback at `main.py:934` with friendly generic message |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12 | Backend language | Already in use |
| FastAPI | (current) | API framework | Already in use, HTTPException for error responses |
| Pydantic | v2 | Data models | ImportFailure, RowError models already defined |

### Supporting
No new libraries needed. This is a string-formatting change to existing code.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Inline string formatting | i18n library (babel, gettext) | Overkill for single-language office app with ~15 error messages |
| Pattern-matching str(e) | Custom exception classes | Would require refactoring csv_importer internals; str(e) translation is sufficient |

## Architecture Patterns

### Error Message Flow (Existing -- No Changes Needed)

```
Python exception / API status code
    -> RowError.message or ImportFailure.reason (string field)
    -> JSON response to dashboard
    -> Dashboard table renders `reason` column as-is
```

The architecture is already correct. The problem is purely the **content** of the string fields.

### Pattern 1: "Problem -- Fix Action" Message Format
**What:** Every user-facing error message follows `"{problem description} -- {what to do about it}"`
**When to use:** All error messages displayed to office staff
**Example:**
```python
# GOOD: follows the pattern
"Required columns missing: OrderNo, ConsumerAddress -- make sure you're uploading the raw CDCMS export"

# BAD: Python internals leak through
f"CDCMS export is missing required columns: {missing_required}. Found columns: {sorted(present)}."
```

### Pattern 2: Server-Side Logging for IT, Friendly Messages for Users
**What:** Raw technical details go to `logger.warning()`, user gets only the friendly message
**When to use:** Whenever technical information is useful for debugging but confusing for office staff
**Example:**
```python
# Log raw details for IT debugging
logger.warning(
    "CDCMS missing required columns: %s. Found: %s",
    missing_required,
    sorted(present),
)
# User sees only the friendly part
raise ValueError(
    f"Required columns missing: {', '.join(sorted(missing_required))} -- "
    "make sure you're uploading the raw CDCMS export"
)
```

### Pattern 3: ValueError Catch at API Boundary
**What:** Catch ValueError from preprocessor/importer at the API endpoint level and convert to HTTPException(400)
**When to use:** At the upload endpoint where `preprocess_cdcms()` is called without error handling
**Example:**
```python
try:
    preprocessed_df = preprocess_cdcms(tmp_path, area_suffix=config.CDCMS_AREA_SUFFIX)
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))
```

### Anti-Patterns to Avoid
- **Passing `str(e)` directly to users:** Python exception messages contain class names, repr notation, and internal details. Always translate or wrap.
- **Including technical context in user messages:** "Found columns: [...]" is debugging info, not user info. Log it server-side.
- **Using Python set/list repr in strings:** `{set}` and `[list]` notation is meaningless to non-programmers. Use `', '.join()`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Error message translation | Complex error registry/framework | Simple string formatting + dict lookup | Only ~15 messages total; a framework adds complexity for no benefit |
| Exception pattern matching | Regex parser for Python tracebacks | if/elif on exception type + simple string checks | Row-level errors are already caught by type (ValueError, KeyError, TypeError) |

**Key insight:** This phase has exactly 4 code locations to fix and ~15 error messages to rewrite. No infrastructure is needed -- just careful string formatting.

## Common Pitfalls

### Pitfall 1: Uncaught ValueError from preprocess_cdcms()
**What goes wrong:** `_validate_cdcms_columns()` raises `ValueError` but `preprocess_cdcms()` is called at main.py:764 without a try/except. The ValueError propagates as a 500 Internal Server Error with a full Python traceback visible to the user.
**Why it happens:** The try block at main.py:736 only has a `finally` (for temp file cleanup), no `except ValueError`.
**How to avoid:** Add `except ValueError as e: raise HTTPException(status_code=400, detail=str(e))` around the `preprocess_cdcms()` call. Since we're also fixing the ValueError message itself, the detail will now be friendly.
**Warning signs:** Any 500 error on CSV upload with CDCMS format when columns are missing.

### Pitfall 2: Set Ordering is Non-Deterministic
**What goes wrong:** `{missing_required}` renders as `{'ConsumerAddress', 'OrderNo'}` or `{'OrderNo', 'ConsumerAddress'}` -- the order changes between runs.
**Why it happens:** Python sets are unordered.
**How to avoid:** Use `', '.join(sorted(missing_required))` to produce consistent, alphabetically-ordered column names.
**Warning signs:** Flaky test assertions that depend on set element order.

### Pitfall 3: csv_importer._validate_columns() Also Leaks
**What goes wrong:** `csv_importer.py:270-272` has `f"{alternatives}. Found columns: {list(df.columns)}"` which shows Python list notation.
**Why it happens:** Same pattern as the CDCMS validator -- using Python repr in f-strings.
**How to avoid:** Same fix: join with commas, remove "Found columns" from user message, log it server-side.
**Warning signs:** Non-CDCMS CSV uploads with wrong column names show `['address', 'delivery_address', ...]` notation.

### Pitfall 4: str(e) in Catch-All Exposes Python Internals
**What goes wrong:** `csv_importer.py:237` uses `message=str(e)` which for ValueError might be `could not convert string to float: 'abc'`, for KeyError it's `'column_name'` (with quotes), for TypeError it's `float() argument must be a string or a real number, not 'NoneType'`.
**Why it happens:** Python exception messages are designed for developers, not users.
**How to avoid:** Add a helper function that translates common exception patterns to friendly messages with a generic fallback.
**Warning signs:** Any row-level error in the dashboard failure table showing Python-style messages.

### Pitfall 5: Forgetting to Update Tests
**What goes wrong:** Existing tests assert on the old error message wording (e.g., `match="missing required columns"` in test_cdcms_preprocessor.py:371).
**Why it happens:** Changing error message strings breaks `pytest.raises(match=...)` assertions.
**How to avoid:** Update test assertions to match the new wording. The test at line 371 uses `match="missing required columns"` which still works with the new format since that substring is preserved.
**Warning signs:** Failing tests after changing error messages.

## Code Examples

### Fix 1: CDCMS Column Validation (cdcms_preprocessor.py:346-352)

```python
# BEFORE (line 346-352):
if missing_required:
    raise ValueError(
        f"CDCMS export is missing required columns: {missing_required}. "
        f"Found columns: {sorted(present)}. "
        f"Expected at least: {sorted(required)}. "
        "Make sure you're uploading the raw CDCMS export file."
    )

# AFTER:
if missing_required:
    # Log technical details for IT debugging
    logger.warning(
        "CDCMS missing required columns: %s. Found: %s",
        missing_required,
        sorted(present),
    )
    raise ValueError(
        f"Required columns missing: {', '.join(sorted(missing_required))} -- "
        "make sure you're uploading the raw CDCMS export"
    )
```

### Fix 2: CSV Importer Column Validation (csv_importer.py:269-273)

```python
# BEFORE (line 269-273):
if not found:
    raise ValueError(
        f"Missing address column. Expected '{address_col}' or one of "
        f"{alternatives}. Found columns: {list(df.columns)}"
    )

# AFTER:
if not found:
    logger.warning(
        "Missing address column '%s'. Found columns: %s",
        address_col,
        list(df.columns),
    )
    raise ValueError(
        f"Missing address column '{address_col}' -- "
        "make sure you're uploading the correct file format"
    )
```

### Fix 3: Row-Level Exception Translation (csv_importer.py:233-240)

```python
# BEFORE (line 233-237):
result.errors.append(
    RowError(
        row_number=row_num,
        column="",
        message=str(e),
        stage="validation",
    )
)

# AFTER:
result.errors.append(
    RowError(
        row_number=row_num,
        column="",
        message=_humanize_row_error(e),
        stage="validation",
    )
)

# New helper function:
def _humanize_row_error(exc: Exception) -> str:
    """Translate Python exceptions to office-friendly messages."""
    msg = str(exc)
    if isinstance(exc, ValueError):
        if "could not convert" in msg and "float" in msg:
            return "Invalid number value -- check for letters or symbols in numeric fields"
        if "could not convert" in msg:
            return "Unexpected value format -- check the cell contents"
        return f"Invalid value -- {msg}" if len(msg) < 60 else "Invalid value in this row"
    if isinstance(exc, KeyError):
        # KeyError str(e) is "'column_name'" with quotes
        col = msg.strip("'\"")
        return f"Missing required field '{col}' -- check your CSV has all required columns"
    if isinstance(exc, TypeError):
        return "Empty or invalid cell -- fill in required fields"
    return "Could not process this row -- check the data format"
```

### Fix 4: GEOCODING_REASON_MAP Update (main.py:82-89)

```python
# BEFORE:
GEOCODING_REASON_MAP: dict[str, str] = {
    "ZERO_RESULTS": "Address not recognized by Google Maps",
    "REQUEST_DENIED": "Geocoding service error (contact admin)",
    "OVER_QUERY_LIMIT": "Geocoding quota exceeded (try again later)",
    "OVER_DAILY_LIMIT": "Geocoding quota exceeded (try again later)",
    "INVALID_REQUEST": "Address could not be processed",
    "UNKNOWN_ERROR": "Geocoding service temporarily unavailable",
}

# AFTER:
GEOCODING_REASON_MAP: dict[str, str] = {
    "ZERO_RESULTS": "Address not found -- check spelling in CDCMS",
    "REQUEST_DENIED": "Geocoding service blocked -- contact IT",
    "OVER_QUERY_LIMIT": "Google Maps quota exceeded -- contact IT",
    "OVER_DAILY_LIMIT": "Google Maps quota exceeded -- contact IT",
    "INVALID_REQUEST": "Address could not be processed -- check for unusual characters",
    "UNKNOWN_ERROR": "Google Maps is temporarily unavailable -- try again in a few minutes",
}
```

### Fix 5: Geocoding Fallback (main.py:934)

```python
# BEFORE:
reason = GEOCODING_REASON_MAP.get(
    status, f"Geocoding failed ({status})"
)

# AFTER:
reason = GEOCODING_REASON_MAP.get(
    status, "Could not find this address -- try checking the spelling"
)
# Log the raw status for IT debugging
if status not in GEOCODING_REASON_MAP:
    logger.warning("Unmapped geocoding status '%s' for order %s", status, order.order_id)
```

### Fix 6: ValueError Catch in Upload Endpoint (main.py, around line 764)

```python
# BEFORE (no error handling for ValueError):
preprocessed_df = preprocess_cdcms(
    tmp_path,
    area_suffix=config.CDCMS_AREA_SUFFIX,
)

# AFTER (catch ValueError and convert to HTTPException):
try:
    preprocessed_df = preprocess_cdcms(
        tmp_path,
        area_suffix=config.CDCMS_AREA_SUFFIX,
    )
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))
```

Note: The same pattern applies to the standard CSV path. If `csv_importer._validate_columns()` raises a ValueError at line 270, it also propagates uncaught. The catch should cover both paths or be placed appropriately.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `{set}` in f-strings | `', '.join(sorted(set))` | This phase | Prevents Python set notation in error messages |
| `str(e)` passthrough | Pattern-match + translate | This phase | Prevents raw Python exception text reaching users |
| `f"Geocoding failed ({status})"` | Generic friendly fallback | This phase | Prevents raw API status codes reaching users |

## Open Questions

1. **Should csv_importer._validate_columns() ValueError also be caught in main.py?**
   - What we know: The standard CSV path (line 796) calls `importer.import_orders()` which calls `_validate_columns()`. If it raises ValueError, same 500 error problem.
   - What's unclear: Whether _validate_columns is ever reached in practice (it checks for address column, which is usually present)
   - Recommendation: Add the same ValueError catch around the non-CDCMS path for safety. It's a one-line addition.

2. **How many row-level error patterns exist in practice?**
   - What we know: The catch-all handles ValueError, KeyError, TypeError. Most rows either succeed or fail at address (pre-validated). The `_row_to_order_with_warnings` method is fairly defensive with defaults.
   - What's unclear: How often the catch-all fires in production
   - Recommendation: Translate the 3-4 most common patterns (float conversion, missing key, None type), use generic fallback for the rest. The helper function in Code Examples covers this.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest with pytest-asyncio |
| Config file | `pytest.ini` (asyncio_mode = auto) |
| Quick run command | `python -m pytest tests/core/data_import/ -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ERR-01 | CDCMS missing column error is plain English (no set notation) | unit | `python -m pytest tests/core/data_import/test_cdcms_preprocessor.py::TestValidation::test_missing_required_columns_raises -x` | Exists -- needs assertion update |
| ERR-01 | CSV importer missing column error is plain English (no list repr) | unit | `python -m pytest tests/core/data_import/test_csv_importer.py -x -k "missing"` | Needs new test |
| ERR-01 | Row-level exceptions produce friendly messages | unit | `python -m pytest tests/core/data_import/test_csv_importer.py -x -k "humanize"` | Needs new test |
| ERR-02 | GEOCODING_REASON_MAP entries use "problem -- fix action" format | unit | `python -m pytest tests/apps/kerala_delivery/api/test_api.py -x -k "geocod"` | Needs new test or inline check |
| ERR-02 | Fallback geocoding message is friendly (no raw status) | unit | Inline verification in GEOCODING_REASON_MAP test | Needs new test |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/core/data_import/ -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/core/data_import/test_cdcms_preprocessor.py::TestValidation::test_missing_required_columns_raises` -- update assertion to verify new message format (no set notation, has "-- " fix action)
- [ ] `tests/core/data_import/test_csv_importer.py` -- add test for missing address column error message format
- [ ] `tests/core/data_import/test_csv_importer.py` -- add test for `_humanize_row_error()` helper
- [ ] No new framework install needed -- pytest already configured

## Sources

### Primary (HIGH confidence)
- Direct code inspection of `core/data_import/cdcms_preprocessor.py` (lines 338-368)
- Direct code inspection of `core/data_import/csv_importer.py` (lines 225-243, 262-273)
- Direct code inspection of `apps/kerala_delivery/api/main.py` (lines 82-89, 736-797, 925-941)
- Direct code inspection of test files: `tests/core/data_import/test_cdcms_preprocessor.py`, `tests/core/data_import/test_csv_importer.py`
- CONTEXT.md with locked decisions from user discussion

### Secondary (MEDIUM confidence)
- None needed -- all findings are from direct code inspection

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new libraries; all changes are to existing Python files
- Architecture: HIGH - No architectural changes; existing error flow is correct, only message content changes
- Pitfalls: HIGH - All pitfalls identified from direct code reading; the uncaught ValueError is verified by examining the try/except structure

**Research date:** 2026-03-05
**Valid until:** Indefinite -- this is a one-time string formatting fix, not dependent on external library versions
