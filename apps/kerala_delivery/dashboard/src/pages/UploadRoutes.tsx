/**
 * UploadRoutes — Primary workflow page for daily route generation.
 *
 * This is the page employees use every day:
 * 1. Upload the CDCMS export file (drag & drop or click)
 * 2. System parses, geocodes, and optimizes routes
 * 3. View route summaries per driver with QR codes
 * 4. Print QR sheet → drivers scan to open Google Maps navigation
 *
 * Design: Industrial-utilitarian. Clear visual states for each step.
 * Large drop zone for file upload. Progress feedback during optimization.
 * QR codes displayed at scannable size with driver details.
 */

import { useState, useCallback, useRef, useEffect } from "react";
import {
  parseUpload,
  processSelected,
  fetchRoutes,
  fetchRouteDetail,
  fetchGoogleMapsRoute,
  getQrSheetUrl,
  ApiUploadError,
  type UploadResponse,
  type GoogleMapsRouteResponse,
} from "../lib/api";
import type { RouteSummary, RouteDetail, ImportFailure, DuplicateLocationWarning, ParsePreviewResponse, DriverPreview } from "../types";
import type { ApiError } from "../lib/errors";
import { isApiError } from "../lib/errors";
import { StatusBadge, deriveRouteStatus } from "../components/StatusBadge";
import { ErrorBanner } from "../components/ErrorBanner";
import { ErrorTable } from "../components/ErrorTable";
import { FileText, Printer, CheckCircle, ArrowLeft, ArrowRight } from "lucide-react";
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
 * Uses DaisyUI 5 components with tw: prefix alongside existing CSS patterns.
 */
function ImportSummary({ uploadResult, onReupload }: { uploadResult: UploadResponse; onReupload?: () => void }) {
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

  // --- All-success state: compact inline indicator ---
  if (failures.length === 0) {
    return (
      <div className="import-summary">
        <div className="tw:flex tw:items-center tw:gap-2 tw:py-2 tw:px-3 tw:rounded-lg tw:text-success" style={{ backgroundColor: 'oklch(55% 0.2 145 / 0.1)' }}>
          <CheckCircle size={18} className="tw:shrink-0" />
          <span className="tw:text-sm tw:font-medium">All {totalRows} orders geocoded successfully</span>
        </div>
      </div>
    );
  }

  // --- Partial-success or zero-success: amber bar with counts + failure table ---
  return (
    <div className="import-summary">
      {/* Summary counts bar */}
      <div className="tw:alert tw:alert-warning">
        <svg xmlns="http://www.w3.org/2000/svg" className="tw:h-5 tw:w-5 tw:shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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
        <div className="tw:alert tw:alert-error tw:mt-4">
          <svg xmlns="http://www.w3.org/2000/svg" className="tw:h-5 tw:w-5 tw:shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>No orders could be geocoded -- check addresses below</span>
        </div>
      )}

      {/* Failure detail table with download/re-upload actions */}
      {failures.length > 0 && (
        <div className="tw:collapse tw:collapse-arrow tw:bg-base-200 tw:mt-4">
          <input
            type="checkbox"
            checked={failuresOpen}
            onChange={() => setFailuresOpen(!failuresOpen)}
          />
          <div className="tw:collapse-title tw:font-semibold">
            {failures.length} failed row{failures.length !== 1 ? "s" : ""} -- click to expand
          </div>
          <div className="tw:collapse-content">
            <ErrorTable
              failures={failures}
              onReupload={onReupload}
            />
          </div>
        </div>
      )}

      {/* Warnings section */}
      {warnings.length > 0 && (
        <div className="tw:collapse tw:collapse-arrow tw:bg-base-100 tw:mt-3 tw:border tw:border-base-300">
          <input
            type="checkbox"
            checked={warningsOpen}
            onChange={() => setWarningsOpen(!warningsOpen)}
          />
          <div className="tw:collapse-title tw:font-semibold tw:text-sm">
            {warnings.length} warning{warnings.length !== 1 ? "s" : ""} -- defaults applied
          </div>
          <div className="tw:collapse-content">
            <div className="tw:overflow-x-auto">
              <table className="tw:table tw:table-sm">
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
 * Uses DaisyUI 5 `stat` component with tw: prefix.
 * Only renders when at least one address was geocoded.
 */
function CostSummary({ uploadResult }: { uploadResult: UploadResponse }) {
  const hits = uploadResult.cache_hits ?? 0;
  const calls = uploadResult.api_calls ?? 0;
  const cost = uploadResult.estimated_cost_usd ?? 0;
  const note = uploadResult.free_tier_note ?? "";
  const geocoded = uploadResult.geocoded ?? uploadResult.orders_assigned ?? 0;

  // Don't render if zero orders were processed
  if (geocoded === 0 && hits === 0 && calls === 0) return null;

  // All orders had pre-existing coordinates (no geocoding needed)
  if (hits === 0 && calls === 0 && geocoded > 0) {
    return (
      <div className="tw:stats tw:stats-horizontal tw:shadow tw:w-full tw:mt-4">
        <div className="tw:stat">
          <div className="tw:stat-title">Geocoding</div>
          <div className="tw:stat-value tw:text-lg tw:text-success">All cached</div>
          <div className="tw:stat-desc">{geocoded} addresses resolved from cache (no API cost)</div>
        </div>
      </div>
    );
  }

  return (
    <div className="tw:stats tw:stats-vertical lg:tw:stats-horizontal tw:shadow tw:w-full tw:mt-4">
      <div className="tw:stat">
        <div className="tw:stat-title">Cache Hits</div>
        <div className="tw:stat-value tw:text-success">{hits}</div>
        <div className="tw:stat-desc">Free (from database)</div>
      </div>
      <div className="tw:stat">
        <div className="tw:stat-title">API Calls</div>
        <div className="tw:stat-value">{calls}</div>
        <div className="tw:stat-desc">~${cost.toFixed(2)} estimated</div>
      </div>
      {note && (
        <div className="tw:stat">
          <div className="tw:stat-title">Cost Note</div>
          <div className="tw:stat-desc tw:text-sm">{note}</div>
        </div>
      )}
    </div>
  );
}

/**
 * DuplicateWarnings — alerts for orders with suspiciously close GPS coordinates.
 *
 * Non-blocking: shown alongside results, does not prevent route display.
 * Uses DaisyUI 5 `alert` + `collapse` components with tw: prefix.
 * Each cluster is expandable showing order IDs, addresses, and distance.
 */
function DuplicateWarnings({
  warnings,
  orderDriverMap,
}: {
  warnings: DuplicateLocationWarning[];
  orderDriverMap: Map<string, string>;
}) {
  if (!warnings || warnings.length === 0) return null;

  return (
    <div className="tw:mt-4">
      <div role="alert" className="tw:alert tw:alert-warning">
        <svg xmlns="http://www.w3.org/2000/svg" className="tw:h-5 tw:w-5 tw:shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
        </svg>
        <span>
          <strong>Duplicate Location Warning:</strong>{" "}
          {warnings.length} group{warnings.length !== 1 ? "s" : ""} of orders resolve to very similar GPS coordinates
        </span>
      </div>
      {warnings.map((cluster, idx) => {
        const firstAddr = cluster.addresses[0] ?? "";
        const truncAddr = firstAddr.length > 35 ? firstAddr.slice(0, 35) + "..." : firstAddr;
        return (
          <div key={idx} className="tw:collapse tw:collapse-arrow tw:bg-base-200 tw:mt-2">
            <input type="checkbox" />
            <div className="tw:collapse-title tw:text-sm tw:font-semibold">
              {cluster.order_ids.length} orders near {truncAddr} — within {cluster.max_distance_m.toFixed(0)}m of each other
            </div>
            <div className="tw:collapse-content">
              <ul className="tw:list-disc tw:pl-4 tw:space-y-1">
                {cluster.order_ids.map((id, i) => (
                  <li key={id}>
                    <strong>{id}</strong>: {cluster.addresses[i]}
                    {orderDriverMap.get(id) && (
                      <span className="tw:badge tw:badge-sm tw:badge-ghost tw:ml-2">
                        {orderDriverMap.get(id)}
                      </span>
                    )}
                  </li>
                ))}
              </ul>
              <p className="tw:text-xs text-muted-60 tw:mt-2">
                Different addresses resolving to nearby coordinates may indicate a data entry error.
                If these are intentional (e.g., neighboring buildings), no action is needed.
              </p>
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** Workflow states — drives the UI transitions. */
type WorkflowState =
  | "idle"            // No file selected, show drop zone
  | "selected"        // File chosen, ready to parse
  | "parsing"         // Parsing file (fast)
  | "driver-preview"  // Show driver checkbox table
  | "uploading"       // Geocoding + optimization in progress
  | "success"         // Routes generated, showing results
  | "error";          // Something went wrong

/** Status badge visual mapping for driver preview. */
const STATUS_BADGE_CLASS: Record<DriverPreview["status"], string> = {
  existing: "tw:badge-success",
  new: "tw:badge-info",
  matched: "tw:badge-warning",
  reactivated: "tw:badge-secondary",
};

const STATUS_BADGE_LABEL: Record<DriverPreview["status"], string> = {
  existing: "Existing",
  new: "New",
  matched: "Matched",
  reactivated: "Reactivated",
};

export function UploadRoutes() {
  // --- File upload state ---
  const [workflowState, setWorkflowState] = useState<WorkflowState>("idle");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [apiError, setApiError] = useState<ApiError | null>(null);
  const [uploadProgress, setUploadProgress] = useState<string>("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // --- Driver preview state (Phase 17) ---
  const [parseResult, setParseResult] = useState<ParsePreviewResponse | null>(null);
  const [selectedDrivers, setSelectedDrivers] = useState<Set<string>>(new Set());

  // --- Results state ---
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const [routes, setRoutes] = useState<RouteSummary[]>([]);
  const [routeDetails, setRouteDetails] = useState<Map<string, RouteDetail>>(new Map());
  const [qrData, setQrData] = useState<Map<string, GoogleMapsRouteResponse>>(new Map());
  const [expandedRoute, setExpandedVehicle] = useState<string | null>(null);

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

  /**
   * Helper to create a synthetic ApiError for client-side validation errors.
   * These never hit the backend, so we generate a local error shape.
   */
  const makeSyntheticError = (code: string, message: string): ApiError => ({
    success: false,
    error_code: code,
    user_message: message,
    technical_message: "",
    request_id: "",
    timestamp: new Date().toISOString(),
    help_url: "",
  });

  const validateAndSelectFile = (file: File) => {
    const validExtensions = [".csv", ".xlsx", ".xls"];
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();

    if (!validExtensions.includes(ext)) {
      setApiError(makeSyntheticError("UPLOAD_INVALID_FORMAT", "Please upload a .csv, .xlsx, or .xls file"));
      setWorkflowState("error");
      return;
    }

    // 10 MB max (matches backend limit)
    if (file.size > 10 * 1024 * 1024) {
      setApiError(makeSyntheticError("UPLOAD_FILE_TOO_LARGE", "File too large. Maximum size is 10 MB."));
      setWorkflowState("error");
      return;
    }

    setSelectedFile(file);
    setApiError(null);
    setWorkflowState("selected");
  };

  // --- Upload & Parse (Step 1: parse file, show driver preview) ---
  const handleUpload = useCallback(async () => {
    if (!selectedFile) return;

    setWorkflowState("parsing");
    setUploadProgress("Parsing file...");

    try {
      const result = await parseUpload(selectedFile);
      setParseResult(result);
      // Select all drivers by default (per CONTEXT.md decision)
      setSelectedDrivers(new Set(result.drivers.map(d => d.csv_name)));
      setWorkflowState("driver-preview");
      setUploadProgress("");
    } catch (err) {
      if (err instanceof ApiUploadError) {
        setApiError(err.apiError);
      } else if (isApiError(err)) {
        setApiError(err as ApiError);
      } else {
        setApiError(makeSyntheticError(
          "PARSE_FAILED",
          err instanceof Error ? err.message : "Failed to parse file. Please try again."
        ));
      }
      setWorkflowState("error");
      setUploadProgress("");
    }
  }, [selectedFile]);

  // --- Process Selected Drivers (Step 2: geocode + optimize selected) ---
  const handleProcessSelected = useCallback(async () => {
    if (!parseResult) return;

    setWorkflowState("uploading");
    setUploadProgress("Processing orders & optimizing routes...");

    try {
      const driverList = Array.from(selectedDrivers);
      const result = await processSelected(parseResult.upload_token, driverList);
      setUploadResult(result);

      // Derive geocoded count with backward-compat fallback
      const geocodedCount = result.geocoded ?? result.orders_assigned ?? 0;

      // Only fetch routes if some orders were geocoded successfully
      if (geocodedCount > 0) {
        // Fetch route summaries
        setUploadProgress("Loading route details...");
        const routesRes = await fetchRoutes();
        setRoutes(routesRes.routes);

        // Fetch details for all vehicles in parallel
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

        // Fetch QR codes for all vehicles in parallel
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
      if (err instanceof ApiUploadError) {
        setApiError(err.apiError);
      } else if (isApiError(err)) {
        setApiError(err as ApiError);
      } else {
        setApiError(makeSyntheticError(
          "INTERNAL_ERROR",
          err instanceof Error ? err.message : "Processing failed. Please try again."
        ));
      }
      setWorkflowState("error");
      setUploadProgress("");
    }
  }, [parseResult, selectedDrivers]);

  // --- Back to upload (clean reset) ---
  const handleBackToUpload = useCallback(() => {
    setWorkflowState("idle");
    setSelectedFile(null);
    setParseResult(null);
    setSelectedDrivers(new Set());
    setApiError(null);
    setUploadProgress("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }, []);

  // --- Driver selection handlers ---
  const toggleDriver = useCallback((csvName: string) => {
    setSelectedDrivers(prev => {
      const next = new Set(prev);
      if (next.has(csvName)) next.delete(csvName);
      else next.add(csvName);
      return next;
    });
  }, []);

  const toggleAll = useCallback(() => {
    if (!parseResult) return;
    setSelectedDrivers(prev => {
      if (prev.size === parseResult.drivers.length) return new Set();
      return new Set(parseResult.drivers.map(d => d.csv_name));
    });
  }, [parseResult]);

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
    setParseResult(null);
    setSelectedDrivers(new Set());
    setUploadResult(null);
    setRoutes([]);
    setRouteDetails(new Map());
    setQrData(new Map());
    setApiError(null);
    setExpandedVehicle(null);
    setUploadProgress("");
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  // --- Toggle expanded route for QR details ---
  const toggleRoute = (vehicleId: string) => {
    setExpandedVehicle(expandedRoute === vehicleId ? null : vehicleId);
  };

  // --- Render ---
  return (
    <div className="upload-routes">
      {/* Upload Section — visible in idle, selected, parsing, and error states */}
      {(workflowState === "idle" || workflowState === "selected" || workflowState === "parsing" || workflowState === "error") && (
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
            } ${workflowState === "parsing" ? "uploading" : ""}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            onClick={() => workflowState !== "parsing" && fileInputRef.current?.click()}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv,.xlsx,.xls"
              onChange={handleFileInput}
              className="file-input-hidden"
            />

            {workflowState === "parsing" ? (
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
                <span className="drop-hint">.csv, .xlsx, or .xls -- max 10 MB</span>
              </div>
            )}
          </div>

          {/* Upload & Preview Button */}
          {workflowState === "selected" && (
            <button className="upload-btn" onClick={handleUpload}>
              Upload & Preview
            </button>
          )}

          {/* Error Display -- structured error banner with details toggle */}
          {workflowState === "error" && apiError && (
            <ErrorBanner
              error={apiError}
              onRetry={handleReset}
              onDismiss={() => {
                setApiError(null);
                setWorkflowState("idle");
              }}
            />
          )}
        </div>
      )}

      {/* Driver Preview Section — shown after parse, before processing */}
      {workflowState === "driver-preview" && parseResult && (
        <div className="upload-section driver-preview">
          <div className="driver-preview-header">
            <h2>Driver Preview</h2>
            <p className="tw:text-sm" style={{ color: "var(--color-text-muted)" }}>
              {parseResult.filename}
            </p>
          </div>

          {/* Stats Bar */}
          <div className="tw:stats tw:stats-horizontal tw:shadow tw:w-full tw:mb-4 driver-preview-stats">
            <div className="tw:stat tw:py-2 tw:px-4">
              <div className="tw:stat-title tw:text-xs">Drivers</div>
              <div className="tw:stat-value tw:text-lg numeric">{parseResult.drivers.length}</div>
            </div>
            <div className="tw:stat tw:py-2 tw:px-4">
              <div className="tw:stat-title tw:text-xs">Orders</div>
              <div className="tw:stat-value tw:text-lg numeric">{parseResult.filtered_rows}</div>
            </div>
            {parseResult.drivers.filter(d => d.status === "new").length > 0 && (
              <div className="tw:stat tw:py-2 tw:px-4">
                <div className="tw:stat-title tw:text-xs">New</div>
                <div className="tw:stat-value tw:text-lg tw:text-info numeric">
                  {parseResult.drivers.filter(d => d.status === "new").length}
                </div>
              </div>
            )}
            {parseResult.drivers.filter(d => d.status === "matched").length > 0 && (
              <div className="tw:stat tw:py-2 tw:px-4">
                <div className="tw:stat-title tw:text-xs">Matched</div>
                <div className="tw:stat-value tw:text-lg tw:text-warning numeric">
                  {parseResult.drivers.filter(d => d.status === "matched").length}
                </div>
              </div>
            )}
            {parseResult.drivers.filter(d => d.status === "reactivated").length > 0 && (
              <div className="tw:stat tw:py-2 tw:px-4">
                <div className="tw:stat-title tw:text-xs">Reactivated</div>
                <div className="tw:stat-value tw:text-lg numeric" style={{ color: "oklch(55% 0.2 310)" }}>
                  {parseResult.drivers.filter(d => d.status === "reactivated").length}
                </div>
              </div>
            )}
          </div>

          {/* Select All / Deselect All toggle */}
          <div className="tw:flex tw:items-center tw:justify-between tw:mb-3">
            <label className="tw:flex tw:items-center tw:gap-2 tw:cursor-pointer">
              <input
                type="checkbox"
                className="tw:checkbox tw:checkbox-sm"
                checked={selectedDrivers.size === parseResult.drivers.length}
                ref={(el) => {
                  if (el) el.indeterminate = selectedDrivers.size > 0 && selectedDrivers.size < parseResult.drivers.length;
                }}
                onChange={toggleAll}
              />
              <span className="tw:text-sm tw:font-semibold">
                {selectedDrivers.size === parseResult.drivers.length
                  ? "Deselect All"
                  : `Select All (${parseResult.drivers.length})`}
              </span>
            </label>
            <span className="tw:text-sm" style={{ color: "var(--color-text-muted)" }}>
              {selectedDrivers.size} of {parseResult.drivers.length} selected
            </span>
          </div>

          {/* Driver Checkbox Table */}
          <div className="tw:overflow-x-auto tw:rounded-lg tw:border tw:border-base-300">
            <table className="tw:table tw:table-sm">
              <thead>
                <tr>
                  <th className="tw:w-10"></th>
                  <th>Driver</th>
                  <th className="tw:text-right">Orders</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {parseResult.drivers.map(d => (
                  <tr key={d.csv_name} className={selectedDrivers.has(d.csv_name) ? "" : "tw:opacity-50"}>
                    <th>
                      <label>
                        <input
                          type="checkbox"
                          className="tw:checkbox tw:checkbox-sm"
                          checked={selectedDrivers.has(d.csv_name)}
                          onChange={() => toggleDriver(d.csv_name)}
                        />
                      </label>
                    </th>
                    <td>
                      <div className="tw:font-medium">{d.display_name}</div>
                      {d.status === "matched" && d.matched_to && d.match_score != null && (
                        <div className="tw:text-xs tw:pl-4 tw:mt-0.5" style={{ color: "var(--color-warning, #d97706)" }}>
                          &ldquo;{d.csv_name}&rdquo; &rarr; {d.matched_to} ({d.match_score}%)
                        </div>
                      )}
                      {d.status === "reactivated" && d.matched_to && (
                        <div className="tw:text-xs tw:pl-4 tw:mt-0.5" style={{ color: "oklch(55% 0.2 310)" }}>
                          Reactivated: was deactivated
                        </div>
                      )}
                    </td>
                    <td className="tw:text-right numeric tw:font-semibold">{d.order_count}</td>
                    <td>
                      <span className={`tw:badge tw:badge-sm ${STATUS_BADGE_CLASS[d.status]}`}
                        style={d.status === "reactivated" ? { backgroundColor: "oklch(55% 0.2 310)", color: "white" } : undefined}
                      >
                        {STATUS_BADGE_LABEL[d.status]}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Action Buttons */}
          <div className="tw:flex tw:justify-between tw:mt-4 tw:gap-3">
            <button
              className="tw:btn tw:btn-ghost tw:gap-1"
              onClick={handleBackToUpload}
            >
              <ArrowLeft size={16} /> Back
            </button>
            <button
              className="tw:btn tw:btn-warning tw:flex-1 tw:gap-2"
              onClick={handleProcessSelected}
              disabled={selectedDrivers.size === 0}
            >
              Process Selected ({selectedDrivers.size}) <ArrowRight size={16} />
            </button>
          </div>
        </div>
      )}

      {/* Upload Progress Section — shown during geocoding/optimization */}
      {workflowState === "uploading" && (
        <div className="upload-section">
          <div className="upload-header">
            <h2>Processing Orders</h2>
            <p className="upload-subtitle">
              Geocoding addresses and optimizing routes for {selectedDrivers.size} driver{selectedDrivers.size !== 1 ? "s" : ""}
            </p>
          </div>
          <div className="drop-zone uploading">
            <div className="upload-progress">
              <div className="spinner" />
              <span className="progress-text">{uploadProgress}</span>
            </div>
          </div>
        </div>
      )}

      {/* Results Section */}
      {workflowState === "success" && (
        <div className="results-section">
          {/* Import Summary — only shown after a fresh upload with diagnostics */}
          {uploadResult && (
            <ImportSummary
              uploadResult={uploadResult}
              onReupload={() => fileInputRef.current?.click()}
            />
          )}

          {/* Geocoding cost summary — shows cache hits vs API calls (GEO-04) */}
          {uploadResult && <CostSummary uploadResult={uploadResult} />}

          {/* Duplicate location warnings — non-blocking alerts for suspicious clusters (GEO-03) */}
          {uploadResult && (() => {
            const orderDriverMap = new Map<string, string>();
            routeDetails.forEach((detail) => {
              detail.stops.forEach((stop) => {
                orderDriverMap.set(stop.order_id, detail.vehicle_id);
              });
            });
            return (
              <DuplicateWarnings
                warnings={uploadResult.duplicate_warnings ?? []}
                orderDriverMap={orderDriverMap}
              />
            );
          })()}

          {/* Route cards — shown when routes exist (fresh upload or loaded from API) */}
          {routes.length > 0 && (
            <>
              {/* Summary Bar */}
              <div className="results-header">
                <div>
                  <h2 className="tw:text-xl tw:font-bold tw:text-base-content tw:mb-3">Routes Generated</h2>
                  {uploadResult ? (
                    <div className="tw:stats tw:stats-horizontal tw:shadow tw:bg-base-100">
                      <div className="tw:stat tw:py-2 tw:px-4">
                        <div className="tw:stat-title tw:text-xs">Orders</div>
                        <div className="tw:stat-value tw:text-lg numeric">{uploadResult.orders_assigned}</div>
                      </div>
                      <div className="tw:stat tw:py-2 tw:px-4">
                        <div className="tw:stat-title tw:text-xs">Drivers</div>
                        <div className="tw:stat-value tw:text-lg numeric">{uploadResult.vehicles_used}</div>
                      </div>
                      {uploadResult.orders_unassigned > 0 && (
                        <div className="tw:stat tw:py-2 tw:px-4">
                          <div className="tw:stat-title tw:text-xs">Unassigned</div>
                          <div className="tw:stat-value tw:text-lg tw:text-error numeric">{uploadResult.orders_unassigned}</div>
                        </div>
                      )}
                      <div className="tw:stat tw:py-2 tw:px-4">
                        <div className="tw:stat-title tw:text-xs">Solve Time</div>
                        <div className="tw:stat-value tw:text-lg numeric">{uploadResult.optimization_time_ms.toFixed(0)} ms</div>
                      </div>
                    </div>
                  ) : routes.length > 0 && (
                    <div className="tw:stats tw:stats-horizontal tw:shadow tw:bg-base-100">
                      <div className="tw:stat tw:py-2 tw:px-4">
                        <div className="tw:stat-title tw:text-xs">Stops</div>
                        <div className="tw:stat-value tw:text-lg numeric">{routes.reduce((s, r) => s + r.total_stops, 0)}</div>
                      </div>
                      <div className="tw:stat tw:py-2 tw:px-4">
                        <div className="tw:stat-title tw:text-xs">Drivers</div>
                        <div className="tw:stat-value tw:text-lg numeric">{routes.length}</div>
                      </div>
                      <div className="tw:stat tw:py-2 tw:px-4">
                        <div className="tw:stat-title tw:text-xs">Distance</div>
                        <div className="tw:stat-value tw:text-lg numeric">{routes.reduce((s, r) => s + r.total_distance_km, 0).toFixed(1)} km</div>
                      </div>
                      <div className="tw:stat tw:py-2 tw:px-4">
                        <div className="tw:stat-title tw:text-xs">Weight</div>
                        <div className="tw:stat-value tw:text-lg numeric">{routes.reduce((s, r) => s + r.total_weight_kg, 0).toFixed(1)} kg</div>
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

              {/* Driver Route Cards */}
              <div className="route-cards">
            {routes.map((route) => {
              const detail = routeDetails.get(route.vehicle_id);
              const routeQr = qrData.get(route.vehicle_id);
              const isExpanded = expandedRoute === route.vehicle_id;

              return (
                <div
                  key={route.vehicle_id}
                  className="tw:card tw:bg-base-100 tw:shadow-sm tw:border tw:border-base-300"
                >
                  <div className="tw:card-body tw:p-4">
                    <div
                      className="tw:flex tw:items-center tw:justify-between tw:cursor-pointer"
                      onClick={() => toggleRoute(route.vehicle_id)}
                    >
                      <h2 className="tw:card-title tw:text-sm tw:gap-2">
                        <span className="tw:font-semibold">{route.vehicle_id}</span>
                      </h2>
                      <div className="tw:flex tw:items-center tw:gap-2">
                        {detail && <StatusBadge status={deriveRouteStatus(detail.stops)} />}
                        <span className={`expand-arrow ${isExpanded ? "open" : ""}`}>▼</span>
                      </div>
                    </div>
                    <div className="tw:flex tw:gap-4 tw:mt-2">
                      <span className="numeric"><strong>{route.total_stops}</strong> stops</span>
                      <span className="numeric"><strong>{route.total_distance_km.toFixed(1)}</strong> km</span>
                      <span className="numeric"><strong>{Math.round(route.total_duration_minutes)}</strong> min</span>
                      <span className="numeric"><strong>{route.total_weight_kg.toFixed(1)}</strong> kg</span>
                    </div>

                    {/* Expanded: QR codes + stop list */}
                    {isExpanded && (
                      <div className="tw:mt-4 tw:border-t tw:border-base-300 tw:pt-4">
                        {/* QR Codes */}
                        {routeQr && (
                          <div className="qr-section">
                            <h4 className="qr-heading">
                              Google Maps QR Code{routeQr.total_segments > 1 ? "s" : ""}
                            </h4>
                            {routeQr.total_segments > 1 && (
                              <p className="qr-note">
                                Route split into {routeQr.total_segments} parts
                                (Google Maps supports max 11 stops per URL)
                              </p>
                            )}
                            <div className="qr-grid">
                              {routeQr.segments.map((seg) => (
                                <div key={seg.segment} className="qr-card">
                                  {routeQr.total_segments > 1 && (
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
                                    {stop.address_raw && stop.address_raw !== stop.address && (
                                      <span className="stop-address-raw">{stop.address_raw}</span>
                                    )}
                                    <span className="stop-meta">
                                      <span className="numeric">{Number(stop.weight_kg).toFixed(1)} kg</span> ·{" "}
                                      <span className="numeric">{stop.quantity} cyl</span> ·{" "}
                                      <span className="numeric">{Number(stop.distance_from_prev_km).toFixed(1)} km</span> from prev
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
