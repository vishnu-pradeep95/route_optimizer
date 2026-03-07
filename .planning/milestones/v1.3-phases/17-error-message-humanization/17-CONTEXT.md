# Phase 17: Error Message Humanization - Context

**Gathered:** 2026-03-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace Python internals (set notation, list repr, raw API codes) with plain-English error messages in upload validation and geocoding error flows. The office employee should never see Python tracebacks, `{set}` notation, or raw Google API status codes.

</domain>

<decisions>
## Implementation Decisions

### Error message style
- Every error message follows "Problem -- fix action" pattern
- Example: "Address not found -- check spelling in CDCMS"
- Example: "Google Maps quota exceeded -- contact IT"
- Matches the tone established in success criteria

### Missing column errors (ERR-01)
- Replace Python set notation `{'OrderNo', 'ConsumerAddress'}` with plain English
- Format: "Required columns missing: OrderNo, ConsumerAddress -- make sure you're uploading the raw CDCMS export"
- Do NOT show "Found columns: [...]" in user-facing message -- that's noise for office staff
- Log found columns at WARNING level server-side for IT debugging

### Geocoding errors (ERR-02)
- Update all 6 entries in `GEOCODING_REASON_MAP` to match success criteria style (problem + fix action)
- Specific phrasing from success criteria:
  - ZERO_RESULTS: "Address not found -- check spelling in CDCMS"
  - OVER_DAILY_LIMIT: "Google Maps quota exceeded -- contact IT"
- Extend same pattern to remaining 4 codes (REQUEST_DENIED, OVER_QUERY_LIMIT, INVALID_REQUEST, UNKNOWN_ERROR)

### Unknown error fallback
- For unexpected/unmapped geocoding status codes: "Could not find this address -- try checking the spelling"
- No raw status codes exposed to user -- IT checks server logs
- Replace current fallback `f"Geocoding failed ({status})"` with the generic friendly message

### Row-level CSV errors
- Claude translates common Python exception patterns to friendly messages (e.g., float conversion → "Invalid weight value", KeyError → "Missing required field")
- Generic fallback for unrecognized patterns
- Claude has discretion on which patterns to translate and fallback wording

### Claude's Discretion
- Exact contact phrasing per error context ("contact IT" vs "contact admin" -- Claude picks what fits)
- Which row-level error patterns to translate vs use generic fallback
- Whether to add a catch-all error wrapper in the upload endpoint for unexpected exceptions

</decisions>

<specifics>
## Specific Ideas

- Success criteria gives exact phrasing for two errors -- implement those literally, extend the pattern to all others
- Phase 15 CSV_FORMAT.md already documents rejection reasons in user-friendly language -- error messages should be consistent with that document's tone

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `GEOCODING_REASON_MAP` (main.py:82-89): Already maps 6 API codes to messages -- needs wording update, not structural change
- `ImportFailure` Pydantic model (main.py:584): Structured error with row_number, address_snippet, reason, stage -- no model changes needed
- Dashboard `ImportSummary` component (UploadRoutes.tsx): Already renders failure table with reason column -- no frontend changes needed

### Established Patterns
- Error messages flow: Python exception/API code → `ImportFailure.reason` string → JSON response → dashboard table
- Server-side logging at WARNING/ERROR level for raw details, user sees friendly `reason` field only
- `HTTPException` for hard failures (wrong file type, too large), `ImportFailure` list for per-row issues

### Integration Points
- `cdcms_preprocessor.py:_validate_cdcms_columns()` -- primary set notation offender (line 347-352)
- `csv_importer.py:_validate_columns()` -- list repr offender (line 270-272)
- `csv_importer.py:import_orders()` -- catches ValueError/KeyError/TypeError, uses `str(e)` as message (line 233-237)
- `main.py:GEOCODING_REASON_MAP` -- geocoding code-to-message translation (line 82-89)
- `main.py` fallback: `f"Geocoding failed ({status})"` (line 934) -- leaks raw status codes

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 17-error-message-humanization*
*Context gathered: 2026-03-05*
