---
created: 2026-03-01T20:33:21.237Z
title: Fix geocoding cache normalization inconsistency
area: database
files:
  - core/database/repository.py:741-746
  - core/geocoding/google_adapter.py:189-196
---

## Problem

Two-tier geocoding cache uses inconsistent address normalization:
- **PostGIS DB** (`repository.py:741`): `address.strip().lower()` — preserves internal whitespace and punctuation
- **File cache** (`google_adapter.py:195`): `" ".join(address.lower().split())` via SHA256 — collapses all whitespace

This causes:
1. Cache misses when the same address has minor formatting differences (extra spaces, punctuation)
2. Duplicate cache entries pointing to the same GPS coordinates
3. Unnecessary Google API calls for addresses that should hit cache
4. Root cause of the "stacked nodes" bug on the live map (nodes 3-6 overlapping)

## Solution

1. Unify normalization: both caches should use the same function
2. Normalize: collapse whitespace, strip punctuation, lowercase
3. Example: `re.sub(r'[^a-z0-9\s]', '', " ".join(address.lower().split()))`
4. Migration: re-normalize existing cache entries or let them expire naturally
