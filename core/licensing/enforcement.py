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
    get_license_status,
    set_license_state,
    validate_license,
    verify_integrity,
)

logger = logging.getLogger(__name__)

_is_dev_mode = os.environ.get("ENVIRONMENT") == "development"


def enforce(app: FastAPI) -> None:
    """Single entry point for all license enforcement.

    Called once from main.py lifespan. Does:
    1. Validate license at startup
    2. Verify file integrity against embedded manifest
    3. Register middleware for ongoing enforcement
    """
    # Step 1: Validate license
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
