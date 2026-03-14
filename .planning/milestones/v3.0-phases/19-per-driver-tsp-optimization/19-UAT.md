---
status: complete
phase: 19-per-driver-tsp-optimization
source: [19-01-SUMMARY.md, 19-02-SUMMARY.md, 19-03-SUMMARY.md]
started: 2026-03-14T05:30:00Z
updated: 2026-03-14T06:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running Docker stack. Run `docker compose up -d`. Wait for all services healthy. Upload a CDCMS CSV with DeliveryMan column. Server boots without errors, migration runs cleanly, upload completes with routes generated.
result: pass

### 2. CDCMS Upload Per-Driver TSP
expected: Upload a CDCMS CSV/XLSX file containing multiple drivers in the DeliveryMan column. After driver selection and processing, each driver gets their own TSP-optimized route with stops in an optimal order. All routes appear together from the single upload.
result: pass

### 3. DeliveryMan Column Missing — Fail Fast
expected: Upload a standard CSV that has no DeliveryMan column. The API returns a 400 error with a clear message about the missing column (not a 500 crash).
result: pass

### 4. Per-Driver Routes in Dashboard
expected: After uploading a multi-driver CDCMS file, the dashboard route list shows all drivers' routes from the same optimization run. Each route card shows the driver name (not a generic vehicle ID like VEH-01).
result: pass

### 5. Driver PWA — QR Access with ?driver= Parameter
expected: Open the Driver PWA at `/driver/?driver=DRIVER_NAME` (URL-encoded driver name from a completed optimization). The app loads directly into the route view showing that driver's stops in order. No vehicle selector is shown.
result: pass

### 6. Driver PWA — No Parameter Shows Upload Screen
expected: Open the Driver PWA at `/driver/` (no ?driver= parameter). The app shows the upload screen with "Today's Deliveries" heading and "Upload Delivery List" button. No vehicle selector screen appears.
result: pass

### 7. Vehicle Selector Completely Removed
expected: There is no way to reach a vehicle selector screen in the Driver PWA. No dropdown, no vehicle list, no VEH-XX options anywhere in the interface.
result: pass

### 8. QR Sheet — Driver Name Titles
expected: After optimization, print the QR sheet (via dashboard or API endpoint). Each card on the QR sheet shows the driver's name as the primary title (not vehicle ID). A "Scan to open route" QR code is prominently displayed.
result: pass

### 9. QR Sheet — URLs Use ?driver= Parameter
expected: The QR codes on the printed sheet encode URLs with `?driver=DRIVER_NAME` (URL-encoded). Scanning a QR code opens the Driver PWA with the correct driver's route loaded.
result: pass

### 10. Reset Button Behavior in QR Mode
expected: While viewing a route loaded via QR (?driver= parameter), tapping the reset button (arrows icon) re-fetches the same driver's route (refreshes data). It does NOT return to a vehicle selector or upload screen.
result: pass

## Summary

total: 10
passed: 10
issues: 0
pending: 0
skipped: 0

## Gaps

[none]
