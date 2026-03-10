# Phase 04: Documentation Accuracy Refresh - Context

**Gathered:** 2026-03-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Update ERROR-MAP.md line number references that drifted after Phase 02 added ~140 lines to main.py, and remove stale plan/ directory references from FleetManagement.tsx comments. Pure mechanical fixes — no new content or features.

</domain>

<decisions>
## Implementation Decisions

### Line Number Updates
- Re-verify every `main.py:NNN` line reference in docs/ERROR-MAP.md against the actual current source
- Update each reference to the correct current line number
- Mark all entries as "verified" with current date

### Stale Reference Removal
- Remove 2 `plan/kerala_delivery_route_system_design.md` references in FleetManagement.tsx comments (lines 53, 74)
- Replace with accurate source references or remove entirely if the comments add no value

### Claude's Discretion
- Whether to replace stale plan/ references with new doc paths or simply remove the comments
- Exact verification approach for line numbers

</decisions>

<specifics>
## Specific Ideas

No specific requirements — straightforward documentation accuracy fixes.

</specifics>

<code_context>
## Existing Code Insights

### Files to Update
- `docs/ERROR-MAP.md`: 25 entries mapping error messages to source code locations (9 file-level + 9 row-level + 7 geocoding). Line references point to `apps/kerala_delivery/api/main.py` which grew ~140 lines from Phase 02 error handling additions.
- `apps/kerala_delivery/dashboard/src/pages/FleetManagement.tsx`: Lines 53 and 74 reference `plan/kerala_delivery_route_system_design.md` which no longer exists (deleted in Phase 01 documentation restructure).

### Integration Points
- ERROR-MAP.md is a developer-audience traceability artifact created in Phase 20 (v1.3)
- FleetManagement.tsx comments are JSDoc-style documentation for vehicle constants

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 04-documentation-accuracy-refresh*
*Context gathered: 2026-03-10*
