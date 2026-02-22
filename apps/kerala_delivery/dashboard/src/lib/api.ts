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
  RouteDetail,
  TelemetryResponse,
  RunsResponse,
  HealthResponse,
} from "../types";

/**
 * Base URL for API requests.
 * In development, Vite's proxy forwards /api/* to localhost:8000.
 * In production, the API is served from the same origin.
 */
const BASE_URL: string = import.meta.env.VITE_API_URL ?? "";

/**
 * Generic fetch wrapper with error handling.
 *
 * Why a custom wrapper instead of raw fetch everywhere:
 * 1. Centralizes error handling — one place to add auth headers later
 * 2. Parses JSON and checks HTTP status in one step
 * 3. Throws user-friendly errors instead of opaque fetch failures
 */
async function apiFetch<T>(path: string): Promise<T> {
  const url = `${BASE_URL}${path}`;

  try {
    const response = await fetch(url);

    if (!response.ok) {
      // Extract error detail from FastAPI's standard error format if available
      const errorBody = await response.text();
      throw new Error(
        `API error ${response.status}: ${errorBody || response.statusText}`
      );
    }

    return (await response.json()) as T;
  } catch (error) {
    // Re-throw API errors as-is; wrap network errors with user-friendly context
    if (error instanceof Error && error.message.startsWith("API error")) {
      throw error;
    }
    throw new Error(
      `Network error fetching ${path}: ${error instanceof Error ? error.message : "Unknown error"}`
    );
  }
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

/** Check if the backend API is reachable and healthy. */
export async function fetchHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/health");
}
