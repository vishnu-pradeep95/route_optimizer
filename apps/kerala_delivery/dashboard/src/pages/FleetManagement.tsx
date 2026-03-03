/**
 * FleetManagement — View, create, edit, and deactivate vehicles.
 *
 * Why a dedicated fleet page instead of embedding in LiveMap:
 * Fleet configuration is an admin task (done once per vehicle, not daily).
 * Keeping it separate from the live ops view avoids accidental edits
 * during active deliveries and keeps each page focused on one workflow.
 *
 * Data flow:
 * 1. On mount: fetch GET /api/vehicles for the full list
 * 2. "Add Vehicle" opens an inline form at the top
 * 3. "Edit" per-row replaces that row with editable inputs
 * 4. "Deactivate" / "Reactivate" toggles is_active via DELETE / PUT
 * 5. After any mutation: re-fetch the list to stay in sync with the server
 *
 * Why inline forms instead of a modal dialog:
 * Modals interrupt the user's spatial context — they lose sight of the
 * table while editing. Inline forms keep the data visible, which reduces
 * errors when operators are comparing vehicles side-by-side.
 * See: https://www.nngroup.com/articles/modal-nonmodal-dialog/
 */

import { useState, useEffect, useCallback } from "react";
import { Pencil, Truck, Plus, RotateCw, X, Check } from "lucide-react";
import {
  fetchVehicles,
  createVehicle,
  updateVehicle,
  deleteVehicle,
} from "../lib/api";
import { EmptyState } from "../components/EmptyState";
import type { Vehicle } from "../types";
import "./FleetManagement.css";

// --- Constants ---

/**
 * Default depot coordinates: Vatakara, Kozhikode district.
 *
 * Why Vatakara: it's the actual HPCL LPG godown location for this business.
 * These defaults save operators from looking up coords for the primary depot.
 * Must stay in sync with apps/kerala_delivery/config.py DEPOT_LOCATION.
 */
const DEFAULT_DEPOT_LAT = 11.6244;
const DEFAULT_DEPOT_LNG = 75.5796;

/**
 * Default max payload in kg for a Piaggio Ape Xtra LDX.
 * 446 kg = 496 kg rated payload × 0.9 safety factor.
 * Source: plan/kerala_delivery_route_system_design.md, Section 3.
 * Also: apps/kerala_delivery/config.py VEHICLE_MAX_WEIGHT_KG
 *
 * Why 90%? Overloaded three-wheelers are unstable on narrow Kerala
 * roads — the 10% margin accounts for packaging weight, fuel, and
 * measurement errors.
 */
const DEFAULT_MAX_WEIGHT_KG = 446;

/**
 * Maximum rated payload for the Piaggio Ape Xtra LDX (kg).
 * This is the hard upper limit — no vehicle should be configured above this.
 * The effective limit (DEFAULT_MAX_WEIGHT_KG) applies the 90% safety factor.
 */
const MAX_RATED_PAYLOAD_KG = 496;

/**
 * Maximum allowed speed limit (km/h) — Kerala MVD directive.
 * Non-negotiable: the Motor Vehicles Department caps three-wheeler
 * delivery speeds at 40 km/h in urban zones after accidents linked
 * to quick-commerce delivery pressure.
 * Source: plan/kerala_delivery_route_system_design.md, Safety Constraints
 */
const MAX_SPEED_LIMIT_KMH = 40;

/** Default max items — matches apps/kerala_delivery/config.py DEFAULT_MAX_ITEMS. */
const DEFAULT_MAX_ITEMS = 40;

/**
 * Speed limit for urban Kerala zones (km/h).
 * Kerala MVD directive — 40 km/h cap in urban areas for safety.
 */
const DEFAULT_SPEED_LIMIT_KMH = 40;

// --- Types for form state ---

/** Shape of the "Add Vehicle" form. All fields are strings for controlled inputs. */
interface VehicleFormState {
  vehicle_id: string;
  registration_no: string;
  vehicle_type: "diesel" | "electric" | "cng";
  max_weight_kg: string;
  max_items: string;
  depot_latitude: string;
  depot_longitude: string;
  speed_limit_kmh: string;
}

/** Create a blank form with sensible defaults for Kerala operations. */
function emptyForm(): VehicleFormState {
  return {
    vehicle_id: "",
    registration_no: "",
    vehicle_type: "diesel",
    max_weight_kg: String(DEFAULT_MAX_WEIGHT_KG),
    max_items: String(DEFAULT_MAX_ITEMS),
    depot_latitude: String(DEFAULT_DEPOT_LAT),
    depot_longitude: String(DEFAULT_DEPOT_LNG),
    speed_limit_kmh: String(DEFAULT_SPEED_LIMIT_KMH),
  };
}

/** Populate form state from an existing vehicle (for editing). */
function vehicleToForm(v: Vehicle): VehicleFormState {
  return {
    vehicle_id: v.vehicle_id,
    registration_no: v.registration_no ?? "",
    vehicle_type: v.vehicle_type,
    max_weight_kg: String(v.max_weight_kg),
    max_items: String(v.max_items),
    depot_latitude: v.depot_latitude !== null ? String(v.depot_latitude) : String(DEFAULT_DEPOT_LAT),
    depot_longitude: v.depot_longitude !== null ? String(v.depot_longitude) : String(DEFAULT_DEPOT_LNG),
    speed_limit_kmh: String(v.speed_limit_kmh),
  };
}

// --- Component ---

export function FleetManagement() {
  // --- State ---

  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  /** Transient success message shown after create/update/delete. */
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  /** When true, only active vehicles are shown. */
  const [activeOnly, setActiveOnly] = useState(false);

  /** Controls visibility of the "Add Vehicle" form at the top. */
  const [showAddForm, setShowAddForm] = useState(false);
  const [addForm, setAddForm] = useState<VehicleFormState>(emptyForm());
  /** Tracks which mutation is in-flight to disable buttons. */
  const [saving, setSaving] = useState(false);

  /**
   * ID of the vehicle currently being edited inline.
   * null = no edit in progress. Only one row can be edited at a time
   * to avoid confusing partial-save states.
   */
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState<VehicleFormState>(emptyForm());

  // --- Data fetching ---

  /**
   * Load all vehicles from the API.
   *
   * Why useCallback: React's useEffect dependency array needs a stable
   * reference. Without useCallback, loadVehicles would be recreated
   * every render, causing an infinite fetch loop.
   * See: https://react.dev/reference/react/useCallback
   */
  const loadVehicles = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await fetchVehicles(activeOnly);
      setVehicles(data.vehicles);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load vehicles");
    } finally {
      setLoading(false);
    }
  }, [activeOnly]);

  useEffect(() => {
    loadVehicles();
  }, [loadVehicles]);

  /**
   * Auto-dismiss success messages after 4 seconds.
   *
   * Why a separate effect instead of a setTimeout in each handler:
   * Centralizing the auto-dismiss logic avoids race conditions when
   * multiple mutations happen in quick succession.
   */
  useEffect(() => {
    if (!successMsg) return;
    const timer = setTimeout(() => setSuccessMsg(null), 4000);
    return () => clearTimeout(timer);
  }, [successMsg]);

  // --- Mutation handlers ---

  /** Submit the "Add Vehicle" form. */
  const handleCreate = useCallback(async () => {
    // Validate required fields before sending to API
    if (!addForm.vehicle_id.trim()) {
      setError("Vehicle ID is required.");
      return;
    }

    const lat = parseFloat(addForm.depot_latitude);
    const lng = parseFloat(addForm.depot_longitude);
    if (isNaN(lat) || isNaN(lng)) {
      setError("Depot latitude and longitude must be valid numbers.");
      return;
    }

    // --- CRITICAL safety validations (Kerala MVD + design doc) ---

    // Speed limit: Kerala MVD directive caps three-wheelers at 40 km/h.
    // Allowing higher values would suppress speed alerts, defeating
    // the safety system. Non-negotiable.
    const speedLimit = parseFloat(addForm.speed_limit_kmh);
    if (!isNaN(speedLimit) && speedLimit > MAX_SPEED_LIMIT_KMH) {
      setError(`Speed limit cannot exceed ${MAX_SPEED_LIMIT_KMH} km/h (Kerala MVD safety rule).`);
      return;
    }

    // Weight: Piaggio Ape Xtra LDX rated at 496 kg. Values above this
    // create overloaded routes — a physical safety hazard on narrow
    // Kerala roads.
    const weight = parseFloat(addForm.max_weight_kg);
    if (!isNaN(weight) && (weight <= 0 || weight > MAX_RATED_PAYLOAD_KG)) {
      setError(`Max weight must be between 1 and ${MAX_RATED_PAYLOAD_KG} kg (Piaggio rated payload).`);
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const safeWeight = isNaN(weight) ? DEFAULT_MAX_WEIGHT_KG : weight;
      const safeSpeed = isNaN(speedLimit) ? DEFAULT_SPEED_LIMIT_KMH : speedLimit;
      const safeItems = parseInt(addForm.max_items, 10) || DEFAULT_MAX_ITEMS;

      const result = await createVehicle({
        vehicle_id: addForm.vehicle_id.trim(),
        depot_latitude: lat,
        depot_longitude: lng,
        max_weight_kg: safeWeight,
        max_items: safeItems,
        registration_no: addForm.registration_no.trim() || undefined,
        vehicle_type: addForm.vehicle_type,
        speed_limit_kmh: safeSpeed,
      });
      setSuccessMsg(result.message);
      setShowAddForm(false);
      setAddForm(emptyForm());
      // Re-fetch to show the new vehicle in the table
      await loadVehicles();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create vehicle");
    } finally {
      setSaving(false);
    }
  }, [addForm, loadVehicles]);

  /** Save an inline edit. */
  const handleUpdate = useCallback(async () => {
    if (!editingId) return;

    setSaving(true);
    setError(null);

    try {
      // --- CRITICAL safety validations (same rules as handleCreate) ---
      const editSpeed = parseFloat(editForm.speed_limit_kmh);
      if (!isNaN(editSpeed) && editSpeed > MAX_SPEED_LIMIT_KMH) {
        setError(`Speed limit cannot exceed ${MAX_SPEED_LIMIT_KMH} km/h (Kerala MVD safety rule).`);
        setSaving(false);
        return;
      }
      const editWeight = parseFloat(editForm.max_weight_kg);
      if (!isNaN(editWeight) && (editWeight <= 0 || editWeight > MAX_RATED_PAYLOAD_KG)) {
        setError(`Max weight must be between 1 and ${MAX_RATED_PAYLOAD_KG} kg (Piaggio rated payload).`);
        setSaving(false);
        return;
      }

      const payload: Record<string, unknown> = {
        registration_no: editForm.registration_no.trim() || null,
        vehicle_type: editForm.vehicle_type,
        max_weight_kg: isNaN(editWeight) ? DEFAULT_MAX_WEIGHT_KG : editWeight,
        max_items: parseInt(editForm.max_items, 10) || DEFAULT_MAX_ITEMS,
        depot_latitude: parseFloat(editForm.depot_latitude) || DEFAULT_DEPOT_LAT,
        depot_longitude: parseFloat(editForm.depot_longitude) || DEFAULT_DEPOT_LNG,
        speed_limit_kmh: isNaN(editSpeed) ? DEFAULT_SPEED_LIMIT_KMH : editSpeed,
      };

      const result = await updateVehicle(editingId, payload);
      setSuccessMsg(result.message);
      setEditingId(null);
      await loadVehicles();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update vehicle");
    } finally {
      setSaving(false);
    }
  }, [editingId, editForm, loadVehicles]);

  /**
   * Deactivate a vehicle (soft-delete).
   *
   * Why soft-delete instead of hard-delete:
   * Route history references vehicle IDs. Hard-deleting would break
   * foreign key relationships and make historical reports incomplete.
   * The backend's DELETE endpoint sets is_active=false, preserving data.
   */
  const handleDeactivate = useCallback(
    async (vehicleId: string) => {
      setSaving(true);
      setError(null);

      try {
        const result = await deleteVehicle(vehicleId);
        setSuccessMsg(result.message);
        await loadVehicles();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to deactivate vehicle");
      } finally {
        setSaving(false);
      }
    },
    [loadVehicles]
  );

  /**
   * Reactivate a previously deactivated vehicle.
   *
   * Uses the same PUT endpoint with { is_active: true }.
   * The UI shows this as a separate "Reactivate" button to make
   * the action explicit — operators shouldn't wonder what "Edit" does
   * for an inactive vehicle.
   */
  const handleReactivate = useCallback(
    async (vehicleId: string) => {
      setSaving(true);
      setError(null);

      try {
        const result = await updateVehicle(vehicleId, { is_active: true });
        setSuccessMsg(result.message);
        await loadVehicles();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to reactivate vehicle");
      } finally {
        setSaving(false);
      }
    },
    [loadVehicles]
  );

  /** Start editing a vehicle — populate the edit form from current data. */
  const startEdit = useCallback((vehicle: Vehicle) => {
    setEditingId(vehicle.vehicle_id);
    setEditForm(vehicleToForm(vehicle));
    // Close the add form to avoid two forms open simultaneously
    setShowAddForm(false);
  }, []);

  /** Cancel an in-progress edit. */
  const cancelEdit = useCallback(() => {
    setEditingId(null);
  }, []);

  // --- Helpers ---

  /**
   * Generic handler for controlled form inputs.
   *
   * Why a factory function instead of inline onChange per input:
   * Reduces boilerplate — one handler generator covers all fields.
   * The `setter` and `field` params are captured in the closure.
   */
  function handleFieldChange(
    setter: React.Dispatch<React.SetStateAction<VehicleFormState>>,
    field: keyof VehicleFormState
  ) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
      setter((prev) => ({ ...prev, [field]: e.target.value }));
    };
  }

  /** Format depot coords for display — 4 decimal places is ~11m precision. */
  function formatCoord(val: number | null): string {
    return val !== null ? val.toFixed(4) : "—";
  }

  // --- Render ---

  if (loading && vehicles.length === 0) {
    return (
      <div className="fleet-page">
        <div className="fleet-header">
          <div className="tw:skeleton tw:h-8 tw:w-48" />
        </div>
        <div className="tw:overflow-x-auto tw:p-4">
          <table className="tw:table">
            <thead>
              <tr>
                {['Vehicle ID', 'Reg. No', 'Type', 'Max Weight', 'Max Items', 'Speed Limit', 'Depot', 'Status', 'Actions'].map((h) => (
                  <th key={h}><div className="tw:skeleton tw:h-4 tw:w-20" /></th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Array.from({ length: 5 }).map((_, r) => (
                <tr key={r}>
                  {Array.from({ length: 9 }).map((_, c) => (
                    <td key={c}><div className="tw:skeleton tw:h-4 tw:w-full" /></td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  return (
    <div className="fleet-page">
      {/* Header bar with title, filter toggle, and action buttons */}
      <div className="fleet-header">
        <h2>Fleet Management</h2>
        <div className="fleet-header-actions">
          <label className="filter-toggle">
            <input
              type="checkbox"
              checked={activeOnly}
              onChange={(e) => setActiveOnly(e.target.checked)}
            />
            Active only
          </label>
          <button
            className="tw:btn tw:btn-sm tw:btn-primary"
            onClick={() => {
              setShowAddForm(!showAddForm);
              setEditingId(null); // Close any edit when toggling add form
              if (!showAddForm) setAddForm(emptyForm());
            }}
          >
            {showAddForm ? <><X size={16} /> Cancel</> : <><Plus size={16} /> Add Vehicle</>}
          </button>
          <button className="tw:btn tw:btn-sm tw:btn-ghost" onClick={loadVehicles}>
            <RotateCw size={16} /> Refresh
          </button>
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="tw:alert tw:alert-error tw:mb-0 tw:rounded-none">
          <span>{error}</span>
          <button className="tw:btn tw:btn-xs tw:btn-ghost" onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      {/* Success banner — auto-dismisses after 4s (see useEffect above) */}
      {successMsg && (
        <div className="tw:alert tw:alert-success tw:mb-0 tw:rounded-none">
          <span>{successMsg}</span>
          <button className="tw:btn tw:btn-xs tw:btn-ghost" onClick={() => setSuccessMsg(null)}>Dismiss</button>
        </div>
      )}

      {/* --- Add Vehicle Form --- */}
      {showAddForm && (
        <div className="fleet-form-container">
          <h3>Add New Vehicle</h3>
          <div className="fleet-form">
            <div className="fleet-form-field">
              <label htmlFor="add-vehicle-id">Vehicle ID *</label>
              <input
                id="add-vehicle-id"
                type="text"
                className="tw:input tw:input-sm tw:input-bordered"
                placeholder="e.g. VEH-14"
                value={addForm.vehicle_id}
                onChange={handleFieldChange(setAddForm, "vehicle_id")}
              />
            </div>
            <div className="fleet-form-field">
              <label htmlFor="add-reg-no">Registration No.</label>
              <input
                id="add-reg-no"
                type="text"
                className="tw:input tw:input-sm tw:input-bordered"
                placeholder="e.g. KL-07-AX-1234"
                value={addForm.registration_no}
                onChange={handleFieldChange(setAddForm, "registration_no")}
              />
            </div>
            <div className="fleet-form-field">
              <label htmlFor="add-type">Vehicle Type</label>
              <select
                id="add-type"
                className="tw:select tw:select-sm tw:select-bordered"
                value={addForm.vehicle_type}
                onChange={handleFieldChange(setAddForm, "vehicle_type")}
              >
                <option value="diesel">Diesel</option>
                <option value="electric">Electric</option>
                <option value="cng">CNG</option>
              </select>
            </div>
            <div className="fleet-form-field">
              <label htmlFor="add-weight">Max Weight (kg)</label>
              <input
                id="add-weight"
                type="number"
                className="tw:input tw:input-sm tw:input-bordered"
                min={1}
                max={MAX_RATED_PAYLOAD_KG}
                value={addForm.max_weight_kg}
                onChange={handleFieldChange(setAddForm, "max_weight_kg")}
              />
            </div>
            <div className="fleet-form-field">
              <label htmlFor="add-items">Max Items</label>
              <input
                id="add-items"
                type="number"
                className="tw:input tw:input-sm tw:input-bordered"
                value={addForm.max_items}
                onChange={handleFieldChange(setAddForm, "max_items")}
              />
            </div>
            <div className="fleet-form-field">
              <label htmlFor="add-speed">Speed Limit (km/h)</label>
              <input
                id="add-speed"
                type="number"
                className="tw:input tw:input-sm tw:input-bordered"
                min={1}
                max={MAX_SPEED_LIMIT_KMH}
                value={addForm.speed_limit_kmh}
                onChange={handleFieldChange(setAddForm, "speed_limit_kmh")}
              />
            </div>
            <div className="fleet-form-field">
              <label htmlFor="add-lat">Depot Latitude</label>
              <input
                id="add-lat"
                type="number"
                className="tw:input tw:input-sm tw:input-bordered"
                step="0.0001"
                value={addForm.depot_latitude}
                onChange={handleFieldChange(setAddForm, "depot_latitude")}
              />
            </div>
            <div className="fleet-form-field">
              <label htmlFor="add-lng">Depot Longitude</label>
              <input
                id="add-lng"
                type="number"
                className="tw:input tw:input-sm tw:input-bordered"
                step="0.0001"
                value={addForm.depot_longitude}
                onChange={handleFieldChange(setAddForm, "depot_longitude")}
              />
            </div>
            <div className="fleet-form-actions">
              <button
                className="tw:btn tw:btn-sm tw:btn-primary"
                onClick={handleCreate}
                disabled={saving}
              >
                {saving ? "Saving..." : "Create Vehicle"}
              </button>
              <button
                className="tw:btn tw:btn-sm tw:btn-ghost"
                onClick={() => setShowAddForm(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* --- Empty state --- */}
      {!loading && vehicles.length === 0 && !error && (
        <EmptyState
          icon={Truck}
          title="No vehicles yet"
          description="Add a vehicle to start assigning delivery routes."
          actionLabel="Add Vehicle"
          onAction={() => setShowAddForm(true)}
        />
      )}

      {/* --- Vehicle Table --- */}
      {vehicles.length > 0 && (
        <div className="tw:overflow-x-auto fleet-table-wrapper">
          <table className="tw:table tw:table-sm">
            <thead>
              <tr>
                <th>Vehicle ID</th>
                <th>Reg. No</th>
                <th>Type</th>
                <th className="numeric">Max Weight (kg)</th>
                <th className="numeric">Max Items</th>
                <th className="numeric">Speed Limit</th>
                <th>Depot</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {vehicles.map((v) =>
                editingId === v.vehicle_id ? (
                  /* --- Inline edit row --- */
                  <tr key={v.vehicle_id} className="fleet-edit-row">
                    {/* Vehicle ID is immutable — show as plain text */}
                    <td className="tw:font-semibold">{v.vehicle_id}</td>
                    <td>
                      <input
                        type="text"
                        value={editForm.registration_no}
                        onChange={handleFieldChange(setEditForm, "registration_no")}
                        className="tw:input tw:input-xs tw:input-bordered fleet-edit-input--id"
                      />
                    </td>
                    <td>
                      <select
                        value={editForm.vehicle_type}
                        onChange={handleFieldChange(setEditForm, "vehicle_type")}
                        className="tw:select tw:select-xs tw:select-bordered"
                      >
                        <option value="diesel">Diesel</option>
                        <option value="electric">Electric</option>
                        <option value="cng">CNG</option>
                      </select>
                    </td>
                    <td>
                      <input
                        type="number"
                        min={1}
                        max={MAX_RATED_PAYLOAD_KG}
                        value={editForm.max_weight_kg}
                        onChange={handleFieldChange(setEditForm, "max_weight_kg")}
                        className="tw:input tw:input-xs tw:input-bordered fleet-edit-input--weight"
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        value={editForm.max_items}
                        onChange={handleFieldChange(setEditForm, "max_items")}
                        className="tw:input tw:input-xs tw:input-bordered fleet-edit-input--items"
                      />
                    </td>
                    <td>
                      <input
                        type="number"
                        min={1}
                        max={MAX_SPEED_LIMIT_KMH}
                        value={editForm.speed_limit_kmh}
                        onChange={handleFieldChange(setEditForm, "speed_limit_kmh")}
                        className="tw:input tw:input-xs tw:input-bordered fleet-edit-input--speed"
                      />
                    </td>
                    <td>
                      <div className="fleet-coord-group">
                        <input
                          type="number"
                          step="0.0001"
                          value={editForm.depot_latitude}
                          onChange={handleFieldChange(setEditForm, "depot_latitude")}
                          className="tw:input tw:input-xs tw:input-bordered fleet-edit-input--coord"
                          placeholder="Lat"
                        />
                        <input
                          type="number"
                          step="0.0001"
                          value={editForm.depot_longitude}
                          onChange={handleFieldChange(setEditForm, "depot_longitude")}
                          className="tw:input tw:input-xs tw:input-bordered fleet-edit-input--coord"
                          placeholder="Lng"
                        />
                      </div>
                    </td>
                    <td>
                      <span className={`tw-badge tw:badge-sm ${v.is_active ? 'tw:badge-success' : 'tw:badge-ghost'}`}>
                        {v.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td>
                      <div className="fleet-actions">
                        <button
                          className="tw:btn tw:btn-xs tw:btn-primary"
                          onClick={handleUpdate}
                          disabled={saving}
                        >
                          <Check size={16} /> {saving ? "..." : "Save"}
                        </button>
                        <button className="tw:btn tw:btn-xs tw:btn-ghost" onClick={cancelEdit}>
                          <X size={16} />
                        </button>
                      </div>
                    </td>
                  </tr>
                ) : (
                  /* --- Normal display row --- */
                  <tr key={v.vehicle_id}>
                    <td>{v.vehicle_id}</td>
                    <td>{v.registration_no ?? "—"}</td>
                    <td>
                      <span className="fleet-type-badge" data-type={v.vehicle_type}>{v.vehicle_type}</span>
                    </td>
                    <td className="numeric">{v.max_weight_kg}</td>
                    <td className="numeric">{v.max_items}</td>
                    <td className="numeric">{v.speed_limit_kmh} km/h</td>
                    <td className="numeric depot-coords">
                      {formatCoord(v.depot_latitude)}, {formatCoord(v.depot_longitude)}
                    </td>
                    <td>
                      <span className={`tw-badge tw:badge-sm ${v.is_active ? 'tw:badge-success' : 'tw:badge-ghost'}`}>
                        {v.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td>
                      <div className="fleet-actions">
                        <button
                          className="tw:btn tw:btn-xs tw:btn-square tw:btn-ghost"
                          onClick={() => startEdit(v)}
                          disabled={saving}
                          title="Edit vehicle details"
                        >
                          <Pencil size={16} />
                        </button>
                        {v.is_active ? (
                          <button
                            className="tw:btn tw:btn-xs tw:btn-error tw:btn-outline"
                            onClick={() => handleDeactivate(v.vehicle_id)}
                            disabled={saving}
                            title="Deactivate vehicle (soft delete — preserves route history)"
                          >
                            Deactivate
                          </button>
                        ) : (
                          <button
                            className="tw:btn tw:btn-xs tw:btn-success tw:btn-outline"
                            onClick={() => handleReactivate(v.vehicle_id)}
                            disabled={saving}
                            title="Reactivate vehicle for future route assignments"
                          >
                            Reactivate
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
