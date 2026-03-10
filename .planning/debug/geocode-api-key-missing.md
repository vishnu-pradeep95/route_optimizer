---
status: awaiting_human_verify
trigger: "After running ./scripts/reset --all and ./scripts/bootstrap.sh, CSV upload fails with 'unable to geocode' error. User hypothesis: .env was not filled out before bootstrap, so API keys weren't included in the generated Docker images."
created: 2026-03-08T00:00:00Z
updated: 2026-03-08T00:02:00Z
---

## Current Focus

hypothesis: CONFIRMED - bootstrap.sh copies .env.example which has GOOGLE_MAPS_API_KEY=your-key-here (non-empty placeholder). The API initializes GoogleGeocoder with this fake key, and every geocode request gets REQUEST_DENIED from Google. Unlike install.sh, bootstrap.sh never prompts for the Google Maps API key.
test: Fix applied and self-verified. CSV upload with 30 orders succeeds (30 geocoded, 0 failures).
expecting: User confirms geocoding works after their own test
next_action: Await user verification, then archive

## Symptoms

expected: CSV upload should geocode addresses and create optimized routes
actual: Errors out with "unable to geocode" during CSV upload
errors: Google Geocoding API returns REQUEST_DENIED when called with fake key "your-key-here"
reproduction: Run ./scripts/reset --all, then ./scripts/bootstrap.sh without filling .env, then upload CSV
started: Just happened after fresh reset and bootstrap

## Eliminated

- hypothesis: API key not passed to Docker container
  evidence: docker compose exec api env shows GOOGLE_MAPS_API_KEY is set in container. docker-compose.yml line 214 passes ${GOOGLE_MAPS_API_KEY:-} from .env
  timestamp: 2026-03-08T00:00:30Z

- hypothesis: API code doesn't read the env var
  evidence: main.py line 547 reads os.environ.get("GOOGLE_MAPS_API_KEY", "") correctly
  timestamp: 2026-03-08T00:00:30Z

## Evidence

- timestamp: 2026-03-08T00:00:10Z
  checked: scripts/reset.sh step 5 (lines 276-298)
  found: reset --all deletes .env file
  implication: After reset, bootstrap must recreate .env from scratch

- timestamp: 2026-03-08T00:00:15Z
  checked: scripts/bootstrap.sh lines 281-300
  found: bootstrap.sh copies .env.example to .env, then only sed-replaces POSTGRES_PASSWORD and API_KEY. GOOGLE_MAPS_API_KEY is NOT touched.
  implication: Whatever value .env.example has for GOOGLE_MAPS_API_KEY is what the API gets

- timestamp: 2026-03-08T00:00:20Z
  checked: .env.example line 15
  found: GOOGLE_MAPS_API_KEY=your-key-here (non-empty placeholder string)
  implication: After bootstrap, .env has GOOGLE_MAPS_API_KEY=your-key-here -- a truthy but invalid key

- timestamp: 2026-03-08T00:00:25Z
  checked: main.py _get_geocoder() lines 538-550
  found: Checks "if api_key:" -- the string "your-key-here" is truthy, so GoogleGeocoder is initialized with a fake key
  implication: Instead of gracefully degrading (no geocoder, cache-only mode), the API actively sends requests with an invalid key

- timestamp: 2026-03-08T00:00:30Z
  checked: scripts/install.sh lines 196-227
  found: install.sh DOES prompt for Google Maps API key and only sets it if user provides a value
  implication: bootstrap.sh is missing this prompt -- the two scripts have diverged in behavior

- timestamp: 2026-03-08T00:00:35Z
  checked: core/geocoding/google_adapter.py _call_api()
  found: When Google returns REQUEST_DENIED (invalid key), it returns GeocodingResult with location=None
  implication: The error message users see is the geocoding failure for every order

- timestamp: 2026-03-08T00:02:00Z
  checked: POST /api/upload-orders with sample_orders.csv after fix
  found: 30/30 orders geocoded successfully, 0 failures, 2 vehicles used
  implication: Fix verified -- geocoding works correctly with real API key

## Resolution

root_cause: Two bugs combine to cause the failure. (1) .env.example has GOOGLE_MAPS_API_KEY=your-key-here (non-empty placeholder) instead of an empty value. (2) bootstrap.sh (unlike install.sh) does not prompt for the Google Maps API key, so the placeholder passes through verbatim. The API's _get_geocoder() treats any non-empty string as a valid key and initializes GoogleGeocoder with "your-key-here", causing every geocode call to return REQUEST_DENIED from Google.
fix: Three-layer fix applied: (1) .env.example -- changed GOOGLE_MAPS_API_KEY=your-key-here to GOOGLE_MAPS_API_KEY= (empty). (2) scripts/bootstrap.sh -- added interactive prompt for Google Maps API key matching install.sh behavior. (3) apps/kerala_delivery/api/main.py _get_geocoder() -- added placeholder detection that rejects known placeholder strings and logs a clear warning.
verification: Self-verified -- rebuilt API container, uploaded sample_orders.csv, all 30 orders geocoded successfully with 0 failures. Placeholder detection tested with 5 values (4 placeholders correctly rejected, 1 real key correctly accepted).
files_changed:
  - .env.example
  - scripts/bootstrap.sh
  - apps/kerala_delivery/api/main.py
