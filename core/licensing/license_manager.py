"""License manager — validates hardware-bound license keys offline.

This module is the core of the licensing system. It handles:
1. Machine fingerprinting (/etc/machine-id + CPU model → SHA256)
2. License key encoding/decoding (base32 payload + HMAC signature)
3. Validation on API startup (valid, expired, grace period, invalid)

Architecture:
    scripts/get_machine_id.py  →  customer sends fingerprint to us
    scripts/generate_license.py → we generate a key for that fingerprint
    core/licensing/license_manager.py → API validates key on startup

Data flow:
    Customer machine fingerprint (SHA256 hash)
        ↓
    generate_license.py (on OUR machine, NOT shipped)
        ↓
    License key string (LPG-XXXX-XXXX-XXXX-XXXX)
        ↓
    Customer puts in .env or license.key file
        ↓
    license_manager.validate() on API startup
        ↓
    VALID → API runs normally
    GRACE → API runs with X-License-Warning header
    INVALID → API returns 503 on all endpoints
"""

import base64
import hashlib
import hmac
import logging
import os
import struct
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


# =============================================================================
# HMAC secret derivation
# =============================================================================

# Cryptographically random seed -- compiled to .so in distribution builds.
# PBKDF2 derives the actual HMAC key. See docs/LICENSING.md for design.
_DERIVATION_SEED = bytes.fromhex(
    "28c238b88e41c0af1de923f79091f4d4d06d38ed6f880373102951c98807aef4"  # os.urandom(32)
)
_PBKDF2_SALT = bytes.fromhex(
    "cd6bcd0839706543c90e568d7c2e1584"  # os.urandom(16)
)
_PBKDF2_ITERATIONS = 200_000

_HMAC_KEY = hashlib.pbkdf2_hmac(
    "sha256",
    _DERIVATION_SEED,
    salt=_PBKDF2_SALT,
    iterations=_PBKDF2_ITERATIONS,
)


# =============================================================================
# License status enum
# =============================================================================


class LicenseStatus(Enum):
    """Result of license validation.

    VALID: License is active and bound to this machine.
    GRACE: License has expired but within the 7-day grace period.
           API works but adds X-License-Warning header to all responses.
    INVALID: License is missing, expired beyond grace, or wrong machine.
             API returns 503 on all endpoints.
    """

    VALID = "valid"
    GRACE = "grace"
    INVALID = "invalid"


# Severity ordering for one-way state transition guard.
# Higher severity = worse state. Upgrades (lower severity) are blocked.
_STATUS_SEVERITY = {
    LicenseStatus.VALID: 0,
    LicenseStatus.GRACE: 1,
    LicenseStatus.INVALID: 2,
}


# =============================================================================
# License info dataclass
# =============================================================================


@dataclass
class LicenseInfo:
    """Decoded license key information.

    Attributes:
        customer_id: Identifier for the customer (e.g., "vatakara-lpg-01")
        fingerprint: Machine fingerprint hash the key was generated for
        expires_at: UTC datetime when the license expires
        status: Current validation status (valid, grace, invalid)
        days_remaining: Days until expiry (negative = days past expiry)
        message: Human-readable status message
    """

    customer_id: str
    fingerprint: str
    expires_at: datetime
    status: LicenseStatus
    days_remaining: int
    message: str


# =============================================================================
# Machine fingerprinting
# =============================================================================

# Grace period in days — how long past expiry the system still works
GRACE_PERIOD_DAYS = 7


def _read_machine_id() -> str:
    """Read /etc/machine-id (systemd machine identifier).

    This file contains a 32-character hex string unique to the OS installation.
    In Docker, it must be bind-mounted from the host via docker-compose.yml:
        - /etc/machine-id:/etc/machine-id:ro

    Falls back to /var/lib/dbus/machine-id (older systems), then empty string.
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
    all containers automatically. The CPU model string is identical in both
    environments without any bind mounts needed.

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

    Combines two identifiers that are stable across Docker container
    recreation and identical between host and container:

    - /etc/machine-id: unique per OS installation, persists across reboots.
      Must be bind-mounted read-only into Docker containers.
    - CPU model name: hardware identifier from /proc/cpuinfo, shared
      automatically via the Linux kernel's virtual filesystem.

    Why these two (not hostname/MAC/container_id)?
    The old formula used hostname + MAC + container_id, which produced
    different fingerprints on host vs. inside Docker:
    - hostname: host="MSI", container="3da3b7bd30a9" (container ID prefix)
    - MAC: host="00155de6650d", container="ea77d7280813" (virtual adapter)
    - container_id: changes on every docker compose recreate

    MAC was also dropped because WSL2 generates a new random MAC on every
    reboot (microsoft/WSL#5352), making fingerprints unstable across reboots.

    The new formula uses signals that are identical in both environments,
    enabling the same license key to work on host and in Docker.

    Returns:
        64-character hex string (SHA256 hash)
    """
    components = []

    # 1. Machine ID — unique per OS install, stable across reboots
    machine_id = _read_machine_id()
    components.append(machine_id)

    # 2. CPU model — hardware identifier, shared via /proc/cpuinfo
    cpu_model = _read_cpu_model()
    components.append(cpu_model)

    # Combine and hash
    combined = "|".join(components)
    return hashlib.sha256(combined.encode()).hexdigest()


# =============================================================================
# License key encoding/decoding
# =============================================================================

# Key format:
# Payload: customer_id (variable) + expiry_timestamp (4 bytes) + fingerprint_prefix (8 bytes)
# Signature: HMAC-SHA256 of payload (truncated to 8 bytes for shorter keys)
# Encoding: base32 of (payload + signature), formatted as LPG-XXXX-XXXX-...


def encode_license_key(
    customer_id: str,
    fingerprint: str,
    expires_at: datetime,
) -> str:
    """Encode a license key from components.

    This function is used by scripts/generate_license.py (on YOUR machine).
    It should NOT be shipped to customers — they only need validate_license().

    Args:
        customer_id: Customer identifier (e.g., "vatakara-lpg-01")
        fingerprint: Machine fingerprint hash (from get_machine_fingerprint())
        expires_at: UTC datetime when the license expires

    Returns:
        License key string in format LPG-XXXX-XXXX-XXXX-XXXX

    Why truncate fingerprint to 8 bytes?
    We only store the first 8 bytes (16 hex chars) of the fingerprint in
    the key. This keeps the key shorter while still providing 2^64 collision
    resistance — more than enough for our use case (tens of customers, not
    millions). Full SHA256 would make the key unwieldy.
    """
    # Pack the payload:
    # - customer_id as UTF-8 bytes (length-prefixed with 1 byte)
    # - expiry as Unix timestamp (4 bytes, unsigned int)
    # - fingerprint prefix (8 bytes from the 64-char hex hash)
    customer_bytes = customer_id.encode("utf-8")
    if len(customer_bytes) > 255:
        raise ValueError("Customer ID too long (max 255 bytes)")

    # Unix timestamp as 4 bytes — good until year 2106
    expiry_ts = int(expires_at.timestamp())
    fingerprint_prefix = bytes.fromhex(fingerprint[:16])  # First 8 bytes

    payload = (
        struct.pack("B", len(customer_bytes))  # 1 byte: customer_id length
        + customer_bytes  # N bytes: customer_id
        + struct.pack(">I", expiry_ts)  # 4 bytes: expiry timestamp
        + fingerprint_prefix  # 8 bytes: fingerprint prefix
    )

    # Sign with HMAC-SHA256, truncate to 8 bytes
    # Why truncate? Full 32-byte HMAC would make the key very long.
    # 8 bytes = 64 bits of security, which is sufficient for license keys
    # (attacker needs to forge a valid key, not find a collision).
    signature = hmac.new(_HMAC_KEY, payload, hashlib.sha256).digest()[:8]

    # Combine and encode as base32 (uppercase, no padding)
    raw = payload + signature
    encoded = base64.b32encode(raw).decode("ascii").rstrip("=")

    # Format as LPG-XXXX-XXXX-...
    chunks = [encoded[i : i + 4] for i in range(0, len(encoded), 4)]
    return "LPG-" + "-".join(chunks)


def decode_license_key(key: str) -> Optional[LicenseInfo]:
    """Decode and validate a license key.

    Returns LicenseInfo if the key structure is valid AND the HMAC signature
    matches. Returns None if the key format is invalid or tampered with.

    Note: This checks signature validity only, NOT machine fingerprint or
    expiry. Use validate_license() for full validation.
    """
    try:
        # Strip prefix and dashes
        raw_key = key.replace("LPG-", "").replace("-", "")

        # Add base32 padding
        padding = (8 - len(raw_key) % 8) % 8
        raw_key += "=" * padding

        # Decode from base32
        raw = base64.b32decode(raw_key.upper())

        # Extract components
        # First byte: customer_id length
        customer_len = struct.unpack("B", raw[:1])[0]
        offset = 1

        # Customer ID
        customer_id = raw[offset : offset + customer_len].decode("utf-8")
        offset += customer_len

        # Expiry timestamp (4 bytes, big-endian unsigned int)
        expiry_ts = struct.unpack(">I", raw[offset : offset + 4])[0]
        offset += 4

        # Fingerprint prefix (8 bytes)
        fingerprint_prefix = raw[offset : offset + 8].hex()
        offset += 8

        # Signature (remaining 8 bytes)
        signature = raw[offset : offset + 8]

        # Verify HMAC signature
        payload = raw[: offset - 8 + 8]  # Everything before signature
        payload = raw[:offset]
        # Recalculate: payload is everything before the signature
        payload_end = len(raw) - 8
        payload = raw[:payload_end]
        expected_sig = hmac.new(_HMAC_KEY, payload, hashlib.sha256).digest()[:8]

        if not hmac.compare_digest(signature, expected_sig):
            return None  # Tampered or invalid key

        expires_at = datetime.fromtimestamp(expiry_ts, tz=timezone.utc)
        now = datetime.now(timezone.utc)
        days_remaining = (expires_at - now).days

        # Determine status
        if days_remaining >= 0:
            status = LicenseStatus.VALID
            message = f"License valid — {days_remaining} days remaining"
        elif abs(days_remaining) <= GRACE_PERIOD_DAYS + 1:
            # +1 because days_remaining rounds down: expired exactly 7 days
            # ago might report -8 due to sub-day time differences
            status = LicenseStatus.GRACE
            grace_left = GRACE_PERIOD_DAYS - abs(days_remaining) + 1
            message = (
                f"License expired {abs(days_remaining)} days ago. "
                f"Grace period: {max(0, grace_left)} days left. "
                f"Contact support to renew."
            )
        else:
            status = LicenseStatus.INVALID
            message = "License expired beyond grace period. Contact support."

        return LicenseInfo(
            customer_id=customer_id,
            fingerprint=fingerprint_prefix,
            expires_at=expires_at,
            status=status,
            days_remaining=days_remaining,
            message=message,
        )

    except Exception:
        return None  # Any decode error = invalid key


# =============================================================================
# Full license validation
# =============================================================================


def validate_license(key: Optional[str] = None) -> LicenseInfo:
    """Full license validation: decode + verify fingerprint + check expiry.

    Checks (in order):
    1. Key is present (from argument, LICENSE_KEY env var, or license.key file)
    2. Key structure is valid and HMAC signature matches
    3. Machine fingerprint matches (first 16 hex chars)
    4. License is not expired (or within grace period)

    Args:
        key: License key string. If None, reads from LICENSE_KEY env var
             or license.key file in the app directory.

    Returns:
        LicenseInfo with status VALID, GRACE, or INVALID

    Why check fingerprint prefix (8 bytes) instead of full hash?
    The key only stores the first 8 bytes of the fingerprint to keep
    the key reasonably short. 8 bytes = 16 hex chars = enough to uniquely
    identify machines in our deployment scale (< 100 customers).
    """
    # Step 1: Find the key
    if key is None:
        key = os.environ.get("LICENSE_KEY", "")

    if not key:
        # Try reading from file
        for path in ["license.key", "/app/license.key"]:
            try:
                with open(path, "r") as f:
                    key = f.read().strip()
                if key:
                    break
            except FileNotFoundError:
                continue

    if not key:
        return LicenseInfo(
            customer_id="",
            fingerprint="",
            expires_at=datetime.min.replace(tzinfo=timezone.utc),
            status=LicenseStatus.INVALID,
            days_remaining=-999,
            message="No license key found. Set LICENSE_KEY env var or place license.key file.",
        )

    # Step 2: Decode and verify signature
    info = decode_license_key(key)
    if info is None:
        return LicenseInfo(
            customer_id="",
            fingerprint="",
            expires_at=datetime.min.replace(tzinfo=timezone.utc),
            status=LicenseStatus.INVALID,
            days_remaining=-999,
            message="Invalid license key format or tampered key.",
        )

    # Step 3: Verify machine fingerprint
    current_fingerprint = get_machine_fingerprint()
    # Compare first 16 hex chars (8 bytes) — what's stored in the key
    if current_fingerprint[:16] != info.fingerprint[:16]:
        return LicenseInfo(
            customer_id=info.customer_id,
            fingerprint=info.fingerprint,
            expires_at=info.expires_at,
            status=LicenseStatus.INVALID,
            days_remaining=info.days_remaining,
            message=(
                "License key is not valid for this machine. "
                "Run scripts/get_machine_id.py and send the output to support."
            ),
        )

    # Step 4: Status already determined by decode_license_key
    return info


def is_license_valid() -> bool:
    """Quick boolean check — is the license valid or in grace period?

    Use this for simple gate checks. For detailed info, use validate_license().
    """
    info = validate_license()
    return info.status in (LicenseStatus.VALID, LicenseStatus.GRACE)


# =============================================================================
# Integrity manifest (populated by build-dist.sh before Cython compilation)
# =============================================================================

# Placeholder replaced by build-dist.sh Step 4 with real SHA256 hashes.
# Empty dict = development environment (no build), verify_integrity() returns success.
_INTEGRITY_MANIFEST: dict[str, str] = {}

# =============================================================================
# Internal license state (not on app.state -- inside compiled .so)
# =============================================================================

_license_state: LicenseInfo | None = None
_request_counter: int = 0
_REVALIDATION_INTERVAL = int(os.environ.get("REVALIDATION_INTERVAL", "500"))


def get_license_status() -> LicenseStatus | None:
    """Return current license status. Called by middleware on every request.
    Returns None if set_license_state() was never called (middleware passes through)."""
    if _license_state is None:
        return None
    return _license_state.status


def get_license_info() -> LicenseInfo | None:
    """Return full license info. None if no state set (dev mode)."""
    return _license_state


def set_license_state(info: LicenseInfo) -> None:
    """Store license state internally. Called at startup by enforce() and
    during periodic re-validation by maybe_revalidate().

    One-way guard: state can only degrade (VALID->GRACE->INVALID) or stay
    at the same severity. Upgrades (e.g. INVALID->VALID) are rejected --
    a restart is required to upgrade license state.

    First-time set (when _license_state is None) always succeeds.
    """
    global _license_state
    if _license_state is not None:
        current_severity = _STATUS_SEVERITY[_license_state.status]
        new_severity = _STATUS_SEVERITY[info.status]
        if new_severity < current_severity:
            logger.warning(
                "Rejected license state upgrade from %s to %s (restart required)",
                _license_state.status.value,
                info.status.value,
            )
            return
        if new_severity > current_severity:
            logger.warning(
                "License state degraded from %s to %s",
                _license_state.status.value,
                info.status.value,
            )
    _license_state = info


def verify_integrity(base_path: str = "/app") -> tuple[bool, list[str]]:
    """Verify protected files against embedded SHA256 manifest.
    Returns (all_ok, list_of_failure_messages).
    Empty manifest = dev environment = returns (True, [])."""
    import pathlib

    if not _INTEGRITY_MANIFEST:
        return True, []

    failures = []
    base = pathlib.Path(base_path)

    for rel_path, expected_hash in _INTEGRITY_MANIFEST.items():
        file_path = base / rel_path
        if not file_path.exists():
            failures.append(f"{rel_path}: file not found")
            continue
        with open(file_path, "rb") as f:
            actual_hash = hashlib.file_digest(f, "sha256").hexdigest()
        if actual_hash != expected_hash:
            failures.append(f"{rel_path} has been modified")

    return len(failures) == 0, failures


def maybe_revalidate(base_path: str = "/app") -> None:
    """Periodic re-validation: integrity + license expiry check every N requests.

    Called by enforcement middleware on every request. Increments a counter
    and triggers full re-validation when counter hits _REVALIDATION_INTERVAL
    (default 500, configurable via REVALIDATION_INTERVAL env var).

    Re-validation includes:
    1. File integrity verification against embedded SHA256 manifest
    2. License expiry re-check (detects VALID->GRACE->INVALID transitions)

    Skipped in dev mode (empty _INTEGRITY_MANIFEST).
    Raises SystemExit on integrity failure (graceful shutdown).
    """
    global _request_counter
    _request_counter += 1
    if _request_counter % _REVALIDATION_INTERVAL != 0:
        return
    _request_counter = 0

    # Skip in dev mode (no manifest = no files to check)
    if not _INTEGRITY_MANIFEST:
        return

    # 1. Integrity re-check
    ok, failures = verify_integrity(base_path)
    if not ok:
        for f in failures:
            logger.error("Runtime integrity check failed: %s", f)
        raise SystemExit("Runtime integrity check failed. Protected files modified.")

    # 2. License expiry re-check
    if _license_state is not None and _license_state.status != LicenseStatus.INVALID:
        from dataclasses import replace

        now = datetime.now(timezone.utc)
        days_remaining = (_license_state.expires_at - now).days

        if days_remaining >= 0:
            new_status = LicenseStatus.VALID
        elif abs(days_remaining) <= GRACE_PERIOD_DAYS + 1:
            new_status = LicenseStatus.GRACE
        else:
            new_status = LicenseStatus.INVALID

        if new_status != _license_state.status:
            new_msg = (
                f"License state changed during re-validation: "
                f"{_license_state.status.value} -> {new_status.value}"
            )
            new_info = replace(
                _license_state,
                status=new_status,
                days_remaining=days_remaining,
                message=new_msg,
            )
            set_license_state(new_info)
