/**
 * RouteList -- Sidebar panel listing all routes and their stats.
 *
 * Each route row shows: driver name, stops remaining, distance, and ETA range.
 * Clicking a route selects it, which the parent uses to highlight that route
 * on the map and zoom to it.
 *
 * Phase 22: Added "Validate with Google" button on each route card,
 * DaisyUI cost warning modal before API call, inline OSRM vs Google
 * comparison with confidence badge, cached result display with Re-validate,
 * and no-API-key message with Settings link.
 *
 * Why ETAs are shown as time ranges instead of countdowns:
 * Kerala MVD directive prohibits countdown timers in any delivery UI.
 * We show "between HH:MM and HH:MM" to give a realistic arrival window
 * that accounts for the 1.3x safety multiplier on travel times.
 */

import { useState, useEffect, useCallback } from "react";
import { Package, Ruler, Scale, AlertTriangle, ShieldCheck } from "lucide-react";
import type { RouteSummary, RouteDetail, TelemetryPing, ValidationResult, ValidationStats } from "../types";
import { getVehicleColor } from "../types";
import { validateRoute, fetchValidationStats, fetchCachedValidations } from "../lib/api";
import "./RouteList.css";

interface RouteListProps {
  /** Summary for each route. */
  routes: RouteSummary[];
  /** Detailed route data (stops) for each vehicle, keyed by vehicle_id. */
  routeDetailsMap: Map<string, RouteDetail>;
  /** Latest telemetry ping per vehicle, keyed by vehicle_id. */
  latestPings: Map<string, TelemetryPing>;
  /** Currently selected vehicle ID (null if none). */
  selectedVehicleId: string | null;
  /** Callback when a route is clicked. */
  onSelectVehicle: (vehicleId: string | null) => void;
  /** Map from vehicle_id to its color index (for the color dot). */
  vehicleIndexMap: Map<string, number>;
  /** Callback to navigate to Settings page (for no-API-key message). */
  onNavigateToSettings?: () => void;
}

/**
 * Format remaining duration as an ETA time range.
 *
 * Why a range instead of a single time:
 * Real-world delivery times are uncertain. Showing a range
 * (optimistic to pessimistic) sets realistic expectations.
 * The pessimistic bound applies the 1.3x safety multiplier
 * from the Kerala delivery constraints.
 */
function formatETARange(remainingMinutes: number): string {
  const now = new Date();

  // Optimistic: raw estimate
  const optimistic = new Date(now.getTime() + remainingMinutes * 60_000);
  // Pessimistic: 1.3x safety multiplier applied to remaining time
  // Why 1.3x: accounts for Kerala traffic variability, narrow roads, rain
  const SAFETY_MULTIPLIER = 1.3;
  const pessimistic = new Date(
    now.getTime() + remainingMinutes * SAFETY_MULTIPLIER * 60_000
  );

  const fmt = (d: Date) =>
    d.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });

  return `${fmt(optimistic)} \u2013 ${fmt(pessimistic)}`;
}

/**
 * Format a validation timestamp as a human-readable relative or absolute date.
 * Shows "Validated X min ago" for recent, or "Validated Mar 14, 10:30 AM" for older.
 */
function formatValidatedDate(iso: string): string {
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60_000);

  if (diffMin < 1) return "Validated just now";
  if (diffMin < 60) return `Validated ${diffMin} min ago`;
  if (diffMin < 1440) {
    const hours = Math.floor(diffMin / 60);
    return `Validated ${hours} hour${hours > 1 ? "s" : ""} ago`;
  }
  return `Validated ${date.toLocaleString("en-IN", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  })}`;
}

export function RouteList({
  routes,
  routeDetailsMap,
  latestPings,
  selectedVehicleId,
  onSelectVehicle,
  vehicleIndexMap,
  onNavigateToSettings,
}: RouteListProps) {
  // --- Validation state ---
  const [validationResults, setValidationResults] = useState<Map<string, ValidationResult>>(new Map());
  const [validatingVehicle, setValidatingVehicle] = useState<string | null>(null);
  const [showCostModal, setShowCostModal] = useState<string | null>(null);
  const [validationStats, setValidationStats] = useState<ValidationStats | null>(null);
  const [validationError, setValidationError] = useState<{ vehicleId: string; message: string } | null>(null);
  const [noApiKeyVehicle, setNoApiKeyVehicle] = useState<string | null>(null);

  // Fetch validation stats and cached results on mount
  useEffect(() => {
    fetchValidationStats()
      .then(setValidationStats)
      .catch(() => {});
    fetchCachedValidations()
      .then((cached) => {
        const map = new Map<string, ValidationResult>();
        for (const [vid, result] of Object.entries(cached)) {
          map.set(vid, result);
        }
        setValidationResults(map);
      })
      .catch(() => {});
  }, []);

  // Clear validation error after 15 seconds
  useEffect(() => {
    if (!validationError) return;
    const timer = setTimeout(() => setValidationError(null), 15000);
    return () => clearTimeout(timer);
  }, [validationError]);

  /**
   * Handle the validate button click -- opens the cost modal.
   * Does NOT trigger the API call directly (VAL-04 compliance).
   */
  const handleValidateClick = useCallback((vehicleId: string, e: React.MouseEvent) => {
    e.stopPropagation(); // Don't select the route card
    setNoApiKeyVehicle(null);
    setValidationError(null);
    setShowCostModal(vehicleId);
  }, []);

  /**
   * Confirm validation after cost modal -- calls the Google Routes API.
   * For re-validation, force=true bypasses cached results.
   */
  const handleValidateConfirm = useCallback(async () => {
    const vehicleId = showCostModal;
    if (!vehicleId) return;

    const isRevalidate = validationResults.has(vehicleId);
    setShowCostModal(null);
    setValidatingVehicle(vehicleId);
    setValidationError(null);
    setNoApiKeyVehicle(null);

    try {
      const result = await validateRoute(vehicleId, isRevalidate);
      setValidationResults((prev) => {
        const next = new Map(prev);
        next.set(vehicleId, result);
        return next;
      });
      // Refresh stats after successful validation
      fetchValidationStats().then(setValidationStats).catch(() => {});
    } catch (err) {
      if (err instanceof Error && (err as Error & { noApiKey?: boolean }).noApiKey) {
        setNoApiKeyVehicle(vehicleId);
      } else {
        const message = err instanceof Error ? err.message : "Validation failed";
        setValidationError({ vehicleId, message });
      }
    } finally {
      setValidatingVehicle(null);
    }
  }, [showCostModal, validationResults]);

  return (
    <div className="route-list">
      <div className="route-list-header">
        <h3>Routes</h3>
        {selectedVehicleId && (
          <button
            className="clear-selection"
            onClick={() => onSelectVehicle(null)}
            title="Show all routes"
          >
            Show All
          </button>
        )}
      </div>

      <div className="route-list-items">
        {routes.map((route) => {
          const detail = routeDetailsMap.get(route.vehicle_id);
          const ping = latestPings.get(route.vehicle_id);
          const isSelected = selectedVehicleId === route.vehicle_id;
          const colorIndex = vehicleIndexMap.get(route.vehicle_id) ?? 0;
          const validation = validationResults.get(route.vehicle_id);
          const isValidating = validatingVehicle === route.vehicle_id;
          const showNoApiKey = noApiKeyVehicle === route.vehicle_id;

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
              className={`route-item ${isSelected ? "selected" : ""}`}
              onClick={() =>
                onSelectVehicle(
                  isSelected ? null : route.vehicle_id
                )
              }
            >
              {/* Color dot matches the route polyline on the map */}
              <div className="route-item-header">
                <span
                  className="route-color-dot"
                  style={{ backgroundColor: getVehicleColor(colorIndex) }}
                />
                <span className="route-id">{route.vehicle_id}</span>
                {ping?.speed_alert && (
                  <span
                    className="speed-alert-badge"
                    title="Speed exceeds 40 km/h urban limit"
                  >
                    <AlertTriangle size={12} /> SPEED
                  </span>
                )}
              </div>

              <div className="route-driver">{route.driver_name}</div>

              <div className="route-stats">
                <div className="route-stat">
                  <span className="stat-icon"><Package size={14} /></span>
                  <span className="numeric">
                    {stopsCompleted}/{route.total_stops} stops
                  </span>
                </div>
                <div className="route-stat">
                  <span className="stat-icon"><Ruler size={14} /></span>
                  <span className="numeric">{route.total_distance_km.toFixed(1)} km</span>
                </div>
                <div className="route-stat">
                  <span className="stat-icon"><Scale size={14} /></span>
                  <span className="numeric">{route.total_weight_kg.toFixed(0)} kg</span>
                </div>
              </div>

              {/* Efficiency indicator -- km per delivery helps ops spot outliers */}
              {route.total_stops > 0 && (
                <div className="route-efficiency numeric">
                  {(route.total_distance_km / route.total_stops).toFixed(1)} km/delivery
                </div>
              )}

              {/* ETA shown as range, never as a countdown (Kerala MVD directive) */}
              {stopsRemaining > 0 && (
                <div className="route-eta">
                  ETA: {formatETARange(remainingMinutes)}
                </div>
              )}

              {/* Progress bar: amber while in-progress, green at 100% */}
              <div className="route-progress">
                <div
                  className="route-progress-bar"
                  style={{
                    width: `${completionPct}%`,
                    backgroundColor: completionPct >= 100
                      ? "var(--color-success)"
                      : "var(--color-accent)",
                  }}
                />
              </div>

              {/* ── Validation section (Phase 22) ── */}

              {/* No API key message */}
              {showNoApiKey && (
                <div
                  className="no-api-key-message"
                  onClick={(e) => e.stopPropagation()}
                >
                  Google API key required.{" "}
                  <a
                    href="#settings"
                    onClick={(e) => {
                      e.preventDefault();
                      e.stopPropagation();
                      if (onNavigateToSettings) onNavigateToSettings();
                    }}
                  >
                    Configure in Settings
                  </a>
                </div>
              )}

              {/* Inline validation results */}
              {validation && (
                <div
                  className="route-validation"
                  onClick={(e) => e.stopPropagation()}
                >
                  <div className="validation-comparison">
                    <div className="validation-header" />
                    <div className="validation-header">OSRM</div>
                    <div className="validation-header">Google</div>
                    <div className="validation-header">Delta</div>

                    <div className="validation-row">Distance</div>
                    <div className="validation-row numeric">{validation.osrm_distance_km.toFixed(1)} km</div>
                    <div className="validation-row numeric">{validation.google_distance_km.toFixed(1)} km</div>
                    <div className="validation-row numeric">
                      <span className={`tw:badge tw:badge-sm ${
                        validation.confidence === "green"
                          ? "tw:badge-success"
                          : validation.confidence === "amber"
                            ? "tw:badge-warning"
                            : "tw:badge-error"
                      }`}>
                        {validation.distance_delta_pct >= 0 ? "+" : ""}{validation.distance_delta_pct.toFixed(1)}%
                      </span>
                    </div>

                    <div className="validation-row">Time</div>
                    <div className="validation-row numeric">{validation.osrm_duration_minutes.toFixed(0)} min</div>
                    <div className="validation-row numeric">{validation.google_duration_minutes.toFixed(0)} min</div>
                    <div className="validation-row numeric">
                      {validation.duration_delta_pct >= 0 ? "+" : ""}{validation.duration_delta_pct.toFixed(1)}%
                    </div>
                  </div>

                  <div className="validation-meta">
                    {formatValidatedDate(validation.validated_at)}
                  </div>
                </div>
              )}

              {/* Validate / Re-validate button */}
              <div className="route-validate-row" onClick={(e) => e.stopPropagation()}>
                <button
                  className="tw:btn tw:btn-xs tw:btn-outline"
                  onClick={(e) => handleValidateClick(route.vehicle_id, e)}
                  disabled={isValidating}
                >
                  {isValidating ? (
                    <span className="tw:loading tw:loading-spinner tw:loading-xs" />
                  ) : (
                    <ShieldCheck size={12} />
                  )}
                  {validation ? "Re-validate" : "Validate with Google"}
                </button>
              </div>

              {/* Validation error (inline, auto-clears after 5s) */}
              {validationError && validationError.vehicleId === route.vehicle_id && (
                <div className="validation-error" onClick={(e) => e.stopPropagation()}>
                  Validation failed: {validationError.message}
                </div>
              )}
            </div>
          );
        })}

        {routes.length === 0 && (
          <div className="route-list-empty">
            No active routes. Run an optimization first.
          </div>
        )}
      </div>

      {/* ── Cost Warning Modal (DaisyUI) ── */}
      {showCostModal && (
        <div className="tw:modal tw:modal-open">
          <div className="tw:modal-box">
            <h3 className="tw:font-bold tw:text-lg">Validate Route with Google?</h3>
            <p className="tw:py-4">
              This will call the Google Routes API.
              Estimated cost: <strong>~INR 0.93</strong> per validation.
            </p>
            {validationStats && validationStats.count > 0 && (
              <p className="tw:text-sm tw:opacity-70">
                {validationStats.count} validation{validationStats.count !== 1 ? "s" : ""} so far
                (~INR {validationStats.estimated_cost_inr.toFixed(2)} total)
              </p>
            )}
            <div className="tw:modal-action">
              <button
                className="tw:btn"
                onClick={() => setShowCostModal(null)}
              >
                Cancel
              </button>
              <button
                className="tw:btn tw:btn-primary"
                onClick={handleValidateConfirm}
              >
                Validate
              </button>
            </div>
          </div>
          <div
            className="tw:modal-backdrop"
            onClick={() => setShowCostModal(null)}
          />
        </div>
      )}
    </div>
  );
}
