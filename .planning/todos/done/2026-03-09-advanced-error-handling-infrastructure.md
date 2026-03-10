---
created: 2026-03-09T01:35:00.000Z
title: Advanced error handling infrastructure
area: api
files:
  - apps/kerala_delivery/api/main.py
  - apps/kerala_delivery/dashboard/src/lib/api.ts
  - apps/kerala_delivery/dashboard/src/pages/UploadRoutes.tsx
---

## Problem

Basic error humanization is done (Phase 17), but the pipeline lacks structured error infrastructure:
- No structured error response model — still uses FastAPI default `{"detail": "..."}` format
- No request ID tracking for cross-layer debugging
- No retry with exponential backoff for transient Google API errors (OVER_QUERY_LIMIT, network timeouts)
- No frontend error type differentiation (network offline vs API key missing vs server error vs validation error)

## Solution

1. **Structured error model**: `ErrorResponse(error_code, user_message, debug_details, request_id)` — consistent shape across all endpoints
2. **Request ID middleware**: Generate UUID per request, include in response headers and error payloads
3. **Geocoding retry**: Exponential backoff for transient errors (OVER_QUERY_LIMIT, network), max 3 retries
4. **Frontend error categorization**: Differentiate network/auth/validation/server errors with appropriate UI treatment (offline banner, re-auth prompt, field-level validation, generic error toast)
