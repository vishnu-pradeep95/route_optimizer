# Requirements: Kerala LPG Delivery Route Optimizer

**Defined:** 2026-03-01
**Core Value:** Every delivery address uploaded must appear on the map and be assigned to an optimized route — no silent drops, no missing stops.

## v1.1 Requirements

Requirements for v1.1 Polish & Reliability milestone. Each maps to roadmap phases.

### Geocoding

- [ ] **GEO-01**: Geocoding uses a single normalized address key across all cache layers (no duplicate locations from normalization mismatch)
- [ ] **GEO-02**: All geocoding cache reads/writes go through DB only (file-based JSON cache deprecated)
- [ ] **GEO-03**: User sees a warning when two or more orders in an upload resolve to GPS coordinates within 15m of each other
- [ ] **GEO-04**: Upload results show how many addresses were cache hits (free) vs Google API calls, with estimated cost

### Dashboard UI

- [ ] **DASH-01**: All 4 dashboard pages use DaisyUI component vocabulary consistently (no mixed raw CSS + DaisyUI)
- [ ] **DASH-02**: Sidebar uses SVG icons (lucide-react) instead of emoji for navigation items
- [ ] **DASH-03**: Every page shows a skeleton loading state while data loads and a meaningful empty state when no data exists
- [ ] **DASH-04**: Numeric values (distances, weights, counts) use tabular-number font variant for column alignment
- [ ] **DASH-05**: Route cards display color-coded status badges (green=complete, amber=in-progress, red=issues)
- [ ] **DASH-06**: Sidebar collapses to icon-only on screens below 1280px and uses DaisyUI drawer on mobile
- [ ] **DASH-07**: QR sheet prints cleanly with large QR codes, vehicle name, and driver name via @media print

### Driver PWA

- [ ] **PWA-01**: Next stop is displayed as a prominent hero card at top of stop list with large address, distance, and Navigate button
- [ ] **PWA-02**: Header shows delivery progress as "X of Y delivered" with a visual progress bar
- [ ] **PWA-03**: Driver can tap a visible Refresh button to reload route data, with "Last updated" timestamp shown
- [ ] **PWA-04**: All primary action buttons (Delivered, Failed, Navigate, Call Office) are 60px+ touch targets
- [ ] **PWA-05**: All text/background color combinations meet WCAG AAA contrast ratio (7:1 body, 4.5:1 large text)
- [ ] **PWA-06**: Route data persists offline — loading, viewing stops, and marking deliveries work without network

## Future Requirements

Deferred to future milestone. Tracked but not in current roadmap.

### Geocoding Enhancements

- **GEO-05**: Cache migration tool imports file cache entries into DB with correct normalization
- **GEO-06**: Cache statistics show total cached addresses, hit rate, and estimated savings
- **GEO-07**: Driver-verified GPS coordinates are promoted to cache entries on delivery confirmation

### Dashboard Enhancements

- **DASH-08**: Theme switcher (light/dark) with preference stored in localStorage
- **DASH-09**: At-a-glance daily summary card showing total deliveries, vehicles, failures, distance
- **DASH-10**: Per-vehicle capacity utilization bar on route cards (weight vs 446kg max)

### Driver PWA Enhancements

- **PWA-07**: Focus mode — full-screen next-stop-only view with swipe to peek next
- **PWA-08**: Auto-advance to next undelivered stop after marking delivery
- **PWA-09**: Haptic feedback (vibration) on delivery confirmation
- **PWA-10**: Offline sync queue indicator showing pending updates count

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Drag-and-drop route reordering | Undermines VROOM optimizer; manual overrides create sub-optimal routes |
| Turn-by-turn navigation in-app | Google Maps handles this; building nav requires routing engine + voice guidance |
| Photo proof-of-delivery | Camera API complexity, upload on spotty Kerala networks, privacy concerns |
| Countdown timers for delivery windows | Prohibited for Kerala MVD compliance; creates unsafe driving pressure |
| Pre-cached map tiles for entire route | 50-100MB+ storage; browser cache quotas unpredictable on low-memory Android |
| Real-time chat with office | WebSocket infra overkill; drivers can call office via one-tap button |
| Fuzzy address matching (Levenshtein) | False positives assign wrong coordinates; safety-critical system |
| Multiple geocoding provider fallback | Different providers return different coords; mixing creates inconsistency |
| Reverse geocoding for telemetry pings | 25K pings/day x $0.005 = $45K/year; show raw coords, reverse on demand |
| Elegant error handling across pipeline | Deferred to future milestone |
| Code quality cleanup / refactoring | Deferred to future milestone |
| Property-based unit tests / coverage gate | Deferred to future milestone |
| Streamlined installation docs / README | Deferred to future milestone |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| GEO-01 | — | Pending |
| GEO-02 | — | Pending |
| GEO-03 | — | Pending |
| GEO-04 | — | Pending |
| DASH-01 | — | Pending |
| DASH-02 | — | Pending |
| DASH-03 | — | Pending |
| DASH-04 | — | Pending |
| DASH-05 | — | Pending |
| DASH-06 | — | Pending |
| DASH-07 | — | Pending |
| PWA-01 | — | Pending |
| PWA-02 | — | Pending |
| PWA-03 | — | Pending |
| PWA-04 | — | Pending |
| PWA-05 | — | Pending |
| PWA-06 | — | Pending |

**Coverage:**
- v1.1 requirements: 17 total
- Mapped to phases: 0
- Unmapped: 17 ⚠️

---
*Requirements defined: 2026-03-01*
*Last updated: 2026-03-01 after initial definition*
