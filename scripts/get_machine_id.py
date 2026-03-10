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
    - /etc/machine-id (OS installation identifier)
    - CPU model name from /proc/cpuinfo

What it does NOT collect:
    - No personal files or data
    - No browsing history
    - No passwords or credentials
    - No internet connection required

The fingerprint is a one-way hash — the original values cannot be
recovered from it.
"""

import hashlib
import platform
import sys


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

    machine_id = _read_machine_id()
    if machine_id:
        print(f"    Machine ID: {machine_id[:12]}...")
    else:
        print("    Machine ID: not found (check /etc/machine-id)")

    cpu_model = _read_cpu_model()
    if cpu_model:
        print(f"    CPU Model:  {cpu_model}")
    else:
        print("    CPU Model:  not found (check /proc/cpuinfo)")

    print(f"    Platform:   {platform.system()} {platform.release()}")
    print()


if __name__ == "__main__":
    main()
