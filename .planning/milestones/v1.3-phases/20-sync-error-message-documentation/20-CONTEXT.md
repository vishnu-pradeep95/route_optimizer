# Phase 20: Sync Error Message Documentation - Context

**Gathered:** 2026-03-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Update CSV_FORMAT.md and DEPLOY.md so that every documented error message matches the actual humanized output produced by the code after Phase 17. This is a documentation sync -- no code changes, no new error messages, no new documentation pages.

</domain>

<decisions>
## Implementation Decisions

### Message fidelity
- CSV_FORMAT.md "What You See" column must show **exact code strings verbatim** -- employee matches screen output to doc
- Keep existing 3-column table structure (What You See | Why It Happened | How to Fix It) across all error sections
- Include the geocoding fallback message ("Could not find this address -- try checking the spelling") as a 7th geocoding row
- Keep and verify the "Geocoding service not configured (missing API key)" entry -- check actual code message and update to match

### Row-level errors
- Document all 5 _humanize_row_error() patterns plus the catch-all fallback (6 total rows in "During Processing" table)
- Keep row-level errors in the existing "During Processing" table -- no subsections
- Use concrete examples for dynamic messages (e.g., "Missing required field 'order_id'" not "Missing required field '{column_name}'")

### Traceability
- Create a separate error mapping file in `.planning/phases/20-sync-error-message-documentation/` as a verification artifact
- 3-column format: Message | Code Location | Status (verified/stale)
- CSV_FORMAT.md stays clean for office staff -- no code references in user-facing doc

### DEPLOY.md troubleshooting
- Update all 5 troubleshooting sections to use humanized messages (not just the set notation one)
- Keep code blocks for error display -- visually distinct from instructions
- Remove the "File not found" (FileNotFoundError) section -- stale, dashboard uses drag-and-drop upload
- Add cross-link to CSV_FORMAT.md: "For a complete list of error messages, see CSV_FORMAT.md > What Can Go Wrong"

### Claude's Discretion
- Exact wording of "Why It Happened" and "How to Fix It" columns (as long as "What You See" is verbatim)
- Error mapping file name and internal structure
- Whether to reorder troubleshooting sections in DEPLOY.md for better flow after removing "File not found"

</decisions>

<specifics>
## Specific Ideas

- Phase 17 established "problem -- fix action" pattern with double dash separator -- all code messages follow this
- The 8 stale messages identified in audit: 6 geocoding messages in CSV_FORMAT.md + CDCMS column error in CSV_FORMAT.md + DEPLOY.md set notation example
- CSV_FORMAT.md "Geocoding service not configured" may come from a separate code path (not GEOCODING_REASON_MAP) -- verify against actual code

</specifics>

<code_context>
## Existing Code Insights

### Error Message Sources (to sync FROM)
- `main.py:82-89`: GEOCODING_REASON_MAP with 6 named entries (ZERO_RESULTS, REQUEST_DENIED, OVER_QUERY_LIMIT, OVER_DAILY_LIMIT, INVALID_REQUEST, UNKNOWN_ERROR)
- `main.py:934`: Fallback "Could not find this address -- try checking the spelling"
- `cdcms_preprocessor.py:352-354`: "Required columns missing: {cols} -- make sure you're uploading the raw CDCMS export"
- `cdcms_preprocessor.py:370-372`: "The 'ConsumerAddress' column exists but all values are empty. Check the file format."
- `csv_importer.py:300-302`: "Missing address column '{col}' -- make sure you're uploading the correct file format"
- `csv_importer.py:108-124`: _humanize_row_error() with 5 patterns + fallback
- `main.py:720-746`: File type, content type, and file size HTTPExceptions

### Documentation Files (to sync TO)
- `CSV_FORMAT.md:150-189`: "What Can Go Wrong" section with 3 error tables
- `DEPLOY.md:201-243`: Troubleshooting section with 5 error subsections

### Established Patterns
- Error messages flow: code raises ValueError/HTTPException -> API response -> dashboard displays to user
- CSV_FORMAT.md uses 3-column tables per error stage (file-level, row-level, geocoding)
- DEPLOY.md uses H3 headings + code blocks + "Fix:" paragraphs

</code_context>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 20-sync-error-message-documentation*
*Context gathered: 2026-03-07*
