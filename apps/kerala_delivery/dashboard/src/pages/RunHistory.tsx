/**
 * RunHistory — Table of past optimization runs with drill-down to routes.
 *
 * Why a separate page instead of a tab within LiveMap:
 * Run history is a different workflow — operators review past runs
 * to compare performance, not during live operations. Separating it
 * keeps each page focused on one task.
 *
 * Data flow:
 * 1. On mount: fetch /api/runs for the list
 * 2. On row click: fetch /api/runs/{run_id}/routes for that run's routes
 * 3. Display routes in an expandable detail panel below the table
 */

import { useState, useEffect, useCallback, Fragment } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { fetchRuns, fetchRunRoutes } from "../lib/api";
import type { OptimizationRun, RouteSummary } from "../types";
import "./RunHistory.css";

/**
 * Status-to-CSS-color mapping — uses design tokens instead of the
 * legacy STATUS_COLORS from types.ts. These map run statuses to
 * inline background colors for status pills.
 */
const RUN_STATUS_STYLES: Record<string, string> = {
  completed: "#16a34a",   // green-600 — success
  failed: "#dc2626",      // red-600 — danger
  running: "#d97706",     // amber-600 — accent (in progress)
  pending: "#78716c",     // stone-500 — neutral
};

export function RunHistory() {
  const [runs, setRuns] = useState<OptimizationRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  /** Currently expanded run — shows its routes below the row. */
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);
  const [expandedRoutes, setExpandedRoutes] = useState<RouteSummary[]>([]);
  const [routesLoading, setRoutesLoading] = useState(false);

  // --- Data fetching ---

  const loadRuns = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchRuns(20);
      setRuns(data.runs);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load run history"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  /**
   * Toggle expansion of a run row to show its route details.
   *
   * Why toggle instead of always expand:
   * Clicking an already-expanded row collapses it, which is the
   * standard UX pattern for expandable table rows.
   */
  const handleRowClick = useCallback(
    async (runId: string) => {
      if (expandedRunId === runId) {
        // Collapse
        setExpandedRunId(null);
        setExpandedRoutes([]);
        return;
      }

      setExpandedRunId(runId);
      setRoutesLoading(true);

      try {
        const data = await fetchRunRoutes(runId);
        setExpandedRoutes(data.routes);
      } catch {
        setExpandedRoutes([]);
        console.warn(`Failed to load routes for run ${runId}`);
      } finally {
        setRoutesLoading(false);
      }
    },
    [expandedRunId]
  );

  // --- Formatting helpers ---

  /**
   * Format ISO timestamp to a human-readable local date/time.
   * Uses en-IN locale for Indian date formatting conventions.
   */
  function formatDateTime(iso: string): string {
    return new Date(iso).toLocaleString("en-IN", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  }

  /** Format optimization solve time with appropriate units. */
  function formatSolveTime(ms: number): string {
    if (ms < 1000) return `${ms.toFixed(0)} ms`;
    return `${(ms / 1000).toFixed(1)} s`;
  }

  /** Get a color for the run status badge. */
  function statusColor(status: string): string {
    return RUN_STATUS_STYLES[status] ?? "#78716c";
  }

  // --- Render ---

  if (loading) {
    return (
      <div className="run-history-loading">
        <div className="loading-spinner" />
        <p>Loading optimization runs...</p>
      </div>
    );
  }

  return (
    <div className="run-history-page">
      <div className="run-history-header">
        <h2>Optimization Run History</h2>
        <button className="refresh-btn" onClick={loadRuns}>
          ↻ Refresh
        </button>
      </div>

      {error && (
        <div className="run-history-error">
          <span>⚠ {error}</span>
          <button onClick={loadRuns}>Retry</button>
        </div>
      )}

      <div className="run-history-table-wrapper">
        <table className="run-history-table">
          <thead>
            <tr>
              <th>Date / Time</th>
              <th>Orders</th>
              <th>Assigned</th>
              <th>Unassigned</th>
              <th>Vehicles</th>
              <th>Solve Time</th>
              <th>Source</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <Fragment key={run.run_id}>
                <tr
                  className={`run-row ${expandedRunId === run.run_id ? "expanded" : ""}`}
                  onClick={() => handleRowClick(run.run_id)}
                  title="Click to view routes"
                >
                  <td>{formatDateTime(run.created_at)}</td>
                  <td className="numeric">{run.total_orders}</td>
                  <td className="numeric">
                    {/* Mini assignment bar — shows ratio of assigned to total orders.
                     * The track is 40px wide; fill width is proportional to the ratio.
                     * Green fill = healthy assignment rate.
                     */}
                    <span className="assignment-bar">
                      {run.orders_assigned}
                      <span className="assignment-bar-track">
                        <span
                          className="assignment-bar-fill"
                          style={{
                            width: run.total_orders > 0
                              ? `${(run.orders_assigned / run.total_orders) * 100}%`
                              : "0%",
                          }}
                        />
                      </span>
                    </span>
                  </td>
                  <td className="numeric">
                    {run.orders_unassigned > 0 ? (
                      <span style={{ color: "#dc2626", fontWeight: 600 }}>
                        {run.orders_unassigned}
                      </span>
                    ) : (
                      run.orders_unassigned
                    )}
                  </td>
                  <td className="numeric">{run.vehicles_used}</td>
                  <td className="numeric">
                    {formatSolveTime(run.optimization_time_ms)}
                  </td>
                  <td className="source-file">{run.source_filename}</td>
                  <td>
                    <span
                      className="status-badge"
                      style={{
                        backgroundColor: statusColor(run.status),
                      }}
                    >
                      {run.status}
                    </span>
                  </td>
                </tr>

                {/* Expanded detail row — animated height via framer-motion.
                 * Why AnimatePresence: it allows exit animations before the
                 * element is removed from the DOM, giving a smooth collapse.
                 */}
                <AnimatePresence>
                {expandedRunId === run.run_id && (
                  <motion.tr
                    key={`${run.run_id}-detail`}
                    className="detail-row"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.2 }}
                  >
                    <td colSpan={8}>
                      {routesLoading ? (
                        <div className="detail-loading">Loading routes...</div>
                      ) : expandedRoutes.length === 0 ? (
                        <div className="detail-empty">
                          No routes found for this run.
                        </div>
                      ) : (
                        <div className="detail-routes">
                          <h4>Routes</h4>
                          <table className="detail-routes-table">
                            <thead>
                              <tr>
                                <th>Vehicle</th>
                                <th>Driver</th>
                                <th>Stops</th>
                                <th>Distance</th>
                                <th>Duration</th>
                                <th>Weight</th>
                                <th>Items</th>
                              </tr>
                            </thead>
                            <tbody>
                              {expandedRoutes.map((route) => (
                                <tr key={route.route_id}>
                                  <td>{route.vehicle_id}</td>
                                  <td>{route.driver_name}</td>
                                  <td className="numeric">
                                    {route.total_stops}
                                  </td>
                                  <td className="numeric">
                                    {route.total_distance_km.toFixed(1)} km
                                  </td>
                                  <td className="numeric">
                                    {route.total_duration_minutes.toFixed(0)} min
                                  </td>
                                  <td className="numeric">
                                    {route.total_weight_kg.toFixed(0)} kg
                                  </td>
                                  <td className="numeric">
                                    {route.total_items}
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </td>
                  </motion.tr>
                )}
                </AnimatePresence>
              </Fragment>
            ))}

            {runs.length === 0 && !error && (
              <tr>
                <td colSpan={8} className="no-runs">
                  No optimization runs yet. Upload orders and run the optimizer.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
