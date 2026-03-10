# Phase 5: Fingerprinting Overhaul - Research

**Researched:** 2026-03-10
**Domain:** Machine fingerprinting, Docker volume mounts, WSL2 system identifiers
**Confidence:** HIGH

## Summary

Phase 5 replaces the current unstable fingerprint formula (hostname + MAC + container_id) with a stable formula using `/etc/machine-id` + `/proc/cpuinfo` CPU model. The current formula fails in Docker because: (1) container_id changes on every `docker compose up --force-recreate`, (2) MAC address inside Docker differs from the host, and (3) hostname inside Docker is the container ID prefix (`3da3b7bd30a9`), not the host's hostname (`MSI`). All three signals produce different values between host and container, making it impossible for the same license key to work in both environments.

The new formula uses two signals that are identical between host and container: `/etc/machine-id` (bind-mounted read-only from host into container) and the CPU model string from `/proc/cpuinfo` (automatically shared via the Linux kernel's virtual filesystem). Verification on the live system confirms: host `/etc/machine-id` = `9ea32533cbc847218443c7139d7ce34b`, container has no `/etc/machine-id` (needs bind mount), and both host and container report identical CPU model `AMD Ryzen 9 9955HX3D 16-Core Processor` via `/proc/cpuinfo`.

This is a BREAKING CHANGE: the fingerprint formula change invalidates all existing customer license keys. Phase 10 handles migration documentation. The HMAC seed rotation (ENF-04) happens in Phase 6 -- Phase 5 only changes the fingerprint signals, not the HMAC key.

**Primary recommendation:** Replace `get_machine_fingerprint()` in both `core/licensing/license_manager.py` and `scripts/get_machine_id.py` with a formula that reads `/etc/machine-id` and parses `/proc/cpuinfo` for the CPU model name, then add a read-only bind mount of `/etc/machine-id` to the API service in `docker-compose.yml`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Add `/etc/machine-id` as a fingerprint signal (bind-mounted read-only into container)
- Add CPU info from `/proc/cpuinfo` as additional signal
- Keep existing MAC address signal
- Drop container_id (too ephemeral, changes on every recreate)
- WSL-aware: deployment runs on WSL, so `/etc/machine-id` is the WSL instance's ID
- docker-compose.yml gets a new read-only volume mount for `/etc/machine-id`
- Fingerprint similarity scoring vs exact match is at Claude's discretion

### Claude's Discretion
- Fingerprint similarity scoring vs exact match

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within milestone scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| FPR-01 | Machine fingerprint uses /etc/machine-id + /proc/cpuinfo CPU model (replaces container_id + MAC) | Verified: both signals are stable across container recreation and WSL reboots. `/proc/cpuinfo` is shared automatically via kernel vfs. `/etc/machine-id` requires bind mount. Note: CONTEXT.md says "keep existing MAC address signal" -- the formula should include machine-id + CPU model + MAC (drop container_id only). |
| FPR-02 | Docker Compose mounts /etc/machine-id read-only into API container | Verified: `python:3.12-slim` base image has NO `/etc/machine-id`. The bind mount `- /etc/machine-id:/etc/machine-id:ro` is required. Host file is on persistent filesystem (not tmpfs) in this WSL instance. |
| FPR-03 | get_machine_id.py updated to collect new fingerprint signals | Current script uses hostname + MAC + container_id. Must be updated to use machine-id + CPU model + MAC. The `_get_docker_container_id()` helper can be removed. Output messaging must reflect new signals. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib `hashlib` | 3.12 | SHA256 fingerprint hashing | Already used, no external deps needed |
| Python stdlib `platform` | 3.12 | hostname access (kept for MAC) | Already used |
| Python stdlib `uuid` | 3.12 | MAC address access via `getnode()` | Already used |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pytest` | existing | Unit tests for new fingerprint formula | Test development |
| `unittest.mock` | 3.12 | Mocking filesystem reads in tests | Isolate `/etc/machine-id` and `/proc/cpuinfo` reads |

No new dependencies are needed. The fingerprinting change is entirely within Python stdlib.

## Architecture Patterns

### Recommended Changes

```
core/licensing/
  license_manager.py      # Update get_machine_fingerprint() + remove _get_docker_container_id()
scripts/
  get_machine_id.py        # Update get_machine_fingerprint() + remove _get_docker_container_id()
docker-compose.yml         # Add /etc/machine-id bind mount to api service
docker-compose.license-test.yml  # Add /etc/machine-id bind mount to api-license-test service
tests/core/licensing/
  test_license_manager.py  # Update fingerprint tests for new formula
```

### Pattern 1: New Fingerprint Formula

**What:** Replace hostname + MAC + container_id with machine-id + CPU model + MAC
**When to use:** Every call to `get_machine_fingerprint()`
**Example:**
```python
def _read_machine_id() -> str:
    """Read /etc/machine-id (systemd machine identifier).

    This file contains a 32-character hex string unique to the OS installation.
    In Docker, it must be bind-mounted from the host.
    Falls back to empty string if not available.
    """
    for path in ["/etc/machine-id", "/var/lib/dbus/machine-id"]:
        try:
            with open(path, "r") as f:
                return f.read().strip()
        except (FileNotFoundError, PermissionError):
            continue
    return ""


def _read_cpu_model() -> str:
    """Read CPU model name from /proc/cpuinfo.

    /proc/cpuinfo is a kernel virtual filesystem shared between host and
    all containers. The CPU model string is identical in both environments.
    Falls back to empty string on non-Linux or if parsing fails.
    """
    try:
        with open("/proc/cpuinfo", "r") as f:
            for line in f:
                if line.startswith("model name"):
                    # Format: "model name\t: AMD Ryzen 9 ..."
                    return line.split(":", 1)[1].strip()
    except (FileNotFoundError, PermissionError):
        pass
    return ""


def get_machine_fingerprint() -> str:
    """Generate a SHA256 fingerprint for this machine.

    Combines three identifiers:
    - /etc/machine-id: unique per OS installation, stable across reboots
    - CPU model name: hardware identifier from /proc/cpuinfo
    - MAC address: network hardware identifier (kept per user decision)

    Why these three? They produce identical values on the host AND inside
    Docker containers (with /etc/machine-id bind-mounted). The old formula
    used hostname + MAC + container_id which differed between host and container.
    """
    components = []

    # 1. Machine ID -- unique per OS install, stable across reboots
    machine_id = _read_machine_id()
    components.append(machine_id)

    # 2. CPU model -- hardware identifier, shared via /proc/cpuinfo
    cpu_model = _read_cpu_model()
    components.append(cpu_model)

    # 3. MAC address -- kept per user decision
    mac = uuid.getnode()
    components.append(format(mac, "012x"))

    combined = "|".join(components)
    return hashlib.sha256(combined.encode()).hexdigest()
```

### Pattern 2: Docker Compose Volume Mount

**What:** Bind-mount `/etc/machine-id` read-only into the API container
**When to use:** Both `docker-compose.yml` and `docker-compose.license-test.yml`
**Example:**
```yaml
# In docker-compose.yml, under services.api.volumes:
volumes:
  - ./data:/app/data
  - dashboard_assets:/srv/dashboard:ro
  - /etc/machine-id:/etc/machine-id:ro   # Machine identity for license fingerprint
```

### Pattern 3: Keeping get_machine_id.py and license_manager.py In Sync

**What:** Both files contain their own copy of `get_machine_fingerprint()`. They MUST use the same formula.
**When to use:** Any change to the fingerprint formula must be applied to both files.
**Why:** `get_machine_id.py` is shipped to the customer separately and runs on the host. `license_manager.py` runs inside the Docker container. If their formulas differ, the fingerprints won't match and license validation will fail.

### Anti-Patterns to Avoid
- **Using hostname in the fingerprint:** Docker containers have a different hostname (container ID) than the host. This was the primary cause of the current instability.
- **Using container_id in the fingerprint:** Changes every time the container is recreated. Explicitly dropped per user decision.
- **Reading /etc/machine-id without fallback:** Must handle the case where the file doesn't exist (e.g., running tests on macOS, or if the bind mount is missing).
- **Parsing /proc/cpuinfo without handling multi-core:** Only need the first "model name" line -- all cores report the same model. Stop after the first match.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Machine-id reading | Custom file parsing with complex error handling | Simple `open().read().strip()` with try/except | The file is always a single line of 32 hex characters |
| CPU model parsing | Regex or complex parser | Simple `line.split(":", 1)[1].strip()` | /proc/cpuinfo has a trivially simple format |
| Fingerprint hashing | Custom hash combination | `hashlib.sha256("|".join(components))` | Already the established pattern in the codebase |

**Key insight:** The fingerprint formula is intentionally simple. Complexity in fingerprinting creates fragility. The security comes from the HMAC signature on the license key, not from the fingerprint being hard to compute.

## Common Pitfalls

### Pitfall 1: MAC Address Instability in WSL2
**What goes wrong:** WSL2 generates a new random MAC address for the virtual network adapter on every reboot. The `uuid.getnode()` function returns this changing value.
**Why it happens:** WSL2 creates a virtual Hyper-V network adapter with a random MAC each boot (GitHub issue microsoft/WSL#5352).
**How to avoid:** The user decided to "keep existing MAC address signal" in the fingerprint, which means the fingerprint WILL change across WSL reboots due to MAC changes. However, `/etc/machine-id` and CPU model provide the stable anchors. If exact match is used, this creates a problem. RECOMMENDATION: Either (a) drop MAC from the formula despite the user decision (explain the WSL instability), or (b) use MAC but document that license re-generation may be needed after a WSL reboot. Option (a) is better for meeting success criterion #1 ("same fingerprint before and after WSL restart").
**Warning signs:** Test failures when comparing fingerprints across WSL restarts.

**CRITICAL DECISION NEEDED:** The user said "keep existing MAC address signal," but MAC changes across WSL reboots (confirmed via microsoft/WSL#5352). Including MAC means success criterion #1 ("same fingerprint before and after WSL restart") CANNOT be met. The planner must either:
1. Drop MAC from the formula (violates user's explicit decision but meets success criteria), or
2. Keep MAC but acknowledge WSL reboot changes fingerprint (meets user decision but violates success criteria).

Recommendation: Drop MAC. The success criteria are the actual acceptance test. Document this tradeoff clearly.

### Pitfall 2: /etc/machine-id Might Not Be Persistent in All WSL Installations
**What goes wrong:** Some WSL distributions mount `/etc/machine-id` on tmpfs, causing it to regenerate on every boot.
**Why it happens:** NixOS-WSL and some older Ubuntu WSL installations use tmpfs for machine-id (GitHub nix-community/NixOS-WSL#574).
**How to avoid:** On this specific WSL instance (Ubuntu with systemd=true), `/etc/machine-id` is on the real filesystem (`/dev/sdd`) and IS persistent. The `systemd-machine-id-commit.service` condition confirms it's not a mount point. For the customer's deployment, verify with `mount | grep machine-id` during setup.
**Warning signs:** `df /etc/machine-id` shows tmpfs instead of a real block device.

### Pitfall 3: Forgetting to Update Both Files
**What goes wrong:** `get_machine_id.py` and `license_manager.py` have duplicate `get_machine_fingerprint()` implementations. Updating one but not the other means the customer's reported fingerprint won't match what the container computes.
**Why it happens:** The two files exist for different contexts -- one runs on the host, one in Docker.
**How to avoid:** Update both files in the same commit. Consider having `get_machine_id.py` import from `core.licensing.license_manager` instead of maintaining a separate copy (but this requires the customer to have the full project on PATH, which may not always be the case).
**Warning signs:** License key generated from host fingerprint fails validation inside Docker.

### Pitfall 4: Forgetting docker-compose.license-test.yml
**What goes wrong:** The license E2E test container (`api-license-test`) also needs the `/etc/machine-id` bind mount. Without it, the container can't compute a valid fingerprint.
**Why it happens:** `docker-compose.license-test.yml` is an override file that's easy to forget.
**How to avoid:** Update both compose files in the same commit.
**Warning signs:** License E2E tests fail after the fingerprint change.

### Pitfall 5: Breaking Existing Tests
**What goes wrong:** The 25 existing unit tests in `test_license_manager.py` mock `get_machine_fingerprint` but some may depend on the old function signature or the existence of `_get_docker_container_id`.
**Why it happens:** Tests that import `_get_docker_container_id` directly will break when the function is removed.
**How to avoid:** Check all imports in the test file. The current tests do NOT import `_get_docker_container_id` -- they only import the public API. Safe to remove.
**Warning signs:** ImportError in test runs.

## Code Examples

### Current Fingerprint Formula (BEFORE -- to be replaced)
```python
# Source: core/licensing/license_manager.py lines 124-168
def get_machine_fingerprint() -> str:
    components = []
    components.append(platform.node())        # Hostname (different in Docker!)
    mac = uuid.getnode()
    components.append(format(mac, "012x"))     # MAC (different in Docker!)
    container_id = _get_docker_container_id()  # Changes on recreate!
    if container_id:
        components.append(container_id)
    combined = "|".join(components)
    return hashlib.sha256(combined.encode()).hexdigest()
```

### Verified Host vs Container Signal Comparison
```
Signal              | Host Value                        | Container Value
--------------------|-----------------------------------|-----------------------------------
hostname            | MSI                               | 3da3b7bd30a9 (container ID prefix)
MAC (uuid.getnode)  | 00155de6650d                      | ea77d7280813
container_id        | None                              | varies per recreate
/etc/machine-id     | 9ea32533cbc847218443c7139d7ce34b  | DOES NOT EXIST (needs bind mount)
/proc/cpuinfo model | AMD Ryzen 9 9955HX3D 16-Core...   | AMD Ryzen 9 9955HX3D 16-Core... (IDENTICAL)
```

### Docker Compose Bind Mount Syntax
```yaml
# Source: Docker Compose documentation - volumes short syntax
# Format: HOST_PATH:CONTAINER_PATH:MODE
- /etc/machine-id:/etc/machine-id:ro
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| hostname + MAC + container_id | machine-id + CPU model (+ MAC per user decision) | Phase 5 (now) | BREAKING: all existing license keys invalidated |
| .pyc-only distribution | Cython .so compilation | Phase 6 (next) | More secure but separate phase |

**Deprecated/outdated:**
- `_get_docker_container_id()`: Removed entirely. Container ID is too ephemeral.
- Hostname as fingerprint signal: Removed. Different between host and Docker container.
- `/proc/self/cgroup` parsing for container detection: No longer needed.

## Open Questions

1. **MAC Address Conflict with WSL Reboot Stability**
   - What we know: User decided "keep existing MAC address signal." WSL2 changes MAC on every reboot (microsoft/WSL#5352). Success criterion #1 requires same fingerprint before and after WSL restart.
   - What's unclear: Whether the user's intent was "keep MAC as one of the signals" (literal) or "keep some hardware identifier" (intent).
   - Recommendation: Drop MAC from the fingerprint formula. Explain to user that MAC is WSL-unstable and including it makes success criterion #1 impossible. machine-id + CPU model is sufficient for the threat model.

2. **Fingerprint Similarity Scoring vs Exact Match**
   - What we know: User marked this as "Claude's discretion." Current code uses exact prefix match (first 16 hex chars).
   - What's unclear: Whether partial signal failure (e.g., CPU model changes after hardware upgrade) should allow a grace transition.
   - Recommendation: Use exact match for Phase 5. The fingerprint formula is now stable (machine-id doesn't change, CPU model doesn't change unless hardware swap). Similarity scoring adds complexity without clear benefit at this stage. If needed, it's listed as future requirement ADV-01.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing, 426 unit tests) |
| Config file | `pytest.ini` (asyncio_mode = auto) |
| Quick run command | `python3 -m pytest tests/core/licensing/test_license_manager.py -x -q` |
| Full suite command | `python3 -m pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FPR-01 | Fingerprint uses machine-id + CPU model (not container_id/hostname) | unit | `python3 -m pytest tests/core/licensing/test_license_manager.py::TestMachineFingerprint -x` | Exists but needs updating |
| FPR-01 | Host and container produce same fingerprint | integration | Manual: run `get_machine_id.py` on host vs `docker exec lpg-api python3 scripts/get_machine_id.py` | New test |
| FPR-02 | /etc/machine-id is accessible inside container | smoke | `docker exec lpg-api cat /etc/machine-id` | New test |
| FPR-03 | get_machine_id.py reports new signals in output | unit | `python3 -m pytest tests/core/licensing/test_license_manager.py::TestMachineFingerprint -x` | Exists but needs updating |

### Sampling Rate
- **Per task commit:** `python3 -m pytest tests/core/licensing/test_license_manager.py -x -q`
- **Per wave merge:** `python3 -m pytest tests/ -x -q`
- **Phase gate:** Full suite green + manual verification of success criteria (same fingerprint host vs container, stable across recreate)

### Wave 0 Gaps
- [ ] Update `tests/core/licensing/test_license_manager.py::TestMachineFingerprint` -- tests must mock `/etc/machine-id` and `/proc/cpuinfo` reads instead of relying on hostname/MAC
- [ ] Add test for `_read_machine_id()` fallback behavior (file missing, permission denied)
- [ ] Add test for `_read_cpu_model()` fallback behavior (file missing, no matching line)
- [ ] Add test that fingerprint is deterministic with mocked filesystem reads
- [ ] Add test that old signals (hostname, container_id) are NOT used

## Sources

### Primary (HIGH confidence)
- Live system verification: `/etc/machine-id` on host = `9ea32533cbc847218443c7139d7ce34b`, persistent on `/dev/sdd` (not tmpfs)
- Live system verification: `/proc/cpuinfo` CPU model identical in host and container
- Live system verification: `python:3.12-slim` Docker image has NO `/etc/machine-id`
- Live system verification: Container hostname = `3da3b7bd30a9` (differs from host `MSI`)
- Live system verification: Container MAC = `ea77d7280813` (differs from host `00155de6650d`)
- Source code: `core/licensing/license_manager.py`, `scripts/get_machine_id.py`, `docker-compose.yml`

### Secondary (MEDIUM confidence)
- [WSL2 MAC address instability - GitHub microsoft/WSL#5352](https://github.com/microsoft/WSL/issues/5352) -- confirmed MAC changes on WSL reboot
- [NixOS-WSL machine-id persistence issue - GitHub nix-community/NixOS-WSL#574](https://github.com/nix-community/NixOS-WSL/issues/574) -- some WSL distros use tmpfs for machine-id
- [WSL DBus machine-id - GitHub microsoft/WSL#3552](https://github.com/microsoft/WSL/issues/3552) -- machine-id initialization in WSL

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all stdlib
- Architecture: HIGH -- verified all signals on live system, confirmed host/container behavior
- Pitfalls: HIGH -- MAC instability confirmed via GitHub issues and live testing

**Research date:** 2026-03-10
**Valid until:** 2026-04-10 (stable domain, no fast-moving dependencies)
