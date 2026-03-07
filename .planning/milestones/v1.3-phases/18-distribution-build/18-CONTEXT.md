# Phase 18: Distribution Build - Context

**Gathered:** 2026-03-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Build script that compiles the licensing module (`core/licensing/`) to `.pyc`, strips `.py` source, excludes developer artifacts, and packages the project as a tarball for customer delivery. The customer receives a clean archive they can extract and run `bootstrap.sh` from.

</domain>

<decisions>
## Implementation Decisions

### Package scope
- Full repo copy as the base, then strip dev-only files
- Remove `.git/` directory — customer gets no commit history, can't accidentally push
- Aggressive strip: remove `tests/`, `.planning/`, `.github/`, `.claude/`, `plan/`, `.vscode/`, `node_modules/`, `__pycache__/`, non-user-facing `*.md` files
- Keep user-facing docs: README.md, DEPLOY.md, CSV_FORMAT.md, SETUP.md
- Only `core/licensing/*.py` compiled to `.pyc` and `.py` stripped — rest of Python source stays as-is (matches DIST-01 requirement and threat model)

### Build output format
- Shell script: `scripts/build-dist.sh` (consistent with bootstrap.sh, start.sh, install.sh pattern)
- Takes version argument: `./scripts/build-dist.sh v1.3`
- Produces tarball: `dist/kerala-delivery-v1.3.tar.gz`
- Output directory: `dist/` (gitignored)
- No dry-run mode — version arg is required, no other flags

### Developer scripts handling
- Exclude `scripts/generate_license.py` — must NOT ship (contains HMAC signing logic)
- Include `scripts/get_machine_id.py` — customer needs it to report machine fingerprint for license key requests
- Build script warns if `.env.example` still has placeholder Google Maps API key (GOOGLE_MAPS_API_KEY not set or empty)
- If `license.key` file exists in project root, include it in the distribution (optional pre-bake)
- After .pyc compilation and .py removal, run import test: `python -c "from core.licensing import validate_license"` to verify the module loads

### Docker integration
- .pyc compilation happens in build-dist.sh only (not in Dockerfile)
- Ship `docker-compose.yml` only (dev compose) — prod compose is for VPS deployment, not office WSL use
- No Docker build verification in the build script — developer tests separately
- Exclude `node_modules/` — Docker build handles `npm install`

### Claude's Discretion
- Exact list of excluded markdown files vs kept user-facing docs
- Color output helpers (reuse from install.sh or standalone)
- Temporary build directory cleanup approach
- .gitignore entry for dist/

</decisions>

<specifics>
## Specific Ideas

- The licensing module docstring already references `make dist` — update it to reference `scripts/build-dist.sh` after implementation
- build-dist.sh should use the same color helper pattern as install.sh (GREEN/RED/YELLOW/BOLD/NC with info/success/warn/error functions) for visual consistency
- The import test should run against the staging directory (after .py removal) to verify the distribution works, not the source tree

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/install.sh`: Color helpers (info/success/warn/error/header functions) — reuse pattern in build-dist.sh
- `core/licensing/__init__.py` + `core/licensing/license_manager.py`: The two .py files to compile to .pyc
- `scripts/generate_license.py`: Developer-only script to exclude from distribution
- `scripts/get_machine_id.py`: Customer-facing script to include in distribution
- `docker-compose.prod.yml`: Exclude from distribution (VPS deployment, not office WSL)

### Established Patterns
- Shell scripts use `set -euo pipefail` for safety
- Scripts live in `scripts/` directory
- Color output with named functions (info, success, warn, error, header)
- `.env.example` contains pre-baked Google Maps API key for customer delivery

### Integration Points
- `build-dist.sh` produces tarball → developer transfers to customer WSL → customer extracts → runs `bootstrap.sh`
- `.pyc` files must be compatible with the Python version in the Docker image (`infra/Dockerfile`)
- `dist/` directory needs `.gitignore` entry

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 18-distribution-build*
*Context gathered: 2026-03-06*
