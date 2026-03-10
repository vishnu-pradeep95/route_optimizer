# Milestone v2.1: Licensing & Distribution Security - Context

**Gathered:** 2026-03-10
**Status:** Ready for roadmap creation

<domain>
## Milestone Boundary

Close all 6 identified loopholes in the licensing and distribution system that allow customers to circumvent license enforcement. Upgrade from Tier 1 (license-key-at-startup) to solid Tier 2 (compiled enforcement + integrity checks). No call-home, no native binary enforcement beyond Cython.

</domain>

<decisions>
## Implementation Decisions

### Threat Model
- Target: determined reverse engineer (someone willing to decompile, patch bytecode, use debuggers)
- Protection level: reasonable deterrent — close obvious loopholes, add integrity checks, but don't invest in obfuscation theater
- Tier 2 approach: compiled enforcement, integrity checks, stronger fingerprinting, periodic re-validation

### Loophole #1: ENVIRONMENT=development bypass (CRITICAL)
- Strip dev-mode code entirely from the distributed build
- build-dist.sh removes the if/else dev-mode override block from main.py before packaging
- Shipped code has NO concept of development mode — license is always enforced
- Dev mode only exists in the source repository, never in the tarball

### Loophole #2: Plain-text enforcement in main.py (CRITICAL)
- Move license enforcement INTO the compiled licensing module
- The compiled module exposes a single function like `licensing.enforce(app)` that registers middleware and validates the license
- main.py just calls that one function — editing main.py to skip it means the app won't have enforcement registered, but integrity checking (#6) catches that
- All enforcement logic (middleware registration, status checking) lives in core/licensing/

### Loophole #3: Spoofable Docker fingerprint (MEDIUM)
- Add `/etc/machine-id` as a fingerprint signal (bind-mounted read-only into container)
- Add CPU info from `/proc/cpuinfo` as additional signal
- Keep existing MAC address signal
- Drop container_id (too ephemeral, changes on every recreate)
- WSL-aware: deployment runs on WSL, so `/etc/machine-id` is the WSL instance's ID
- docker-compose.yml gets a new read-only volume mount for `/etc/machine-id`

### Loophole #4: Trivial .pyc decompilation (MEDIUM)
- Compile licensing module with Cython to native `.so` instead of `.pyc`
- Produces real machine code — much harder to reverse than Python bytecode
- build-dist.sh updated to use Cython compilation instead of compileall
- Adds Cython as a build-time dependency (NOT shipped to customer)

### Loophole #5: Startup-only license check (LOW-MEDIUM)
- Re-validate license on every Nth request (not a background timer)
- The compiled enforcement middleware counts requests and re-runs validation periodically
- If license becomes invalid mid-runtime (expired, fingerprint changed), middleware starts blocking
- Request counter lives inside compiled module (harder to patch than app.state)

### Loophole #6: No file integrity verification (LOW-MEDIUM)
- SHA256 manifest of critical files embedded in the compiled `.so` module
- Protected files: main.py, middleware.py, docker-compose.yml
- On startup + periodic re-validation, the module hashes these files and compares against embedded manifest
- If any file is modified, license validation fails
- Manifest is generated at build time by build-dist.sh and baked into the Cython source before compilation

### build-dist.sh Updates
- Replace `compileall` with Cython compilation for core/licensing/
- Add code stripping step: remove dev-mode block from main.py
- Generate SHA256 integrity manifest and embed in Cython source
- Update import validation to test `.so` loading instead of `.pyc`
- Validate that enforcement function is callable from main.py

### License Renewal Flow
- Add a mechanism for customers to renew without getting an entirely new key
- Specifics left to Claude's discretion during planning

### TDD Approach
- Test-driven development: write/update tests before implementation
- Existing test infrastructure: 38 E2E tests (Playwright), 426 unit tests (pytest), license E2E tests (docker-compose.license-test.yml on port 8001)
- Run full test suite after each phase implementation
- Extend license.spec.ts for new scenarios (integrity check failure, periodic re-validation, renewal)
- Extend tests/core/licensing/test_license_manager.py for new fingerprinting, Nth-request checking

### Documentation Sync
- Update docs after each change (not deferred to end)
- Key docs to keep current: docs/LICENSING.md, docs/SETUP.md, ERROR-MAP.md
- build-dist.sh inline comments updated with new Cython flow

### Claude's Discretion
- Cython compilation specifics (setup.py vs meson, compiler flags)
- Exact N value for request-based re-validation
- License renewal protocol details
- How to handle integrity check failures gracefully (error messages, logging)
- Fingerprint similarity scoring vs exact match

</decisions>

<specifics>
## Specific Ideas

- Deployment runs on WSL (not bare metal Linux) — fingerprinting must account for WSL-specific behaviors
- "Reasonable deterrent" — not trying to stop nation-state actors, just making it cost more time than buying a license
- Existing license E2E test pattern (docker-compose.license-test.yml, separate container on port 8001) should be extended, not replaced

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `core/licensing/license_manager.py`: Full license validation pipeline (fingerprint, encode, decode, validate) — will be refactored and compiled to .so
- `scripts/build-dist.sh`: Distribution builder — needs Cython compilation, code stripping, manifest generation
- `scripts/verify-dist.sh`: Distribution verification — needs updates for .so validation
- `e2e/license.spec.ts`: License E2E tests — extend for new scenarios
- `tests/core/licensing/test_license_manager.py`: Unit tests — extend for new fingerprinting

### Established Patterns
- License enforcement as FastAPI middleware (main.py:381-427)
- License info stored in `app.state.license_info`
- Grace period (7 days) with X-License-Warning header
- /health always allowed (even with invalid license) for diagnostics
- docker-compose.license-test.yml for isolated production-mode testing

### Integration Points
- `main.py` lifespan function (lines 162-203) — where license validation happens at startup
- `main.py` middleware (lines 381-427) — where enforcement blocks requests
- `docker-compose.yml` — needs /etc/machine-id volume mount
- `build-dist.sh` — primary build pipeline changes
- `scripts/generate_license.py` — key generation (stays on our machine, not shipped)
- `scripts/get_machine_id.py` — customer runs this to get fingerprint (needs updating for new signals)

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within milestone scope.

</deferred>

---

*Milestone: v2.1 Licensing & Distribution Security*
*Context gathered: 2026-03-10*
