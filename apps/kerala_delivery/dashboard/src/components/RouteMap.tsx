/**
 * RouteMap — MapLibre GL map showing vehicle routes, stops, and live positions.
 *
 * Features:
 * - Dark/light basemap toggle (CARTO Dark Matter / Positron)
 * - SVG circle markers with drop shadow and sequence numbers
 * - Larger pulsing ring animation for live vehicle markers
 *
 * Why MapLibre GL JS instead of Mapbox GL JS:
 * - MapLibre is a free, open-source fork with no API key required
 * - No usage-based billing — important for a small delivery business
 * - Compatible with the same style specs and tile sources
 *
 * Why we use react-map-gl instead of raw maplibre-gl:
 * - Declarative React API fits better with our component model
 * - Source/Layer/Marker components handle lifecycle automatically
 * - Less boilerplate than imperative map.addLayer() calls
 */

import { useState, useCallback, useMemo } from "react";
import circle from "@turf/circle";
import Map, {
  Source,
  Layer,
  Marker,
  NavigationControl,
} from "react-map-gl/maplibre";
import type { MapRef } from "react-map-gl/maplibre";
import type { LayerSpecification } from "maplibre-gl";
import type { ValidationResult } from "../types";
import { Moon, Sun } from "lucide-react";
import type { RouteDetail, TelemetryPing } from "../types";
import { getVehicleColor, STATUS_COLORS } from "../types";
import "./RouteMap.css";

/**
 * Vatakara, Kozhikode district — center of our LPG delivery area.
 * All deliveries are within ~5 km radius of this point.
 * Must stay in sync with apps/kerala_delivery/config.py DEPOT_LOCATION.
 */
const VATAKARA_CENTER = {
  longitude: 75.5796,
  latitude: 11.6244,
} as const;

const DEFAULT_ZOOM = 12;

/**
 * Available basemap styles.
 *
 * Why two options instead of one:
 * - Positron (light): better for reading street labels and addresses
 * - Dark Matter (dark): better contrast for colored route overlays,
 *   reduces eye strain during extended monitoring sessions
 * Both are free from CARTO with no API key required.
 */
const MAP_STYLES = {
  light: "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
  dark: "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
} as const;

type MapTheme = keyof typeof MAP_STYLES;

interface RouteMapProps {
  /** Detailed routes to display as polylines and stop markers. */
  routeDetails: RouteDetail[];
  /** Latest GPS ping per vehicle for live position markers. */
  latestPings: Map<string, TelemetryPing>;
  /** Currently selected vehicle (null = show all). */
  selectedVehicleId: string | null;
  /** Map from vehicle_id to its color index. */
  vehicleIndexMap: Map<string, number>;
  /** Callback to capture the map ref for programmatic control. */
  onMapRef?: (ref: MapRef | null) => void;
  /** Zone radius in km from /api/config. When provided, draws boundary circle. */
  zoneRadiusKm?: number;
  /** Cached validation results keyed by vehicle_id. Draws Google's reordered route as dashed polyline. */
  validationResults?: Map<string, ValidationResult>;
}

/**
 * Build a GeoJSON LineString from a route's stop coordinates.
 *
 * Why GeoJSON instead of raw coordinates:
 * MapLibre's Source component expects GeoJSON for vector data.
 * This is the standard interchange format for geographic features.
 */
function routeToGeoJSON(route: RouteDetail): GeoJSON.Feature {
  return {
    type: "Feature",
    properties: {
      vehicle_id: route.vehicle_id,
    },
    geometry: {
      type: "LineString",
      /**
       * GeoJSON coordinates are [longitude, latitude] — the reverse of
       * the common [lat, lon] convention. This trips up many developers.
       * See: https://datatracker.ietf.org/doc/html/rfc7946#section-3.1.1
       */
      coordinates: route.stops.map((stop) => [stop.longitude, stop.latitude]),
    },
  };
}

export function RouteMap({
  routeDetails,
  latestPings,
  selectedVehicleId,
  vehicleIndexMap,
  onMapRef,
  zoneRadiusKm,
  validationResults,
}: RouteMapProps) {
  /**
   * Map theme state — persists during the session.
   * Default: light (Positron) matches the overall dashboard aesthetic.
   * Dark (Dark Matter) available for extended monitoring sessions.
   */
  const [mapTheme, setMapTheme] = useState<MapTheme>("light");

  /**
   * Memoize GeoJSON to avoid rebuilding on every render.
   * Route data only changes when routeDetails changes.
   */
  const routeFeatures = useMemo(() => {
    return routeDetails
      .filter(
        (r) => !selectedVehicleId || r.vehicle_id === selectedVehicleId
      )
      .filter((r) => r.stops.length >= 2);
  }, [routeDetails, selectedVehicleId]);

  /** Collect all stop markers, filtered by selected vehicle. */
  const stopMarkers = useMemo(() => {
    return routeDetails
      .filter(
        (r) => !selectedVehicleId || r.vehicle_id === selectedVehicleId
      )
      .flatMap((route) =>
        route.stops.map((stop) => ({
          ...stop,
          vehicleId: route.vehicle_id,
          colorIndex: vehicleIndexMap.get(route.vehicle_id) ?? 0,
        }))
      );
  }, [routeDetails, selectedVehicleId, vehicleIndexMap]);

  /** Live position markers from telemetry. */
  const liveMarkers = useMemo(() => {
    const entries = Array.from(latestPings.entries());
    if (selectedVehicleId) {
      return entries.filter(([vid]) => vid === selectedVehicleId);
    }
    return entries;
  }, [latestPings, selectedVehicleId]);

  /**
   * Memoized GeoJSON circle for the delivery zone boundary.
   * Uses @turf/circle to generate a 64-step polygon at the configured radius.
   * Rendered as a dashed gray line — subtle informational overlay.
   */
  const zoneCircle = useMemo(() => {
    if (!zoneRadiusKm) return null;
    return circle(
      [VATAKARA_CENTER.longitude, VATAKARA_CENTER.latitude],
      zoneRadiusKm,
      { steps: 64, units: "kilometers" }
    );
  }, [zoneRadiusKm]);

  const handleMapRef = useCallback(
    (ref: MapRef | null) => {
      onMapRef?.(ref);
    },
    [onMapRef]
  );

  return (
    <div className="route-map">
      {/* Dark/light theme toggle — top-left corner */}
      <button
        className="map-theme-toggle"
        onClick={() => setMapTheme(mapTheme === "light" ? "dark" : "light")}
        title={`Switch to ${mapTheme === "light" ? "dark" : "light"} basemap`}
      >
        {mapTheme === "light" ? <Moon size={16} /> : <Sun size={16} />}
      </button>

      <Map
        ref={handleMapRef}
        initialViewState={{
          ...VATAKARA_CENTER,
          zoom: DEFAULT_ZOOM,
        }}
        style={{ width: "100%", height: "100%" }}
        mapStyle={MAP_STYLES[mapTheme]}
        /**
         * attributionControl is required by OpenStreetMap license.
         * We keep it enabled (default) as good open-data citizenship.
         */
      >
        <NavigationControl position="top-right" />

        {/* Zone boundary circle — dashed gray line showing delivery area limit.
            Rendered before route polylines so it sits behind them in z-order. */}
        {zoneCircle && (
          <Source id="zone-boundary" type="geojson" data={zoneCircle}>
            <Layer
              id="zone-boundary-line"
              type="line"
              paint={{
                "line-color": "#888888",
                "line-width": 1.5,
                "line-dasharray": [4, 4],
                "line-opacity": 0.5,
              }}
            />
          </Source>
        )}

        {/* Route polylines — one GeoJSON source + layer per vehicle for distinct colors.
            TODO Phase 3: Add drag-and-drop route adjustment per design doc Section 6.3
            (operator can reorder stops on the map and trigger re-optimization). */}
        {routeFeatures.map((route) => {
          const colorIndex = vehicleIndexMap.get(route.vehicle_id) ?? 0;
          const color = getVehicleColor(colorIndex);
          const geojson = routeToGeoJSON(route);

          /**
           * Layer spec for the route polyline.
           * Why 'line' type: simplest way to draw a path between points.
           * Width of 3 is visible without obscuring street labels.
           */
          const layerStyle: LayerSpecification = {
            id: `route-line-${route.vehicle_id}`,
            type: "line",
            source: `route-${route.vehicle_id}`,
            paint: {
              "line-color": color,
              "line-width": 3,
              "line-opacity": 0.8,
            },
            layout: {
              "line-join": "round",
              "line-cap": "round",
            },
          };

          return (
            <Source
              key={`route-${route.vehicle_id}`}
              id={`route-${route.vehicle_id}`}
              type="geojson"
              data={geojson}
            >
              <Layer {...layerStyle} />
            </Source>
          );
        })}

        {/* Google validation polylines — dashed amber lines showing Google's reordered route.
            Only rendered for routes that have been validated. Uses the google_waypoint_order
            indices to reorder stops, with depot as start/end point. */}
        {validationResults && routeFeatures.map((route) => {
          const validation = validationResults.get(route.vehicle_id);
          if (!validation?.google_waypoint_order?.length) return null;

          const reorderedCoords: [number, number][] = [
            [VATAKARA_CENTER.longitude, VATAKARA_CENTER.latitude],
          ];
          for (const idx of validation.google_waypoint_order) {
            const stop = route.stops[idx];
            if (stop) reorderedCoords.push([stop.longitude, stop.latitude]);
          }
          reorderedCoords.push([VATAKARA_CENTER.longitude, VATAKARA_CENTER.latitude]);

          const geojson: GeoJSON.Feature = {
            type: "Feature",
            properties: { vehicle_id: route.vehicle_id, type: "validation" },
            geometry: { type: "LineString", coordinates: reorderedCoords },
          };

          return (
            <Source
              key={`validation-${route.vehicle_id}`}
              id={`validation-${route.vehicle_id}`}
              type="geojson"
              data={geojson}
            >
              <Layer
                id={`validation-line-${route.vehicle_id}`}
                type="line"
                paint={{
                  "line-color": "#F59E0B",
                  "line-width": 2.5,
                  "line-opacity": 0.7,
                  "line-dasharray": [6, 3],
                }}
                layout={{
                  "line-join": "round",
                  "line-cap": "round",
                }}
              />
            </Source>
          );
        })}

        {/* Delivery stop markers — color-coded by status */}
        {stopMarkers.map((stop) => (
          <Marker
            key={`stop-${stop.vehicleId}-${stop.sequence}`}
            longitude={stop.longitude}
            latitude={stop.latitude}
            anchor="center"
          >
            <div
              className="stop-marker"
              style={{
                backgroundColor: STATUS_COLORS[stop.status],
              }}
              title={`${stop.order_id}: ${stop.address} (${stop.status})`}
            >
              <span className="stop-sequence">{stop.sequence}</span>
            </div>
          </Marker>
        ))}

        {/* Live GPS position markers — pulsing dots showing where each vehicle is now */}
        {liveMarkers.map(([vehicleId, ping]) => {
          const colorIndex = vehicleIndexMap.get(vehicleId) ?? 0;
          return (
            <Marker
              key={`live-${vehicleId}`}
              longitude={ping.longitude}
              latitude={ping.latitude}
              anchor="center"
            >
              <div
                className={`live-marker ${ping.speed_alert ? "speed-alert" : ""}`}
                style={{
                  backgroundColor: ping.speed_alert
                    ? STATUS_COLORS.alert
                    : getVehicleColor(colorIndex),
                }}
                title={`${vehicleId}: ${(ping.speed_kmh ?? 0).toFixed(0)} km/h${ping.speed_alert ? " ⚠ SPEED ALERT" : ""}`}
              >
                {/* Arrow indicating heading direction */}
                <span
                  className="live-marker-arrow"
                  style={{ transform: `rotate(${ping.heading ?? 0}deg)` }}
                >
                  ▲
                </span>
              </div>
            </Marker>
          );
        })}
      </Map>
    </div>
  );
}
