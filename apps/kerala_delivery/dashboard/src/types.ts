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

/** Response from GET /api/routes/{vehicle_id} — full route with stops. */
export interface RouteDetail {
  route_id: string;
  vehicle_id: string;
  driver_name: string;
  total_stops: number;
  total_distance_km: number;
  total_duration_minutes: number;
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
  recorded_at: string;
  /** True when speed exceeds 40 km/h in urban zone (Kerala MVD safety rule). */
  speed_alert: boolean;
}

/** Response from GET /api/telemetry/{vehicle_id}. */
export interface TelemetryResponse {
  vehicle_id: string;
  count: number;
  pings: TelemetryPing[];
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

export interface HealthResponse {
  status: string;
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
  delivered: "#22c55e", // Green — delivery completed successfully
  pending: "#f59e0b",  // Amber — awaiting delivery
  failed: "#ef4444",   // Red — delivery attempt failed
  active: "#3b82f6",   // Blue — vehicle currently en route
  idle: "#6b7280",     // Gray — vehicle not moving
  alert: "#ef4444",    // Red — speed or safety alert
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
