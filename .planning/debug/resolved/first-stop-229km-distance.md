---
status: resolved
trigger: "The first delivery stop in a route shows 229.4 km from prev (the depot). All deliveries are in Vatakara/Kozhikode area, so this is clearly wrong."
created: 2026-03-12T00:00:00Z
updated: 2026-03-12T00:02:00Z
---

## Current Focus

hypothesis: CONFIRMED — vehicles in DB had Kochi depot coords, not Vatakara
test: Fix applied. init.sql updated, DB vehicles updated. Tests pass (561/561).
expecting: User re-uploads CDCMS file, first stop distance drops from 229 km to ~11 km
next_action: User verifies by re-uploading and checking dashboard

## Symptoms

expected: First stop should show a reasonable distance from depot (likely under 30 km for local Vatakara deliveries)
actual: First stop shows 229.4 km from prev (the depot). Subsequent stops show reasonable inter-stop distances (0-8 km).
errors: No errors — just wrong distance value
reproduction: Upload CDCMS file, view routes in dashboard. Stop #1 of any route shows ~229 km.
started: Noticed during dashboard testing. May have always been the case.

## Eliminated

- hypothesis: OSRM returning wrong distances
  evidence: OSRM query from correct Vatakara depot to first stop returns 11.15 km (correct). OSRM query from Kochi depot to first stop returns 230.2 km (matches the 229.4 km bug).
  timestamp: 2026-03-12T00:00:30Z

- hypothesis: VROOM adapter cumulative-distance parsing is wrong
  evidence: Code correctly subtracts prev_cumulative_distance. Manual VROOM test confirms distances are cumulative and parsing logic produces correct incremental values.
  timestamp: 2026-03-12T00:00:30Z

- hypothesis: config.py DEPOT_LOCATION is wrong
  evidence: config.py has (11.624443730714066, 75.57964507762223) — correct Vatakara location. But optimizer uses DB vehicles, not config.py.
  timestamp: 2026-03-12T00:00:30Z

## Evidence

- timestamp: 2026-03-12T00:00:10Z
  checked: API response for VEH-01 route
  found: Stop #1 distance_from_prev_km = 229.4, stop #2 = 8.42, stop #3 = 0.59
  implication: Only first stop (depot->stop1) has inflated distance; inter-stop distances are fine

- timestamp: 2026-03-12T00:00:20Z
  checked: OSRM direct query depot(75.5796,11.6244) -> stop1(75.6523,11.6135)
  found: 11,150 m (11.15 km) — reasonable for Vatakara local delivery
  implication: OSRM is fine; the problem is upstream (wrong depot coords sent to VROOM)

- timestamp: 2026-03-12T00:00:30Z
  checked: vehicles table in PostgreSQL — ST_X/ST_Y of depot_location
  found: ALL 13 vehicles have depot at (76.2846, 9.9716) = Kochi, NOT Vatakara
  implication: VROOM is computing routes starting from Kochi, 229 km from delivery area

- timestamp: 2026-03-12T00:00:35Z
  checked: infra/postgres/init.sql line 254
  found: ST_SetSRID(ST_MakePoint(76.2846, 9.9716), 4326) — hardcoded Kochi coords
  implication: The seed data was written for Kochi (early dev?) and never updated to Vatakara

- timestamp: 2026-03-12T00:00:40Z
  checked: OSRM query from Kochi(76.2846,9.9716) to stop1
  found: 230,239 m (230.2 km) — matches the 229.4 km in the route
  implication: Confirms the 229.4 km IS the Kochi-to-Vatakara distance

- timestamp: 2026-03-12T00:01:00Z
  checked: Applied fix — updated init.sql and DB vehicles, ran 561 tests
  found: All tests pass. Vehicle API now returns Vatakara depot (11.6244, 75.5796). Config and DB depots now match.
  implication: Fix is correct. Old routes still have 229 km (stored at optimization time); re-upload will produce correct distances.

## Resolution

root_cause: infra/postgres/init.sql seeds all 13 vehicles with Kochi depot coordinates (76.2846, 9.9716) instead of the Vatakara depot from config.py (75.5796, 11.6244). The optimizer reads depot from DB, so VROOM computes depot->first_stop as a 229 km trip from Kochi to Vatakara.
fix: Updated init.sql line 254 to use Vatakara coordinates (75.5796450776, 11.6244437307). Updated all 13 vehicles in the running DB via SQL UPDATE. Existing routes still have old distances — user must re-upload CDCMS file to re-optimize with correct depot.
verification: 561 tests pass. API /api/vehicles/VEH-01 now returns depot_latitude=11.6244, depot_longitude=75.5796. OSRM confirms depot->stop1 is 11.15 km (not 229 km). Awaiting user re-upload to confirm end-to-end.
files_changed:
  - infra/postgres/init.sql (depot coordinates: Kochi -> Vatakara)
