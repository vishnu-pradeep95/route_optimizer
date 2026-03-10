# Phase 04: Documentation Accuracy Refresh - Research

**Researched:** 2026-03-10
**Domain:** Documentation accuracy, code comment maintenance
**Confidence:** HIGH

## Summary

This phase addresses two categories of documentation drift: (1) stale line-number references in `docs/ERROR-MAP.md` caused by Phase 02 adding ~140 lines to `main.py`, and (2) stale `plan/` directory references in source code comments pointing to a deleted file.

The ERROR-MAP.md drift is confined to 5 entries referencing `apps/kerala_delivery/api/main.py` -- the line numbers shifted by approximately 140-160 lines. The 20 entries referencing `core/` files (csv_importer.py, cdcms_preprocessor.py) are UNCHANGED and still accurate.

The stale `plan/` reference scope is LARGER than CONTEXT.md describes. CONTEXT.md identifies 2 references in FleetManagement.tsx (lines 53, 74), but there are actually 8 stale references across 6 source files. All 8 reference `plan/kerala_delivery_route_system_design.md` or `plan/session-journal.md`, both of which were deleted in Phase 01.

**Primary recommendation:** Update all 5 drifted line numbers in ERROR-MAP.md and clean all 8 stale plan/ references across 6 source files in a single plan.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Re-verify every `main.py:NNN` line reference in docs/ERROR-MAP.md against the actual current source
- Update each reference to the correct current line number
- Mark all entries as "verified" with current date
- Remove 2 `plan/kerala_delivery_route_system_design.md` references in FleetManagement.tsx comments (lines 53, 74)
- Replace with accurate source references or remove entirely if the comments add no value

### Claude's Discretion
- Whether to replace stale plan/ references with new doc paths or simply remove the comments
- Exact verification approach for line numbers

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DOC-VALIDATE | Validate content against codebase | ERROR-MAP.md line number drift analysis below provides exact old-to-new mappings for all 25 entries; 5 need updates, 20 are still correct |
| DOC-CLEANUP | Delete plan/, clean .github/ refs | Phase 01 cleaned .github/ and deleted plan/; 8 stale plan/ references remain in source code comments across 6 files (FleetManagement.tsx, main.py, config.py, init.sql, repository.py, licensing/__init__.py) |
</phase_requirements>

## ERROR-MAP.md Line Number Drift Analysis

### File-Level Errors (main.py references)

All 5 main.py entries have drifted. Here are the exact corrections:

| # | Message (abbreviated) | ERROR-MAP.md Says | Actual Current Line | Delta |
|---|----------------------|-------------------|---------------------|-------|
| 1 | "Unsupported file type (.pdf)..." | `main.py:722` | `main.py:863` | +141 |
| 2 | "Unexpected content type..." | `main.py:730` | `main.py:874` | +144 |
| 3 | "File too large..." | `main.py:746` | `main.py:893` | +147 |
| 4 | "No 'Allocated-Printed' orders..." | `main.py:771-772` | `main.py:921` | +150 (now single line) |
| 5 | "No valid orders found..." | `main.py:851` | `main.py:1008` | +157 |

### File-Level Errors (core/ references) -- NO DRIFT

All 4 core/ file entries are still accurate:

| # | Message (abbreviated) | ERROR-MAP.md Says | Verified |
|---|----------------------|-------------------|----------|
| 6 | "Missing address column..." | `csv_importer.py:301-302` | CORRECT (lines 301-302) |
| 7 | "Required columns missing..." | `cdcms_preprocessor.py:352-354` | CORRECT (lines 352-354) |
| 8 | "The 'ConsumerAddress' column...empty" | `cdcms_preprocessor.py:370-372` | CORRECT (lines 370-372) |
| 9 | "Unsupported file format: .txt" | `csv_importer.py:279` | CORRECT (line 279) |

### Row-Level Errors (core/ references) -- NO DRIFT

All 9 row-level entries are still accurate:

| # | Message (abbreviated) | ERROR-MAP.md Says | Verified |
|---|----------------------|-------------------|----------|
| 10 | "Empty address..." | `csv_importer.py:221` | CORRECT (line 221) |
| 11 | "Duplicate order_id..." | `csv_importer.py:236-237` | CORRECT (lines 236-237) |
| 12 | "Invalid weight..." | `csv_importer.py:395-396` | CORRECT (lines 395-396) |
| 13 | "Invalid number value..." | `csv_importer.py:115` | CORRECT (line 115) |
| 14 | "Unexpected value format..." | `csv_importer.py:117` | CORRECT (line 117) |
| 15 | "Invalid value in this row" | `csv_importer.py:118` | CORRECT (line 118) |
| 16 | "Missing required field..." | `csv_importer.py:121` | CORRECT (line 121) |
| 17 | "Empty or invalid cell..." | `csv_importer.py:123` | CORRECT (line 123) |
| 18 | "Could not process this row..." | `csv_importer.py:124` | CORRECT (line 124) |

### Geocoding Errors (main.py references)

All 7 geocoding entries have drifted:

| # | Message (abbreviated) | ERROR-MAP.md Says | Actual Current Line | Delta |
|---|----------------------|-------------------|---------------------|-------|
| 19 | "Address not found..." | `main.py:83` (GEOCODING_REASON_MAP, ZERO_RESULTS) | `main.py:94` | +11 |
| 20 | "Geocoding service blocked..." | `main.py:84` (REQUEST_DENIED) | `main.py:95` | +11 |
| 21 | "Google Maps quota exceeded..." | `main.py:85-86` (OVER_QUERY_LIMIT, OVER_DAILY_LIMIT) | `main.py:96-97` | +11 |
| 22 | "Address could not be processed..." | `main.py:87` (INVALID_REQUEST) | `main.py:98` | +11 |
| 23 | "Google Maps is temporarily unavailable..." | `main.py:88` (UNKNOWN_ERROR) | `main.py:99` | +11 |
| 24 | "Geocoding service not configured..." | `main.py:959` | `main.py:1125` | +166 |
| 25 | "Could not find this address..." | `main.py:934` (fallback) | `main.py:1100` | +166 |

**Key insight:** There are two distinct drift amounts:
- GEOCODING_REASON_MAP dict (lines 93-100): shifted by +11 lines (early in file, less affected)
- Upload/processing code (lines 860-1125): shifted by +141 to +166 lines (bulk of Phase 02 additions above this code)

### Total: 12 entries need line number updates, 13 entries are correct as-is.

## Stale plan/ Directory References -- Full Inventory

CONTEXT.md identifies 2 references (FleetManagement.tsx lines 53, 74). Research found 8 total across 6 files:

| # | File | Line | Current Reference | Context |
|---|------|------|-------------------|---------|
| 1 | `apps/kerala_delivery/dashboard/src/pages/FleetManagement.tsx` | 53 | `plan/kerala_delivery_route_system_design.md, Section 3` | JSDoc for DEFAULT_MAX_WEIGHT_KG |
| 2 | `apps/kerala_delivery/dashboard/src/pages/FleetManagement.tsx` | 74 | `plan/kerala_delivery_route_system_design.md, Safety Constraints` | JSDoc for MAX_SPEED_LIMIT_KMH |
| 3 | `apps/kerala_delivery/api/main.py` | 490 | `plan/session-journal.md (OPEN: C1 auth discussion)` | Comment about API key auth |
| 4 | `apps/kerala_delivery/api/main.py` | 1018 | `plan/kerala_delivery_route_system_design.md (Safety Constraints)` | Comment about min delivery window |
| 5 | `apps/kerala_delivery/config.py` | 11 | `plan/kerala_delivery_route_system_design.md` | Module docstring |
| 6 | `apps/kerala_delivery/config.py` | 139 | `plan/kerala_delivery_route_system_design.md, Section 10 (GPS drift risk)` | Comment for GPS_ACCURACY_THRESHOLD_M |
| 7 | `core/licensing/__init__.py` | 30 | `plan/kerala_delivery_route_system_design.md, Phase 4C` | Module docstring |
| 8 | `core/database/repository.py` | 424 | `plan/kerala_delivery_route_system_design.md, Section 10 (GPS drift risk)` | Comment for GPS drift filter |
| 9 | `infra/postgres/init.sql` | 8 | `plan/kerala_delivery_route_system_design.md, Section 5` | Schema design reference |

### Recommended Replacement Strategy

The deleted `plan/kerala_delivery_route_system_design.md` was replaced by `.planning/PROJECT.md` (per Phase 01-01 decisions). However, `.planning/` is a process artifact, not a stable source reference for code comments. The better approach:

- **Remove the `Source:` / `See:` lines entirely** when the comment already contains self-explanatory context (e.g., FleetManagement.tsx lines 53, 74 already explain the 90% safety factor and Kerala MVD directive in the surrounding comment text)
- **Replace with `apps/kerala_delivery/config.py`** when referencing config values that are the canonical source (e.g., VEHICLE_MAX_WEIGHT_KG, GPS_ACCURACY_THRESHOLD_M)
- **Remove `plan/session-journal.md` reference** (main.py:490) -- the C1 auth discussion is historical context that no longer needs a source link
- **For init.sql** -- remove the design reference since the schema IS the implementation

**Confidence: HIGH** -- all references verified by direct source inspection.

## Architecture Patterns

### Pattern: Traceability Map Maintenance

ERROR-MAP.md uses the pattern: `file_path:line_number` (or `file_path:line_start-line_end` for spans).

Rules for updating:
1. Use the line where the user-facing string appears, not the surrounding function
2. For multiline strings, reference the line range containing the complete message
3. For dict entries (GEOCODING_REASON_MAP), reference the specific dict key line with the dict name in parentheses
4. Update the "Verified" date in the header

### Anti-Patterns to Avoid
- **Referencing process docs from source code:** `.planning/` paths change per-milestone. Source code comments should reference stable artifacts (other source files, `docs/`, external standards).
- **Leaving "verified" dates stale:** If you update line numbers, the "Verified" date must also update to the current date.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Finding current line numbers | Manual file reading | grep -n with exact strings | Precise, reproducible, no counting errors |

## Common Pitfalls

### Pitfall 1: Partial plan/ Cleanup
**What goes wrong:** CONTEXT.md only identified 2 of 9 stale plan/ references. Cleaning only FleetManagement.tsx leaves 7 broken references in other files.
**Why it happens:** Phase 01 scoped its plan/ cleanup to .github/ and docs/, not source code comments.
**How to avoid:** Use grep to find ALL occurrences before starting.
**Warning signs:** Any remaining `plan/` references in source code after the phase.

### Pitfall 2: Message Text Mismatch
**What goes wrong:** The error messages in ERROR-MAP.md use slightly different wording than the actual source (e.g., ".pdf" vs dynamic extension, "15.2 MB" vs format string).
**Why it happens:** ERROR-MAP.md was created with example values; actual code uses format strings with dynamic values.
**How to avoid:** The ERROR-MAP.md entries are representative examples, not exact strings. Match by the static portion of the message.
**Warning signs:** ERROR-MAP.md entry #4 previously spanned lines 771-772 but now fits on a single line (921). Update the line reference to just `main.py:921`.

### Pitfall 3: Verified Date Without Actual Verification
**What goes wrong:** Updating the "Verified" date in ERROR-MAP.md header without re-checking every entry.
**Why it happens:** It's tempting to only fix the drifted entries and assume the rest are fine.
**How to avoid:** This research has verified ALL 25 entries. The planner can confidently mark the new date.

## Code Examples

### ERROR-MAP.md Entry Format
```markdown
| "Unsupported file type (.pdf). Accepted: .csv, .xls, .xlsx" | `apps/kerala_delivery/api/main.py:863` | verified |
```

### Comment Cleanup (FleetManagement.tsx example)
Before:
```typescript
/**
 * Default max payload in kg for a Piaggio Ape Xtra LDX.
 * 446 kg = 496 kg rated payload x 0.9 safety factor.
 * Source: plan/kerala_delivery_route_system_design.md, Section 3.
 * Also: apps/kerala_delivery/config.py VEHICLE_MAX_WEIGHT_KG
 */
```

After (remove stale source, keep the config.py cross-reference):
```typescript
/**
 * Default max payload in kg for a Piaggio Ape Xtra LDX.
 * 446 kg = 496 kg rated payload x 0.9 safety factor.
 * See: apps/kerala_delivery/config.py VEHICLE_MAX_WEIGHT_KG
 */
```

## Open Questions

None. All line numbers verified, all stale references inventoried. This is a fully mechanical phase.

## Sources

### Primary (HIGH confidence)
- Direct source file inspection via grep -n and Read tool for all 25 ERROR-MAP.md entries
- Direct grep for all `plan/kerala_delivery_route_system_design.md` and `plan/session-journal.md` references across the entire codebase
- Phase 01-01 SUMMARY confirming `plan/` directory deletion and `.planning/PROJECT.md` as replacement

## Metadata

**Confidence breakdown:**
- ERROR-MAP.md line numbers: HIGH -- every entry verified by reading the actual source files
- Stale plan/ references: HIGH -- exhaustive grep across entire codebase, all 9 occurrences catalogued
- Replacement strategy: HIGH -- follows Phase 01 precedent for plan/ reference cleanup

**Research date:** 2026-03-10
**Valid until:** Indefinite (line numbers only shift on code changes to the referenced files)
