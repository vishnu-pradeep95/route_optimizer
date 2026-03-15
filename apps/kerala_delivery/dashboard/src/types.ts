/**
 * TypeScript interfaces for the Kerala LPG Delivery Ops Dashboard.
 *
 * These types mirror the FastAPI backend response shapes exactly.
 * Keeping them in one file makes it easy to update when the API evolves.
 * See: apps/kerala_delivery/api/ for the corresponding Pydantic models.
 */

// --- Route types ---

/** A single delivery stop within a vehicle's route. */
export interface RouteStop {
  sequence: number;
  order_id: string;
  address: string;
  /** Original unprocessed address from CDCMS source data. */
  address_raw: string | null;
  latitude: number;
  longitude: number;
  weight_kg: number;
  quantity: number;
  notes: string;
  distance_from_prev_km: number;
  duration_from_prev_minutes: number;
  status: "pending" | "delivered" | "failed";
}

/** Summary of one vehicle's route (no individual stops). */
export interface RouteSummary {
  route_id: string;
  vehicle_id: string;
  driver_name: string;
  total_stops: number;
  total_distance_km: number;
  total_duration_minutes: number;
  total_weight_kg: number;
  total_items: number;
}

/** Response from GET /api/routes — all routes for the latest run. */
export interface RoutesResponse {
  assignment_id: string;
  routes: RouteSummary[];
  unassigned_orders: number;
}

/** Response from GET /api/routes?include_stops=true — all routes with stops. */
export interface BatchRoutesResponse {
  assignment_id: string;
  routes: RouteDetail[];
  unassigned_orders: number;
}

/** Response from GET /api/routes/{vehicle_id} — full route with stops. */
export interface RouteDetail {
  route_id: string;
  vehicle_id: string;
  driver_name: string;
  total_stops: number;
  total_distance_km: number;
  total_duration_minutes: number;
  total_weight_kg: number;
  total_items: number;
  stops: RouteStop[];
}

// --- Telemetry types ---

/** A single GPS ping from a vehicle's tracking device. */
export interface TelemetryPing {
  latitude: number;
  longitude: number;
  /** Nullable — API returns null when speed can't be calculated from GPS fix. */
  speed_kmh: number | null;
  /** Nullable — GPS accuracy varies; null means the device didn't report it. */
  accuracy_m: number | null;
  /** Nullable — heading unavailable when vehicle is stationary. */
  heading: number | null;
  /**
   * ISO 8601 timestamp of the GPS fix. Non-null for DB-sourced pings
   * (recorded_at is NOT NULL in the schema), but the API serializes
   * defensively with `if p.recorded_at else None`, so we allow null
   * on the client to stay type-safe against edge cases.
   */
  recorded_at: string | null;
  /** True when speed exceeds 40 km/h in urban zone (Kerala MVD safety rule). */
  speed_alert: boolean;
}

/** Response from GET /api/telemetry/{vehicle_id}. */
export interface TelemetryResponse {
  vehicle_id: string;
  count: number;
  pings: TelemetryPing[];
}

/** Response from GET /api/telemetry/fleet — latest ping per vehicle. */
export interface FleetTelemetryResponse {
  count: number;
  vehicles: Record<string, TelemetryPing>;
}

// --- Driver types ---

/** A driver in the system. Mirrors _driver_to_dict() response from the API. */
export interface Driver {
  id: string;
  name: string;
  is_active: boolean;
  route_count: number;
  created_at: string | null;
  updated_at: string | null;
}

/** Response from GET /api/drivers. */
export interface DriversResponse {
  count: number;
  drivers: Driver[];
}

/** Response from GET /api/drivers/check-name. */
export interface DriverCheckResponse {
  similar_drivers: Array<{
    id: string;
    name: string;
    score: number;
    is_active: boolean;
  }>;
}

// --- Driver Preview types (Phase 17: parse-upload flow) ---

/** A driver found in a parsed upload file, before processing. */
export interface DriverPreview {
  csv_name: string;
  display_name: string;
  order_count: number;
  status: "existing" | "new" | "matched" | "reactivated";
  matched_to?: string;
  match_score?: number;
}

/** Response from POST /api/parse-upload. */
export interface ParsePreviewResponse {
  upload_token: string;
  filename: string;
  total_rows: number;
  filtered_rows: number;
  drivers: DriverPreview[];
}

// --- Vehicle / Fleet types ---

/** A vehicle in the fleet. Mirrors _vehicle_to_dict() response from the API. */
export interface Vehicle {
  vehicle_id: string;
  registration_no: string | null;
  vehicle_type: "diesel" | "electric" | "cng";
  max_weight_kg: number;
  max_items: number;
  depot_latitude: number | null;
  depot_longitude: number | null;
  speed_limit_kmh: number;
  is_active: boolean;
  created_at: string | null;
  updated_at: string | null;
}

/** Response from GET /api/vehicles. */
export interface VehiclesResponse {
  count: number;
  vehicles: Vehicle[];
}

// --- Import failure types ---

/** A single import failure from CSV validation or geocoding. */
export interface ImportFailure {
  row_number: number;
  address_snippet: string;
  reason: string;
  stage: "validation" | "geocoding" | "optimization";
}

/** A cluster of orders with suspiciously close GPS coordinates. */
export interface DuplicateLocationWarning {
  order_ids: string[];
  addresses: string[];
  max_distance_m: number;
}

// --- Optimization run types ---

/** A single optimization run record. */
export interface OptimizationRun {
  run_id: string;
  created_at: string;
  total_orders: number;
  orders_assigned: number;
  orders_unassigned: number;
  vehicles_used: number;
  optimization_time_ms: number;
  source_filename: string;
  status: "completed" | "failed" | "running";
}

/** Response from GET /api/runs. */
export interface RunsResponse {
  runs: OptimizationRun[];
}

// --- Health check ---

/** Status of an individual service in the health response. */
export interface ServiceStatus {
  status: string;
  message: string;
}

/**
 * Enhanced health response from GET /health.
 *
 * Includes per-service status for PostgreSQL, OSRM, VROOM, and Google API.
 * Overall status is "healthy" | "degraded" | "unhealthy".
 * Backward-compatible: the `status` field still works for simple checks.
 */
export interface HealthResponse {
  status: "healthy" | "degraded" | "unhealthy" | string;
  service?: string;
  version?: string;
  uptime_seconds?: number;
  services?: {
    postgresql: ServiceStatus;
    osrm: ServiceStatus;
    vroom: ServiceStatus;
    google_api: ServiceStatus;
  };
}

// --- Settings types ---

/** Response from GET /api/settings. */
export interface SettingsResponse {
  google_maps_api_key: string | null;
  has_api_key: boolean;
}

/** Response from PUT /api/settings/api-key. */
export interface ApiKeyUpdateResponse {
  message: string;
  masked_key: string;
  valid: boolean;
}

/** Response from POST /api/settings/api-key/validate. */
export interface ApiKeyValidateResponse {
  valid: boolean;
  message: string;
}

/** Response from GET /api/geocode-cache/stats. */
export interface GeocodeStats {
  total_entries: number;
  total_hits: number;
  api_calls_saved: number;
  estimated_savings_usd: number;
}

/** Response from POST /api/geocode-cache/import. */
export interface CacheImportResult {
  message: string;
  added: number;
  skipped: number;
}

/** Response from DELETE /api/geocode-cache. */
export interface CacheClearResult {
  message: string;
  deleted: number;
}

// --- Validation types (Phase 22: Google Routes comparison) ---

/** Result from POST /api/routes/{vehicle_id}/validate */
export interface ValidationResult {
  route_id: string;
  vehicle_id: string;
  osrm_distance_km: number;
  osrm_duration_minutes: number;
  google_distance_km: number;
  google_duration_minutes: number;
  distance_delta_pct: number;
  duration_delta_pct: number;
  confidence: "green" | "amber" | "red";
  google_waypoint_order: number[];
  estimated_cost_usd: number;
  validated_at: string;
  cached: boolean;
}

/** Response from GET /api/validation-stats */
export interface ValidationStats {
  count: number;
  total_cost_usd: number;
  estimated_cost_inr: number;
}

/** A single recent validation entry from GET /api/validation-stats/recent */
export interface RecentValidation {
  vehicle_id: string;
  distance_delta_pct: number;
  duration_delta_pct: number;
  confidence: "green" | "amber" | "red";
  validated_at: string;
  estimated_cost_usd: number;
}

// --- UI constants ---

/**
 * Status colors used throughout the dashboard.
 *
 * Why a plain object with `as const` instead of a const enum:
 * TypeScript's `erasableSyntaxOnly` setting (enabled in our tsconfig)
 * forbids const enums — they require emit-time code generation.
 * Plain objects with `as const` give us the same type-safety without emit.
 * See: https://www.typescriptlang.org/tsconfig#erasableSyntaxOnly
 */
export const STATUS_COLORS = {
  delivered: "#16A34A", // Green — delivery completed successfully
  pending: "#D97706",   // Amber — awaiting delivery (matches --color-accent)
  failed: "#DC2626",    // Red — delivery attempt failed
  active: "#1C1917",    // Charcoal — vehicle currently en route (matches --color-text-primary)
  idle: "#78716C",      // Stone — vehicle not moving (matches --color-text-muted)
  alert: "#DC2626",     // Red — speed or safety alert
} as const;

/**
 * Distinct colors for up to 10 vehicle route polylines.
 * Chosen for maximum visual contrast on a light basemap.
 * If more than 10 vehicles are needed, colors cycle from the start.
 */
export const VEHICLE_COLORS = [
  "#3b82f6", // Blue
  "#ef4444", // Red
  "#22c55e", // Green
  "#f59e0b", // Amber
  "#8b5cf6", // Purple
  "#ec4899", // Pink
  "#14b8a6", // Teal
  "#f97316", // Orange
  "#6366f1", // Indigo
  "#06b6d4", // Cyan
] as const;

/**
 * Get a vehicle's assigned color by index.
 * Cycles through the palette if there are more vehicles than colors.
 */
export function getVehicleColor(index: number): string {
  return VEHICLE_COLORS[index % VEHICLE_COLORS.length];
}
