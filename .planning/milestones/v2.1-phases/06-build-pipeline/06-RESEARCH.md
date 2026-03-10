# Phase 6: Build Pipeline -- Dev-Mode Stripping and Cython Compilation - Research

**Researched:** 2026-03-10
**Domain:** Build pipeline automation, Cython native compilation, security hardening
**Confidence:** HIGH

## Summary

This phase transforms the distribution build from `.pyc` bytecode to Cython-compiled `.so` native code, strips all `ENVIRONMENT` variable bypasses from distributed builds, and rotates the compromised HMAC derivation credentials. The phase touches four files directly (`main.py`, `license_manager.py`, `__init__.py`, `build-dist.sh`) plus creates one new file (`infra/Dockerfile.build`).

The main technical risks are: (1) the `__init__.py` compilation pitfall -- Cython historically could not compile `__init__.py` to `.so` (resolved in Cython 3.0 but still fragile with some tooling); the safest approach is to keep `__init__.py` as a minimal plain-text stub and compile only `license_manager.py`; (2) the `main.py` refactor has four distinct ENVIRONMENT-dependent code paths that must be carefully restructured without breaking dev-mode workflows or existing tests; (3) HMAC seed rotation is a breaking change -- all existing license keys become permanently invalid.

**Primary recommendation:** Compile `license_manager.py` to `.so` but keep `__init__.py` as a minimal stub `.py` file (docstring + re-exports only). Use a dedicated `infra/Dockerfile.build` with `python:3.12-slim` + `gcc` + `Cython==3.2.4` for compilation. Refactor `main.py` so production is the default codepath with dev conveniences gated behind an explicit `ENVIRONMENT=development` check (inverted from current logic).

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Hardcode production behavior in distributed builds -- no ENVIRONMENT toggle
- Refactor main.py so production is the default codepath; dev conveniences (permissive CORS, /docs) only activate when ENVIRONMENT=development is explicitly set
- /docs (Swagger UI) disabled entirely in distributed builds -- no localhost-only fallback
- CRITICAL: Run unit tests after every refactoring change. Keep backups if necessary. Verify nothing breaks.
- Rotate ALL THREE values: seed, salt, and iteration count (increase iterations, e.g., 200k)
- New seed: random bytes (os.urandom(32)), embedded as hex literal -- not human-readable
- generate_license.py must import _HMAC_KEY from license_manager (single source of truth)
- No fallback to old seed -- clean break, old licenses simply won't validate
- Compile .so INSIDE Docker using the same python:3.12-slim base image as deployment
- Dedicated build Dockerfile (e.g., infra/Dockerfile.build) with Cython + gcc -- keeps runtime image clean
- Compile scope: core/licensing/ only (2 files: __init__.py, license_manager.py) -- Phase 7 will add more
- Cython -O2 optimization, embedsignature=False per BLD-03
- Document migration procedure NOW while context is fresh (fingerprint change + HMAC rotation = double break)
- Execute actual migration in Phase 10 (E2E Validation) -- ship all breaking changes together
- No dual-key grace period -- clean break, customer must have new license before upgrading

### Claude's Discretion
- CORS dev-mode approach (how to handle dev CORS without ENVIRONMENT variable)
- HMAC seed storage approach (hardcode in source vs build-time injection)
- Build pipeline ordering details within the strip -> hash -> compile -> validate -> package sequence
- Exact Cython setup.py / pyproject.toml configuration

### Deferred Ideas (OUT OF SCOPE)
- Customer migration execution -- Phase 10 (DOC-03)
- Enforcement module compilation (main.py enforcement logic) -- Phase 7
- Integrity manifest embedding in .so -- Phase 7 (RTP-01)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ENF-01 | Dev-mode code stripped from distributed builds (no ENVIRONMENT=development bypass exists in tarball) | main.py refactor pattern: invert default from "dev" to "prod"; strip dev-mode via build-dist.sh post-processing + code refactor |
| ENF-02 | Licensing module compiled to native .so via Cython (replaces decompilable .pyc) | Cython 3.2.4 setup.py with Extension + cythonize pattern; build inside Docker with Dockerfile.build |
| ENF-04 | HMAC derivation seed rotated (old .pyc seed is compromised) | Replace _DERIVATION_SEED with os.urandom(32) hex literal; rotate salt and increase iterations to 200k |
| BLD-01 | build-dist.sh pipeline: strip dev-mode -> hash protected files -> Cython compile -> validate .so import -> package tarball | Detailed pipeline ordering in Architecture Patterns section |
| BLD-02 | Build-time .so import validation inside Docker before packaging (catches platform mismatch) | Docker exec pattern: build .so inside container, validate import inside same container |
| BLD-03 | Cython -O2 optimization flags and embedsignature=False applied | Extension extra_compile_args=["-O2"] + compiler_directives={"embedsignature": False} |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Cython | 3.2.4 | Compile .py to .so via C intermediate | Latest stable, supports Python 3.8-3.14, full Python 3.12 support |
| setuptools | (bundled) | Build system for Extension modules | Standard Python build backend, works with cythonize() |
| gcc | (apt) | C compiler for .so generation | Default C compiler in python:3.12-slim, required by Cython |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python3-dev | (apt) | Python C headers for compilation | Required in build Dockerfile for Cython to find Python.h |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| setup.py + cythonize | pyproject.toml ext-modules | pyproject.toml ext-modules is experimental; setup.py is proven and documented |
| Cython | Nuitka | Nuitka produces standalone executables, not importable .so modules; overkill |
| Cython | PyArmor | Obfuscation theater per project out-of-scope decisions |

**Installation (build Dockerfile only -- NOT runtime):**
```bash
pip install Cython==3.2.4
apt-get install -y --no-install-recommends gcc python3-dev
```

## Architecture Patterns

### Build Pipeline Ordering (BLD-01)

The pipeline must execute in this exact order:

```
build-dist.sh v2.1
  |
  1. STAGE: rsync project tree (existing, exclude dev artifacts)
  |
  2. STRIP: grep -r removal/validation of ENVIRONMENT references
  |     - Verify zero ENVIRONMENT matches in staged .py files
  |     - This catches any missed refactoring
  |
  3. HASH: SHA256 hash of core/licensing/*.py (before compilation)
  |     - Store hashes for Phase 7 integrity manifest
  |     - This step is a placeholder now, becomes critical in Phase 7
  |
  4. COMPILE: Docker-based Cython compilation
  |     - docker build -f infra/Dockerfile.build
  |     - Produces .so files inside container
  |     - docker cp extracts .so files to staging directory
  |
  5. VALIDATE: Import validation inside Docker
  |     - docker run with PYTHONPATH pointing to staged directory
  |     - python -c "from core.licensing.license_manager import get_machine_fingerprint"
  |     - Catches platform mismatch, missing dependencies
  |
  6. CLEAN: Remove .py source from compiled modules
  |     - rm staged core/licensing/license_manager.py
  |     - Keep __init__.py (stub, not compiled -- see Pitfall 1)
  |
  7. PACKAGE: tar czf dist/kerala-delivery-v2.1.tar.gz
```

### Recommended Project Structure Changes

```
infra/
  Dockerfile           # Runtime image (existing, unchanged)
  Dockerfile.build     # NEW: Cython build image (gcc + Cython + python3-dev)
core/licensing/
  __init__.py          # KEEP as .py stub (minimal re-exports, no secrets)
  license_manager.py   # Source -- compiled to .so, .py removed from dist
scripts/
  build-dist.sh        # UPGRADED: new pipeline with Cython + Docker steps
docs/
  MIGRATION.md         # NEW: customer migration procedure
```

### Pattern 1: Cython Build via setup.py

**What:** Compile license_manager.py to a platform-specific .so using setuptools + Cython
**When to use:** For compiling pure Python to native extensions without .pyx files

```python
# infra/cython_build.py (used inside Dockerfile.build)
from setuptools import setup, Extension
from Cython.Build import cythonize

extensions = [
    Extension(
        "core.licensing.license_manager",
        ["core/licensing/license_manager.py"],
        extra_compile_args=["-O2"],
    ),
]

setup(
    ext_modules=cythonize(
        extensions,
        compiler_directives={
            "language_level": "3",
            "embedsignature": False,
        },
    ),
)
```

Build command: `python infra/cython_build.py build_ext --inplace`

This produces `core/licensing/license_manager.cpython-312-x86_64-linux-gnu.so` in-place next to the source.

### Pattern 2: Dedicated Build Dockerfile

**What:** Docker image with build tools for Cython compilation
**When to use:** Compile .so matching the exact runtime platform

```dockerfile
# infra/Dockerfile.build
FROM python:3.12-slim AS cython-builder

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc python3-dev && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir Cython==3.2.4

WORKDIR /build
COPY core/ core/
COPY infra/cython_build.py .

RUN python cython_build.py build_ext --inplace

# Validate the .so imports correctly
RUN python -c "from core.licensing.license_manager import get_machine_fingerprint; print('Import OK')"
```

### Pattern 3: main.py Production-Default Refactor

**What:** Invert the ENVIRONMENT logic so production is the default behavior
**When to use:** All four ENVIRONMENT checks in main.py

Current pattern (INSECURE -- dev is default):
```python
_env_name = os.environ.get("ENVIRONMENT", "development")
_docs_url = "/docs" if _env_name != "production" else None
```

New pattern (production is default):
```python
_is_dev_mode = os.environ.get("ENVIRONMENT") == "development"
_docs_url = "/docs" if _is_dev_mode else None
```

This means: if ENVIRONMENT is unset, missing, or anything other than "development", production behavior applies. Only an explicit `ENVIRONMENT=development` enables dev conveniences.

### Pattern 4: HMAC Seed Rotation

**What:** Replace human-readable seed with cryptographically random hex literal
**When to use:** One-time rotation of all three HMAC derivation parameters

```python
# Generate new values (run once, embed results):
# python -c "import os; print(os.urandom(32).hex())"
# python -c "import os; print(os.urandom(16).hex())"

_DERIVATION_SEED = bytes.fromhex(
    "a7f3...64 hex chars..."  # os.urandom(32), generated at build time
)
_PBKDF2_SALT = bytes.fromhex(
    "b2e1...32 hex chars..."  # os.urandom(16), generated at build time
)
_PBKDF2_ITERATIONS = 200_000  # Increased from 100k

_HMAC_KEY = hashlib.pbkdf2_hmac(
    "sha256",
    _DERIVATION_SEED,
    salt=_PBKDF2_SALT,
    iterations=_PBKDF2_ITERATIONS,
)
```

### Anti-Patterns to Avoid
- **Compiling __init__.py to .so:** While Cython 3.0+ technically supports this, it remains fragile. Keep __init__.py as a minimal .py stub. (See Pitfall 1.)
- **Leaving ENVIRONMENT in code with "production" default string:** The CONTEXT.md says "no ENVIRONMENT toggle" in distributed builds. The grep check in the build pipeline catches this.
- **Hardcoding the seed in generate_license.py:** generate_license.py already imports from license_manager. After rotation, it automatically uses the new seed. Do NOT duplicate.
- **Using `cythonize` CLI directly:** Use setup.py with Extension objects for fine-grained control over compiler flags and directives.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| .py to .so compilation | Manual cython + gcc commands | setuptools Extension + cythonize() | Handles include paths, link flags, naming conventions automatically |
| Cross-platform .so naming | Manual .so file naming | build_ext --inplace | Python extension naming convention: `module.cpython-312-x86_64-linux-gnu.so` is complex |
| HMAC key derivation | Custom KDF | hashlib.pbkdf2_hmac (stdlib) | Already in use, battle-tested, no external dependency |
| Random seed generation | Manual random | os.urandom(32) | OS-level CSPRNG, suitable for cryptographic keys |
| Docker-based compilation | Host compilation | Dockerfile.build | Guarantees ABI compatibility with runtime image |

**Key insight:** Compiling on the host machine and deploying in Docker WILL produce ABI-incompatible .so files if Python versions or glibc versions differ. Always compile inside the same base image used for deployment.

## Common Pitfalls

### Pitfall 1: __init__.py Compilation Fragility
**What goes wrong:** Cython compiles `__init__.py` to `__init__.cpython-312-x86_64-linux-gnu.so` but Python's import system historically cannot find it as a package initializer because it expects `__init__.py` or `__init__.pyc`, not `__init__.so`.
**Why it happens:** Python's import machinery treats `__init__` as a special case. While Cython 3.0+ added support for `__init__.pyx`, many tools (sphinx, pytest, linters) still break when `__init__.py` is a compiled extension.
**How to avoid:** Keep `__init__.py` as a plain-text Python file. Move all sensitive content (HMAC references in docstring) to comments that are benign. Only compile `license_manager.py`.
**Warning signs:** `ImportError: No module named 'core.licensing'` when .py is removed and only .so exists.

### Pitfall 2: Platform Mismatch Between Build and Runtime
**What goes wrong:** `.so` compiled on host Linux (glibc 2.35) fails to load in Docker container (glibc 2.31) or vice versa. Error: `ImportError: ... undefined symbol ...`
**Why it happens:** Cython extensions link against the host's Python shared library and C library at compile time. Different Python minor versions or glibc versions produce incompatible binaries.
**How to avoid:** Compile INSIDE the Docker container using the same `python:3.12-slim` base image. Extract the .so via `docker cp`.
**Warning signs:** Works on build machine, fails in Docker. ImportError with symbol resolution failures.

### Pitfall 3: ENVIRONMENT Grep False Positives
**What goes wrong:** `grep -r "ENVIRONMENT"` matches comments, docstrings, or unrelated uses, causing the build to fail spuriously.
**Why it happens:** Naive grep matches any occurrence of "ENVIRONMENT" in any file.
**How to avoid:** Target the grep specifically: search only `.py` files, use a pattern like `os.environ.*ENVIRONMENT` or limit to `apps/` and `core/` directories. Exclude comments if needed.
**Warning signs:** Build fails on innocuous comment or documentation reference.

### Pitfall 4: Test Suite Breaks After ENVIRONMENT Refactor
**What goes wrong:** Existing test `test_docs_gated_in_production` (line 1963 in test_api.py) patches `ENVIRONMENT=production` and reloads the module. After the refactor, the test logic needs updating because the default behavior changes.
**Why it happens:** The test was written for the old pattern where `ENVIRONMENT` defaults to "development". The new pattern inverts this.
**How to avoid:** Update the test to match the new semantics: test that dev features are OFF by default, and ON only when `ENVIRONMENT=development`.
**Warning signs:** Test failures in `TestSecurityHeaders::test_docs_gated_in_production` after refactor.

### Pitfall 5: HMAC Seed Rotation Invalidates All Existing Keys
**What goes wrong:** After rotating the seed, ALL previously generated license keys fail validation. The customer's system immediately enters INVALID state on upgrade.
**Why it happens:** The HMAC key derived from the new seed produces different signatures. Existing keys were signed with the old key.
**How to avoid:** This is intentional (clean break per user decision). Document the migration procedure. Generate new license keys with the new seed BEFORE shipping the upgrade.
**Warning signs:** Any test using hardcoded license keys will fail. All test fixtures need regeneration.

### Pitfall 6: generate_license.py Already Imports Correctly
**What goes wrong:** Accidentally duplicating the HMAC seed in generate_license.py, creating two sources of truth that can drift.
**Why it happens:** Assuming generate_license.py has its own seed copy (it doesn't -- it already imports from license_manager).
**How to avoid:** Verify before modifying: `generate_license.py` already does `from core.licensing.license_manager import encode_license_key`. No changes needed to generate_license.py for seed rotation.
**Warning signs:** Diff showing HMAC constants added to generate_license.py.

### Pitfall 7: Cython async def Limitations
**What goes wrong:** If any function in the compiled module uses `async def`, Cython compiles it but `asyncio.iscoroutinefunction()` returns False, breaking FastAPI's dependency injection.
**Why it happens:** Cython's coroutine implementation doesn't set the flags that asyncio checks.
**How to avoid:** `license_manager.py` uses only synchronous functions. Verify no `async def` exists in the file before compiling. This is not an issue for Phase 6 but becomes critical in Phase 7 when compiling enforcement logic.
**Warning signs:** FastAPI middleware silently fails to `await` compiled async functions.

## Code Examples

### Verified: Existing ENVIRONMENT Usage in main.py

Four locations that reference ENVIRONMENT (must all be refactored):

```python
# Location 1: Lifespan function (line 149) - API key warning
env = os.environ.get("ENVIRONMENT", "development")
if not api_key and env != "development":
    logger.warning(...)

# Location 2: Lifespan function (line 185) - License enforcement bypass
if env == "production":
    logger.error(...)
else:
    # Dev mode: override license to VALID
    license_info = LicenseInfo(customer_id="dev-mode", ...)

# Location 3: Module-level (line 239) - Docs URL gating
_env_name = os.environ.get("ENVIRONMENT", "development")
_docs_url = "/docs" if _env_name != "production" else None

# Location 4: Module-level (line 328/343) - HSTS + CORS
if _env_name != "development":
    _secweb_options["hsts"] = {...}
if _env_name == "development" and not _cors_origins_raw:
    _allowed_origins = ["http://localhost:8000", ...]
```

### Verified: Existing HMAC Configuration in license_manager.py

```python
# Lines 51-65 -- ALL THREE values must change:
_DERIVATION_SEED = b"kerala-logistics-platform-2025-route-optimizer"  # Line 51
_PBKDF2_ITERATIONS = 100_000                                          # Line 52
# salt is inline at line 63:
_HMAC_KEY = hashlib.pbkdf2_hmac(
    "sha256",
    _DERIVATION_SEED,
    salt=b"lpg-delivery-hmac-salt",     # Line 63
    iterations=_PBKDF2_ITERATIONS,       # Line 64
)
```

### Verified: Existing build-dist.sh Pipeline

Current pipeline (lines 1-174):
1. rsync to staging (excludes .git, tests, .planning, generate_license.py, etc.)
2. Copy license.key if present
3. `python3 -m compileall -b -f -q` for .pyc (legacy placement)
4. Remove .py source from licensing module
5. Import validation: `PYTHONPATH="$STAGE" python3 -c "import core.licensing; ..."`
6. Warn about .env.example placeholder
7. Create tarball

New pipeline replaces step 3 (compileall -> Cython) and adds steps 2a (ENVIRONMENT strip validation) and 3a (hash protected files).

### CORS Dev-Mode Recommendation (Claude's Discretion)

After refactoring, CORS in distributed builds should use explicit whitelist only. In dev mode, keep the permissive localhost origins:

```python
_is_dev_mode = os.environ.get("ENVIRONMENT") == "development"

_cors_origins_raw = os.environ.get("CORS_ALLOWED_ORIGINS", "")
if _is_dev_mode and not _cors_origins_raw:
    _allowed_origins = [
        "http://localhost:8000",
        "http://localhost:3000",
        "http://localhost:5173",
    ]
else:
    _allowed_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
```

This preserves dev convenience while ensuring distributed builds (where ENVIRONMENT is never "development") use strict CORS.

### HMAC Seed Storage Recommendation (Claude's Discretion)

Hardcode in source (not build-time injection). Rationale:
1. The seed is compiled into .so -- it's not readable from the binary without reverse engineering
2. Build-time injection adds complexity (environment variables, build args) with no security benefit since the .so is the distribution artifact
3. Single source of truth: generate_license.py imports from license_manager.py, so both tools use the same seed automatically

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| .pyc bytecode distribution | Cython .so native code | Phase 6 (now) | .pyc trivially decompilable; .so requires reverse engineering |
| ENVIRONMENT=development default | Production-default, dev opt-in | Phase 6 (now) | Eliminates bypass via missing env var |
| Human-readable HMAC seed | Random hex literal seed | Phase 6 (now) | Grep/search no longer reveals seed |
| Host-side compileall | Docker-based Cython compilation | Phase 6 (now) | Guarantees ABI compatibility |

**Deprecated/outdated:**
- `python3 -m compileall -b` for licensing module: replaced by Cython compilation
- `_DERIVATION_SEED = b"kerala-logistics-platform-2025-route-optimizer"`: compromised, must be rotated

## Open Questions

1. **__init__.py content after refactor**
   - What we know: Current __init__.py has a docstring mentioning HMAC and .pyc. The CONTEXT.md says compile both files.
   - What's unclear: Whether to compile __init__.py or keep it as .py stub. Compilation is fragile.
   - Recommendation: Keep __init__.py as .py stub. Update docstring to remove HMAC references. This is safer and still satisfies ENF-02 since all functional code is in license_manager.so. The user said "compile scope: 2 files" but the planner should note that __init__.py compilation is risky and recommend the stub approach.

2. **Exact grep pattern for ENVIRONMENT validation in build pipeline**
   - What we know: Success criteria says `grep -r "ENVIRONMENT"` returns zero matches in Python source files.
   - What's unclear: Whether comments/docstrings mentioning ENVIRONMENT should also be stripped.
   - Recommendation: Use `grep -rn "ENVIRONMENT" --include="*.py" "$STAGE/"` and ensure ALL matches are eliminated including comments. This is the safest approach -- no references means no attack surface.

3. **docker-compose.license-test.yml updates**
   - What we know: This file sets `ENVIRONMENT=production` for testing. After the refactor, production is the default.
   - What's unclear: Whether to simplify this file by removing the explicit ENVIRONMENT setting.
   - Recommendation: Keep `ENVIRONMENT=production` explicitly in the test compose file for clarity, even though it's now the default behavior.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `pytest.ini` (asyncio_mode = auto) |
| Quick run command | `python -m pytest tests/core/licensing/ -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ENF-01 | No ENVIRONMENT references in dist tarball | integration | `./scripts/build-dist.sh v-test && grep -r "ENVIRONMENT" --include="*.py" /tmp/stage/ \| wc -l` | No -- Wave 0 |
| ENF-01 | main.py production-default behavior | unit | `python -m pytest tests/apps/kerala_delivery/api/test_api.py::TestSecurityHeaders -x` | Partial -- needs update |
| ENF-02 | license_manager compiles to .so and imports | integration | `docker build -f infra/Dockerfile.build . && docker run --rm img python -c "from core.licensing.license_manager import get_machine_fingerprint"` | No -- Wave 0 |
| ENF-04 | New HMAC seed produces different signatures | unit | `python -m pytest tests/core/licensing/test_license_manager.py -x` | Exists -- needs fixture update |
| BLD-01 | build-dist.sh pipeline ordering | integration | `./scripts/build-dist.sh v-test` | Exists -- needs upgrade |
| BLD-02 | .so import validation inside Docker | integration | Part of build-dist.sh pipeline | No -- Wave 0 |
| BLD-03 | -O2 and embedsignature=False applied | unit | `python -c "import core.licensing.license_manager; print(core.licensing.license_manager.get_machine_fingerprint.__doc__)"` should return None | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/core/licensing/ tests/apps/kerala_delivery/api/test_api.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green + `./scripts/build-dist.sh v-test` succeeds + tarball validation passes

### Wave 0 Gaps
- [ ] `tests/core/licensing/test_license_manager.py` -- update all fixtures for new HMAC seed (existing file, needs modification)
- [ ] `tests/apps/kerala_delivery/api/test_api.py::TestSecurityHeaders::test_docs_gated_in_production` -- update for inverted ENVIRONMENT logic
- [ ] Build pipeline integration test: verify tarball has .so files, no .py source for licensing, no ENVIRONMENT references
- [ ] Cython build Dockerfile validation: `infra/Dockerfile.build` builds successfully and produces importable .so

## Sources

### Primary (HIGH confidence)
- [Cython 3.2.4 on PyPI](https://pypi.org/project/Cython/) - latest stable, Python 3.12 support confirmed
- [Cython Source Files and Compilation docs](https://cython.readthedocs.io/en/latest/src/userguide/source_files_and_compilation.html) - Extension, cythonize, compiler_directives usage
- [Cython Building code docs](https://cython.readthedocs.io/en/latest/src/quickstart/build.html) - setup.py patterns, build_ext --inplace
- Direct codebase analysis: `main.py`, `license_manager.py`, `build-dist.sh`, `generate_license.py`, `test_license_manager.py`

### Secondary (MEDIUM confidence)
- [Cython __init__.pyx issue #2665](https://github.com/cython/cython/issues/2665) - closed as completed in Cython 3.0 milestone, but tooling fragility remains
- [Cython async issues #2273, #1573](https://github.com/cython/cython/issues/2273) - asyncio.iscoroutinefunction() returns False for compiled async functions
- [Cython Docker multi-stage gist](https://gist.github.com/operatorequals/a1264ad67b3b9a08651c9736bbfe26b0) - pattern for Cython in Docker
- [Protecting Python with Cython and Docker](https://shawinnes.com/protecting-python/) - multi-stage Docker pattern for .so distribution
- [Compiling Python Code with Cython](https://ron.sh/compiling-python-code-with-cython/) - __init__.py handling, multi-module setup.py

### Tertiary (LOW confidence)
- None -- all findings verified against multiple sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Cython 3.2.4 verified on PyPI, Python 3.12 compatibility confirmed, setup.py patterns verified in official docs
- Architecture: HIGH - build pipeline pattern based on existing build-dist.sh (known working) + verified Cython compilation patterns
- Pitfalls: HIGH - __init__.py issue verified via official Cython issue tracker; ENVIRONMENT refactor risks identified via direct code analysis of all 4 usage sites and existing test
- HMAC rotation: HIGH - straightforward stdlib (hashlib.pbkdf2_hmac) usage, no external dependencies

**Research date:** 2026-03-10
**Valid until:** 2026-04-10 (Cython ecosystem is stable; 30 days reasonable)
