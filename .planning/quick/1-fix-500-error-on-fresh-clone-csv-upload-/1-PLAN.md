---
phase: quick-fix
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - apps/kerala_delivery/api/main.py
  - scripts/reset.sh
autonomous: true
must_haves:
  truths:
    - "CSV upload on a fresh clone (OSRM/VROOM not ready) returns a clear error message, not a 500"
    - "Any unhandled exception in the upload endpoint returns a structured JSON error, not a stack trace"
    - "scripts/reset.sh is tracked in git"
  artifacts:
    - path: "apps/kerala_delivery/api/main.py"
      provides: "Robust exception handling in upload_and_optimize endpoint"
      contains: "httpx.ConnectError"
    - path: "scripts/reset.sh"
      provides: "Reset script tracked in version control"
  key_links:
    - from: "apps/kerala_delivery/api/main.py"
      to: "core/optimizer/vroom_adapter.py"
      via: "httpx exceptions propagating from VROOM adapter"
      pattern: "httpx\\.(ConnectError|TimeoutException)"
---

<objective>
Fix the 500 Internal Server Error that occurs when uploading a CSV on a fresh clone where OSRM/VROOM services are not yet ready, and track the reset script in git.

Purpose: On a fresh clone, OSRM data download takes 15+ minutes. The upload endpoint only catches `ValueError`, so any `httpx.ConnectError` from the VROOM adapter or `SQLAlchemy` connection error propagates as an opaque 500 error. Users need an actionable message explaining what is happening.

Output: Patched upload endpoint with comprehensive error handling; reset script tracked in git.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@apps/kerala_delivery/api/main.py
@core/optimizer/vroom_adapter.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add comprehensive exception handling to upload endpoint</name>
  <files>apps/kerala_delivery/api/main.py</files>
  <action>
In the `upload_and_optimize` endpoint (line 702-1127), expand the `except` block at line 1114 to catch additional exception types. Currently only `ValueError` is caught.

Add these exception handlers BETWEEN the existing `except ValueError` (line 1114) and the `finally` block (line 1119):

1. **httpx connection/timeout errors** (VROOM/OSRM unreachable):
   ```python
   except httpx.ConnectError as e:
       logger.error("VROOM/OSRM connection failed during upload: %s", e)
       raise HTTPException(
           status_code=503,
           detail=(
               "Route optimizer is not ready yet. "
               "OSRM may still be downloading map data (this takes ~15 minutes on first run). "
               "Please wait and try again."
           ),
       )
   except httpx.TimeoutException as e:
       logger.error("VROOM/OSRM timed out during upload: %s", e)
       raise HTTPException(
           status_code=503,
           detail=(
               "Route optimizer timed out. "
               "OSRM may still be processing map data. "
               "Please wait a few minutes and try again."
           ),
       )
   ```

2. **httpx.HTTPStatusError** (VROOM returned non-200, e.g. during startup):
   ```python
   except httpx.HTTPStatusError as e:
       logger.error("VROOM returned error %d: %s", e.response.status_code, e.response.text[:300])
       raise HTTPException(
           status_code=502,
           detail=(
               f"Route optimizer returned an error (HTTP {e.response.status_code}). "
               "This may indicate OSRM is still starting up. Please try again in a few minutes."
           ),
       )
   ```

3. **General catch-all** (any other unexpected exception):
   ```python
   except Exception as e:
       logger.exception("Unexpected error during upload: %s", e)
       raise HTTPException(
           status_code=500,
           detail=(
               "An unexpected error occurred while processing your upload. "
               "Please check that all services are running and try again. "
               f"Error: {type(e).__name__}: {e}"
           ),
       )
   ```

Also add `import httpx` at the top of the file (in the imports section, around line 14-30). Place it with the third-party imports, after the fastapi/pydantic imports block.

The order of except clauses MUST be: ValueError (existing), httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError, Exception (most general last).
  </action>
  <verify>
    <automated>cd /home/vishnu/projects/routing_opt && python -c "import ast; ast.parse(open('apps/kerala_delivery/api/main.py').read()); print('Syntax OK')" && grep -c "httpx.ConnectError\|httpx.TimeoutException\|httpx.HTTPStatusError" apps/kerala_delivery/api/main.py</automated>
  </verify>
  <done>
    - The upload endpoint catches httpx.ConnectError and returns 503 with "optimizer is not ready yet" message
    - The upload endpoint catches httpx.TimeoutException and returns 503 with timeout message
    - The upload endpoint catches httpx.HTTPStatusError and returns 502 with VROOM error details
    - A general Exception catch-all returns 500 with the error type and message (no raw stack trace to client)
    - All exceptions are logged with logger.error/logger.exception before raising HTTPException
    - `import httpx` is present in the imports section
    - File parses without syntax errors
  </done>
</task>

<task type="auto">
  <name>Task 2: Track reset script in git and rebuild API container</name>
  <files>scripts/reset.sh</files>
  <action>
Two small items:

1. Run `git add scripts/reset.sh` to stage the untracked reset script for the next commit. This file is already complete and correct -- it just needs to be tracked.

2. After the main.py changes from Task 1, rebuild the API Docker container so the fix takes effect:
   ```bash
   docker compose build api && docker compose up -d --no-deps api
   ```

3. Verify the API is healthy after restart:
   ```bash
   curl -s http://localhost:8000/health | python3 -m json.tool
   ```
  </action>
  <verify>
    <automated>cd /home/vishnu/projects/routing_opt && git ls-files scripts/reset.sh | grep -q reset.sh && echo "reset.sh tracked" || echo "reset.sh NOT tracked"</automated>
  </verify>
  <done>
    - scripts/reset.sh is staged/tracked in git
    - API container rebuilt with the new exception handling code
    - /health endpoint returns 200
  </done>
</task>

</tasks>

<verification>
1. `python -c "import ast; ast.parse(open('apps/kerala_delivery/api/main.py').read())"` -- syntax valid
2. `grep "httpx.ConnectError" apps/kerala_delivery/api/main.py` -- new handler present
3. `grep "httpx.TimeoutException" apps/kerala_delivery/api/main.py` -- timeout handler present
4. `grep "except Exception" apps/kerala_delivery/api/main.py` -- catch-all present
5. `git ls-files scripts/reset.sh` -- tracked in git
6. `curl -s http://localhost:8000/health` -- API responds after rebuild
</verification>

<success_criteria>
- Uploading a CSV when VROOM/OSRM is unreachable returns HTTP 503 with a clear message mentioning "15 minutes on first run"
- Any unhandled exception returns a structured JSON error (not a raw traceback)
- All new exception handlers log before raising HTTPException
- scripts/reset.sh is tracked in git
- API container is rebuilt and healthy
</success_criteria>

<output>
After completion, create `.planning/quick/1-fix-500-error-on-fresh-clone-csv-upload-/1-SUMMARY.md`
</output>
