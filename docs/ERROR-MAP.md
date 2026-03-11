# Error Message Traceability Map

> **Audience:** Developer

**Created:** Phase 20 (Sync Error Message Documentation)
**Verified:** 2026-03-11
**Total entries:** 35 (9 file-level + 9 row-level + 7 geocoding + 7 licensing errors + 3 licensing headers)

This artifact maps every user-facing error message documented in CSV_FORMAT.md to its source code location. Used by the development team to keep documentation in sync with code.

---

## File-Level Errors (Before Processing)

| Message | Code Location | Status |
|---------|--------------|--------|
| "Unsupported file type (.pdf). Accepted: .csv, .xls, .xlsx" | `apps/kerala_delivery/api/main.py:862` | verified |
| "Unexpected content type (application/pdf). Upload a CSV or Excel file." | `apps/kerala_delivery/api/main.py:873` | verified |
| "File too large (15.2 MB). Maximum: 10 MB." | `apps/kerala_delivery/api/main.py:892` | verified |
| "No 'Allocated-Printed' orders found in CDCMS export. Check that the file has orders with status 'Allocated-Printed'." | `apps/kerala_delivery/api/main.py:920` | verified |
| "No valid orders found in file" | `apps/kerala_delivery/api/main.py:1007` | verified |
| "Missing address column 'address' -- make sure you're uploading the correct file format" | `core/data_import/csv_importer.py:301-302` | verified |
| "Required columns missing: ConsumerAddress, OrderNo -- make sure you're uploading the raw CDCMS export" | `core/data_import/cdcms_preprocessor.py:352-354` | verified |
| "The 'ConsumerAddress' column exists but all values are empty. Check the file format." | `core/data_import/cdcms_preprocessor.py:370-372` | verified |
| "Unsupported file format: .txt. Use .csv, .xlsx, or .xls" | `core/data_import/csv_importer.py:279` | verified |

## Row-Level Errors (During Processing)

| Message | Code Location | Status |
|---------|--------------|--------|
| "Empty address -- add a delivery address" | `core/data_import/csv_importer.py:221` | verified |
| "Duplicate order_id 'ORD-001' -- already imported from an earlier row" | `core/data_import/csv_importer.py:236-237` | verified |
| "Invalid weight '20kg' in weight_kg column -- using default 14.2 kg" | `core/data_import/csv_importer.py:395-396` | verified |
| "Invalid number value -- check for letters or symbols in numeric fields" | `core/data_import/csv_importer.py:115` | verified |
| "Unexpected value format -- check the cell contents" | `core/data_import/csv_importer.py:117` | verified |
| "Invalid value in this row" | `core/data_import/csv_importer.py:118` | verified |
| "Missing required field 'order_id' -- check your CSV has all required columns" | `core/data_import/csv_importer.py:121` | verified |
| "Empty or invalid cell -- fill in required fields" | `core/data_import/csv_importer.py:123` | verified |
| "Could not process this row -- check the data format" | `core/data_import/csv_importer.py:124` | verified |

## Geocoding Errors (During Map Lookup)

| Message | Code Location | Status |
|---------|--------------|--------|
| "Address not found -- check spelling in CDCMS" | `apps/kerala_delivery/api/main.py:94` (GEOCODING_REASON_MAP, key: ZERO_RESULTS) | verified |
| "Geocoding service blocked -- contact IT" | `apps/kerala_delivery/api/main.py:95` (GEOCODING_REASON_MAP, key: REQUEST_DENIED) | verified |
| "Google Maps quota exceeded -- contact IT" | `apps/kerala_delivery/api/main.py:96-97` (GEOCODING_REASON_MAP, keys: OVER_QUERY_LIMIT, OVER_DAILY_LIMIT) | verified |
| "Address could not be processed -- check for unusual characters" | `apps/kerala_delivery/api/main.py:98` (GEOCODING_REASON_MAP, key: INVALID_REQUEST) | verified |
| "Google Maps is temporarily unavailable -- try again in a few minutes" | `apps/kerala_delivery/api/main.py:99` (GEOCODING_REASON_MAP, key: UNKNOWN_ERROR) | verified |
| "Geocoding service not configured (missing API key)" | `apps/kerala_delivery/api/main.py:1123` (no geocoder configured fallback) | verified |
| "Could not find this address -- try checking the spelling" | `apps/kerala_delivery/api/main.py:1098` (GEOCODING_REASON_MAP.get default fallback) | verified |

## Licensing Errors (v2.1)

Error messages returned by the licensing system. All licensing errors result in HTTP 503 responses on all endpoints (except `/health`).

| Message | Code Location | Status |
|---------|--------------|--------|
| "No license key found. Set LICENSE_KEY env var or place license.key file." | `core/licensing/license_manager.py:410` | verified |
| "Invalid license key format or tampered key." | `core/licensing/license_manager.py:422` | verified |
| "License key is not valid for this machine. Run scripts/get_machine_id.py and send the output to support." | `core/licensing/license_manager.py:436-437` | verified |
| "License expired beyond grace period. Contact support." | `core/licensing/license_manager.py:347` | verified |
| "License expired or invalid. Contact support." | `core/licensing/enforcement.py:203` (503 JSON body) | verified |
| "File integrity check failed. Protected files have been modified." | `core/licensing/enforcement.py:171` (SystemExit at startup) | verified |
| "Runtime integrity check failed. Protected files modified." | `core/licensing/license_manager.py:566-567` (SystemExit during re-validation) | verified |

### Licensing Response Headers (v2.1)

Headers added to HTTP responses by the license enforcement middleware.

| Header | Value | Code Location | Status |
|--------|-------|--------------|--------|
| `X-License-Status` | `invalid` | `core/licensing/enforcement.py:193` | verified |
| `X-License-Warning` | `License in grace period` | `core/licensing/enforcement.py:215` | verified |
| `X-License-Expires-In` | `{N}d` (e.g., `45d`, `-3d`) | `core/licensing/enforcement.py:219` | verified |
