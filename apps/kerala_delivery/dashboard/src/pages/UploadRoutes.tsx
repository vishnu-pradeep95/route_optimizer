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
import type { RouteSummary, RouteDetail, ImportFailure, DuplicateLocationWarning } from "../types";
import { StatusBadge, deriveRouteStatus } from "../components/StatusBadge";
import { FileText, AlertTriangle, Printer } from "lucide-react";
import "./UploadRoutes.css";

// --- Import Summary Component ---

/**
 * ImportSummary — displays between upload area and route cards.
 *
 * Three visual states:
 * 1. All succeed (zero failures): green bar "All N orders geocoded successfully"
 * 2. Partial success: amber bar with counts + expandable failure detail table
 * 3. Zero success (all fail): failure details, no route cards, clear message
 *
 * Uses DaisyUI 5 components with tw- prefix alongside existing CSS patterns.
 */
function ImportSummary({ uploadResult }: { uploadResult: UploadResponse }) {
  const [failuresOpen, setFailuresOpen] = useState(false);
  const [warningsOpen, setWarningsOpen] = useState(false);

  // Backward-compatible field access: fall back to existing fields
  // if the server hasn't been updated to include new diagnostic fields
  const totalRows = uploadResult.total_rows ?? uploadResult.total_orders ?? 0;
  const failures: ImportFailure[] = uploadResult.failures ?? [];
  const warnings: ImportFailure[] = uploadResult.warnings ?? [];
  const geocoded = uploadResult.geocoded ?? uploadResult.orders_assigned ?? 0;
  const failedCount =
    (uploadResult.failed_geocoding ?? 0) + (uploadResult.failed_validation ?? 0);

  // No diagnostic data available (pre-Phase-3 server) — don't render
  if (totalRows === 0 && failures.length === 0) {
    return null;
  }

  // --- All-success state: green confirmation bar ---
  if (failures.length === 0) {
    return (
      <div className="import-summary">
        <div className="tw-alert tw-alert-success">
          <svg xmlns="http://www.w3.org/2000/svg" className="tw-h-5 tw-w-5 tw-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>All {totalRows} orders geocoded successfully</span>
        </div>
      </div>
    );
  }

  // --- Partial-success or zero-success: amber bar with counts + failure table ---
  return (
    <div className="import-summary">
      {/* Summary counts bar */}
      <div className="tw-alert tw-alert-warning">
        <svg xmlns="http://www.w3.org/2000/svg" className="tw-h-5 tw-w-5 tw-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <div className="summary-counts">
          <span>
            <strong>{uploadResult.orders_assigned}</strong> routed
          </span>
          {uploadResult.orders_unassigned > 0 && (
            <span>
              <strong>{uploadResult.orders_unassigned}</strong> unassigned
            </span>
          )}
          <span className="failed-count">
            <strong>{failedCount}</strong> failed
          </span>
        </div>
      </div>

      {/* Zero-success message */}
      {geocoded === 0 && failures.length > 0 && (
        <div className="tw-alert tw-alert-error tw-mt-4">
          <svg xmlns="http://www.w3.org/2000/svg" className="tw-h-5 tw-w-5 tw-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>No orders could be geocoded -- check addresses below</span>
        </div>
      )}

      {/* Expandable failure detail table */}
      {failures.length > 0 && (
        <div className="tw-collapse tw-collapse-arrow tw-bg-base-200 tw-mt-4">
          <input
            type="checkbox"
            checked={failuresOpen}
            onChange={() => setFailuresOpen(!failuresOpen)}
          />
          <div className="tw-collapse-title tw-font-semibold">
            {failures.length} failed row{failures.length !== 1 ? "s" : ""} -- click to expand
          </div>
          <div className="tw-collapse-content">
            <div className="tw-overflow-x-auto">
              <table className="tw-table tw-table-sm">
                <thead>
                  <tr>
                    <th>Row</th>
                    <th>Address</th>
                    <th>Reason</th>
                    <th>Stage</th>
                  </tr>
                </thead>
                <tbody>
                  {failures.map((f, idx) => (
                    <tr key={`fail-${f.row_number}-${idx}`}>
                      <td>{f.row_number}</td>
                      <td>{f.address_snippet || "--"}</td>
                      <td>{f.reason}</td>
                      <td>{f.stage}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Warnings section */}
      {warnings.length > 0 && (
        <div className="tw-collapse tw-collapse-arrow tw-bg-base-100 tw-mt-3 tw-border tw-border-base-300">
          <input
            type="checkbox"
            checked={warningsOpen}
            onChange={() => setWarningsOpen(!warningsOpen)}
          />
          <div className="tw-collapse-title tw-font-semibold tw-text-sm">
            {warnings.length} warning{warnings.length !== 1 ? "s" : ""} -- defaults applied
          </div>
          <div className="tw-collapse-content">
            <div className="tw-overflow-x-auto">
              <table className="tw-table tw-table-sm">
                <thead>
                  <tr>
                    <th>Row</th>
                    <th>Address</th>
                    <th>Reason</th>
                    <th>Stage</th>
                  </tr>
                </thead>
                <tbody>
                  {warnings.map((w, idx) => (
                    <tr key={`warn-${w.row_number}-${idx}`}>
                      <td>{w.row_number}</td>
                      <td>{w.address_snippet || "--"}</td>
                      <td>{w.reason}</td>
                      <td>{w.stage}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * CostSummary — geocoding cost transparency display.
 *
 * Shows cache hits (free) vs API calls with estimated cost.
 * Uses DaisyUI 5 `stat` component with tw- prefix.
 * Only renders when at least one address was geocoded.
 */
function CostSummary({ uploadResult }: { uploadResult: UploadResponse }) {
  const hits = uploadResult.cache_hits ?? 0;
  const calls = uploadResult.api_calls ?? 0;
  const cost = uploadResult.estimated_cost_usd ?? 0;
  const note = uploadResult.free_tier_note ?? "";

  // Don't render if no geocoding happened (pre-Phase-5 server or all-validation-failure)
  if (hits === 0 && calls === 0) return null;

  return (
    <div className="tw-stats tw-stats-vertical lg:tw-stats-horizontal tw-shadow tw-w-full tw-mt-4">
      <div className="tw-stat">
        <div className="tw-stat-title">Cache Hits</div>
        <div className="tw-stat-value tw-text-success">{hits}</div>
        <div className="tw-stat-desc">Free (from database)</div>
      </div>
      <div className="tw-stat">
        <div className="tw-stat-title">API Calls</div>
        <div className="tw-stat-value">{calls}</div>
        <div className="tw-stat-desc">~${cost.toFixed(2)} estimated</div>
      </div>
      {note && (
        <div className="tw-stat">
          <div className="tw-stat-title">Cost Note</div>
          <div className="tw-stat-desc tw-text-sm">{note}</div>
        </div>
      )}
    </div>
  );
}

/**
 * DuplicateWarnings — alerts for orders with suspiciously close GPS coordinates.
 *
 * Non-blocking: shown alongside results, does not prevent route display.
 * Uses DaisyUI 5 `alert` + `collapse` components with tw- prefix.
 * Each cluster is expandable showing order IDs, addresses, and distance.
 */
function DuplicateWarnings({ warnings }: { warnings: DuplicateLocationWarning[] }) {
  if (!warnings || warnings.length === 0) return null;

  return (
    <div className="tw-mt-4">
      <div role="alert" className="tw-alert tw-alert-warning">
        <svg xmlns="http://www.w3.org/2000/svg" className="tw-h-5 tw-w-5 tw-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <span>
          <strong>Duplicate Location Warning:</strong>{" "}
          {warnings.length} group{warnings.length !== 1 ? "s" : ""} of orders resolve to very similar GPS coordinates
        </span>
      </div>
      {warnings.map((cluster, idx) => (
        <div key={idx} className="tw-collapse tw-collapse-arrow tw-bg-base-200 tw-mt-2">
          <input type="checkbox" defaultChecked />
          <div className="tw-collapse-title tw-font-semibold">
            Orders {cluster.order_ids.join(", ")} — within {cluster.max_distance_m.toFixed(0)}m of each other
          </div>
          <div className="tw-collapse-content">
            <ul className="tw-list-disc tw-pl-4 tw-space-y-1">
              {cluster.order_ids.map((id, i) => (
                <li key={id}>
                  <strong>{id}</strong>: {cluster.addresses[i]}
                </li>
              ))}
            </ul>
            <p className="tw-text-xs tw-text-base-content/60 tw-mt-2">
              Different addresses resolving to nearby coordinates may indicate a data entry error.
              If these are intentional (e.g., neighboring buildings), no action is needed.
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}

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

      // Derive geocoded count with backward-compat fallback
      const geocodedCount = result.geocoded ?? result.orders_assigned ?? 0;

      // Only fetch routes if some orders were geocoded successfully
      if (geocodedCount > 0) {
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
      }

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
                <div className="file-icon"><FileText size={24} /></div>
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
              <span className="error-icon"><AlertTriangle size={18} /></span>
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
          {/* Import Summary — only shown after a fresh upload with diagnostics */}
          {uploadResult && <ImportSummary uploadResult={uploadResult} />}

          {/* Geocoding cost summary — shows cache hits vs API calls (GEO-04) */}
          {uploadResult && <CostSummary uploadResult={uploadResult} />}

          {/* Duplicate location warnings — non-blocking alerts for suspicious clusters (GEO-03) */}
          {uploadResult && (
            <DuplicateWarnings warnings={uploadResult.duplicate_warnings ?? []} />
          )}

          {/* Route cards — shown when routes exist (fresh upload or loaded from API) */}
          {routes.length > 0 && (
            <>
              {/* Summary Bar */}
              <div className="results-header">
                <div>
                  <h2 className="tw-text-xl tw-font-bold tw-text-base-content tw-mb-3">Routes Generated</h2>
                  {uploadResult && (
                    <div className="tw-stats tw-stats-horizontal tw-shadow tw-bg-base-100">
                      <div className="tw-stat tw-py-2 tw-px-4">
                        <div className="tw-stat-title tw-text-xs">Orders</div>
                        <div className="tw-stat-value tw-text-lg numeric">{uploadResult.orders_assigned}</div>
                      </div>
                      <div className="tw-stat tw-py-2 tw-px-4">
                        <div className="tw-stat-title tw-text-xs">Vehicles</div>
                        <div className="tw-stat-value tw-text-lg numeric">{uploadResult.vehicles_used}</div>
                      </div>
                      {uploadResult.orders_unassigned > 0 && (
                        <div className="tw-stat tw-py-2 tw-px-4">
                          <div className="tw-stat-title tw-text-xs">Unassigned</div>
                          <div className="tw-stat-value tw-text-lg tw-text-error numeric">{uploadResult.orders_unassigned}</div>
                        </div>
                      )}
                      <div className="tw-stat tw-py-2 tw-px-4">
                        <div className="tw-stat-title tw-text-xs">Solve Time</div>
                        <div className="tw-stat-value tw-text-lg numeric">{uploadResult.optimization_time_ms.toFixed(0)} ms</div>
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
                    <Printer size={16} /> Print QR Sheet
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
                  className="tw-card tw-bg-base-100 tw-shadow-sm tw-border tw-border-base-300"
                >
                  <div className="tw-card-body tw-p-4">
                    <div
                      className="tw-flex tw-items-center tw-justify-between tw-cursor-pointer"
                      onClick={() => toggleVehicle(route.vehicle_id)}
                    >
                      <h2 className="tw-card-title tw-text-sm tw-gap-2">
                        <span className="tw-badge tw-badge-neutral tw-font-mono">{route.vehicle_id}</span>
                        <span className="tw-text-base-content/60">{route.driver_name}</span>
                      </h2>
                      <div className="tw-flex tw-items-center tw-gap-2">
                        {detail && <StatusBadge status={deriveRouteStatus(detail.stops)} />}
                        <span className={`expand-arrow ${isExpanded ? "open" : ""}`}>▼</span>
                      </div>
                    </div>
                    <div className="tw-flex tw-gap-4 tw-mt-2">
                      <span className="numeric"><strong>{route.total_stops}</strong> stops</span>
                      <span className="numeric"><strong>{route.total_distance_km}</strong> km</span>
                      <span className="numeric"><strong>{Math.round(route.total_duration_minutes)}</strong> min</span>
                      <span className="numeric"><strong>{route.total_weight_kg}</strong> kg</span>
                    </div>

                    {/* Expanded: QR codes + stop list */}
                    {isExpanded && (
                      <div className="tw-mt-4 tw-border-t tw-border-base-300 tw-pt-4">
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
                                      <span className="numeric">{stop.weight_kg} kg</span> ·{" "}
                                      <span className="numeric">{stop.quantity} cyl</span> ·{" "}
                                      <span className="numeric">{stop.distance_from_prev_km} km</span> from prev
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
                </div>
              );
            })}
              </div>
            </>
          )}

          {/* Zero-success after fresh upload: show Upload New File button */}
          {uploadResult && (uploadResult.geocoded ?? uploadResult.orders_assigned ?? 0) === 0 && (
            <div className="import-summary-actions">
              <button className="new-upload-btn" onClick={handleReset}>
                Upload New File
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
