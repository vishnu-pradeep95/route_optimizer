/**
 * DriverManagement -- View, create, edit, and deactivate drivers.
 *
 * Why a dedicated drivers page instead of embedding in Fleet:
 * Drivers are standalone entities (not vehicle accessories). They need
 * their own management UI for adding, renaming, and deactivating.
 * The fuzzy name matching warns operators about potential duplicates.
 *
 * Data flow:
 * 1. On mount: fetch GET /api/drivers for the full list
 * 2. "Add Driver" opens an inline form at the top
 * 3. "Edit" per-row replaces that row with an editable name input
 * 4. "Deactivate" / "Reactivate" toggles is_active via DELETE / PUT
 * 5. After any mutation: re-fetch the list to stay in sync with the server
 *
 * Fuzzy matching:
 * On blur of the name input (add or edit), we call GET /api/drivers/check-name
 * and display a warning banner if similar drivers exist. The operator can
 * proceed despite the warning -- auto-merge only happens during CSV upload.
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { Users, Pencil, RotateCw, X, Check, Plus } from "lucide-react";
import {
  fetchDrivers,
  createDriver,
  updateDriver,
  deleteDriver,
  checkDriverName,
} from "../lib/api";
import { EmptyState } from "../components/EmptyState";
import { ErrorBanner } from "../components/ErrorBanner";
import { isApiError } from "../lib/errors";
import type { ApiError } from "../lib/errors";
import type { Driver } from "../types";
import "./DriverManagement.css";

/** Shape of a fuzzy match warning. */
interface SimilarMatch {
  id: string;
  name: string;
  score: number;
  is_active: boolean;
}

export function DriverManagement() {
  // --- State ---
  const [drivers, setDrivers] = useState<Driver[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [addingNew, setAddingNew] = useState(false);
  const [newDriverName, setNewDriverName] = useState("");
  const [editDriverName, setEditDriverName] = useState("");
  const [similarWarnings, setSimilarWarnings] = useState<SimilarMatch[]>([]);
  const [saving, setSaving] = useState(false);

  const nameInputRef = useRef<HTMLInputElement>(null);
  const editInputRef = useRef<HTMLInputElement>(null);

  // --- Data fetching ---

  const loadDrivers = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchDrivers();
      setDrivers(data.drivers);
      setError(null);
    } catch (err) {
      if (isApiError(err)) {
        setError(err as ApiError);
      } else {
        setError({
          success: false,
          error_code: "INTERNAL_ERROR",
          user_message: err instanceof Error ? err.message : "Failed to load drivers",
          technical_message: "",
          request_id: "",
          timestamp: new Date().toISOString(),
          help_url: "",
        });
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDrivers();
  }, [loadDrivers]);

  // --- Fuzzy name check ---

  const handleNameBlur = useCallback(async (name: string, excludeId?: string) => {
    if (!name.trim()) {
      setSimilarWarnings([]);
      return;
    }
    try {
      const result = await checkDriverName(name.trim(), excludeId);
      setSimilarWarnings(result.similar_drivers);
    } catch {
      // Silently fail -- fuzzy check is informational
      setSimilarWarnings([]);
    }
  }, []);

  // --- Add driver ---

  const handleStartAdd = useCallback(() => {
    setAddingNew(true);
    setEditingId(null);
    setNewDriverName("");
    setSimilarWarnings([]);
    setTimeout(() => nameInputRef.current?.focus(), 50);
  }, []);

  const handleCancelAdd = useCallback(() => {
    setAddingNew(false);
    setNewDriverName("");
    setSimilarWarnings([]);
  }, []);

  const handleSaveNew = useCallback(async () => {
    const trimmed = newDriverName.trim();
    if (!trimmed) return;

    try {
      setSaving(true);
      await createDriver(trimmed);
      setAddingNew(false);
      setNewDriverName("");
      setSimilarWarnings([]);
      await loadDrivers();
    } catch (err) {
      if (isApiError(err)) {
        setError(err as ApiError);
      } else {
        setError({
          success: false,
          error_code: "INTERNAL_ERROR",
          user_message: err instanceof Error ? err.message : "Failed to create driver",
          technical_message: "",
          request_id: "",
          timestamp: new Date().toISOString(),
          help_url: "",
        });
      }
    } finally {
      setSaving(false);
    }
  }, [newDriverName, loadDrivers]);

  // --- Edit driver ---

  const handleStartEdit = useCallback((driver: Driver) => {
    setEditingId(driver.id);
    setEditDriverName(driver.name);
    setAddingNew(false);
    setSimilarWarnings([]);
    setTimeout(() => editInputRef.current?.focus(), 50);
  }, []);

  const handleCancelEdit = useCallback(() => {
    setEditingId(null);
    setEditDriverName("");
    setSimilarWarnings([]);
  }, []);

  const handleSaveEdit = useCallback(async () => {
    if (!editingId) return;
    const trimmed = editDriverName.trim();
    if (!trimmed) return;

    try {
      setSaving(true);
      await updateDriver(editingId, { name: trimmed });
      setEditingId(null);
      setEditDriverName("");
      setSimilarWarnings([]);
      await loadDrivers();
    } catch (err) {
      if (isApiError(err)) {
        setError(err as ApiError);
      } else {
        setError({
          success: false,
          error_code: "INTERNAL_ERROR",
          user_message: err instanceof Error ? err.message : "Failed to update driver",
          technical_message: "",
          request_id: "",
          timestamp: new Date().toISOString(),
          help_url: "",
        });
      }
    } finally {
      setSaving(false);
    }
  }, [editingId, editDriverName, loadDrivers]);

  // --- Toggle active status ---

  const handleToggleActive = useCallback(async (driver: Driver) => {
    try {
      if (driver.is_active) {
        await deleteDriver(driver.id);
      } else {
        await updateDriver(driver.id, { is_active: true });
      }
      await loadDrivers();
    } catch (err) {
      if (isApiError(err)) {
        setError(err as ApiError);
      } else {
        setError({
          success: false,
          error_code: "INTERNAL_ERROR",
          user_message: err instanceof Error ? err.message : "Failed to update driver status",
          technical_message: "",
          request_id: "",
          timestamp: new Date().toISOString(),
          help_url: "",
        });
      }
    }
  }, [loadDrivers]);

  // --- Key handlers ---

  const handleAddKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSaveNew();
    } else if (e.key === "Escape") {
      handleCancelAdd();
    }
  }, [handleSaveNew, handleCancelAdd]);

  const handleEditKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleSaveEdit();
    } else if (e.key === "Escape") {
      handleCancelEdit();
    }
  }, [handleSaveEdit, handleCancelEdit]);

  // --- Fuzzy warning banner ---

  const renderFuzzyWarning = () => {
    if (similarWarnings.length === 0) return null;
    return (
      <div className="driver-fuzzy-warning" role="alert">
        <strong>Similar driver(s) found:</strong>
        <ul>
          {similarWarnings.map((m) => (
            <li key={m.id}>
              {m.name} ({Math.round(m.score)}% match, {m.is_active ? "active" : "inactive"})
            </li>
          ))}
        </ul>
        <span>Continue to create a new driver, or cancel.</span>
      </div>
    );
  };

  // --- Render ---

  // Loading state
  if (loading && drivers.length === 0) {
    return (
      <div className="driver-page">
        <div className="tw:flex tw:items-center tw:justify-center tw:h-full">
          <span className="tw:loading tw:loading-spinner tw:loading-lg" />
        </div>
      </div>
    );
  }

  // Empty state
  if (!loading && drivers.length === 0 && !addingNew && !error) {
    return (
      <div className="driver-page">
        <EmptyState
          icon={Users}
          title="No drivers yet"
          description="Drivers are automatically created when you upload a CDCMS file, or you can add them manually."
          actionLabel="Add Driver"
          onAction={handleStartAdd}
        />
        {addingNew && renderAddForm()}
      </div>
    );
  }

  function renderAddForm() {
    return (
      <div className="driver-form-container">
        <h3>Add Driver</h3>
        <div className="driver-form">
          <div className="driver-form-field">
            <label htmlFor="new-driver-name">Name</label>
            <input
              ref={nameInputRef}
              id="new-driver-name"
              type="text"
              className="tw:input tw:input-bordered tw:input-sm"
              placeholder="e.g. Suresh Kumar"
              value={newDriverName}
              onChange={(e) => setNewDriverName(e.target.value)}
              onBlur={() => handleNameBlur(newDriverName)}
              onKeyDown={handleAddKeyDown}
              maxLength={100}
              disabled={saving}
            />
          </div>
          <div className="driver-form-actions">
            <button
              type="button"
              className="tw:btn tw:btn-primary tw:btn-sm"
              onClick={handleSaveNew}
              disabled={!newDriverName.trim() || saving}
            >
              <Check size={14} /> Save
            </button>
            <button
              type="button"
              className="tw:btn tw:btn-ghost tw:btn-sm"
              onClick={handleCancelAdd}
              disabled={saving}
            >
              <X size={14} /> Cancel
            </button>
          </div>
        </div>
        {renderFuzzyWarning()}
      </div>
    );
  }

  return (
    <div className="driver-page">
      {/* Header */}
      <div className="driver-header">
        <h2>Drivers</h2>
        <div className="driver-header-actions">
          <button
            type="button"
            className="tw:btn tw:btn-ghost tw:btn-sm"
            onClick={loadDrivers}
            title="Refresh driver list"
          >
            <RotateCw size={14} />
          </button>
          {!addingNew && (
            <button
              type="button"
              className="tw:btn tw:btn-primary tw:btn-sm"
              onClick={handleStartAdd}
            >
              <Plus size={14} /> Add Driver
            </button>
          )}
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="tw:px-6 tw:pt-4">
          <ErrorBanner
            error={error}
            onRetry={loadDrivers}
            onDismiss={() => setError(null)}
          />
        </div>
      )}

      {/* Add form */}
      {addingNew && renderAddForm()}

      {/* Table */}
      <div className="driver-table-wrapper">
        <table className="tw:table tw:table-zebra tw:w-full">
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th>Routes</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {drivers.map((driver) => {
              if (editingId === driver.id) {
                // Edit row
                return (
                  <tr key={driver.id} className="driver-edit-row">
                    <td>
                      <input
                        ref={editInputRef}
                        type="text"
                        className="tw:input tw:input-bordered tw:input-sm tw:w-full"
                        value={editDriverName}
                        onChange={(e) => setEditDriverName(e.target.value)}
                        onBlur={() => handleNameBlur(editDriverName, driver.id)}
                        onKeyDown={handleEditKeyDown}
                        maxLength={100}
                        disabled={saving}
                      />
                      {renderFuzzyWarning()}
                    </td>
                    <td>
                      <span className={`tw:badge ${driver.is_active ? "tw:badge-success" : "tw:badge-ghost"}`}>
                        {driver.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td>{driver.route_count}</td>
                    <td>
                      <div className="driver-actions">
                        <button
                          type="button"
                          className="tw:btn tw:btn-primary tw:btn-xs"
                          onClick={handleSaveEdit}
                          disabled={!editDriverName.trim() || saving}
                          title="Save"
                        >
                          <Check size={12} />
                        </button>
                        <button
                          type="button"
                          className="tw:btn tw:btn-ghost tw:btn-xs"
                          onClick={handleCancelEdit}
                          disabled={saving}
                          title="Cancel"
                        >
                          <X size={12} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              }

              // Display row
              return (
                <tr key={driver.id}>
                  <td>{driver.name}</td>
                  <td>
                    <span className={`tw:badge ${driver.is_active ? "tw:badge-success" : "tw:badge-ghost"}`}>
                      {driver.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td>{driver.route_count}</td>
                  <td>
                    <div className="driver-actions">
                      <button
                        type="button"
                        className="tw:btn tw:btn-ghost tw:btn-xs"
                        onClick={() => handleStartEdit(driver)}
                        title="Edit name"
                      >
                        <Pencil size={12} />
                      </button>
                      <button
                        type="button"
                        className={`tw:btn tw:btn-xs ${driver.is_active ? "tw:btn-warning" : "tw:btn-success"}`}
                        onClick={() => handleToggleActive(driver)}
                        title={driver.is_active ? "Deactivate" : "Reactivate"}
                      >
                        {driver.is_active ? "Deactivate" : "Reactivate"}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
