/**
 * API client for the Kerala LPG Delivery backend.
 *
 * All fetch functions are typed and return parsed JSON.
 * The base URL is configurable via VITE_API_URL environment variable,
 * defaulting to "" (same origin) for production deployments where
 * the dashboard is served alongside the API.
 *
 * Why a simple fetch wrapper instead of axios or react-query:
 * - Fewer dependencies to maintain in an educational project
 * - The dashboard has only ~6 endpoints — a full HTTP client is overkill
 * - Easy to understand for new contributors
 * - Native fetch is well-supported in all modern browsers
 */

import type {
  RoutesResponse,
  BatchRoutesResponse,
  RouteDetail,
  TelemetryResponse,
  FleetTelemetryResponse,
  RunsResponse,
  HealthResponse,
  Vehicle,
  VehiclesResponse,
  Driver,
  DriversResponse,
  DriverCheckResponse,
  ImportFailure,
  DuplicateLocationWarning,
} from "../types";
import { isApiError, type ApiError } from "./errors";

/**
 * Base URL for API requests.
 * In development, Vite's proxy forwards /api/* to localhost:8000.
 * In production, the API is served from the same origin.
 */
const BASE_URL: string = import.meta.env.VITE_API_URL ?? "";

/**
 * Generic fetch wrapper with error handling and optional auth.
 *
 * Why a custom wrapper instead of raw fetch everywhere:
 * 1. Centralizes error handling — one place to manage auth headers
 * 2. Parses JSON and checks HTTP status in one step
 * 3. Throws user-friendly errors instead of opaque fetch failures
 *
 * Auth: Sends the X-API-Key header on ALL requests (reads & writes).
 * The backend requires it on sensitive GET endpoints (fleet telemetry,
 * vehicles) and all POST/PUT/DELETE endpoints. For public endpoints
 * like /health, the backend ignores the header if present.
 */
async function apiFetch<T>(path: string): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const headers: Record<string, string> = {};

  // Include API key on all requests — the backend requires it for
  // sensitive reads (fleet telemetry, vehicle details) and all writes.
  const apiKey = import.meta.env.VITE_API_KEY;
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  } else if (import.meta.env.DEV) {
    console.warn(
      "[api] VITE_API_KEY not set — protected GET endpoints (fleet telemetry, vehicles) " +
      "may return 401. Set VITE_API_KEY in your .env file."
    );
  }

  try {
    const response = await fetch(url, { headers, cache: "no-store" });

    if (!response.ok) {
      // Parse response body -- if it matches ErrorResponse shape, throw as typed ApiError
      const errorBody = await response.text();
      try {
        const parsed = JSON.parse(errorBody);
        if (isApiError(parsed)) {
          throw parsed;
        }
      } catch (parseErr) {
        // Not JSON or not ApiError shape -- fall through to generic error
        if (isApiError(parseErr)) throw parseErr;
      }
      throw new Error(
        `API error ${response.status}: ${errorBody || response.statusText}`
      );
    }

    return (await response.json()) as T;
  } catch (error) {
    // Re-throw typed ApiError objects directly
    if (isApiError(error)) {
      throw error;
    }
    // Re-throw API errors as-is; wrap network errors with user-friendly context
    if (error instanceof Error && error.message.startsWith("API error")) {
      throw error;
    }
    throw new Error(
      `Network error fetching ${path}: ${error instanceof Error ? error.message : "Unknown error"}`
    );
  }
}

/**
 * Helper for authenticated write requests (POST, PUT, DELETE).
 *
 * The backend requires an X-API-Key header on all mutating endpoints.
 * The dashboard reads the key from a VITE_API_KEY env var.
 * In development, the key can be set in .env.local.
 *
 * Why a separate helper instead of adding method/body params to apiFetch:
 * Both helpers send the API key, but writes also need a Content-Type header
 * and JSON-serialized request body. Keeping them separate follows the
 * Command-Query Separation principle — reads and writes have different shapes.
 * See: https://martinfowler.com/bliki/CommandQuerySeparation.html
 */
async function apiWrite<T>(path: string, method: string, body?: unknown): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  // Read the API key from Vite's env. Only VITE_-prefixed vars are
  // exposed to client code: https://vite.dev/guide/env-and-mode
  const apiKey = import.meta.env.VITE_API_KEY;
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  } else if (import.meta.env.DEV) {
    console.warn(
      "[api] VITE_API_KEY not set — mutations may be rejected by the backend. " +
      "Set VITE_API_KEY in your .env file."
    );
  }

  const response = await fetch(url, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    const errorBody = await response.text();
    try {
      const parsed = JSON.parse(errorBody);
      if (isApiError(parsed)) {
        throw parsed;
      }
    } catch (parseErr) {
      if (isApiError(parseErr)) throw parseErr;
    }
    throw new Error(`API error ${response.status}: ${errorBody || response.statusText}`);
  }

  return (await response.json()) as T;
}

// --- Fleet / Vehicle endpoints ---

/** Fetch all vehicles in the fleet. */
export async function fetchVehicles(activeOnly: boolean = false): Promise<VehiclesResponse> {
  const qs = activeOnly ? "?active_only=true" : "";
  return apiFetch<VehiclesResponse>(`/api/vehicles${qs}`);
}

/** Create a new vehicle. */
export async function createVehicle(data: {
  vehicle_id: string;
  depot_latitude: number;
  depot_longitude: number;
  max_weight_kg?: number;
  max_items?: number;
  registration_no?: string;
  vehicle_type?: "diesel" | "electric" | "cng";
  speed_limit_kmh?: number;
}): Promise<{ message: string; vehicle: Vehicle }> {
  return apiWrite(`/api/vehicles`, "POST", data);
}

/** Update a vehicle's fields. */
export async function updateVehicle(
  vehicleId: string,
  data: Record<string, unknown>
): Promise<{ message: string }> {
  return apiWrite(`/api/vehicles/${encodeURIComponent(vehicleId)}`, "PUT", data);
}

/** Soft-delete (deactivate) a vehicle. */
export async function deleteVehicle(vehicleId: string): Promise<{ message: string }> {
  return apiWrite(`/api/vehicles/${encodeURIComponent(vehicleId)}`, "DELETE");
}

// --- Driver endpoints ---

/** Fetch all drivers with route counts. */
export async function fetchDrivers(activeOnly: boolean = false): Promise<DriversResponse> {
  const qs = activeOnly ? "?active_only=true" : "";
  return apiFetch<DriversResponse>(`/api/drivers${qs}`);
}

/** Create a new driver by name. */
export async function createDriver(
  name: string
): Promise<{ message: string; driver: Driver; similar_drivers: Array<{ id: string; name: string; score: number; is_active: boolean }> }> {
  return apiWrite(`/api/drivers`, "POST", { name });
}

/** Update a driver's name and/or active status. */
export async function updateDriver(
  id: string,
  data: { name?: string; is_active?: boolean }
): Promise<{ message: string; similar_drivers?: Array<{ id: string; name: string; score: number; is_active: boolean }> }> {
  return apiWrite(`/api/drivers/${encodeURIComponent(id)}`, "PUT", data);
}

/** Soft-delete (deactivate) a driver. */
export async function deleteDriver(id: string): Promise<{ message: string }> {
  return apiWrite(`/api/drivers/${encodeURIComponent(id)}`, "DELETE");
}

/** Check if a driver name has similar matches. */
export async function checkDriverName(
  name: string,
  excludeId?: string
): Promise<DriverCheckResponse> {
  let qs = `?name=${encodeURIComponent(name)}`;
  if (excludeId) qs += `&exclude_id=${encodeURIComponent(excludeId)}`;
  return apiFetch<DriverCheckResponse>(`/api/drivers/check-name${qs}`);
}

// --- Route endpoints ---

/** Fetch routes for the latest optimization run. */
export async function fetchRoutes(): Promise<RoutesResponse> {
  return apiFetch<RoutesResponse>("/api/routes");
}

/** Fetch detailed route (with stops) for a specific vehicle. */
export async function fetchRouteDetail(
  vehicleId: string
): Promise<RouteDetail> {
  return apiFetch<RouteDetail>(`/api/routes/${encodeURIComponent(vehicleId)}`);
}

/** Fetch all routes with full stop details in a single request. */
export async function fetchRoutesWithStops(): Promise<BatchRoutesResponse> {
  return apiFetch<BatchRoutesResponse>("/api/routes?include_stops=true");
}

// --- Telemetry endpoints ---

/**
 * Fetch GPS telemetry pings for a vehicle.
 *
 * @param vehicleId - The vehicle identifier (e.g., "VEH-01")
 * @param limit - Max pings to return (default 100, backend enforces bounds)
 */
export async function fetchTelemetry(
  vehicleId: string,
  limit: number = 100
): Promise<TelemetryResponse> {
  return apiFetch<TelemetryResponse>(
    `/api/telemetry/${encodeURIComponent(vehicleId)}?limit=${limit}`
  );
}

/**
 * Fetch latest GPS ping for every vehicle in one request.
 *
 * Replaces the N+1 pattern of calling fetchTelemetry per vehicle.
 * At 13 vehicles polling every 15s, this reduces 13 HTTP requests
 * and 13 DB queries down to 1+1.
 */
export async function fetchFleetTelemetry(): Promise<FleetTelemetryResponse> {
  return apiFetch<FleetTelemetryResponse>("/api/telemetry/fleet");
}

// --- Optimization run endpoints ---

/**
 * Fetch optimization run history.
 * @param limit - Max runs to return (default 10)
 */
export async function fetchRuns(limit: number = 10): Promise<RunsResponse> {
  return apiFetch<RunsResponse>(`/api/runs?limit=${limit}`);
}

/** Fetch routes for a specific historical optimization run. */
export async function fetchRunRoutes(runId: string): Promise<RoutesResponse> {
  return apiFetch<RoutesResponse>(
    `/api/runs/${encodeURIComponent(runId)}/routes`
  );
}

// --- Health check ---

/** Check if the backend API is reachable and healthy.
 *
 * Uses direct fetch instead of apiFetch because /health intentionally
 * returns 503 with valid JSON body on degraded/unhealthy state.
 * apiFetch throws on non-2xx, which would discard the per-service data.
 */
export async function fetchHealth(): Promise<HealthResponse> {
  const url = `${BASE_URL}/health`;
  const response = await fetch(url, { cache: "no-store" });
  // /health always returns valid JSON regardless of status code (200 or 503)
  return (await response.json()) as HealthResponse;
}

// --- Upload / Optimize ---

/**
 * Upload a CDCMS export file and run route optimization.
 *
 * This is the main workflow endpoint: upload CSV/Excel → parse → geocode →
 * optimize → persist routes. Returns a summary with run_id.
 *
 * Why FormData instead of JSON?
 * File uploads require multipart/form-data encoding. The browser handles
 * the Content-Type header (including boundary) automatically when you
 * pass a FormData object to fetch. Never set Content-Type manually
 * for file uploads — the browser adds the correct multipart boundary.
 */
export interface UploadResponse {
  // Existing fields
  run_id: string;
  assignment_id: string;
  total_orders: number;
  orders_assigned: number;
  orders_unassigned: number;
  vehicles_used: number;
  optimization_time_ms: number;
  created_at: string;

  // Import diagnostics (added in Phase 3)
  total_rows: number;
  geocoded: number;
  failed_geocoding: number;
  failed_validation: number;
  failures: ImportFailure[];
  warnings: ImportFailure[];

  // GEO-04: Cost transparency (Phase 5)
  cache_hits?: number;
  api_calls?: number;
  estimated_cost_usd?: number;
  free_tier_note?: string;
  per_order_geocode_source?: Record<string, string>;

  // GEO-03: Duplicate location warnings (Phase 5)
  duplicate_warnings?: DuplicateLocationWarning[];
}

/**
 * Error class for upload failures that carries the typed ApiError.
 *
 * Pages can check `instanceof ApiUploadError` to access the structured
 * error object for ErrorBanner display. Falls back to Error.message
 * for legacy catch blocks.
 */
export class ApiUploadError extends Error {
  public apiError: ApiError;
  constructor(apiError: ApiError) {
    super(apiError.user_message);
    this.name = "ApiUploadError";
    this.apiError = apiError;
  }
}

export async function uploadAndOptimize(file: File): Promise<UploadResponse> {
  const url = `${BASE_URL}/api/upload-orders`;
  const formData = new FormData();
  formData.append("file", file);

  const headers: Record<string, string> = {};
  const apiKey = import.meta.env.VITE_API_KEY;
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }

  const response = await fetch(url, {
    method: "POST",
    headers,
    body: formData,
  });

  if (!response.ok) {
    const errorBody = await response.text();
    try {
      const parsed = JSON.parse(errorBody);
      if (isApiError(parsed)) {
        throw new ApiUploadError(parsed);
      }
    } catch (parseErr) {
      if (parseErr instanceof ApiUploadError) throw parseErr;
    }
    throw new Error(
      `Upload failed (${response.status}): ${errorBody || response.statusText}`
    );
  }

  return (await response.json()) as UploadResponse;
}

// --- QR Code / Google Maps URLs ---

/** A segment of a route (one Google Maps URL, max 11 stops). */
export interface RouteSegment {
  segment: number;
  start_stop: number;
  end_stop: number;
  stop_count: number;
  url: string;
  qr_svg: string;
}

/** Response from GET /api/routes/{vehicle_id}/google-maps */
export interface GoogleMapsRouteResponse {
  vehicle_id: string;
  driver_name: string;
  total_stops: number;
  total_segments: number;
  segments: RouteSegment[];
}

/** Fetch Google Maps URLs and QR codes for a vehicle's route. */
export async function fetchGoogleMapsRoute(
  vehicleId: string
): Promise<GoogleMapsRouteResponse> {
  return apiFetch<GoogleMapsRouteResponse>(
    `/api/routes/${encodeURIComponent(vehicleId)}/google-maps`
  );
}

/** Get the URL for the printable QR sheet (opens in new tab). */
export function getQrSheetUrl(): string {
  return `${BASE_URL}/api/qr-sheet`;
}
