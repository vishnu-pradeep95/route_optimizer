# Error Message Traceability Map

> **Audience:** Developer

**Created:** Phase 20 (Sync Error Message Documentation)
**Verified:** 2026-03-12
**Total entries:** 25 (9 file-level + 9 row-level + 7 geocoding)

This artifact maps every user-facing error message documented in CSV_FORMAT.md to its source code location. Used by the development team to keep documentation in sync with code.

---

## File-Level Errors (Before Processing)

| Message | Code Location | Status |
|---------|--------------|--------|
| "Unsupported file type (.pdf). Accepted: .csv, .xls, .xlsx" | `apps/kerala_delivery/api/main.py:868` | verified |
| "Unexpected content type (application/pdf). Upload a CSV or Excel file." | `apps/kerala_delivery/api/main.py:879` | verified |
| "File too large (15.2 MB). Maximum: 10 MB." | `apps/kerala_delivery/api/main.py:898` | verified |
| "No 'Allocated-Printed' orders found in CDCMS export. Check that the file has orders with status 'Allocated-Printed'." | `apps/kerala_delivery/api/main.py:926` | verified |
| "No valid orders found in file" | `apps/kerala_delivery/api/main.py:1036` | verified |
| "Missing address column 'address' -- make sure you're uploading the correct file format" | `core/data_import/csv_importer.py:301-302` | verified |
| "Required columns missing: ConsumerAddress, OrderNo -- make sure you're uploading the raw CDCMS export" | `core/data_import/cdcms_preprocessor.py:538-540` | verified |
| "The 'ConsumerAddress' column exists but all values are empty. Check the file format." | `core/data_import/cdcms_preprocessor.py:556-558` | verified |
| "Unsupported file format: .txt. Use .csv, .xlsx, or .xls" | `core/data_import/csv_importer.py:279` | verified |

## Row-Level Errors (During Processing)

| Message | Code Location | Status |
|---------|--------------|--------|
| "Empty address -- add a delivery address" | `core/data_import/csv_importer.py:221` | verified |
| "Duplicate order_id 'ORD-001' -- already imported from an earlier row" | `core/data_import/csv_importer.py:236-237` | verified |
| "Invalid weight '20kg' in weight_kg column -- using default 14.2 kg" | `core/data_import/csv_importer.py:402-403` | verified |
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
| "Geocoding service not configured (missing API key)" | `apps/kerala_delivery/api/main.py:1173` (no geocoder configured fallback) | verified |
| "Could not find this address -- try checking the spelling" | `apps/kerala_delivery/api/main.py:1148` (GEOCODING_REASON_MAP.get default fallback) | verified |
