/**
 * LiveMap — Main operational view combining map, vehicle list, and stats.
 *
 * This is the primary page operators use during daily deliveries.
 * It fetches all route data, telemetry, and displays them in a
 * three-panel layout: stats bar (top), vehicle list (left), map (center).
 *
 * Data flow:
 * 1. On mount: fetch /api/routes for route summaries
 * 2. For each vehicle: fetch /api/routes/{vehicle_id} for stop details
 * 3. Every 15s: fetch /api/telemetry/{vehicle_id} for live positions
 * 4. Pass data down to StatsBar, VehicleList, RouteMap components
 *
 * Why 15-second polling instead of WebSockets:
 * - Simpler to implement and debug
 * - GPS pings from Piaggio Ape devices arrive every 10-30s anyway
 * - Reduces server load compared to persistent connections
 * - Good enough for ops visibility (this isn't emergency dispatch)
 */

import { useState, useEffect, useCallback, useRef } from "react";
import type { MapRef } from "react-map-gl/maplibre";
import { MapPin, AlertTriangle } from "lucide-react";
import { StatsBar } from "../components/StatsBar";
import { VehicleList } from "../components/VehicleList";
import { RouteMap } from "../components/RouteMap";
import { EmptyState } from "../components/EmptyState";
import { fetchRoutes, fetchRouteDetail, fetchFleetTelemetry } from "../lib/api";
import type {
  RouteSummary,
  RouteDetail,
  TelemetryPing,
} from "../types";
import "./LiveMap.css";

/** How often to refresh telemetry data (milliseconds). */
const TELEMETRY_REFRESH_INTERVAL_MS = 15_000;

export function LiveMap() {
  // --- State ---
  const [routes, setRoutes] = useState<RouteSummary[]>([]);
  const [routeDetailsMap, setRouteDetailsMap] = useState<Map<string, RouteDetail>>(new Map());
  const [latestPings, setLatestPings] = useState<Map<string, TelemetryPing>>(new Map());
  const [unassignedOrders, setUnassignedOrders] = useState(0);
  const [selectedVehicleId, setSelectedVehicleId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  /** Map ref for programmatic zoom/pan when a vehicle is selected. */
  const mapRef = useRef<MapRef | null>(null);

  /**
   * Build a stable vehicle-to-index map so each vehicle always gets
   * the same color, even when the list order changes.
   */
  const vehicleIndexMap = new Map(
    routes.map((r, i) => [r.vehicle_id, i])
  );

  // --- Data fetching ---

  /**
   * Fetch all route data: summaries, then details for each vehicle.
   *
   * Why sequential fetch (summaries first, then details):
   * We need the vehicle IDs from the summary response before we can
   * fetch individual route details. Promise.allSettled handles partial
   * failures gracefully — if one vehicle's detail fails, others still show.
   */
  const loadRouteData = useCallback(async () => {
    try {
      const routesRes = await fetchRoutes();
      setRoutes(routesRes.routes);
      setUnassignedOrders(routesRes.unassigned_orders);

      // Fetch details for all vehicles in parallel
      // TODO Phase 3: Replace this N+1 pattern with a single batch endpoint
      // (e.g. GET /api/routes?include_stops=true) to reduce HTTP round-trips.
      // At current scale (5-13 vehicles) this is fine, but won't scale to 50+.
      const detailResults = await Promise.allSettled(
        routesRes.routes.map((r) => fetchRouteDetail(r.vehicle_id))
      );

      const newDetailsMap = new Map<string, RouteDetail>();
      detailResults.forEach((result, index) => {
        if (result.status === "fulfilled") {
          newDetailsMap.set(routesRes.routes[index].vehicle_id, result.value);
        }
      });
      setRouteDetailsMap(newDetailsMap);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load route data"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  /**
   * Fetch latest telemetry for all active vehicles in one request.
   *
   * Uses the batch fleet endpoint (GET /api/telemetry/fleet) which returns
   * the latest ping per vehicle in a single DB query with DISTINCT ON.
   * Replaces the old N+1 pattern (one HTTP request per vehicle).
   */
  const loadTelemetry = useCallback(async () => {
    if (routes.length === 0) return;

    try {
      const fleetData = await fetchFleetTelemetry();
      const newPings = new Map<string, TelemetryPing>();

      // The fleet endpoint returns { vehicles: { "VEH-01": {...}, "VEH-02": {...} } }
      for (const [vehicleId, ping] of Object.entries(fleetData.vehicles)) {
        newPings.set(vehicleId, ping);
      }
      setLatestPings(newPings);
    } catch {
      // Telemetry fetch failures are non-critical — don't show error
      // The map just won't show live positions until next successful fetch
      console.warn("Telemetry fetch failed, will retry on next interval");
    }
  }, [routes]);

  // Initial data load
  useEffect(() => {
    loadRouteData();
  }, [loadRouteData]);

  // Telemetry polling — runs after routes are loaded, refreshes every 15s
  useEffect(() => {
    if (routes.length === 0) return;

    // Fetch immediately, then set up interval
    loadTelemetry();
    const interval = setInterval(loadTelemetry, TELEMETRY_REFRESH_INTERVAL_MS);

    // Cleanup on unmount or when routes change
    return () => clearInterval(interval);
  }, [routes, loadTelemetry]);

  // --- Vehicle selection → map zoom ---

  /**
   * When a vehicle is selected, fly the map to its route's bounding box.
   *
   * Why flyTo instead of jumpTo:
   * Animated transitions help the operator maintain spatial context
   * when switching between vehicles.
   */
  const handleSelectVehicle = useCallback(
    (vehicleId: string | null) => {
      setSelectedVehicleId(vehicleId);

      if (vehicleId && mapRef.current) {
        const detail = routeDetailsMap.get(vehicleId);
        if (detail && detail.stops.length > 0) {
          // Calculate bounding box of the route's stops
          const lngs = detail.stops.map((s) => s.longitude);
          const lats = detail.stops.map((s) => s.latitude);

          mapRef.current.fitBounds(
            [
              [Math.min(...lngs) - 0.005, Math.min(...lats) - 0.005],
              [Math.max(...lngs) + 0.005, Math.max(...lats) + 0.005],
            ],
            { padding: 60, duration: 1000 }
          );
        }
      }
    },
    [routeDetailsMap]
  );

  const handleMapRef = useCallback((ref: MapRef | null) => {
    mapRef.current = ref;
  }, []);

  // --- Render ---

  // Skeleton loading state matching the 3-panel layout
  if (loading) {
    return (
      <div className="live-map-page">
        {/* Stats bar skeleton */}
        <div className="stats-bar">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="stat-card" style={{ borderLeftColor: 'var(--color-border)' }}>
              <div className="tw-skeleton tw-h-8 tw-w-12 tw-mb-1" />
              <div className="tw-skeleton tw-h-3 tw-w-20" />
            </div>
          ))}
        </div>
        {/* Content area skeleton */}
        <div className="live-map-content">
          <div className="live-map-sidebar">
            <div className="vehicle-list">
              <div className="vehicle-list-header">
                <div className="tw-skeleton tw-h-5 tw-w-20" />
              </div>
              <div className="vehicle-list-items">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="tw-p-3 tw-border-b tw-border-base-300">
                    <div className="tw-skeleton tw-h-4 tw-w-24 tw-mb-2" />
                    <div className="tw-skeleton tw-h-3 tw-w-32 tw-mb-2" />
                    <div className="tw-flex tw-gap-2">
                      <div className="tw-skeleton tw-h-3 tw-w-16" />
                      <div className="tw-skeleton tw-h-3 tw-w-16" />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="live-map-canvas">
            <div className="tw-flex tw-items-center tw-justify-center tw-h-full tw-bg-base-200">
              <div className="text-muted-30">Loading map...</div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Empty state when no active routes exist
  if (routes.length === 0) {
    return (
      <div className="live-map-page tw-flex tw-items-center tw-justify-center">
        <EmptyState
          icon={MapPin}
          title="No active routes"
          description="Upload orders and run optimization to see routes on the map."
        />
      </div>
    );
  }

  return (
    <div className="live-map-page">
      {/* Error banner — non-blocking, shown above content */}
      {error && (
        <div className="live-map-error">
          <AlertTriangle size={16} className="tw-inline tw-mr-1" />
          <span>{error}</span>
          <button onClick={loadRouteData}>Retry</button>
        </div>
      )}

      {/* Stats bar across the top */}
      <StatsBar
        routes={routes}
        routeDetails={Array.from(routeDetailsMap.values())}
        unassignedOrders={unassignedOrders}
      />

      {/* Main content: sidebar + map */}
      <div className="live-map-content">
        <div className="live-map-sidebar">
          <VehicleList
            routes={routes}
            routeDetailsMap={routeDetailsMap}
            latestPings={latestPings}
            selectedVehicleId={selectedVehicleId}
            onSelectVehicle={handleSelectVehicle}
            vehicleIndexMap={vehicleIndexMap}
          />
        </div>
        <div className="live-map-canvas">
          <RouteMap
            routeDetails={Array.from(routeDetailsMap.values())}
            latestPings={latestPings}
            selectedVehicleId={selectedVehicleId}
            vehicleIndexMap={vehicleIndexMap}
            onMapRef={handleMapRef}
          />
        </div>
      </div>
    </div>
  );
}
