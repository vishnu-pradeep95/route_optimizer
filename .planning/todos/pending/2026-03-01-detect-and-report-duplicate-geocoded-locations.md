---
created: 2026-03-01T20:33:21.237Z
title: Detect and report duplicate geocoded locations
area: api
files:
  - apps/kerala_delivery/api/main.py:846-898
  - core/geocoding/google_adapter.py:111-180
  - apps/kerala_delivery/dashboard/src/components/RouteMap.tsx:223-240
---

## Problem

User observed on the live map: nodes 1, 2, then jumps to 7 — nodes 3, 4, 5, 6 are stacked at the same GPS coordinates. Different customer bookings should have unique delivery locations, but Google's fuzzy geocoding returns identical (lat, lon) for similar addresses. No detection or reporting exists for this case.

This creates:
- Invisible stops on the map (markers stacked)
- Misleading route visualization
- Potential optimization issues (VROOM treats co-located stops as separate but same-distance)

## Solution

1. **Detection**: After geocoding, check for orders within X meters of each other (e.g., 50m threshold using Haversine). Flag as warning.
2. **Reporting**: Add "duplicate_locations" to ImportResult/OptimizationSummary with pairs of order IDs that resolved to same coords
3. **UI**: Show duplicate location warnings in ImportSummary (expandable section like failures)
4. **Map**: Apply marker clustering or slight offset for co-located stops so all are visible
5. **Root cause**: Investigate if the CSV data itself has duplicate/similar addresses, or if this is purely a Google API precision issue
