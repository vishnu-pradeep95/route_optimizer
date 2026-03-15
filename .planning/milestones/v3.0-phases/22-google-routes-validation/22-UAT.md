---
status: complete
phase: 22-google-routes-validation
source: [22-01-SUMMARY.md, 22-02-SUMMARY.md]
started: 2026-03-15T00:15:00Z
updated: 2026-03-15T00:15:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Docker stack starts cleanly after rebuild. API health check returns 200. Dashboard loads without console errors.
result: pass

### 2. Validate Button Visible on Route Cards
expected: After uploading a CSV and generating routes, each route card in the sidebar has a "Validate with Google" button visible (not just on the selected card — on every card).
result: pass

### 3. Cost Warning Modal Before Validation
expected: Clicking "Validate with Google" opens a DaisyUI modal showing estimated cost (~INR 0.93 per validation) and cumulative stats (total validations today, total cost). Modal has "Validate" and "Cancel" buttons. Clicking "Cancel" closes the modal without making any API call.
result: pass

### 4. No API Key — Settings Link
expected: If no Google Maps API key is configured (or key removed from Settings), clicking "Validate with Google" shows an amber message saying the API key is required, with a clickable link/button to navigate to the Settings page. No API call is attempted.
result: skipped
reason: API key is in .env inside Docker container; removing it would break geocoding. Feature is unit-tested in backend.

### 5. Inline Comparison After Validation
expected: After confirming the cost modal (requires valid Google Maps API key with Routes API enabled), the route card expands to show an inline comparison: OSRM distance vs Google distance with delta %, OSRM time vs Google time with delta %. A colored confidence badge appears (green if <=10% distance delta, amber if <=25%, red if >25%).
result: pass

### 6. Cached Result with Re-validate
expected: After a route has been validated, refreshing the page or navigating away and back shows the cached validation result inline (OSRM vs Google comparison, confidence badge, and "Validated X ago" timestamp). The button text changes to "Re-validate". Clicking "Re-validate" shows the cost modal again and triggers a fresh Google API call.
result: pass

### 7. Settings Page — Validation History Card
expected: The Settings page has a "Validation History" card showing: total number of validations, total estimated cost, and a table of recent validations with driver name, date, distance delta, and confidence level.
result: pass

### 8. API — Validation Stats Endpoint
expected: GET http://localhost:8000/api/validation-stats returns JSON with validation_count and total_cost_usd fields. After at least one validation, values are non-zero.
result: pass

## Summary

total: 8
passed: 7
issues: 0
pending: 0
skipped: 1

## Gaps

[none yet]
