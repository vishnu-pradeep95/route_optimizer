---
phase: 14-api-confidence-fields-and-driver-pwa-badge
verified: 2026-03-11T00:00:00Z
status: human_needed
score: 4/4 must-haves verified
re_verification: false
human_verification:
  - test: "Visual badge rendering on a real stop with location_approximate: true"
    expected: "DaisyUI badge-warning appears below address with orange background, warning symbol, and 'Approx. location' text — readable at arm's length outdoors"
    why_human: "Cannot programmatically confirm CSS variable resolution (--color-warning) renders as visible orange in the dark-theme PWA without a live browser render"
  - test: "Badge persists after marking stop Delivered"
    expected: "After tapping Done on an approximate-location stop, the hero card for the next stop (if it is also approximate) still shows the badge; completed stops on the compact list retain the orange dot"
    why_human: "State-transition persistence across DOM re-renders requires live interaction testing"
  - test: "Null-confidence route renders without visual artifacts"
    expected: "When loading a route uploaded before Phase 13 (geocode_confidence: null), no badge appears on hero cards and no orange dot appears on compact cards — no JS errors, no layout breakage"
    why_human: "Requires uploading a pre-Phase 13 CSV file and observing the live PWA response"
---

# Phase 14: API Confidence Fields and Driver PWA Badge — Verification Report

**Phase Goal:** Drivers can see at a glance which delivery stops have approximate locations, so they know when to expect navigation imprecision
**Verified:** 2026-03-11
**Status:** human_needed — all automated checks pass; 3 items need live PWA testing
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from ROADMAP.md Success Criteria)

| #   | Truth                                                                                                  | Status     | Evidence                                                                                                         |
| --- | ------------------------------------------------------------------------------------------------------ | ---------- | ---------------------------------------------------------------------------------------------------------------- |
| 1   | `GET /api/routes/{vehicle_id}` returns `geocode_confidence` (float) and `location_approximate` (bool) | ✓ VERIFIED | `main.py:1574-1579` — both fields serialized; `location_approximate` computed inline from `geocode_confidence`  |
| 2   | Hero card shows "Approx. location" DaisyUI badge-warning when `location_approximate: true`             | ✓ VERIFIED | `index.html:1404` — `stop.location_approximate ? '<div class="approx-badge tw:badge tw:badge-warning tw:badge-sm">&#9888; Approx. location</div>' : ''` |
| 3   | Compact cards show orange dot for `location_approximate: true` stops                                  | ✓ VERIFIED | `index.html:1434` — `stop.location_approximate ? '<div class="approx-dot"></div>' : ''` inside `.stop-number` div |
| 4   | Pre-upgrade routes with null confidence render without badges or errors (graceful null handling)       | ✓ VERIFIED | `main.py:1576-1579` — `None is not None and None < 0.5` evaluates to `False`; conditional in HTML emits nothing |

**Score:** 4/4 truths verified

---

### Required Artifacts

| Artifact                                             | Expected                                                          | Status      | Details                                                                                        |
| ---------------------------------------------------- | ----------------------------------------------------------------- | ----------- | ---------------------------------------------------------------------------------------------- |
| `core/models/route.py`                               | RouteStop with `geocode_confidence` and `geocode_method` fields   | ✓ VERIFIED  | Lines 62-72: both fields present, `ge=0.0, le=1.0` constraint, `None` defaults                |
| `core/database/repository.py`                        | `route_db_to_pydantic` propagates geocode fields from OrderDB     | ✓ VERIFIED  | Lines 855-861: `stop_db.order.geocode_confidence if stop_db.order else None` with None guard   |
| `apps/kerala_delivery/api/main.py`                   | Stop serialization dict with 3 new fields + computed boolean      | ✓ VERIFIED  | Lines 1573-1579: `geocode_confidence`, `geocode_method`, `location_approximate` all present    |
| `apps/kerala_delivery/driver_app/index.html`         | Badge in `renderHeroCard`, dot in `renderCompactCard`, map pins   | ✓ VERIFIED  | Lines 1404, 1434, 1495-1499: all three indicator insertion points confirmed                    |
| `apps/kerala_delivery/driver_app/tailwind.css`       | Compiled with DaisyUI `badge-warning` and `badge-sm` styles       | ✓ VERIFIED  | Single-line minified CSS contains `.tw\:badge`, `.tw\:badge-sm`, `.tw\:badge-warning` classes |

---

### Key Link Verification

| From                         | To                                      | Via                                           | Status      | Details                                                                  |
| ---------------------------- | --------------------------------------- | --------------------------------------------- | ----------- | ------------------------------------------------------------------------ |
| `core/database/repository.py`| `core/database/models.py` (OrderDB)     | `stop_db.order.geocode_confidence`            | ✓ WIRED     | Pattern confirmed at `repository.py:856-861`                             |
| `apps/kerala_delivery/api/main.py` | `core/models/route.py` (RouteStop) | `stop.geocode_confidence` in serialization    | ✓ WIRED     | Pattern confirmed at `main.py:1574`                                      |
| `apps/kerala_delivery/driver_app/index.html` | `/api/routes/{vehicle_id}` | `stop.location_approximate` in `renderHeroCard` and `renderCompactCard` | ✓ WIRED | Confirmed at `index.html:1404` and `1434`; `isApprox` used at `1495` |
| `apps/kerala_delivery/driver_app/index.html` | `tailwind.css`            | `tw:badge tw:badge-warning tw:badge-sm` classes compiled by tailwindcss-extra | ✓ WIRED | `index.html:22` loads `tailwind.css`; compiled CSS contains all three badge classes |

---

### Requirements Coverage

| Requirement | Source Plan  | Description                                                                     | Status       | Evidence                                                                  |
| ----------- | ------------ | ------------------------------------------------------------------------------- | ------------ | ------------------------------------------------------------------------- |
| APUI-01     | 14-01-PLAN   | API route response includes `geocode_confidence` field for each delivery stop   | ✓ SATISFIED  | `main.py:1574`: `"geocode_confidence": stop.geocode_confidence`           |
| APUI-02     | 14-01-PLAN   | API route response includes `location_approximate` flag (true when conf < 0.5) | ✓ SATISFIED  | `main.py:1576-1579`: computed inline; null -> false; <0.5 -> true         |
| APUI-03     | 14-02-PLAN   | Driver PWA hero card shows "Approx. location" warning badge for approximate stops | ✓ SATISFIED | `index.html:1404`: DaisyUI `badge-warning badge-sm` conditional rendering |
| APUI-04     | 14-02-PLAN   | Driver PWA compact cards show orange dot indicator for approximate stops        | ✓ SATISFIED  | `index.html:1434, 466-476`: `.approx-dot` CSS + conditional rendering     |

No orphaned requirements. All four APUI requirements declared in plan frontmatter match the REQUIREMENTS.md entries for Phase 14 and are accounted for in the codebase.

---

### Additional Deliverables (Beyond Requirements)

The following were implemented per PLAN instructions and are present in the code, though not tracked as named requirements:

- `geocode_method` field in API response (`main.py:1575`) — present and wired through all three layers
- Map pin dashed orange border for approximate delivered/failed stops (`index.html:1495-1499`) — `isApprox && stop.status !== 'pending'` guard
- CSS: `.stop-number { position: relative }` at `index.html:433-434` (required for `.approx-dot` absolute positioning)
- `.approx-dot` and `.approx-badge` CSS rules at `index.html:466-479`

---

### Commit Verification

All four task commits from the SUMMARY files were confirmed to exist in the repository:

| Commit    | Plan  | Content                                                                |
| --------- | ----- | ---------------------------------------------------------------------- |
| `9db2807` | 14-01 | `feat(14-01): add geocode_confidence and geocode_method to RouteStop`  |
| `d3ffd04` | 14-01 | `feat(14-01): propagate geocode fields through repository and API`     |
| `b9e5698` | 14-02 | `feat(14-02): add approximate location indicators to Driver PWA`       |
| `a69e4b8` | 14-02 | `chore(14-02): rebuild Tailwind CSS with DaisyUI badge-warning styles` |

---

### Anti-Patterns Found

No anti-patterns detected in Phase 14 modified files:

- No `TODO`, `FIXME`, `PLACEHOLDER` comments related to Phase 14 changes
- No stub implementations (`return null`, `return {}`, `console.log`-only handlers)
- No unguarded null access on `stop_db.order` — the `if stop_db.order` guard is present
- `location_approximate` computation is a real boolean expression, not a stub

---

### Human Verification Required

#### 1. Visual Badge Rendering in Live PWA

**Test:** Upload a CSV that produces stops with `geocode_confidence < 0.5` (e.g., centroid or depot fallback), select a vehicle, and observe the hero card.
**Expected:** An orange DaisyUI warning badge reading "⚠ Approx. location" appears below the address line, with proper background color from `--color-warning` CSS variable (approximately yellow/amber in DaisyUI default theme, or orange in the PWA's dark theme).
**Why human:** CSS variable resolution for `--color-warning` in the compiled tailwind.css (oklch value) vs. the PWA's custom dark theme variables cannot be confirmed by static analysis. The badge will render — but whether it looks visually distinct at outdoor brightness requires physical observation.

#### 2. Badge Persistence Across Delivery State Transitions

**Test:** On an approximate-location stop, tap "Done". Observe whether the next stop's hero card (if also approximate) shows the badge, and whether the previous stop's compact card retains the orange dot.
**Expected:** Badge and dot persist regardless of delivery status. The `location_approximate` boolean is read from the stop data, not from status.
**Why human:** DOM re-render behavior during status transitions requires live interaction. The JS template functions `renderHeroCard` and `renderCompactCard` both gate on `stop.location_approximate`, which comes from the API and is not mutated on status change — but this transition behavior needs live confirmation.

#### 3. Null-Confidence Route (Pre-Phase 13 Data)

**Test:** Upload a CSV for a route that was geocoded before Phase 13 (i.e., before `geocode_confidence` was stored). Load the route in the Driver PWA and visually inspect all cards.
**Expected:** No badge on any hero card, no orange dot on any compact card, no JS console errors from accessing `.location_approximate` on undefined.
**Why human:** The null-safety path (`None is not None` = `False`) has been verified in Python; the JS equivalent (`false ? ... : ''`) is confirmed in the template. However, confirming no JS runtime errors requires loading a real pre-Phase 13 dataset.

---

### Gaps Summary

No gaps found. All four ROADMAP success criteria are satisfied by the implementation:

1. The API endpoint returns `geocode_confidence` and `location_approximate` per stop — verified in `main.py:1573-1579`
2. The hero card badge renders conditionally on `location_approximate` — verified in `index.html:1404`
3. The compact card orange dot renders conditionally — verified in `index.html:1434`
4. Null confidence gracefully maps to no badge — verified by logic check and Python execution

Three items flagged for human verification relate to visual quality (outdoor contrast, live rendering of DaisyUI CSS variables) and real-time state-transition behavior — not to functional correctness. The code paths are complete and wired.

---

_Verified: 2026-03-11_
_Verifier: Claude (gsd-verifier)_
