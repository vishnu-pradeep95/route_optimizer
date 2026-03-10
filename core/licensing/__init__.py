"""Software licensing module for the delivery route optimizer.

Provides hardware-bound license key validation for offline deployment.
See docs/LICENSING.md for architecture and design decisions.

Public API:
    license_manager.validate_license() -- full validation pipeline
    license_manager.get_machine_fingerprint() -- machine identity hash
    license_manager.encode_license_key() -- key generation (dev only)
"""
