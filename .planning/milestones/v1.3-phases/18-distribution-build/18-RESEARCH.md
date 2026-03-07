# Phase 18: Distribution Build - Research

**Researched:** 2026-03-06
**Domain:** Shell scripting, Python bytecode compilation, tarball packaging
**Confidence:** HIGH

## Summary

Phase 18 builds a shell script (`scripts/build-dist.sh`) that packages the project for customer delivery. The script copies the project tree, strips developer artifacts (`.git/`, `tests/`, `.planning/`, etc.), compiles the licensing module (`core/licensing/`) to `.pyc` bytecode, removes the `.py` source for that module only, and produces a versioned tarball. The customer extracts the tarball and runs `bootstrap.sh`.

The critical technical finding is that Python 3.12 `.pyc` files from the default `__pycache__/` directory (PEP 3147 format) **do NOT work** when the corresponding `.py` source is removed. The `.pyc` files must be placed directly alongside where the `.py` files were (legacy placement) using `python3 -m compileall -b`. This was verified experimentally on the project's Python 3.12.3 installation.

**Primary recommendation:** Use `rsync --exclude` to create a clean copy, `python3 -m compileall -b` to compile `.pyc` in legacy placement, remove `.py` source for the licensing module only, then `tar czf` to produce the final archive. Follow existing script conventions (color helpers, `set -euo pipefail`, header comments).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Full repo copy as the base, then strip dev-only files
- Remove `.git/` directory -- customer gets no commit history
- Aggressive strip: remove `tests/`, `.planning/`, `.github/`, `.claude/`, `plan/`, `.vscode/`, `node_modules/`, `__pycache__/`, non-user-facing `*.md` files
- Keep user-facing docs: README.md, DEPLOY.md, CSV_FORMAT.md, SETUP.md
- Only `core/licensing/*.py` compiled to `.pyc` and `.py` stripped -- rest of Python source stays as-is
- Shell script: `scripts/build-dist.sh` (consistent with bootstrap.sh, start.sh, install.sh pattern)
- Takes version argument: `./scripts/build-dist.sh v1.3`
- Produces tarball: `dist/kerala-delivery-v1.3.tar.gz`
- Output directory: `dist/` (gitignored)
- No dry-run mode -- version arg is required, no other flags
- Exclude `scripts/generate_license.py` -- must NOT ship (contains HMAC signing logic)
- Include `scripts/get_machine_id.py` -- customer needs it for machine fingerprint
- Build script warns if `.env.example` has placeholder Google Maps API key
- If `license.key` file exists in project root, include it in the distribution
- After .pyc compilation and .py removal, run import test: `python -c "from core.licensing import validate_license"` to verify the module loads
- `.pyc` compilation happens in build-dist.sh only (not in Dockerfile)
- Ship `docker-compose.yml` only (not prod compose)
- No Docker build verification in the build script
- Exclude `node_modules/` -- Docker build handles `npm install`

### Claude's Discretion
- Exact list of excluded markdown files vs kept user-facing docs
- Color output helpers (reuse from install.sh or standalone)
- Temporary build directory cleanup approach
- .gitignore entry for dist/

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DIST-01 | Build script compiles licensing module to .pyc and strips .py source for customer delivery | Fully supported: `python3 -m compileall -b` for legacy .pyc placement, rsync for clean copy with exclusions, tar for packaging. All tools verified available on the build host. |
</phase_requirements>

## Standard Stack

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| bash | 5.x | Script runtime | All project scripts use bash with `set -euo pipefail` |
| python3 -m compileall | 3.12 stdlib | .pyc compilation | Built-in, no dependencies, `-b` flag for legacy placement |
| rsync | 3.2.7 | File copy with exclusions | Available on system, superior to `cp` for selective copy |
| tar/gzip | GNU tar 1.35 | Archive creation | Standard, produces `.tar.gz` |

### Supporting
| Tool | Version | Purpose | When to Use |
|------|---------|---------|-------------|
| mktemp -d | coreutils | Temporary build directory | Safe temp directory for staging the distribution |
| python3 -c | 3.12.3 | Import validation test | Post-compilation verification |
| wc -c / du | coreutils | Tarball size reporting | User feedback on output size |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| rsync --exclude | cp + find -delete | rsync is cleaner for multi-pattern exclusion; cp+find requires two passes |
| python3 -m compileall -b | py_compile per-file | compileall handles directories recursively; per-file is more code |
| Legacy .pyc placement | PEP 3147 (__pycache__) | **PEP 3147 DOES NOT WORK without .py source** -- legacy is mandatory |

## Architecture Patterns

### Build Script Structure
```
scripts/build-dist.sh
  |-- Argument parsing (require version arg)
  |-- Color helpers (reuse pattern from install.sh/bootstrap.sh)
  |-- Create temp build directory (mktemp -d)
  |-- rsync project tree with exclusions to temp dir
  |-- Compile core/licensing/*.py to .pyc (legacy placement)
  |-- Remove core/licensing/*.py source files
  |-- Remove core/licensing/__pycache__/ directory
  |-- Run import validation test against staged directory
  |-- Warn about .env.example placeholder API key
  |-- Create dist/ directory
  |-- tar czf the versioned archive
  |-- Cleanup temp directory (trap EXIT)
  |-- Report success with tarball path and size
```

### Recommended File Layout
```
scripts/
  build-dist.sh       # NEW: distribution build script

dist/                  # OUTPUT (gitignored): versioned tarballs
  kerala-delivery-v1.3.tar.gz
```

### Pattern 1: Trap-based Cleanup
**What:** Use bash `trap` to ensure temp directory is always cleaned up
**When to use:** Any script that creates temporary resources
**Example:**
```bash
# Source: existing project pattern (bootstrap.sh uses similar)
BUILD_DIR=$(mktemp -d)
trap 'rm -rf "$BUILD_DIR"' EXIT

# All work happens in BUILD_DIR
# Cleanup is automatic on exit, error, or interrupt
```

### Pattern 2: rsync Exclusion for Clean Copy
**What:** Use rsync with multiple `--exclude` patterns for selective copy
**When to use:** Copying project tree while skipping many directories/files
**Example:**
```bash
rsync -a \
  --exclude='.git/' \
  --exclude='.github/' \
  --exclude='.claude/' \
  --exclude='.planning/' \
  --exclude='.vscode/' \
  --exclude='.playwright-mcp/' \
  --exclude='.pytest_cache/' \
  --exclude='.venv/' \
  --exclude='tests/' \
  --exclude='plan/' \
  --exclude='gsd-template/' \
  --exclude='node_modules/' \
  --exclude='__pycache__/' \
  --exclude='.env' \
  --exclude='.env.production.example' \
  --exclude='docker-compose.prod.yml' \
  --exclude='scripts/generate_license.py' \
  --exclude='scripts/__pycache__/' \
  --exclude='CLAUDE.md' \
  --exclude='GUIDE.md' \
  --exclude='pytest.ini' \
  --exclude='dist/' \
  ./ "$BUILD_DIR/kerala-delivery/"
```

### Pattern 3: Legacy .pyc Compilation
**What:** Compile Python to bytecode in legacy placement (same directory as source)
**When to use:** When .py source will be removed and .pyc must be importable standalone
**Example:**
```bash
# -b = legacy placement (same dir, not __pycache__/)
# -f = force recompile even if .pyc exists
# -q = quiet output (0 = show all, 1 = errors only)
python3 -m compileall -b -f -q "$BUILD_DIR/kerala-delivery/core/licensing/"
```

### Pattern 4: Color Helpers (Project Convention)
**What:** Consistent color output functions used by all project scripts
**When to use:** Every shell script in `scripts/`
**Example:**
```bash
# Matches install.sh, bootstrap.sh, start.sh exactly
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    BLUE='\033[0;34m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    GREEN='' YELLOW='' RED='' BLUE='' BOLD='' NC=''
fi

info()    { echo -e "${BLUE}->${NC} $*"; }
success() { echo -e "${GREEN}ok${NC} $*"; }
warn()    { echo -e "${YELLOW}!!${NC} $*"; }
error()   { echo -e "${RED}x${NC} $*" >&2; }
header()  { echo -e "\n${BOLD}$*${NC}"; echo "---"; }
```
Note: The actual Unicode symbols used are from the existing scripts. Planner should copy the exact helper block from `install.sh` lines 39-63.

### Anti-Patterns to Avoid
- **Using PEP 3147 (__pycache__) .pyc placement when removing .py source:** Python 3.12 CANNOT import from `__pycache__/*.cpython-312.pyc` when the `.py` file is missing. The import fails silently. MUST use legacy `-b` placement.
- **Compiling against the source tree:** The compilation and `.py` removal must happen in the staging directory, never the source tree. The source tree must remain untouched.
- **Forgetting `__init__.pyc`:** The `core/licensing/__init__.py` must also be compiled. Without it, `core.licensing` is not a valid package. `compileall -b` on the directory handles this automatically.
- **Hardcoding Python path:** Use `python3` not `python` -- the system may not have `python` symlinked. Or even better, detect with `command -v python3`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Selective file copy | Custom find+cp loops | `rsync --exclude` | rsync handles all edge cases (symlinks, permissions, nested excludes) |
| .pyc compilation | Manual `py_compile.compile()` calls per file | `python3 -m compileall -b` | Handles directory recursion, error reporting, legacy placement flag |
| Temp directory cleanup | Manual `rm -rf` at script end | `trap 'rm -rf "$DIR"' EXIT` | trap fires on error/interrupt/exit -- manual rm can be skipped on failure |
| Version validation | Regex parsing | Simple `[[ -z "${1:-}" ]]` check | Version is a label, not parsed semantically |

**Key insight:** Every component of this script has a well-established shell/Python tool. The script is orchestration glue, not custom logic.

## Common Pitfalls

### Pitfall 1: PEP 3147 .pyc Incompatibility with Source Removal
**What goes wrong:** Using default `compileall` (without `-b`) places `.pyc` in `__pycache__/` with versioned names like `__init__.cpython-312.pyc`. When the `.py` source is removed, Python 3.12 cannot import the module -- it returns `ImportError`.
**Why it happens:** Python's import system for PEP 3147 checks for the source file first. Without it, the import machinery does not reliably fall back to the `__pycache__/` bytecode.
**How to avoid:** Always use `python3 -m compileall -b` (the `-b` flag means "legacy bytecode location"). This places `__init__.pyc` and `license_manager.pyc` directly in the `core/licensing/` directory.
**Warning signs:** The import validation test (`python3 -c "from core.licensing.license_manager import validate_license"`) will fail if this is wrong.
**Confidence:** HIGH -- verified experimentally on Python 3.12.3.

### Pitfall 2: Import Test Path Must Match Staging Directory
**What goes wrong:** Running the import test against the source tree (which still has `.py` files) instead of the staged distribution directory (which only has `.pyc`).
**Why it happens:** Developer forgets to `cd` or set `PYTHONPATH` to the staging directory before running the test.
**How to avoid:** Run the test explicitly with the staged directory: `PYTHONPATH="$BUILD_DIR/kerala-delivery" python3 -c "from core.licensing.license_manager import validate_license"`.
**Warning signs:** Test passes even though `.pyc` compilation failed (because it's importing from source tree `.py` files).

### Pitfall 3: Incorrect Import Path in Validation Test
**What goes wrong:** CONTEXT.md specifies `from core.licensing import validate_license` but `validate_license` is NOT exported from `core/licensing/__init__.py`. It lives in `core/licensing/license_manager.py`.
**Why it happens:** The `__init__.py` is a docstring-only module -- it does not re-export from `license_manager`.
**How to avoid:** Use `from core.licensing.license_manager import validate_license` or simply `import core.licensing.license_manager` (which verifies both `.pyc` files load). Alternatively, importing both submodules: `python3 -c "import core.licensing; import core.licensing.license_manager"`.
**Warning signs:** Import test fails with `ImportError: cannot import name 'validate_license' from 'core.licensing'`.
**Confidence:** HIGH -- verified: `python3 -c "from core.licensing import validate_license"` fails even with `.py` source present.

### Pitfall 4: .env Leaking Into Distribution
**What goes wrong:** The `.env` file (containing real secrets like database passwords) gets included in the distribution tarball.
**Why it happens:** `.env` is not in the exclusion list, or rsync doesn't exclude it.
**How to avoid:** Explicitly `--exclude='.env'` in the rsync command. Only `.env.example` should ship.
**Warning signs:** Tarball contains `.env` file with real credentials.

### Pitfall 5: Python Version Mismatch Between Build Host and Docker
**What goes wrong:** `.pyc` compiled on Python 3.12 won't load on Python 3.11 (or vice versa). The magic number in the `.pyc` header (`cb0d0d0a` for 3.12) is version-specific.
**Why it happens:** Build host has a different Python minor version than the Docker image.
**How to avoid:** Both currently use Python 3.12 (`python:3.12-slim` in Dockerfile, Python 3.12.3 on host). The script should verify the Python version and warn if it doesn't match 3.12.
**Warning signs:** Runtime `ImportError` or `RuntimeError: Bad magic number` in Docker.
**Confidence:** HIGH -- `.pyc` magic number `cb0d0d0a` is tied to CPython 3.12.

### Pitfall 6: Tarball Root Directory Naming
**What goes wrong:** Tarball extracts files into the current directory (no containing folder) or uses an unintuitive root name.
**Why it happens:** `tar czf` without `-C` and proper path structuring.
**How to avoid:** Structure the staging directory so the tarball root is `kerala-delivery/` (not the temp dir path). Use `tar czf output.tar.gz -C "$BUILD_DIR" kerala-delivery/`.
**Warning signs:** Customer extracts and gets files scattered in their current directory.

## Code Examples

### Complete Build Flow (Pseudo-script)
```bash
#!/usr/bin/env bash
# Source: Synthesized from project patterns + research findings
set -euo pipefail

VERSION="${1:?Usage: $0 <version>  (e.g., v1.3)}"

# --- Color helpers (copy from install.sh lines 39-63) ---

# --- Create staging directory ---
BUILD_DIR=$(mktemp -d)
trap 'rm -rf "$BUILD_DIR"' EXIT

DIST_NAME="kerala-delivery"
STAGE="$BUILD_DIR/$DIST_NAME"

# --- Copy project with exclusions ---
rsync -a \
  --exclude='.git/' \
  --exclude='.github/' \
  --exclude='.claude/' \
  # ... (all exclusions)
  ./ "$STAGE/"

# --- Compile licensing module to .pyc (legacy placement) ---
python3 -m compileall -b -f -q "$STAGE/core/licensing/"

# --- Remove .py source from licensing module ---
rm "$STAGE/core/licensing/__init__.py"
rm "$STAGE/core/licensing/license_manager.py"

# --- Remove __pycache__ from licensing module (cleanup) ---
rm -rf "$STAGE/core/licensing/__pycache__/"

# --- Validate import from staged directory ---
PYTHONPATH="$STAGE" python3 -c "from core.licensing.license_manager import validate_license" \
  || { error "Import validation failed!"; exit 1; }

# --- Warn about placeholder API key ---
if grep -q 'your-key-here' "$STAGE/.env.example" 2>/dev/null; then
  warn ".env.example still has placeholder GOOGLE_MAPS_API_KEY"
fi

# --- Include license.key if present ---
# (rsync already copies it if it exists in the source tree)

# --- Create tarball ---
mkdir -p dist
tar czf "dist/$DIST_NAME-$VERSION.tar.gz" -C "$BUILD_DIR" "$DIST_NAME/"

success "Built dist/$DIST_NAME-$VERSION.tar.gz"
```

### .pyc Legacy Compilation Command
```bash
# Source: Verified on Python 3.12.3 -- produces .pyc files
# directly in core/licensing/ (not __pycache__/)
python3 -m compileall -b -f -q /path/to/staging/core/licensing/

# Result:
#   core/licensing/__init__.pyc      (from __init__.py)
#   core/licensing/license_manager.pyc (from license_manager.py)
```

### Import Validation Test
```bash
# Source: Verified -- correct import path for this project
# CONTEXT.md says "from core.licensing import validate_license" but
# that import FAILS because __init__.py does not re-export it.
# Correct import:
PYTHONPATH="$STAGE" python3 -c "from core.licensing.license_manager import validate_license"

# Alternative (tests both .pyc files load):
PYTHONPATH="$STAGE" python3 -c "import core.licensing; import core.licensing.license_manager"
```

### Exclusion List (Complete)
```bash
# Directories to exclude:
--exclude='.git/'                    # No commit history for customer
--exclude='.github/'                 # CI/CD, agent configs -- dev only
--exclude='.claude/'                 # Claude Code config -- dev only
--exclude='.planning/'               # GSD planning files -- dev only
--exclude='.vscode/'                 # IDE settings -- dev only
--exclude='.playwright-mcp/'         # Test tooling -- dev only
--exclude='.pytest_cache/'           # Test cache -- dev only
--exclude='.venv/'                   # Local venv -- dev only
--exclude='tests/'                   # Test suite -- dev only
--exclude='plan/'                    # Design docs, session journal -- dev only
--exclude='gsd-template/'            # GSD template -- dev only
--exclude='node_modules/'            # Docker handles npm install
--exclude='__pycache__/'             # Bytecode cache (rebuilt at runtime)
--exclude='dist/'                    # Previous builds
--exclude='backups/'                 # Database backups

# Files to exclude:
--exclude='.env'                     # Real secrets -- NEVER ship
--exclude='.env.production.example'  # VPS deployment -- not for office WSL
--exclude='docker-compose.prod.yml'  # VPS deployment compose
--exclude='scripts/generate_license.py'  # HMAC signing logic -- NEVER ship
--exclude='scripts/__pycache__/'     # Script bytecode cache
--exclude='CLAUDE.md'               # Dev instructions
--exclude='GUIDE.md'                # Dev guide (not user-facing)
--exclude='pytest.ini'              # Test config
--exclude='alembic.ini'             # DB migrations config (inside Docker)
--exclude='.gitignore'              # Git-specific -- no git in distribution

# Markdown files KEPT (user-facing):
# README.md, DEPLOY.md, CSV_FORMAT.md, SETUP.md
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `__pycache__/*.cpython-3X.pyc` (PEP 3147) | `compileall -b` for legacy `.pyc` | PEP 3147 since Python 3.2, `-b` flag always available | Must use `-b` when removing `.py` source |
| `Makefile` targets (`make dist`) | Shell script (`build-dist.sh`) | Project convention decision | Consistent with existing `scripts/*.sh` pattern |
| PyInstaller/cx_Freeze for distribution | Simple tarball + `.pyc` for licensing only | Out-of-scope decision | `.pyc` is sufficient deterrent per REQUIREMENTS.md |

**Deprecated/outdated:**
- The `core/licensing/__init__.py` docstring references `make dist` -- this should be updated to reference `scripts/build-dist.sh` per CONTEXT.md.

## Open Questions

1. **alembic.ini exclusion**
   - What we know: `alembic.ini` configures database migrations. The Docker container handles migrations internally.
   - What's unclear: Does the Docker build or entrypoint depend on `alembic.ini` being present in the project root?
   - Recommendation: Check if `alembic.ini` is copied into the Docker image in the Dockerfile. If yes, it must be included. If no (e.g., it's baked into the image or not needed), exclude it. **Research finding:** The Dockerfile likely copies the entire project root into the image, so `alembic.ini` should be included to be safe.

2. **data/ directory handling**
   - What we know: `data/` contains `kerala.osm.pbf`, `geocode_cache/`, and `osrm/` -- all gitignored large data files.
   - What's unclear: Should the empty `data/` directory structure be included for OSRM init container?
   - Recommendation: Include `data/` but it will be empty (gitignored files won't be in the source tree copy). rsync will copy only tracked content.

3. **tools/ directory**
   - What we know: Contains `tailwindcss-extra` binary (gitignored, ~60MB).
   - What's unclear: Is `tools/` needed at runtime?
   - Recommendation: Exclude `tools/` -- the Tailwind binary is for development CSS building, not production Docker runtime.

## Validation Architecture

> `workflow.nyquist_validation` key is absent from `.planning/config.json` -- treating as enabled.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Manual shell script validation (no automated test framework for shell scripts) |
| Config file | None -- this is a build script, not application code |
| Quick run command | `./scripts/build-dist.sh v0.0-test` |
| Full suite command | `./scripts/build-dist.sh v0.0-test && tar tzf dist/kerala-delivery-v0.0-test.tar.gz \| head -20` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DIST-01a | .pyc files produced for licensing module | smoke | `tar tzf dist/kerala-delivery-v0.0-test.tar.gz \| grep 'licensing.*\.pyc'` | N/A -- Wave 0 |
| DIST-01b | .py source stripped from licensing module | smoke | `tar tzf dist/kerala-delivery-v0.0-test.tar.gz \| grep 'licensing.*\.py$' \| grep -v '.pyc' && echo FAIL \|\| echo PASS` | N/A -- Wave 0 |
| DIST-01c | System runs with .pyc-only licensing | smoke | Built into build-dist.sh (import validation test) | N/A -- Wave 0 |
| DIST-01d | generate_license.py excluded | smoke | `tar tzf dist/kerala-delivery-v0.0-test.tar.gz \| grep generate_license && echo FAIL \|\| echo PASS` | N/A -- Wave 0 |
| DIST-01e | .git excluded | smoke | `tar tzf dist/kerala-delivery-v0.0-test.tar.gz \| grep '\.git/' && echo FAIL \|\| echo PASS` | N/A -- Wave 0 |
| DIST-01f | User docs included | smoke | `tar tzf dist/kerala-delivery-v0.0-test.tar.gz \| grep -E '(README|DEPLOY|CSV_FORMAT|SETUP)\.md'` | N/A -- Wave 0 |

### Sampling Rate
- **Per task commit:** `./scripts/build-dist.sh v0.0-test` (run build, verify output)
- **Per wave merge:** Full suite: build + tar content inspection + import test
- **Phase gate:** Tarball produced, all smoke tests pass

### Wave 0 Gaps
- [ ] `scripts/build-dist.sh` -- the entire deliverable (does not exist yet)
- [ ] `dist/` directory creation is handled by the script itself
- [ ] No framework install needed -- uses bash + python3 stdlib only

## Sources

### Primary (HIGH confidence)
- Python 3.12.3 `compileall` module -- verified `-b` flag behavior experimentally
- Python 3.12.3 `py_compile` module -- verified legacy .pyc placement
- Python 3.12.3 import system -- **experimentally confirmed** PEP 3147 .pyc FAILS without .py source, legacy .pyc WORKS
- Project codebase: `scripts/install.sh`, `scripts/bootstrap.sh`, `scripts/start.sh` -- color helper patterns
- Project codebase: `core/licensing/__init__.py`, `core/licensing/license_manager.py` -- module structure
- Project codebase: `infra/Dockerfile` -- confirms Python 3.12-slim base image
- Project codebase: `.gitignore` -- confirms `dist/` already gitignored

### Secondary (MEDIUM confidence)
- `rsync 3.2.7` `--exclude` flag behavior -- standard, well-documented
- `tar` (GNU 1.35) `-C` flag for directory-relative archiving -- standard

### Tertiary (LOW confidence)
- `alembic.ini` inclusion/exclusion decision -- needs verification against Dockerfile COPY commands
- `tools/` directory exclusion -- assumed not needed at runtime but not fully verified

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all tools are system utilities and Python stdlib, verified available
- Architecture: HIGH -- project has established shell script conventions, patterns extracted from 3 existing scripts
- Pitfalls: HIGH -- critical .pyc placement issue verified experimentally; import path issue verified against actual codebase
- Exclusion list: MEDIUM -- most items are clear from CONTEXT.md, a few (alembic.ini, tools/) need verification

**Research date:** 2026-03-06
**Valid until:** 2026-04-06 (stable domain -- shell scripting and Python bytecode compilation are mature)
