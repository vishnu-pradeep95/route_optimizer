---
created: 2026-03-01T20:33:21.237Z
title: Add elegant error handling across pipeline
area: general
files:
  - apps/kerala_delivery/api/main.py
  - apps/kerala_delivery/dashboard/src/pages/UploadRoutes.tsx
  - core/geocoding/google_adapter.py
  - core/optimizer/vroom_adapter.py
---

## Problem

Error handling is minimal across the pipeline. User requested "elegant error handling on anything that should have it." Areas needing attention:
- API endpoints: generic 500s instead of structured error responses
- Geocoding: silent failures, no retry logic for transient Google API errors
- Optimization: VROOM failures not gracefully surfaced
- Frontend: basic error banner, no differentiation between error types (network, validation, server)
- File upload: limited feedback on malformed CSV structure

## Solution

1. **API layer**: Structured error responses with error codes, user-friendly messages, and debug details
2. **Geocoding**: Retry with backoff for transient errors (OVER_QUERY_LIMIT, network), clear error categorization
3. **Optimization**: Graceful degradation (partial results if some vehicles fail), timeout handling
4. **Frontend**: Error type differentiation (network offline, API key missing, server error, validation error) with appropriate UI treatment
5. **Global**: Request ID tracking for debugging, consistent error shape across all endpoints
