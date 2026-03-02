/**
 * VehicleList — Sidebar panel listing all vehicles and their route stats.
 *
 * Each vehicle row shows: driver name, stops remaining, distance, and ETA range.
 * Clicking a vehicle selects it, which the parent uses to highlight that route
 * on the map and zoom to it.
 *
 * Why ETAs are shown as time ranges instead of countdowns:
 * Kerala MVD directive prohibits countdown timers in any delivery UI.
 * We show "between HH:MM and HH:MM" to give a realistic arrival window
 * that accounts for the 1.3× safety multiplier on travel times.
 */

import { Package, Ruler, Scale, AlertTriangle } from "lucide-react";
import type { RouteSummary, RouteDetail, TelemetryPing } from "../types";
import { getVehicleColor } from "../types";
import "./VehicleList.css";

interface VehicleListProps {
  /** Summary for each vehicle's route. */
  routes: RouteSummary[];
  /** Detailed route data (stops) for each vehicle, keyed by vehicle_id. */
  routeDetailsMap: Map<string, RouteDetail>;
  /** Latest telemetry ping per vehicle, keyed by vehicle_id. */
  latestPings: Map<string, TelemetryPing>;
  /** Currently selected vehicle ID (null if none). */
  selectedVehicleId: string | null;
  /** Callback when a vehicle is clicked. */
  onSelectVehicle: (vehicleId: string | null) => void;
  /** Map from vehicle_id to its color index (for the color dot). */
  vehicleIndexMap: Map<string, number>;
}

/**
 * Format remaining duration as an ETA time range.
 *
 * Why a range instead of a single time:
 * Real-world delivery times are uncertain. Showing a range
 * (optimistic to pessimistic) sets realistic expectations.
 * The pessimistic bound applies the 1.3× safety multiplier
 * from the Kerala delivery constraints.
 */
function formatETARange(remainingMinutes: number): string {
  const now = new Date();

  // Optimistic: raw estimate
  const optimistic = new Date(now.getTime() + remainingMinutes * 60_000);
  // Pessimistic: 1.3× safety multiplier applied to remaining time
  // Why 1.3×: accounts for Kerala traffic variability, narrow roads, rain
  const SAFETY_MULTIPLIER = 1.3;
  const pessimistic = new Date(
    now.getTime() + remainingMinutes * SAFETY_MULTIPLIER * 60_000
  );

  const fmt = (d: Date) =>
    d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });

  return `${fmt(optimistic)} – ${fmt(pessimistic)}`;
}

export function VehicleList({
  routes,
  routeDetailsMap,
  latestPings,
  selectedVehicleId,
  onSelectVehicle,
  vehicleIndexMap,
}: VehicleListProps) {
  return (
    <div className="vehicle-list">
      <div className="vehicle-list-header">
        <h3>Vehicles</h3>
        {selectedVehicleId && (
          <button
            className="clear-selection"
            onClick={() => onSelectVehicle(null)}
            title="Show all vehicles"
          >
            Show All
          </button>
        )}
      </div>

      <div className="vehicle-list-items">
        {routes.map((route) => {
          const detail = routeDetailsMap.get(route.vehicle_id);
          const ping = latestPings.get(route.vehicle_id);
          const isSelected = selectedVehicleId === route.vehicle_id;
          const colorIndex = vehicleIndexMap.get(route.vehicle_id) ?? 0;

          // Count stops by status from detail data
          const stopsRemaining = detail
            ? detail.stops.filter((s) => s.status === "pending").length
            : route.total_stops;
          const stopsCompleted = detail
            ? detail.stops.filter((s) => s.status === "delivered").length
            : 0;

          // Estimate remaining duration from pending stops
          const remainingMinutes = detail
            ? detail.stops
                .filter((s) => s.status === "pending")
                .reduce((sum, s) => sum + s.duration_from_prev_minutes, 0)
            : route.total_duration_minutes;

          // Completion percentage for progress bar coloring
          // Amber while in-progress, switches to green at 100%
          const completionPct = route.total_stops > 0
            ? (stopsCompleted / route.total_stops) * 100
            : 0;

          return (
            <div
              key={route.vehicle_id}
              className={`vehicle-item ${isSelected ? "selected" : ""}`}
              onClick={() =>
                onSelectVehicle(
                  isSelected ? null : route.vehicle_id
                )
              }
            >
              {/* Color dot matches the route polyline on the map */}
              <div className="vehicle-item-header">
                <span
                  className="vehicle-color-dot"
                  style={{ backgroundColor: getVehicleColor(colorIndex) }}
                />
                <span className="vehicle-id">{route.vehicle_id}</span>
                {ping?.speed_alert && (
                  <span
                    className="speed-alert-badge"
                    title="Speed exceeds 40 km/h urban limit"
                  >
                    <AlertTriangle size={12} /> SPEED
                  </span>
                )}
              </div>

              <div className="vehicle-driver">{route.driver_name}</div>

              <div className="vehicle-stats">
                <div className="vehicle-stat">
                  <span className="stat-icon"><Package size={14} /></span>
                  <span className="numeric">
                    {stopsCompleted}/{route.total_stops} stops
                  </span>
                </div>
                <div className="vehicle-stat">
                  <span className="stat-icon"><Ruler size={14} /></span>
                  <span className="numeric">{route.total_distance_km.toFixed(1)} km</span>
                </div>
                <div className="vehicle-stat">
                  <span className="stat-icon"><Scale size={14} /></span>
                  <span className="numeric">{route.total_weight_kg.toFixed(0)} kg</span>
                </div>
              </div>

              {/* Efficiency indicator — km per delivery helps ops spot outliers */}
              {route.total_stops > 0 && (
                <div className="vehicle-efficiency numeric">
                  {(route.total_distance_km / route.total_stops).toFixed(1)} km/delivery
                </div>
              )}

              {/* ETA shown as range, never as a countdown (Kerala MVD directive) */}
              {stopsRemaining > 0 && (
                <div className="vehicle-eta">
                  ETA: {formatETARange(remainingMinutes)}
                </div>
              )}

              {/* Progress bar: amber while in-progress, green at 100% */}
              <div className="vehicle-progress">
                <div
                  className="vehicle-progress-bar"
                  style={{
                    width: `${completionPct}%`,
                    backgroundColor: completionPct >= 100
                      ? "var(--color-success)"
                      : "var(--color-accent)",
                  }}
                />
              </div>
            </div>
          );
        })}

        {routes.length === 0 && (
          <div className="vehicle-list-empty">
            No active routes. Run an optimization first.
          </div>
        )}
      </div>
    </div>
  );
}
