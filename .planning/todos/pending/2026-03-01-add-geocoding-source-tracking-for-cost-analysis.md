---
created: 2026-03-01T20:33:21.237Z
title: Add geocoding source tracking for cost analysis
area: api
files:
  - core/geocoding/google_adapter.py:111-180
  - apps/kerala_delivery/api/main.py:846-898
  - core/database/repository.py:741-746
---

## Problem

There is no visibility into which addresses hit the geocoding cache vs requiring a fresh Google Maps API call. Office staff and administrators need this information to:
- Analyze Google Geocoding API costs per upload
- Understand cache hit rates over time
- Identify addresses that consistently miss cache (potential normalization issues)

Currently, the geocoding loop in `main.py` silently checks cache then falls through to the API with no tracking of which path was taken per address.

## Solution

1. Add a `source` field to the geocoding result tracking (e.g., "cache_db", "cache_file", "google_api")
2. Include per-address source in the `ImportFailure`/success response alongside existing fields
3. Add summary counts to `OptimizationSummary`: `cache_hits`, `api_calls`, `estimated_cost`
4. Surface this in the ImportSummary UI component (e.g., "23 from cache, 4 API calls (~$0.02)")
