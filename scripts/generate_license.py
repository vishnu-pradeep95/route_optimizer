#!/usr/bin/env python3
"""License key generator — runs on the DEVELOPER's machine only.

⚠️  DO NOT ship this script to customers. It contains the HMAC signing logic.
    Customers only get: scripts/get_machine_id.py (to report their fingerprint).

Usage:
    # Generate a 12-month license for a specific machine:
    python scripts/generate_license.py \\
        --customer "vatakara-lpg-01" \\
        --fingerprint "abc123...def456" \\
        --months 12

    # Generate a 6-month license (default):
    python scripts/generate_license.py \\
        --customer "test-customer" \\
        --fingerprint "abc123def456..."

    # Generate for THIS machine (useful for testing):
    python scripts/generate_license.py \\
        --customer "dev-local" \\
        --months 12 \\
        --this-machine

Workflow:
    1. Customer runs: python scripts/get_machine_id.py
    2. Customer sends the fingerprint hash to you
    3. You run this script with their fingerprint → get a license key
    4. You send the key to the customer
    5. Customer puts it in LICENSE_KEY env var or license.key file
"""

import argparse
import sys
from datetime import datetime, timezone, timedelta

# Add project root to path so we can import core modules
sys.path.insert(0, ".")

from core.licensing.license_manager import (
    encode_license_key,
    get_machine_fingerprint,
    decode_license_key,
    validate_license,
)


def main():
    parser = argparse.ArgumentParser(
        description="Generate a hardware-bound license key",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--customer",
        required=True,
        help="Customer identifier (e.g., 'vatakara-lpg-01')",
    )
    parser.add_argument(
        "--fingerprint",
        help="Machine fingerprint hash (64-char hex from get_machine_id.py)",
    )
    parser.add_argument(
        "--this-machine",
        action="store_true",
        help="Generate a license for THIS machine (uses local fingerprint)",
    )
    parser.add_argument(
        "--months",
        type=int,
        default=6,
        help="License duration in months (default: 6)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="After generating, verify the key decodes correctly",
    )
    parser.add_argument(
        "--renew",
        action="store_true",
        help="Generate a renewal key (same format, customer drops as renewal.key)",
    )

    args = parser.parse_args()

    # Get fingerprint
    if args.this_machine:
        fingerprint = get_machine_fingerprint()
        print(f"Using THIS machine's fingerprint: {fingerprint[:16]}...")
    elif args.fingerprint:
        fingerprint = args.fingerprint
        if len(fingerprint) != 64:
            print(
                f"⚠️  Warning: fingerprint is {len(fingerprint)} chars "
                f"(expected 64). Using as-is.",
                file=sys.stderr,
            )
    else:
        print(
            "Error: provide --fingerprint or --this-machine", file=sys.stderr
        )
        sys.exit(1)

    # Calculate expiry
    expires_at = datetime.now(timezone.utc) + timedelta(days=args.months * 30)

    # Generate the key
    key = encode_license_key(
        customer_id=args.customer,
        fingerprint=fingerprint,
        expires_at=expires_at,
    )

    print()
    print("=" * 60)
    if args.renew:
        print("  RENEWAL KEY GENERATED")
    else:
        print("  LICENSE KEY GENERATED")
    print("=" * 60)
    print()
    print(f"  Customer:    {args.customer}")
    print(f"  Machine:     {fingerprint[:16]}...")
    print(f"  Expires:     {expires_at.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"  Duration:    {args.months} months")
    print()
    print(f"  Key: {key}")
    print()
    if args.renew:
        print("  Save as: renewal.key")
        print("  Customer drops this file alongside license.key and restarts the API.")
        print("  The API will pick up the new expiry automatically on restart.")
    else:
        print("  To activate: set LICENSE_KEY environment variable or")
        print("  save the key to a file called 'license.key' in the project root.")
    print()

    # Optionally verify
    if args.verify:
        print("─" * 60)
        print("  VERIFICATION")
        print("─" * 60)
        info = decode_license_key(key)
        if info:
            print(f"  ✓ Decoded customer:    {info.customer_id}")
            print(f"  ✓ Decoded fingerprint: {info.fingerprint}")
            print(f"  ✓ Decoded expiry:      {info.expires_at}")
            print(f"  ✓ Status:              {info.status.value}")
            print(f"  ✓ Days remaining:      {info.days_remaining}")
            print(f"  ✓ Message:             {info.message}")
        else:
            print("  ✗ FAILED to decode generated key — this is a bug!")
            sys.exit(1)
        print()


if __name__ == "__main__":
    main()
