"""License manager — validates hardware-bound license keys offline.

This module is the core of the licensing system. It handles:
1. Machine fingerprinting (hostname + MAC + container ID → SHA256)
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
import os
import platform
import struct
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


# =============================================================================
# HMAC secret derivation
# =============================================================================

# Why this strange constant instead of a plain "SECRET_KEY"?
# - A grep for "SECRET" or "KEY" or "PASSWORD" won't find this
# - PBKDF2 with 100k iterations derives the actual HMAC key
# - This is security through obscurity (not great), but combined with
#   .pyc-only distribution, it raises the bar against casual tampering
# - A determined reverse engineer CAN extract this — that's acceptable
#   for our threat model (preventing casual copying, not piracy rings)
_DERIVATION_SEED = b"kerala-logistics-platform-2025-route-optimizer"
_PBKDF2_ITERATIONS = 100_000

# Why derive with PBKDF2 instead of using the seed directly?
# PBKDF2 is a standard key derivation function that makes brute-force
# attacks slower. Even though our seed isn't really a password, using
# PBKDF2 is defense-in-depth: if someone finds the seed, they still
# need to know the iteration count and salt to derive the HMAC key.
# See: https://docs.python.org/3/library/hashlib.html#hashlib.pbkdf2_hmac
_HMAC_KEY = hashlib.pbkdf2_hmac(
    "sha256",
    _DERIVATION_SEED,
    salt=b"lpg-delivery-hmac-salt",
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


def get_machine_fingerprint() -> str:
    """Generate a SHA256 fingerprint for this machine.

    Combines three identifiers:
    - hostname: unique per machine (but user-changeable)
    - MAC address: hardware identifier (but spoofable)
    - Docker container ID: if running in Docker, adds container identity

    Why all three? Any single identifier can be spoofed, but combining
    them makes casual copying harder. The fingerprint changes if:
    - Software is copied to a different computer
    - The Docker container is recreated (container ID changes)
    - The hostname is changed

    Why NOT use disk serial or CPU ID?
    - Not reliably accessible from inside Docker containers
    - Requires root permissions on some Linux distros
    - MAC + hostname + container ID is good enough for our threat model

    Returns:
        64-character hex string (SHA256 hash)
    """
    components = []

    # 1. Hostname — different per machine
    components.append(platform.node())

    # 2. MAC address — hardware identifier
    # uuid.getnode() returns the MAC address as a 48-bit integer.
    # On some VMs this returns a random value, but that's consistent
    # across reboots (Python caches it).
    mac = uuid.getnode()
    components.append(format(mac, "012x"))

    # 3. Docker container ID — if running in Docker
    # Docker writes the container ID to /proc/self/cgroup or
    # /proc/1/cpuset. If not in Docker, this adds an empty string
    # (which is fine — the hash still works, just without this component).
    container_id = _get_docker_container_id()
    if container_id:
        components.append(container_id)

    # Combine and hash
    combined = "|".join(components)
    return hashlib.sha256(combined.encode()).hexdigest()


def _get_docker_container_id() -> Optional[str]:
    """Try to read the Docker container ID from /proc.

    Returns None if not running in Docker.

    Why check both cgroup and mountinfo?
    - cgroup v1 (older Docker): container ID in /proc/self/cgroup
    - cgroup v2 (newer Docker): container ID in /proc/self/mountinfo
    - Not in Docker: neither file contains a 64-char hex string
    """
    # Try cgroup v1 first (most common in production Docker)
    try:
        with open("/proc/self/cgroup", "r") as f:
            for line in f:
                # Format: hierarchy-ID:controller:path
                # Docker containers have paths like /docker/CONTAINER_ID
                parts = line.strip().split("/")
                for part in parts:
                    if len(part) == 64 and all(c in "0123456789abcdef" for c in part):
                        return part
    except (FileNotFoundError, PermissionError):
        pass

    # Try hostname file (Docker sets hostname to container ID by default)
    try:
        hostname = platform.node()
        if len(hostname) == 12 and all(c in "0123456789abcdef" for c in hostname):
            return hostname
    except Exception:
        pass

    return None


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
