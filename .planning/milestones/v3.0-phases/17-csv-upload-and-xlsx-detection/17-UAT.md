---
status: complete
phase: 17-csv-upload-and-xlsx-detection
source: 17-01-SUMMARY.md, 17-02-SUMMARY.md, 17-03-SUMMARY.md
started: 2026-03-13T22:10:00Z
updated: 2026-03-13T22:45:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running server/service. Start the Docker stack from scratch with `docker compose up -d`. Server boots without errors, database migrations complete, and `GET /health` returns 200 with live data.
result: pass

### 2. Upload .xlsx CDCMS File
expected: From the dashboard Upload page, select a .xlsx file (CDCMS export format). The file is accepted and parsed successfully — no format detection errors. The UI transitions from the upload drop zone to a driver preview screen.
result: pass

### 3. Driver Preview Table
expected: After uploading, a driver preview panel appears showing a table with columns: checkbox, driver name, order count, and status badge. Each driver has a colored badge — green for "existing", amber for "matched", blue for "new", purple for "reactivated". A stats bar above the table shows total drivers and order count.
result: pass

### 4. Driver Selection Checkboxes
expected: All drivers are selected by default. Clicking a checkbox deselects that driver. A "Select All / Deselect All" toggle works correctly. The stats bar updates to reflect only selected drivers.
result: issue
reported: "Allocation Pending appears as a driver name with 3 orders. It's a CDCMS placeholder meaning no driver assigned — should be filtered out in preprocessor, not shown in preview or geocoded."
severity: major

### 5. Process Selected Drivers
expected: After selecting/deselecting drivers, clicking the process button triggers geocoding and optimization for only the selected drivers' orders. Progress indicators show during processing. On success, routes/results are displayed.
result: issue
reported: "Process Selected button size/alignment is off. After clicking, only a spinning circle shows — no indication of what's happening. Need a collapsible progress window showing real-time status (which step, how many orders geocoded, etc.) so operators know it's working."
severity: major

### 6. Fuzzy-Matched Driver Shows Amber Badge
expected: If a driver name in the uploaded file fuzzy-matches an existing driver in the database (e.g., slight spelling difference), that driver's status badge in the preview is amber "matched" — NOT green "existing".
result: skipped
reason: Cannot produce a true fuzzy match with current test data (same file = exact match). Unit tests verified the code fix. Second upload showed all drivers as "Matched" with 100% match score and match details, confirming the status display works.

### 7. Back Button from Preview
expected: From the driver preview screen, clicking the Back button returns to a clean empty upload state (drop zone visible, no stale data from previous upload).
result: pass

## Summary

total: 7
passed: 4
issues: 3
pending: 0
skipped: 1
skipped: 1

## Infrastructure Issues Found During Testing

1. API container not rebuilt — Phase 17 code not deployed. Fix: docker compose build api
2. Database migration pending — drivers.name_normalized column missing. Fix: alembic upgrade head
3. Dashboard volume stale — Old JS bundle in Docker volume. Fix: docker volume rm routing_opt_dashboard_assets + rebuild
4. Unused import — uploadAndOptimize in UploadRoutes.tsx caused TS build failure. Fixed by removing import.

## Additional Observations

- Second upload: All 35 drivers showed "Matched" with amber badges and match details, confirming Plan 03 fix works
- Results page issues (pre-existing): Generic vehicle names (VEH-01/VEH-02), garbled CDCMS addresses, "0 km from prev", information overload
- Driver-to-vehicle mapping missing: VROOM uses static fleet, not driver names. Selected 3 drivers but VROOM sent 13 vehicles

## Scope of Fixes

### Fix Now (Phase 17 Gap Closure)
1. Geocoding filter bug (blocker) — Move driver filter before geocoding loop (line 1853 -> before line 1628)
2. Allocation Pending filter (major) — Filter non-driver placeholders in preprocess_cdcms()
3. Process Selected button alignment (cosmetic) — CSS fix

### Fix Soon (Next Phase — driver-vehicle mapping + progress)
4. Driver-to-vehicle mapping — Create VROOM vehicles from selected drivers instead of static fleet
5. Progress feedback — Collapsible window showing geocoding/optimization status real-time

### Backlog (Todos)
6. Address display quality, results page overhaul, geocoding precision, performance metrics

## Gaps

- truth: "Driver preview only shows real drivers, not CDCMS placeholders like Allocation Pending"
  status: failed
  reason: "User reported: Allocation Pending appears as a driver name with 3 orders. It's a CDCMS placeholder meaning no driver assigned — should be filtered out in preprocessor, not shown in preview or geocoded."
  severity: major
  test: 4
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""

- truth: "Processing shows detailed progress feedback so operators know the system is working"
  status: failed
  reason: "User reported: Process Selected button size/alignment is off. After clicking, only a spinning circle shows — no indication of what's happening. Need a collapsible progress window showing real-time status (which step, how many orders geocoded, etc.)."
  severity: major
  test: 5
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""

- truth: "Selecting 3 drivers should only geocode those 3 drivers' orders, not all 1885"
  status: failed
  reason: "User reported: Selected only 3 drivers but 775+ geocoding API calls made. Driver selection filtering happens AFTER geocoding (line 1853), not before. All orders are geocoded regardless of selection, wasting Google Maps API costs."
  severity: blocker
  test: 5
  root_cause: "main.py:1848-1851 — deliberate but wrong design: driver filtering at optimization step, geocoding loop at line 1628 processes all orders unconditionally"
  artifacts:
    - path: "apps/kerala_delivery/api/main.py"
      issue: "Driver selection filter applied at line 1853 (post-geocoding) instead of before geocoding loop at line 1628"
  missing:
    - "Move driver filtering before geocoding loop so only selected drivers' orders are geocoded"
  debug_session: ""
