# Phase 2: Error Handling Infrastructure - Context

**Gathered:** 2026-03-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Build structured error infrastructure across the API and frontend — replacing ad-hoc `{"detail": "..."}` HTTPException responses with a consistent ErrorResponse model, request ID tracing, retry logic for transient failures, startup health gates, and frontend error differentiation with proper UI treatment. Driver PWA is out of scope for this phase (API + Dashboard only).

</domain>

<decisions>
## Implementation Decisions

### Error Response Structure
- **Tiered by role**: Response includes both `user_message` (plain-English "Problem — fix action") and `technical_message`. Dashboard shows `user_message` by default, with a "Show details" toggle for advanced users revealing error_code, request_id, timestamp
- **Namespaced error codes**: Grouped by subsystem — `GEOCODING_FAILED`, `UPLOAD_INVALID_FORMAT`, `OPTIMIZER_TIMEOUT`, `AUTH_KEY_MISSING`, etc. Maps cleanly to ERROR-MAP.md
- **Partial success uses HTTP 200 with warnings**: Not 207. Response includes `success: true`, `imported` count, `total` count, and `warnings[]` array with per-row details. Keeps frontend success path simple
- **Help URL field included**: Each error code maps to a section in docs/ files (ERROR-MAP.md, GOOGLE-MAPS.md, etc.). Dashboard renders as clickable help link

### Frontend Error Presentation
- **CSV upload errors**: Inline table showing failed rows with row number, field, and reason. Matches existing import summary UI pattern. Include "Download Error Report" and "Upload Fixed CSV" actions
- **Network/server errors**: Contextual banner at top of affected section. Auto-dismisses when connection restores. Includes [Retry] button
- **Color-coded by severity**: Red for failures (upload rejected), amber for warnings (partial import), green for success, blue for info (retry in progress). Matches existing v1.1 status badge color system
- **Detail toggle**: Claude's Discretion on collapse vs modal — but whichever is chosen MUST have Playwright E2E test coverage
- **HARD REQUIREMENT**: Every error UI element must be thoroughly tested with Playwright E2E tests. No half-baked UI components. All spacing and alignment must be correct

### Retry & Degradation
- **Retry scope**: Claude's Discretion on which services get retry logic (geocoding, OSRM, VROOM, PostgreSQL) — pick based on transient vs permanent failure likelihood
- **Service-specific error messages**: When external service is down, tell user exactly what's broken with actionable fix. Follow "Problem — fix action" pattern from v1.3
- **HARD REQUIREMENT — Startup health gates**: API must check PostgreSQL, OSRM, VROOM on startup. Block until healthy (60s timeout). If timeout, start anyway but return 503 with specific service name. This is non-negotiable
- **Per-service health endpoint**: `GET /health` returns per-service status (postgresql, osrm, vroom, google_api) with overall status (healthy/degraded/unhealthy) and uptime

### Request Tracing
- **Short UUID format**: First 8 chars of UUID (e.g., "abc12def"). Easy to read over the phone for support
- **Visible in error details only**: Request ID appears in the "Show details" toggle of error messages. Not shown on success responses. Employee can read it to support: "My error ID is abc12def"
- **Every log line includes request ID**: Middleware injects request_id into logging context. Format: `[abc12def] INFO  message`. Enables grep-based log correlation
- **Scope: API + Dashboard only**: Driver PWA does not get request tracing (too simple, drivers won't use it)

### Claude's Discretion
- Detail toggle implementation (DaisyUI collapse vs modal)
- Which services get retry logic and retry counts/backoff strategy
- Exact ErrorResponse Pydantic model field names
- Compression/batching of warning arrays for large imports

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `apps/kerala_delivery/api/main.py`: ~30 HTTPException calls to migrate to ErrorResponse model
- DaisyUI alert components (`tw:alert`, `tw:alert-error`, `tw:alert-warning`, `tw:alert-success`, `tw:alert-info`) available for color-coded errors
- Existing import summary UI in UploadRoutes.tsx — extend with error table
- `docs/ERROR-MAP.md`: 25 error messages already traced to source — use as help_url targets
- Status badge color system from v1.1 (green/amber/red) — extend to error severity

### Established Patterns
- "Problem — fix action" error pattern (v1.3 Phase 17) — maintain for all user-facing messages
- Module-level `logger = logging.getLogger(__name__)` — add request_id to logging context
- FastAPI middleware pattern available for request ID injection
- `slowapi` already wired (limiter initialized, exception handler registered) — not enforced yet

### Integration Points
- `apps/kerala_delivery/api/main.py` lifespan handler — add startup health checks
- `apps/kerala_delivery/dashboard/src/lib/api.ts` — add error type differentiation
- `apps/kerala_delivery/dashboard/src/pages/UploadRoutes.tsx` — add inline error table
- `GET /health` endpoint — integrate with existing `start-daily.sh` health polling
- Docker Compose healthcheck — align with new `/health` response format

</code_context>

<specifics>
## Specific Ideas

- Startup health gate sequence: PostgreSQL first, then OSRM, then VROOM. All must be healthy before accepting requests
- Error table for CSV upload should match the preview: row number | field | reason columns
- Server error banner should auto-dismiss when connection restores (not require manual close)
- Request ID "abc12def" format chosen specifically because office employees may read it over the phone to support
- Every error UI component must have Playwright E2E test proving it renders correctly, displays correct content, and responds to user interaction

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-error-handling-infrastructure*
*Context gathered: 2026-03-09*
