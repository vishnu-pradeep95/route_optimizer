"""Software licensing module for the delivery route optimizer.

This module provides hardware-bound license key validation to prevent
unauthorized redistribution of the software. It's designed to stop
*casual* copying — a determined reverse engineer could bypass it,
but that's an acceptable trade-off for a small-scale deployment tool.

Design decisions:
-   OFFLINE validation — no license server needed (matches our
    offline-capable constraint for Kerala's patchy internet).
-   Hardware fingerprint — ties the license to a specific machine
    using hostname + MAC address + Docker container ID.
-   HMAC-based keys — the license key itself contains the customer ID,
    expiry date, and machine fingerprint, signed with HMAC-SHA256.
-   7-day grace period — after expiry, the system continues to work
    for 7 days with a warning header, giving time to renew.

License key format:
    LPG-XXXX-XXXX-XXXX-XXXX (base32-encoded payload + HMAC signature)

Security notes:
    - The HMAC secret is derived via PBKDF2 from an innocuous-looking
      constant (not a plain "SECRET_KEY" string that's easy to grep).
    - The .py source for this module should be compiled to .pyc before
      distribution (see `scripts/build-dist.sh`). This isn't real protection
      but raises the bar slightly above "open the file and delete the check".
    - This module is in core/ (not apps/) because licensing is reusable
      across any deployment of the platform.

See: plan/kerala_delivery_route_system_design.md, Phase 4C
"""
