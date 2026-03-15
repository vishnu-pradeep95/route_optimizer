/**
 * Settings -- Dashboard settings page for API key, geocode cache, upload history,
 * and validation history.
 *
 * Four card sections stacked vertically:
 * 1. Google Maps API Key -- view masked key, update with validation
 * 2. Geocode Cache -- stats, export, import, clear with confirmation modal
 * 3. Upload History -- compact table of recent optimization runs
 * 4. Validation History -- cumulative Google Routes validation stats and recent results
 *
 * Data flow:
 * On mount: parallel fetch of settings, cache stats, recent runs, and validation stats.
 * Mutations: save API key, export/import/clear cache -- each updates local state.
 *
 * Follows patterns from DriverManagement.tsx (mutations) and RunHistory.tsx (data fetching).
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { Key, Database, ClipboardList, Download, Upload, Trash2, ShieldCheck } from "lucide-react";
import {
  fetchSettings,
  updateApiKey,
  fetchGeocodeStats,
  exportGeocodeCache,
  importGeocodeCache,
  clearGeocodeCache,
  fetchRuns,
  fetchValidationStats,
  fetchRecentValidations,
} from "../lib/api";
import { EmptyState } from "../components/EmptyState";
import { StatusBadge } from "../components/StatusBadge";
import type {
  GeocodeStats,
  CacheImportResult,
  OptimizationRun,
  ValidationStats,
  RecentValidation,
} from "../types";
import "./Settings.css";

/**
 * Mask an API key for display: show first 4 and last 4 characters.
 * Example: "AIzaSyB1234...5678" -> "AIza***...5678"
 */
function maskApiKey(key: string | null): string {
  if (!key || key.length < 8) return key ?? "";
  return `${key.slice(0, 4)}***...***${key.slice(-4)}`;
}

/**
 * Format ISO timestamp to compact local date/time for the upload history table.
 * Uses en-IN locale for Indian date formatting conventions.
 */
function formatShortDate(iso: string): string {
  return new Date(iso).toLocaleString("en-IN", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    hour12: true,
  });
}

export function Settings() {
  // --- API Key section state ---
  const [maskedKey, setMaskedKey] = useState<string | null>(null);
  const [hasApiKey, setHasApiKey] = useState(false);
  const [newApiKey, setNewApiKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveResult, setSaveResult] = useState<{ ok: boolean; msg: string } | null>(null);

  // --- Cache section state ---
  const [cacheStats, setCacheStats] = useState<GeocodeStats | null>(null);

  // --- Upload history section state ---
  const [runs, setRuns] = useState<OptimizationRun[]>([]);

  // --- Loading / error ---
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // --- Clear cache modal ---
  const [showClearModal, setShowClearModal] = useState(false);
  const [clearing, setClearing] = useState(false);

  // --- Import ---
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<CacheImportResult | null>(null);
  const importInputRef = useRef<HTMLInputElement>(null);

  // --- Export ---
  const [exporting, setExporting] = useState(false);

  // --- Validation history section state ---
  const [validationStats, setValidationStats] = useState<ValidationStats | null>(null);
  const [recentValidations, setRecentValidations] = useState<RecentValidation[]>([]);

  // --- Data loading ---

  const loadAll = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const [settingsData, statsData, runsData, valStats, valRecent] = await Promise.all([
        fetchSettings(),
        fetchGeocodeStats(),
        fetchRuns(10),
        fetchValidationStats().catch(() => null),
        fetchRecentValidations().catch(() => ({ validations: [] })),
      ]);

      // Settings
      setHasApiKey(settingsData.has_api_key);
      setMaskedKey(settingsData.google_maps_api_key);

      // Cache stats
      setCacheStats(statsData);

      // Runs
      setRuns(runsData.runs);

      // Validation history
      setValidationStats(valStats);
      setRecentValidations(valRecent.validations.slice(0, 10));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load settings");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // --- API Key handlers ---

  const handleSaveApiKey = useCallback(async () => {
    const trimmed = newApiKey.trim();
    if (!trimmed) return;

    try {
      setSaving(true);
      setSaveResult(null);
      const result = await updateApiKey(trimmed);
      setMaskedKey(result.masked_key);
      setHasApiKey(true);
      setNewApiKey("");
      setSaveResult({
        ok: result.valid,
        msg: result.valid
          ? "API key updated and validated"
          : `API key saved but validation failed: ${result.message}`,
      });
    } catch (err) {
      setSaveResult({
        ok: false,
        msg: err instanceof Error ? err.message : "Failed to save API key",
      });
    } finally {
      setSaving(false);
    }
  }, [newApiKey]);

  const handleApiKeyKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleSaveApiKey();
      }
    },
    [handleSaveApiKey]
  );

  // --- Cache handlers ---

  const handleExport = useCallback(async () => {
    try {
      setExporting(true);
      await exportGeocodeCache();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }, []);

  const handleImportClick = useCallback(() => {
    importInputRef.current?.click();
  }, []);

  const handleImportFile = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      setImporting(true);
      setImportResult(null);
      const result = await importGeocodeCache(file);
      setImportResult(result);
      // Refresh cache stats after import
      const stats = await fetchGeocodeStats();
      setCacheStats(stats);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
    } finally {
      setImporting(false);
      // Reset file input so the same file can be selected again
      if (importInputRef.current) importInputRef.current.value = "";
    }
  }, []);

  const handleClearConfirm = useCallback(async () => {
    try {
      setClearing(true);
      await clearGeocodeCache();
      setShowClearModal(false);
      // Refresh cache stats after clear
      const stats = await fetchGeocodeStats();
      setCacheStats(stats);
      setImportResult(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Clear failed");
    } finally {
      setClearing(false);
    }
  }, []);

  // --- Render: Loading state ---

  if (loading) {
    return (
      <div className="settings-page">
        <div className="settings-header">
          <h2>Settings</h2>
        </div>
        <div className="settings-content">
          <div className="tw:flex tw:items-center tw:justify-center tw:py-16">
            <span className="tw:loading tw:loading-spinner tw:loading-lg" />
          </div>
        </div>
      </div>
    );
  }

  // --- Render ---

  return (
    <div className="settings-page">
      <div className="settings-header">
        <h2>Settings</h2>
      </div>

      {/* Global error banner */}
      {error && (
        <div className="settings-error">
          <span>{error}</span>
          <button onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      <div className="settings-content">
        {/* ──────────── Card 1: Google Maps API Key ──────────── */}
        <div className="tw:card tw:bg-base-100 tw:shadow-sm settings-card">
          <div className="tw:card-body">
            <h3 className="tw:card-title tw:text-base tw:gap-2">
              <Key size={18} />
              Google Maps API Key
            </h3>

            {/* Current key status */}
            <div className="settings-key-status">
              {hasApiKey ? (
                <code className="settings-masked-key">{maskApiKey(maskedKey)}</code>
              ) : (
                <span className="tw:text-sm tw:opacity-50">Not configured</span>
              )}
            </div>

            {/* Update form */}
            <div className="settings-key-form">
              <input
                type="password"
                className="tw:input tw:input-bordered tw:input-sm tw:flex-1"
                placeholder="Enter new API key"
                value={newApiKey}
                onChange={(e) => {
                  setNewApiKey(e.target.value);
                  setSaveResult(null);
                }}
                onKeyDown={handleApiKeyKeyDown}
                disabled={saving}
                autoComplete="off"
              />
              <button
                className="tw:btn tw:btn-primary tw:btn-sm"
                onClick={handleSaveApiKey}
                disabled={!newApiKey.trim() || saving}
              >
                {saving ? (
                  <span className="tw:loading tw:loading-spinner tw:loading-xs" />
                ) : (
                  "Save"
                )}
              </button>
            </div>

            {/* Validation result */}
            {saveResult && (
              <div
                className={`tw:text-sm tw:mt-1 ${
                  saveResult.ok ? "tw:text-success" : "tw:text-error"
                }`}
              >
                {saveResult.msg}
              </div>
            )}

            <p className="tw:text-xs tw:opacity-50 tw:mt-1">
              Key is validated against Google Maps API before saving
            </p>
          </div>
        </div>

        {/* ──────────── Card 2: Geocode Cache ──────────── */}
        <div className="tw:card tw:bg-base-100 tw:shadow-sm settings-card">
          <div className="tw:card-body">
            <h3 className="tw:card-title tw:text-base tw:gap-2">
              <Database size={18} />
              Geocode Cache
            </h3>

            {/* Stats */}
            {cacheStats && (
              <div className="settings-stats">
                <div className="settings-stat">
                  <span className="settings-stat-value">
                    {cacheStats.total_entries.toLocaleString()}
                  </span>
                  <span className="settings-stat-label">Cached Addresses</span>
                </div>
                <div className="settings-stat">
                  <span className="settings-stat-value">
                    {cacheStats.api_calls_saved.toLocaleString()}
                  </span>
                  <span className="settings-stat-label">API Calls Saved</span>
                </div>
                <div className="settings-stat">
                  <span className="settings-stat-value">
                    ~INR {(cacheStats.estimated_savings_usd * 92.5).toFixed(2)}
                  </span>
                  <span className="settings-stat-label">Est. Savings</span>
                </div>
              </div>
            )}

            <p className="tw:text-xs tw:opacity-50">
              Based on Google Maps Geocoding API rate of ~INR 0.46 per request
            </p>

            {/* Action buttons */}
            <div className="settings-cache-actions">
              <button
                className="tw:btn tw:btn-outline tw:btn-sm"
                onClick={handleExport}
                disabled={exporting}
              >
                {exporting ? (
                  <span className="tw:loading tw:loading-spinner tw:loading-xs" />
                ) : (
                  <Download size={14} />
                )}
                Export Cache
              </button>
              <button
                className="tw:btn tw:btn-outline tw:btn-sm"
                onClick={handleImportClick}
                disabled={importing}
              >
                {importing ? (
                  <span className="tw:loading tw:loading-spinner tw:loading-xs" />
                ) : (
                  <Upload size={14} />
                )}
                Import Cache
              </button>
              <button
                className="tw:btn tw:btn-outline tw:btn-error tw:btn-sm"
                onClick={() => setShowClearModal(true)}
              >
                <Trash2 size={14} />
                Clear Cache
              </button>
            </div>

            {/* Hidden file input for import */}
            <input
              ref={importInputRef}
              type="file"
              accept=".json"
              className="tw:hidden"
              onChange={handleImportFile}
            />

            {/* Import result feedback */}
            {importResult && (
              <div className="tw:text-sm tw:text-success tw:mt-2">
                Added {importResult.added} entries, skipped {importResult.skipped} duplicates
              </div>
            )}
          </div>
        </div>

        {/* ──────────── Card 3: Upload History ──────────── */}
        <div className="tw:card tw:bg-base-100 tw:shadow-sm settings-card">
          <div className="tw:card-body">
            <h3 className="tw:card-title tw:text-base tw:gap-2">
              <ClipboardList size={18} />
              Recent Uploads
            </h3>

            {runs.length === 0 ? (
              <EmptyState
                icon={ClipboardList}
                title="No uploads yet"
                description="Upload a CDCMS file to generate optimized delivery routes."
              />
            ) : (
              <>
                <div className="tw:overflow-x-auto">
                  <table className="tw:table tw:table-sm tw:table-zebra">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Filename</th>
                        <th className="numeric">Drivers</th>
                        <th className="numeric">Orders</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {runs.map((run) => (
                        <tr key={run.run_id}>
                          <td className="tw:whitespace-nowrap">
                            {formatShortDate(run.created_at)}
                          </td>
                          <td className="settings-source-file">
                            {run.source_filename}
                          </td>
                          <td className="numeric">{run.vehicles_used}</td>
                          <td className="numeric">{run.total_orders}</td>
                          <td>
                            <StatusBadge status={run.status} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        </div>

        {/* ──────────── Card 4: Validation History ──────────── */}
        <div className="tw:card tw:bg-base-100 tw:shadow-sm settings-card">
          <div className="tw:card-body">
            <h3 className="tw:card-title tw:text-base tw:gap-2">
              <ShieldCheck size={18} />
              Validation History
            </h3>

            {/* Stats row */}
            {validationStats && (
              <div className="validation-stats-row">
                <div className="validation-stat">
                  <span className="settings-stat-value">
                    {validationStats.count}
                  </span>
                  <span className="settings-stat-label">Total Validations</span>
                </div>
                <div className="validation-stat">
                  <span className="settings-stat-value">
                    ~INR {validationStats.estimated_cost_inr.toFixed(2)}
                  </span>
                  <span className="settings-stat-label">Total Cost</span>
                </div>
                <div className="validation-stat">
                  <span className="settings-stat-value">~INR 0.93</span>
                  <span className="settings-stat-label">Per Validation</span>
                </div>
              </div>
            )}

            {/* Recent validations table or empty state */}
            {(!validationStats || validationStats.count === 0) ? (
              <EmptyState
                icon={ShieldCheck}
                title="No validations yet"
                description="Use the Validate button on route cards to compare OSRM routes against Google Routes API."
              />
            ) : (
              <div className="tw:overflow-x-auto">
                <table className="tw:table tw:table-sm tw:table-zebra">
                  <thead>
                    <tr>
                      <th>Driver</th>
                      <th className="numeric">Distance Delta</th>
                      <th>Confidence</th>
                      <th>Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentValidations.map((v, i) => (
                      <tr key={`${v.vehicle_id}-${i}`}>
                        <td>{v.vehicle_id}</td>
                        <td className="numeric">
                          {v.distance_delta_pct >= 0 ? "+" : ""}{v.distance_delta_pct.toFixed(1)}%
                        </td>
                        <td>
                          <span className={`tw:badge tw:badge-sm ${
                            v.confidence === "green"
                              ? "tw:badge-success"
                              : v.confidence === "amber"
                                ? "tw:badge-warning"
                                : "tw:badge-error"
                          }`}>
                            {v.confidence === "green" ? "Good" : v.confidence === "amber" ? "Fair" : "Poor"}
                          </span>
                        </td>
                        <td className="tw:whitespace-nowrap">
                          {formatShortDate(v.validated_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ──────────── Clear Cache Confirmation Modal ──────────── */}
      {showClearModal && (
        <div className="tw:modal tw:modal-open">
          <div className="tw:modal-box">
            <h3 className="tw:font-bold tw:text-lg">Clear Geocode Cache?</h3>
            <p className="tw:py-4">
              This will permanently delete all{" "}
              <strong>{cacheStats?.total_entries.toLocaleString() ?? 0}</strong>{" "}
              cached addresses. This action cannot be undone.
            </p>
            <div className="tw:modal-action">
              <button
                className="tw:btn"
                onClick={() => setShowClearModal(false)}
                disabled={clearing}
              >
                Cancel
              </button>
              <button
                className="tw:btn tw:btn-error"
                onClick={handleClearConfirm}
                disabled={clearing}
              >
                {clearing ? (
                  <span className="tw:loading tw:loading-spinner tw:loading-xs" />
                ) : null}
                Yes, Clear Cache
              </button>
            </div>
          </div>
          <div
            className="tw:modal-backdrop"
            onClick={() => !clearing && setShowClearModal(false)}
          />
        </div>
      )}
    </div>
  );
}
