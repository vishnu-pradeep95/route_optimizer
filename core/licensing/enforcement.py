"""License enforcement module -- async wrapper for compiled license_manager.so.

This module stays as .py (Cython cannot compile async def). It provides a
single entry point enforce(app) that main.py calls at startup. All enforcement
logic (license checking, integrity verification, state storage) lives in
license_manager.py which is compiled to .so in distribution builds.

Architecture:
    main.py -> enforce(app) -> license_manager.so
    middleware (async, in this file) -> get_license_status() (sync, in .so)

Protected by the SHA256 integrity manifest embedded in the compiled .so.
"""

import logging
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.licensing.license_manager import (
    GRACE_PERIOD_DAYS,
    LicenseInfo,
    LicenseStatus,
    get_license_info,
    get_license_status,
    maybe_revalidate,
    set_license_state,
    validate_license,
    verify_integrity,
)

logger = logging.getLogger(__name__)

_is_dev_mode = os.environ.get("ENVIRONMENT") == "development"

# File paths for renewal key lookup and post-renewal file handling
_RENEWAL_KEY_PATHS = ["renewal.key", "/app/renewal.key"]
_LICENSE_KEY_PATHS = ["license.key", "/app/license.key"]


def _try_load_renewal_key() -> tuple[LicenseInfo | None, str | None]:
    """Try to load and validate renewal.key.

    Checks renewal.key in the current directory and /app/renewal.key (Docker).
    If found and valid (VALID or GRACE status), returns (LicenseInfo, key_content).
    If not found or invalid, returns (None, None).
    """
    for path in _RENEWAL_KEY_PATHS:
        try:
            with open(path, "r") as f:
                key = f.read().strip()
            if key:
                info = validate_license(key)
                if info.status in (LicenseStatus.VALID, LicenseStatus.GRACE):
                    return info, key
                else:
                    logger.warning("renewal.key present but invalid: %s", info.message)
        except FileNotFoundError:
            continue
    return None, None


def _handle_post_renewal(key_content: str) -> None:
    """Post-renewal file handling: replace license.key, delete renewal.key.

    Both operations are best-effort: if the Docker volume is read-only,
    the warning is logged but the API still runs with the renewed license
    in memory.
    """
    # Write renewed key content to license.key
    for path in _LICENSE_KEY_PATHS:
        try:
            with open(path, "w") as f:
                f.write(key_content)
            logger.info("Replaced %s with renewal key content", path)
            break
        except OSError as e:
            logger.warning("Could not write renewal to %s: %s", path, e)

    # Delete renewal.key
    for path in _RENEWAL_KEY_PATHS:
        try:
            os.remove(path)
            logger.info("Deleted %s after successful renewal", path)
            break
        except OSError as e:
            logger.warning("Could not delete %s: %s", path, e)


def enforce(app: FastAPI) -> None:
    """Single entry point for all license enforcement.

    Called once from main.py lifespan. Does:
    1. Validate license at startup
    2. Verify file integrity against embedded manifest
    3. Register middleware for ongoing enforcement
    """
    # Step 0: Check for renewal.key (before normal validation)
    # CRITICAL: renewal must happen BEFORE set_license_state() because the
    # one-way state guard blocks INVALID->VALID upgrades. The renewal key
    # becomes the initial license_info, and set_license_state() is called
    # once with the renewed state.
    renewal_info, renewal_key = _try_load_renewal_key()
    if renewal_info:
        logger.info(
            "License renewed via renewal.key -- customer=%s, new expiry=%s",
            renewal_info.customer_id,
            renewal_info.expires_at.strftime("%Y-%m-%d"),
        )
        license_info = renewal_info
        _handle_post_renewal(renewal_key)
    else:
        # Step 1: Normal validation
        license_info = validate_license()

    if license_info.status == LicenseStatus.VALID:
        logger.info(
            "License valid -- customer=%s, expires=%s, %d days remaining",
            license_info.customer_id,
            license_info.expires_at.strftime("%Y-%m-%d"),
            license_info.days_remaining,
        )
    elif license_info.status == LicenseStatus.GRACE:
        logger.warning(
            "LICENSE IN GRACE PERIOD -- %s. "
            "System will stop working in %d days. Renew immediately.",
            license_info.message,
            max(0, GRACE_PERIOD_DAYS - abs(license_info.days_remaining)),
        )
    else:
        if _is_dev_mode:
            logger.info(
                "License not configured (dev mode) -- running without enforcement"
            )
            license_info = LicenseInfo(
                customer_id="dev-mode",
                fingerprint="",
                expires_at=license_info.expires_at,
                status=LicenseStatus.VALID,
                days_remaining=999,
                message="Development mode -- no license required",
            )
        else:
            logger.error(
                "LICENSE INVALID: %s. All endpoints will return 503.",
                license_info.message,
            )

    # Store in compiled module's internal state (not on app.state)
    set_license_state(license_info)

    # Step 2: Verify file integrity
    if not _is_dev_mode:
        ok, failures = verify_integrity()
        if not ok:
            for f in failures:
                logger.error("Integrity check failed: %s", f)
            raise SystemExit(
                "File integrity check failed. Protected files have been modified."
            )
        logger.info("File integrity verification passed")
    else:
        logger.info("Skipping integrity verification (dev mode)")

    # Step 3: Register middleware
    @app.middleware("http")
    async def license_enforcement_middleware(request: Request, call_next):
        """Check license status on every request via compiled accessor."""
        status = get_license_status()  # Calls into .so -- fast, no I/O

        if status is not None:
            maybe_revalidate()  # Periodic check, may raise SystemExit
            status = get_license_status()  # Re-read: may have changed

        if status is None:
            return await call_next(request)

        if request.url.path == "/health":
            response = await call_next(request)
            if status != LicenseStatus.VALID:
                response.headers["X-License-Status"] = status.value
            return response

        if status == LicenseStatus.INVALID:
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "License expired or invalid. Contact support.",
                    "license_status": "invalid",
                },
            )

        response = await call_next(request)

        if status == LicenseStatus.GRACE:
            response.headers["X-License-Warning"] = "License in grace period"

        return response
