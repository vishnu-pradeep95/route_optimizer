/**
 * Frontend error types and utilities for structured API error handling.
 *
 * Mirrors the backend ErrorResponse model from api/errors.py.
 * Provides:
 * - ApiError interface matching the backend ErrorResponse JSON shape
 * - ErrorSeverity classification for color-coded UI display
 * - Type guard (isApiError) for safe parsing of API responses
 * - ERROR_HELP_URLS mapping error codes to docs sections
 *
 * See: apps/kerala_delivery/api/errors.py for the corresponding Pydantic model
 */

/**
 * Typed representation of the backend's ErrorResponse model.
 *
 * Every non-2xx API response returns this shape. The frontend parses it
 * in api.ts and throws it as a typed object so components can render
 * contextual error UI (banner, table, details panel).
 */
export interface ApiError {
  success: false;
  error_code: string;
  user_message: string;
  technical_message: string;
  request_id: string;
  timestamp: string;
  help_url: string;
}

/**
 * Severity levels for error UI color coding.
 *
 * Maps to DaisyUI alert variants:
 * - "error" -> tw:alert-error (red) -- upload failures, auth errors
 * - "warning" -> tw:alert-warning (amber) -- timeouts, service unavailable
 * - "info" -> tw:alert-info (blue) -- degraded service, informational
 */
export type ErrorSeverity = "error" | "warning" | "info";

/**
 * Classify an API error into a severity level for UI color coding.
 *
 * Logic:
 * - Upload errors are always critical (red) -- user action needed
 * - Timeouts and unavailable services are warnings (amber) -- may self-resolve
 * - Degraded status is informational (blue) -- system still usable
 * - Everything else defaults to error (red) -- safe default
 */
export function classifyError(error: ApiError): ErrorSeverity {
  if (error.error_code.startsWith("UPLOAD_")) return "error";
  if (error.error_code.startsWith("AUTH_")) return "error";
  if (error.error_code.includes("TIMEOUT")) return "warning";
  if (error.error_code.includes("UNAVAILABLE")) return "warning";
  if (error.error_code.includes("DEGRADED")) return "info";
  return "error";
}

/**
 * Type guard to check if an unknown object is an ApiError.
 *
 * Used in api.ts to determine whether a non-ok response body
 * is the structured ErrorResponse format or a legacy plain text error.
 */
export function isApiError(obj: unknown): obj is ApiError {
  return (
    typeof obj === "object" &&
    obj !== null &&
    "error_code" in obj &&
    "user_message" in obj &&
    (obj as Record<string, unknown>).success === false
  );
}

/**
 * Map error codes to docs/ help URLs.
 *
 * Mirrors ERROR_HELP_URLS from api/errors.py. The backend also populates
 * help_url in ErrorResponse, but we keep a client-side copy so the
 * frontend can provide help links even for synthetic errors (e.g., network
 * errors that never reach the backend).
 */
export const ERROR_HELP_URLS: Record<string, string> = {
  UPLOAD_INVALID_FORMAT: "/docs/CSV_FORMAT.md#before-processing-file-level-errors",
  UPLOAD_FILE_TOO_LARGE: "/docs/CSV_FORMAT.md#before-processing-file-level-errors",
  UPLOAD_EMPTY_FILE: "/docs/CSV_FORMAT.md#before-processing-file-level-errors",
  UPLOAD_NO_VALID_ORDERS: "/docs/CSV_FORMAT.md#during-processing-row-level-errors",
  UPLOAD_NO_ALLOCATED: "/docs/CSV_FORMAT.md#cdcms-export-format",
  GEOCODING_NOT_CONFIGURED: "/docs/GOOGLE-MAPS.md#setting-up-a-google-maps-api-key",
  GEOCODING_QUOTA_EXCEEDED: "/docs/GOOGLE-MAPS.md#over_query_limit",
  GEOCODING_FAILED: "/docs/GOOGLE-MAPS.md#common-errors",
  OPTIMIZER_UNAVAILABLE: "/docs/SETUP.md#osrm-not-ready",
  OPTIMIZER_TIMEOUT: "/docs/SETUP.md#osrm-not-ready",
  OPTIMIZER_ERROR: "/docs/SETUP.md#osrm-not-ready",
  FLEET_NO_VEHICLES: "/docs/SETUP.md#step-11-cdcms-data-workflow",
  AUTH_KEY_INVALID: "/docs/SETUP.md#step-6-environment-variables",
  AUTH_KEY_MISSING: "/docs/SETUP.md#step-6-environment-variables",
  SERVICE_UNAVAILABLE: "/docs/SETUP.md#troubleshooting-1",
};
