# Phase 9: License Management - Context

**Gathered:** 2026-03-11
**Status:** Ready for planning

<domain>
## Phase Boundary

License renewal is a simple file drop without re-keying, and license expiry is visible to monitoring tools. Three capabilities: (1) renewal.key file mechanism for extending license expiry, (2) X-License-Expires-In response header on all API responses, (3) license status fields in /health endpoint body.

Requirements: LIC-01, LIC-02, LIC-03.

</domain>

<decisions>
## Implementation Decisions

### Renewal Mechanism
- Renewal key uses the **same LPG-XXXX-XXXX format** as the original license key (reuses existing encode/decode/validate infrastructure)
- `generate_license.py --renew --customer ID --fingerprint HASH --months N` generates the renewal key with guidance about dropping as `renewal.key`
- API checks for `renewal.key` at **startup only** (inside `enforce()`, before `validate_license()`). Customer restarts API after dropping the file. Matches existing `license.key` behavior.
- **Post-renewal file handling:** Claude's discretion (leave in place vs replace license.key)

### Expiry Header (X-License-Expires-In)
- Header appears on **all responses** (including /health and 503 INVALID responses)
- Format: **days with 'd' suffix** (e.g., `45d`, `0d`, `-3d` for expired)
- Header is **omitted when license state is None** (dev mode, no license configured)
- INVALID 503 responses include the header showing how far past expiry (e.g., `-15d`)

### Health Endpoint License Fields
- License info in a **nested `license` object** alongside `services` in /health body:
  ```json
  {
    "license": {
      "status": "valid",
      "expires_at": "2026-09-10",
      "days_remaining": 183,
      "fingerprint_match": true
    }
  }
  ```
- **No customer_id** in the license section (considered sensitive)
- **Omit `license` key entirely** when no license is configured (dev mode)
- **License vs overall health impact:** Claude's discretion (informational only vs degrading overall status)

### Claude's Discretion
- Post-renewal file handling (leave renewal.key in place vs replace license.key and delete)
- Whether GRACE/INVALID license status degrades overall /health status or is purely informational
- Exact implementation of renewal key precedence logic (if both license.key and renewal.key exist)

</decisions>

<specifics>
## Specific Ideas

- Success criteria specifies exact format: `X-License-Expires-In: 45d`
- Renewal must work "without requiring a new fingerprint exchange" — same fingerprint, new expiry only
- `generate_license.py --renew` is the generation command (not a separate script)

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `encode_license_key()` / `decode_license_key()` in license_manager.py — reuse for renewal key generation and validation
- `validate_license()` already reads from `LICENSE_KEY` env var or `license.key` file — extend to check `renewal.key`
- `generate_license.py` CLI with argparse — add `--renew` flag alongside existing flags
- `get_license_status()` / `_license_state` — `days_remaining` and `expires_at` already stored in LicenseInfo

### Established Patterns
- Middleware adds response headers in `license_enforcement_middleware` (X-License-Warning for GRACE, X-License-Status for /health)
- `set_license_state()` has one-way guard — renewal must happen at startup (state guard blocks INVALID->VALID upgrades)
- Dev mode detection: `_is_dev_mode = os.environ.get("ENVIRONMENT") == "development"`
- `/health` endpoint returns JSONResponse with nested service objects

### Integration Points
- `enforce()` in enforcement.py — add renewal.key check before `validate_license()`
- `license_enforcement_middleware` — add X-License-Expires-In header to responses
- `/health` endpoint in main.py — add license section using `get_license_status()` and `_license_state`
- `core/licensing/__init__.py` — may need to export additional accessors for health endpoint

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 09-license-management*
*Context gathered: 2026-03-11*
