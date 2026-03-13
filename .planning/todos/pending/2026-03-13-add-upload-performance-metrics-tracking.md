---
created: 2026-03-13T22:26:00.057Z
title: Add upload performance metrics tracking
area: api
files:
  - apps/kerala_delivery/api/main.py
  - apps/kerala_delivery/dashboard/src/pages/UploadRoutes.tsx
---

## Problem

No visibility into where time is spent during the upload-to-results pipeline. Operators can't tell if slowness is from geocoding, VROOM optimization, or something else. Useful for understanding operational costs and identifying bottlenecks — especially as order counts grow.

Key timing points:
- Geocoding: time per order and total (dominant cost with Google Maps API)
- VROOM solve time (typically fast, but scales with stop count)
- End-to-end upload-to-results time

## Solution

1. Instrument `upload_and_optimize()` and `parse_upload()` with timing around each stage (preprocess, geocode, optimize, persist)
2. Return timing breakdown in the API response (e.g., `timing: { geocoding_ms, vroom_ms, total_ms }`)
3. Display timing summary in the dashboard results view so operators can see where time was spent
4. Log timing to server logs for monitoring
