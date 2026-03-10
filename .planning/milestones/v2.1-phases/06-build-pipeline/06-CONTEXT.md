# Phase 6: Build Pipeline -- Dev-Mode Stripping and Cython Compilation - Context

**Gathered:** 2026-03-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Transform the distribution build pipeline from .pyc bytecode to Cython-compiled .so native code, strip all dev-mode bypasses from distributed builds, and rotate the compromised HMAC derivation credentials. The distributed tarball must contain zero ENVIRONMENT references and no decompilable Python source for licensing modules.

</domain>

<decisions>
## Implementation Decisions

### Dev-mode stripping
- Hardcode production behavior in distributed builds — no ENVIRONMENT toggle
- Refactor main.py so production is the default codepath; dev conveniences (permissive CORS, /docs) only activate when ENVIRONMENT=development is explicitly set
- /docs (Swagger UI) disabled entirely in distributed builds — no localhost-only fallback
- CRITICAL: Run unit tests after every refactoring change. Keep backups if necessary. Verify nothing breaks.

### HMAC seed rotation
- Rotate ALL THREE values: seed, salt, and iteration count (increase iterations, e.g., 200k)
- New seed: random bytes (os.urandom(32)), embedded as hex literal — not human-readable
- generate_license.py must import _HMAC_KEY from license_manager (single source of truth)
- No fallback to old seed — clean break, old licenses simply won't validate

### Cython build environment
- Compile .so INSIDE Docker using the same python:3.12-slim base image as deployment
- Dedicated build Dockerfile (e.g., infra/Dockerfile.build) with Cython + gcc — keeps runtime image clean
- Compile scope: core/licensing/ only (2 files: __init__.py, license_manager.py) — Phase 7 will add more
- Cython -O2 optimization, embedsignature=False per BLD-03

### Customer migration timing
- Document migration procedure NOW while context is fresh (fingerprint change + HMAC rotation = double break)
- Execute actual migration in Phase 10 (E2E Validation) — ship all breaking changes together
- No dual-key grace period — clean break, customer must have new license before upgrading

### Claude's Discretion
- CORS dev-mode approach (how to handle dev CORS without ENVIRONMENT variable)
- HMAC seed storage approach (hardcode in source vs build-time injection)
- Build pipeline ordering details within the strip -> hash -> compile -> validate -> package sequence
- Exact Cython setup.py / pyproject.toml configuration

</decisions>

<specifics>
## Specific Ideas

- User emphasized extreme caution during main.py refactor: "absolutely positively make sure everything works, keep backups if necessary, run unit tests after every change"
- Migration docs should be written in this phase even though execution is Phase 10 — captures context while fresh

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/build-dist.sh`: Existing build pipeline with rsync staging, .pyc compilation, import validation, tarball packaging. Will be upgraded in-place.
- `infra/Dockerfile`: Runtime Docker image. Build Dockerfile will be a separate file sharing the same base image.

### Established Patterns
- .pyc compilation with `-b` flag (legacy placement) — will be replaced by Cython .so
- Import validation: `PYTHONPATH="$STAGE" python3 -c "import core.licensing..."` — same pattern continues for .so
- rsync exclusion list for staging directory — already strips .git, tests, .planning, etc.

### Integration Points
- `core/licensing/license_manager.py` — HMAC seed lives here (line 51), fingerprint functions from Phase 5
- `core/licensing/__init__.py` — module docstring references HMAC, needs compile
- `scripts/generate_license.py` — must import from license_manager instead of duplicating seed
- `apps/kerala_delivery/api/main.py` — 4 ENVIRONMENT checks (lines 149, 239, 328, 343) to refactor
- `docker-compose.yml` / `docker-compose.license-test.yml` — may need build service for Cython compilation

</code_context>

<deferred>
## Deferred Ideas

- Customer migration execution — Phase 10 (DOC-03)
- Enforcement module compilation (main.py enforcement logic) — Phase 7
- Integrity manifest embedding in .so — Phase 7 (RTP-01)

</deferred>

---

*Phase: 06-build-pipeline*
*Context gathered: 2026-03-10*
