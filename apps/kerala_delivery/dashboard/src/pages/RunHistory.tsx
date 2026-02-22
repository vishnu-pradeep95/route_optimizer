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

import { useState, useEffect, useCallback } from "react";
import { fetchRuns, fetchRunRoutes } from "../lib/api";
import type { OptimizationRun, RouteSummary } from "../types";
import { STATUS_COLORS } from "../types";
import "./RunHistory.css";

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
    switch (status) {
      case "completed":
        return STATUS_COLORS.delivered;
      case "failed":
        return STATUS_COLORS.failed;
      case "running":
        return STATUS_COLORS.active;
      default:
        return STATUS_COLORS.idle;
    }
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
              <>
                <tr
                  key={run.run_id}
                  className={`run-row ${expandedRunId === run.run_id ? "expanded" : ""}`}
                  onClick={() => handleRowClick(run.run_id)}
                  title="Click to view routes"
                >
                  <td>{formatDateTime(run.created_at)}</td>
                  <td className="numeric">{run.total_orders}</td>
                  <td className="numeric">{run.orders_assigned}</td>
                  <td className="numeric">
                    {run.orders_unassigned > 0 ? (
                      <span style={{ color: STATUS_COLORS.failed, fontWeight: 600 }}>
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

                {/* Expanded detail row showing routes for this run */}
                {expandedRunId === run.run_id && (
                  <tr key={`${run.run_id}-detail`} className="detail-row">
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
                  </tr>
                )}
              </>
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
