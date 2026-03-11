"""Software licensing module for the delivery route optimizer.

Provides hardware-bound license key validation for offline deployment.
See docs/LICENSING.md for architecture and design decisions.

Public API:
    license_manager.validate_license() -- full validation pipeline
    license_manager.get_machine_fingerprint() -- machine identity hash
    license_manager.encode_license_key() -- key generation (dev only)
    license_manager.get_license_status() -- current license status (per-request)
    license_manager.set_license_state() -- store license state (startup only)
    license_manager.verify_integrity() -- SHA256 manifest verification
    license_manager.maybe_revalidate() -- periodic integrity + expiry re-check (every 500 requests)

    enforcement.enforce(app) -- single entry point for all enforcement
        Import as: from core.licensing.enforcement import enforce
"""
