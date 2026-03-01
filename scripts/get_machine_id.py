#!/usr/bin/env python3
"""Machine fingerprint reporter — run this on the CUSTOMER's machine.

This script generates a unique identifier for the machine, which is needed
to create a hardware-bound license key. Send the output to the software
provider.

Usage:
    python scripts/get_machine_id.py

Output:
    Machine Fingerprint: abc123def456...  (64-character hex string)

What it collects:
    - Computer hostname
    - Network adapter MAC address
    - Docker container ID (if running inside Docker)

What it does NOT collect:
    - No personal files or data
    - No browsing history
    - No passwords or credentials
    - No internet connection required

The fingerprint is a one-way hash — the original values cannot be
recovered from it.
"""

import hashlib
import os
import platform
import sys
import uuid
from typing import Optional


def _get_docker_container_id() -> Optional[str]:
    """Try to read the Docker container ID from /proc.

    Returns None if not running in Docker.
    """
    try:
        with open("/proc/self/cgroup", "r") as f:
            for line in f:
                parts = line.strip().split("/")
                for part in parts:
                    if len(part) == 64 and all(
                        c in "0123456789abcdef" for c in part
                    ):
                        return part
    except (FileNotFoundError, PermissionError):
        pass

    try:
        hostname = platform.node()
        if len(hostname) == 12 and all(
            c in "0123456789abcdef" for c in hostname
        ):
            return hostname
    except Exception:
        pass

    return None


def get_machine_fingerprint() -> str:
    """Generate a SHA256 fingerprint for this machine."""
    components = []
    components.append(platform.node())
    mac = uuid.getnode()
    components.append(format(mac, "012x"))
    container_id = _get_docker_container_id()
    if container_id:
        components.append(container_id)

    combined = "|".join(components)
    return hashlib.sha256(combined.encode()).hexdigest()


def main():
    fingerprint = get_machine_fingerprint()

    print()
    print("=" * 60)
    print("  MACHINE FINGERPRINT")
    print("=" * 60)
    print()
    print(f"  {fingerprint}")
    print()
    print("  Send this fingerprint to the software provider to")
    print("  receive your license key.")
    print()
    print("  Details (for reference):")
    print(f"    Hostname:  {platform.node()}")
    print(f"    Platform:  {platform.system()} {platform.release()}")

    container_id = _get_docker_container_id()
    if container_id:
        print(f"    Container: {container_id[:12]}...")
    else:
        print("    Container: not running in Docker")
    print()


if __name__ == "__main__":
    main()
