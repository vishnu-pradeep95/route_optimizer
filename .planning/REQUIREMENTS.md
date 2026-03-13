# Requirements: Kerala LPG Delivery Route Optimizer

**Defined:** 2026-03-12
**Core Value:** Every delivery address uploaded must appear on the map and be assigned to an optimized route -- no silent drops, no missing stops.

## v3.0 Requirements

Requirements for v3.0 Driver-Centric Model. Each maps to roadmap phases.

### Driver Management

- [ ] **DRV-01**: User can view a list of all drivers with name and active status
- [ ] **DRV-02**: User can manually add a new driver by entering a name
- [ ] **DRV-03**: User can edit an existing driver's name
- [ ] **DRV-04**: User can deactivate a driver (soft delete)
- [ ] **DRV-05**: System auto-creates new drivers from CSV DeliveryMan column on upload
- [x] **DRV-06**: System uses fuzzy name matching (RapidFuzz) to avoid creating duplicate drivers from CDCMS name variations (e.g., "SURESH K" vs "SURESH KUMAR")
- [x] **DRV-07**: System starts with zero drivers (no pre-loaded fleet)

### Route Optimization

- [ ] **OPT-01**: System optimizes stop order within each driver's assigned orders using per-driver TSP (VROOM with 1 vehicle per driver)
- [ ] **OPT-02**: System groups orders by DeliveryMan column from CSV before optimization
- [ ] **OPT-03**: System stores all per-driver routes under a single optimization_run
- [ ] **OPT-04**: System validates post-optimization that no orders overlap between driver routes
- [ ] **OPT-05**: System reports validation warnings if cross-driver geographic anomalies are detected

### CSV Upload Flow

- [ ] **CSV-01**: System correctly detects CDCMS format in .xlsx Excel files (not just tab-separated .csv)
- [ ] **CSV-02**: User can see which drivers are found in the uploaded CSV before processing
- [ ] **CSV-03**: User can select which drivers' routes to generate from a multi-driver CSV
- [ ] **CSV-04**: System filters to "Allocated-Printed" OrderStatus by default
- [ ] **CSV-05**: Column order in CSV/XLSX does not affect parsing (column name matching only)

### Address Preprocessing

- [ ] **ADDR-01**: System correctly preserves "MUTTUNGAL" as a single word (fix trailing-letter split garbling)
- [ ] **ADDR-02**: System correctly handles (H) expansion without splitting adjacent words
- [ ] **ADDR-03**: System correctly splits PO abbreviations from concatenated text without garbling surrounding words
- [ ] **ADDR-04**: Geocode validation uses 20km radius (reduced from 30km)
- [ ] **ADDR-05**: Geocode validation centroid is always the Vatakara depot location from config

### Route Validation

- [ ] **VAL-01**: User can trigger Google Routes API comparison for a generated route
- [ ] **VAL-02**: System displays VROOM/OSRM vs Google Routes distance/time comparison with confidence indicator
- [ ] **VAL-03**: System shows cost warning before running Google Routes validation
- [ ] **VAL-04**: Google Routes validation is never triggered automatically (user-initiated only)

### Dashboard Settings & Operations

- [ ] **SET-01**: User can enter/update Google Maps API key in the dashboard settings page
- [ ] **SET-02**: API key is stored server-side and displayed masked in the UI (e.g., AIza...****1234)
- [ ] **SET-03**: User can view upload history with date, filename, driver count, and order count
- [ ] **SET-04**: User can view geocode cache statistics (total cached addresses, API calls made, estimated cost)
- [ ] **SET-05**: User can export geocode cache to JSON file for migration to another machine
- [ ] **SET-06**: User can import geocode cache from a JSON file

### UI Terminology

- [ ] **UI-01**: Dashboard displays "Driver" instead of "Vehicle" in all user-facing labels, headers, and navigation
- [ ] **UI-02**: API field names remain backward-compatible (vehicle_id stays in API responses for PWA compatibility)
- [ ] **UI-03**: Fleet Management page becomes Driver Management page with driver-centric UI

## Future Requirements

Deferred to stage two or future milestones.

### Driver PWA Enhancements

- **PWA-01**: Driver PWA shows driver name instead of vehicle ID
- **PWA-02**: Driver PWA route lookup by driver name (alongside vehicle_id)
- **PWA-03**: QR codes link to driver-specific routes

### Route Preview

- **PREVIEW-01**: User can preview route on map before sending to drivers
- **PREVIEW-02**: User can compare multiple drivers' routes side by side

### Driver Performance

- **PERF-01**: Dashboard shows per-driver delivery stats (completed, failed, average time)
- **PERF-02**: Historical trend charts for driver performance

## Out of Scope

| Feature | Reason |
|---------|--------|
| Drag-and-drop route reordering | Undermines VROOM optimizer -- established out-of-scope |
| Cross-driver route reassignment (CVRP) | Replaced by per-driver TSP per business requirements |
| Driver vehicle assignment management | Drivers identified by name only, no vehicle tracking this milestone |
| Automatic Google Routes validation | Cost risk -- must be user-triggered only |
| API field name renames (vehicle_id → driver_id) | Would break Driver PWA and existing QR codes |
| Real-time route tracking | Out of scope for dashboard-focused milestone |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DRV-01 | Phase 16 | Pending |
| DRV-02 | Phase 16 | Pending |
| DRV-03 | Phase 16 | Pending |
| DRV-04 | Phase 16 | Pending |
| DRV-05 | Phase 16 | Pending |
| DRV-06 | Phase 16 | Complete |
| DRV-07 | Phase 16 | Complete |
| OPT-01 | Phase 19 | Pending |
| OPT-02 | Phase 19 | Pending |
| OPT-03 | Phase 19 | Pending |
| OPT-04 | Phase 19 | Pending |
| OPT-05 | Phase 19 | Pending |
| CSV-01 | Phase 17 | Pending |
| CSV-02 | Phase 17 | Pending |
| CSV-03 | Phase 17 | Pending |
| CSV-04 | Phase 17 | Pending |
| CSV-05 | Phase 17 | Pending |
| ADDR-01 | Phase 18 | Pending |
| ADDR-02 | Phase 18 | Pending |
| ADDR-03 | Phase 18 | Pending |
| ADDR-04 | Phase 18 | Pending |
| ADDR-05 | Phase 18 | Pending |
| VAL-01 | Phase 22 | Pending |
| VAL-02 | Phase 22 | Pending |
| VAL-03 | Phase 22 | Pending |
| VAL-04 | Phase 22 | Pending |
| SET-01 | Phase 21 | Pending |
| SET-02 | Phase 21 | Pending |
| SET-03 | Phase 21 | Pending |
| SET-04 | Phase 21 | Pending |
| SET-05 | Phase 21 | Pending |
| SET-06 | Phase 21 | Pending |
| UI-01 | Phase 20 | Pending |
| UI-02 | Phase 20 | Pending |
| UI-03 | Phase 20 | Pending |

**Coverage:**
- v3.0 requirements: 35 total
- Mapped to phases: 35
- Unmapped: 0

---
*Requirements defined: 2026-03-12*
*Last updated: 2026-03-12 after roadmap creation (all 35 requirements mapped to phases 16-22)*
