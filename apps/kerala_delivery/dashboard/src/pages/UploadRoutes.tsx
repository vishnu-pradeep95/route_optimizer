/**
 * UploadRoutes — Primary workflow page for daily route generation.
 *
 * This is the page employees use every day:
 * 1. Upload the CDCMS export file (drag & drop or click)
 * 2. System parses, geocodes, and optimizes routes
 * 3. View route summaries per vehicle with QR codes
 * 4. Print QR sheet → drivers scan to open Google Maps navigation
 *
 * Design: Industrial-utilitarian. Clear visual states for each step.
 * Large drop zone for file upload. Progress feedback during optimization.
 * QR codes displayed at scannable size with vehicle/driver details.
 */

import { useState, useCallback, useRef, useEffect } from "react";
import {
  uploadAndOptimize,
  fetchRoutes,
  fetchRouteDetail,
  fetchGoogleMapsRoute,
  getQrSheetUrl,
  type UploadResponse,
  type GoogleMapsRouteResponse,
} from "../lib/api";
import type { RouteSummary, RouteDetail } from "../types";
import "./UploadRoutes.css";

/** Workflow states — drives the UI transitions. */
type WorkflowState =
  | "idle"        // No file selected, show drop zone
  | "selected"    // File chosen, ready to upload
  | "uploading"   // Upload + optimization in progress
  | "success"     // Routes generated, showing results
  | "error";      // Something went wrong

export function UploadRoutes() {
  // --- File upload state ---
  const [workflowState, setWorkflowState] = useState<WorkflowState>("idle");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string>("");
  const [uploadProgress, setUploadProgress] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // --- Results state ---
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const [routes, setRoutes] = useState<RouteSummary[]>([]);
  const [routeDetails, setRouteDetails] = useState<Map<string, RouteDetail>>(new Map());
  const [qrData, setQrData] = useState<Map<string, GoogleMapsRouteResponse>>(new Map());
  const [expandedVehicle, setExpandedVehicle] = useState<string | null>(null);

  // --- Drag & Drop handlers ---
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    const files = e.dataTransfer.files;
    if (files.length > 0) {
      validateAndSelectFile(files[0]);
    }
  }, []);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      validateAndSelectFile(files[0]);
    }
  }, []);

  const validateAndSelectFile = (file: File) => {
    const validExtensions = [".csv", ".xlsx", ".xls"];
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();

    if (!validExtensions.includes(ext)) {
      setErrorMessage("Please upload a .csv, .xlsx, or .xls file");
      setWorkflowState("error");
      return;
    }

    // 10 MB max (matches backend limit)
    if (file.size > 10 * 1024 * 1024) {
      setErrorMessage("File too large. Maximum size is 10 MB.");
      setWorkflowState("error");
      return;
    }

    setSelectedFile(file);
    setErrorMessage("");
    setWorkflowState("selected");
  };

  // --- Upload & Optimize ---
  const handleUpload = useCallback(async () => {
    if (!selectedFile) return;

    setWorkflowState("uploading");
    setUploadProgress("Uploading file...");

    try {
      // Step 1: Upload and optimize
      setUploadProgress("Processing orders & optimizing routes...");
      const result = await uploadAndOptimize(selectedFile);
      setUploadResult(result);

      // Step 2: Fetch route summaries
      setUploadProgress("Loading route details...");
      const routesRes = await fetchRoutes();
      setRoutes(routesRes.routes);

      // Step 3: Fetch details for all vehicles in parallel
      const detailResults = await Promise.allSettled(
        routesRes.routes.map((r) => fetchRouteDetail(r.vehicle_id))
      );
      const detailsMap = new Map<string, RouteDetail>();
      detailResults.forEach((result, index) => {
        if (result.status === "fulfilled") {
          detailsMap.set(routesRes.routes[index].vehicle_id, result.value);
        }
      });
      setRouteDetails(detailsMap);

      // Step 4: Fetch QR codes for all vehicles in parallel
      setUploadProgress("Generating QR codes...");
      const qrResults = await Promise.allSettled(
        routesRes.routes.map((r) => fetchGoogleMapsRoute(r.vehicle_id))
      );
      const newQrData = new Map<string, GoogleMapsRouteResponse>();
      qrResults.forEach((result, index) => {
        if (result.status === "fulfilled") {
          newQrData.set(routesRes.routes[index].vehicle_id, result.value);
        }
      });
      setQrData(newQrData);

      setWorkflowState("success");
      setUploadProgress("");
    } catch (err) {
      setErrorMessage(
        err instanceof Error ? err.message : "Upload failed. Please try again."
      );
      setWorkflowState("error");
      setUploadProgress("");
    }
  }, [selectedFile]);

  // --- Load existing routes on mount (if any) ---
  useEffect(() => {
    const loadExisting = async () => {
      try {
        const routesRes = await fetchRoutes();
        if (routesRes.routes.length > 0) {
          setRoutes(routesRes.routes);

          // Fetch details + QR codes
          const [detailResults, qrResults] = await Promise.all([
            Promise.allSettled(
              routesRes.routes.map((r) => fetchRouteDetail(r.vehicle_id))
            ),
            Promise.allSettled(
              routesRes.routes.map((r) => fetchGoogleMapsRoute(r.vehicle_id))
            ),
          ]);

          const detailsMap = new Map<string, RouteDetail>();
          detailResults.forEach((result, index) => {
            if (result.status === "fulfilled") {
              detailsMap.set(routesRes.routes[index].vehicle_id, result.value);
            }
          });
          setRouteDetails(detailsMap);

          const newQrData = new Map<string, GoogleMapsRouteResponse>();
          qrResults.forEach((result, index) => {
            if (result.status === "fulfilled") {
              newQrData.set(routesRes.routes[index].vehicle_id, result.value);
            }
          });
          setQrData(newQrData);

          setWorkflowState("success");
        }
      } catch {
        // No existing routes — stay in idle state
      }
    };
    loadExisting();
  }, []);

  // --- Reset to start over ---
  const handleReset = () => {
    setWorkflowState("idle");
    setSelectedFile(null);
    setUploadResult(null);
    setRoutes([]);
    setRouteDetails(new Map());
    setQrData(new Map());
    setErrorMessage("");
    setExpandedVehicle(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  // --- Toggle expanded vehicle for QR details ---
  const toggleVehicle = (vehicleId: string) => {
    setExpandedVehicle(expandedVehicle === vehicleId ? null : vehicleId);
  };

  // --- Render ---
  return (
    <div className="upload-routes">
      {/* Upload Section — always visible unless showing results */}
      {workflowState !== "success" && (
        <div className="upload-section">
          <div className="upload-header">
            <h2>Upload CDCMS Orders</h2>
            <p className="upload-subtitle">
              Upload today's CDCMS export to generate optimized delivery routes and QR codes
            </p>
          </div>

          {/* Drop Zone */}
          <div
            className={`drop-zone ${isDragOver ? "drag-over" : ""} ${
              workflowState === "selected" ? "has-file" : ""
            } ${workflowState === "uploading" ? "uploading" : ""}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => workflowState !== "uploading" && fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={handleFileInput}
              className="file-input-hidden"
            />

            {workflowState === "uploading" ? (
              <div className="upload-progress">
                <div className="spinner" />
                <span className="progress-text">{uploadProgress}</span>
              </div>
            ) : selectedFile ? (
              <div className="file-selected">
                <div className="file-icon">📄</div>
                <div className="file-info">
                  <span className="file-name">{selectedFile.name}</span>
                  <span className="file-size">
                    {(selectedFile.size / 1024).toFixed(1)} KB
                  </span>
                </div>
                <button
                  className="change-file-btn"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleReset();
                  }}
                >
                  Change
                </button>
              </div>
            ) : (
              <div className="drop-prompt">
                <div className="drop-icon">
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
                    <polyline points="17 8 12 3 7 8" />
                    <line x1="12" y1="3" x2="12" y2="15" />
                  </svg>
                </div>
                <span className="drop-text">
                  Drop CDCMS export file here or click to browse
                </span>
                <span className="drop-hint">.csv, .xlsx, or .xls — max 10 MB</span>
              </div>
            )}
          </div>

          {/* Upload Button */}
          {workflowState === "selected" && (
            <button className="upload-btn" onClick={handleUpload}>
              Generate Routes & QR Codes
            </button>
          )}

          {/* Error Display */}
          {workflowState === "error" && (
            <div className="error-banner">
              <span className="error-icon">⚠️</span>
              <span className="error-text">{errorMessage}</span>
              <button className="error-retry" onClick={handleReset}>
                Try Again
              </button>
            </div>
          )}
        </div>
      )}

      {/* Results Section */}
      {workflowState === "success" && (
        <div className="results-section">
          {/* Summary Bar */}
          <div className="results-header">
            <div className="results-summary">
              <h2>Routes Generated</h2>
              {uploadResult && (
                <div className="summary-stats">
                  <div className="summary-stat">
                    <span className="stat-val">{uploadResult.orders_assigned}</span>
                    <span className="stat-lbl">Orders Assigned</span>
                  </div>
                  <div className="summary-stat">
                    <span className="stat-val">{uploadResult.vehicles_used}</span>
                    <span className="stat-lbl">Vehicles</span>
                  </div>
                  {uploadResult.orders_unassigned > 0 && (
                    <div className="summary-stat warning">
                      <span className="stat-val">{uploadResult.orders_unassigned}</span>
                      <span className="stat-lbl">Unassigned</span>
                    </div>
                  )}
                  <div className="summary-stat">
                    <span className="stat-val">
                      {uploadResult.optimization_time_ms.toFixed(0)} ms
                    </span>
                    <span className="stat-lbl">Solve Time</span>
                  </div>
                </div>
              )}
            </div>

            <div className="results-actions">
              <a
                href={getQrSheetUrl()}
                target="_blank"
                rel="noopener noreferrer"
                className="print-sheet-btn"
              >
                🖨️ Print QR Sheet
              </a>
              <button className="new-upload-btn" onClick={handleReset}>
                Upload New File
              </button>
            </div>
          </div>

          {/* Vehicle Route Cards */}
          <div className="route-cards">
            {routes.map((route) => {
              const detail = routeDetails.get(route.vehicle_id);
              const vehicleQr = qrData.get(route.vehicle_id);
              const isExpanded = expandedVehicle === route.vehicle_id;

              return (
                <div
                  key={route.vehicle_id}
                  className={`route-card ${isExpanded ? "expanded" : ""}`}
                >
                  <div
                    className="route-card-header"
                    onClick={() => toggleVehicle(route.vehicle_id)}
                  >
                    <div className="route-card-title">
                      <span className="vehicle-badge">{route.vehicle_id}</span>
                      <span className="driver-label">{route.driver_name}</span>
                    </div>
                    <div className="route-card-meta">
                      <span className="meta-item">
                        <strong>{route.total_stops}</strong> stops
                      </span>
                      <span className="meta-item">
                        <strong>{route.total_distance_km}</strong> km
                      </span>
                      <span className="meta-item">
                        <strong>{Math.round(route.total_duration_minutes)}</strong> min
                      </span>
                      <span className="meta-item">
                        <strong>{route.total_weight_kg}</strong> kg
                      </span>
                    </div>
                    <span className={`expand-arrow ${isExpanded ? "open" : ""}`}>
                      ▼
                    </span>
                  </div>

                  {/* Expanded: QR codes + stop list */}
                  {isExpanded && (
                    <div className="route-card-body">
                      {/* QR Codes */}
                      {vehicleQr && (
                        <div className="qr-section">
                          <h4 className="qr-heading">
                            Google Maps QR Code{vehicleQr.total_segments > 1 ? "s" : ""}
                          </h4>
                          {vehicleQr.total_segments > 1 && (
                            <p className="qr-note">
                              Route split into {vehicleQr.total_segments} parts
                              (Google Maps supports max 11 stops per URL)
                            </p>
                          )}
                          <div className="qr-grid">
                            {vehicleQr.segments.map((seg) => (
                              <div key={seg.segment} className="qr-card">
                                {vehicleQr.total_segments > 1 && (
                                  <div className="qr-segment-label">
                                    Part {seg.segment}: Stops {seg.start_stop}–{seg.end_stop}
                                  </div>
                                )}
                                {/* Safe to use dangerouslySetInnerHTML here because qr_svg is
                                    generated server-side by the qrcode library from coordinate
                                    data — never from user-supplied text. The SVG contains only
                                    <path> elements for QR modules. */}
                                <div
                                  className="qr-image"
                                  dangerouslySetInnerHTML={{ __html: seg.qr_svg }}
                                />
                                <a
                                  href={seg.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="maps-link"
                                >
                                  Open in Google Maps
                                </a>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Stop List */}
                      {detail && (
                        <div className="stops-section">
                          <h4 className="stops-heading">Delivery Stops</h4>
                          <div className="stops-list">
                            {detail.stops.map((stop) => (
                              <div key={stop.order_id} className="stop-row">
                                <span className="stop-seq">{stop.sequence}</span>
                                <div className="stop-info">
                                  <span className="stop-address">{stop.address}</span>
                                  <span className="stop-meta">
                                    {stop.weight_kg} kg · {stop.quantity} cyl ·{" "}
                                    {stop.distance_from_prev_km} km from prev
                                  </span>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
