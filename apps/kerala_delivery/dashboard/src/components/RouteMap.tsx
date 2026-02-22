/**
 * RouteMap — MapLibre GL map showing vehicle routes, stops, and live positions.
 *
 * Why MapLibre GL JS instead of Mapbox GL JS:
 * - MapLibre is a free, open-source fork with no API key required
 * - No usage-based billing — important for a small delivery business
 * - Compatible with the same style specs and tile sources
 * - react-map-gl v8 supports MapLibre as a first-class backend
 *
 * Why we use react-map-gl instead of raw maplibre-gl:
 * - Declarative React API fits better with our component model
 * - Source/Layer/Marker components handle lifecycle automatically
 * - Less boilerplate than imperative map.addLayer() calls
 */

import { useCallback, useMemo } from "react";
import Map, {
  Source,
  Layer,
  Marker,
  NavigationControl,
} from "react-map-gl/maplibre";
import type { MapRef } from "react-map-gl/maplibre";
import type { LayerSpecification } from "maplibre-gl";
import type { RouteDetail, TelemetryPing } from "../types";
import { getVehicleColor, STATUS_COLORS } from "../types";
import "./RouteMap.css";

/**
 * Kochi, Kerala center coordinates — the hub for our LPG delivery area.
 * All deliveries are within ~5 km radius of this point.
 */
const KOCHI_CENTER = {
  longitude: 76.2846,
  latitude: 9.9716,
} as const;

const DEFAULT_ZOOM = 12;

/**
 * Free basemap style from CARTO (Positron).
 * Why Positron: clean, light style that doesn't distract from our route overlays.
 * No API key needed — CARTO provides this as a free community resource.
 */
const MAP_STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";

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
}: RouteMapProps) {
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

  const handleMapRef = useCallback(
    (ref: MapRef | null) => {
      onMapRef?.(ref);
    },
    [onMapRef]
  );

  return (
    <div className="route-map">
      <Map
        ref={handleMapRef}
        initialViewState={{
          ...KOCHI_CENTER,
          zoom: DEFAULT_ZOOM,
        }}
        style={{ width: "100%", height: "100%" }}
        mapStyle={MAP_STYLE}
        /**
         * attributionControl is required by OpenStreetMap license.
         * We keep it enabled (default) as good open-data citizenship.
         */
      >
        <NavigationControl position="top-right" />

        {/* Route polylines — one GeoJSON source + layer per vehicle for distinct colors */}
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
                title={`${vehicleId}: ${ping.speed_kmh.toFixed(0)} km/h${ping.speed_alert ? " ⚠ SPEED ALERT" : ""}`}
              >
                {/* Arrow indicating heading direction */}
                <span
                  className="live-marker-arrow"
                  style={{ transform: `rotate(${ping.heading}deg)` }}
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
