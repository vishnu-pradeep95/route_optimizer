"""Tests for enforcement module and license state management.

Tests cover:
1. State management -- get_license_status() and set_license_state()
2. Integrity verification -- verify_integrity() with manifest checking
3. Enforcement module -- enforce(app) behavior and middleware registration

Phase 6-01 decision: set ENVIRONMENT=development before importing licensing modules.
"""

import hashlib
import os

os.environ.setdefault("ENVIRONMENT", "development")

from datetime import datetime, timedelta, timezone

import pytest

from core.licensing.license_manager import (
    LicenseInfo,
    LicenseStatus,
    get_license_status,
    set_license_state,
    verify_integrity,
)

import core.licensing.license_manager as license_manager


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def reset_license_state():
    """Reset module-level license state before and after each test."""
    license_manager._license_state = None
    yield
    license_manager._license_state = None


@pytest.fixture
def valid_license_info():
    """A valid LicenseInfo object for testing."""
    return LicenseInfo(
        customer_id="test-customer",
        fingerprint="a1b2c3d4e5f6a7b8",
        expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        status=LicenseStatus.VALID,
        days_remaining=365,
        message="License valid -- 365 days remaining",
    )


@pytest.fixture
def grace_license_info():
    """A grace-period LicenseInfo object for testing."""
    return LicenseInfo(
        customer_id="grace-customer",
        fingerprint="a1b2c3d4e5f6a7b8",
        expires_at=datetime.now(timezone.utc) - timedelta(days=3),
        status=LicenseStatus.GRACE,
        days_remaining=-3,
        message="License in grace period",
    )


@pytest.fixture
def invalid_license_info():
    """An invalid LicenseInfo object for testing."""
    return LicenseInfo(
        customer_id="expired-customer",
        fingerprint="a1b2c3d4e5f6a7b8",
        expires_at=datetime.now(timezone.utc) - timedelta(days=30),
        status=LicenseStatus.INVALID,
        days_remaining=-30,
        message="License expired beyond grace period",
    )


# =============================================================================
# State management tests
# =============================================================================


class TestGetLicenseStatus:
    """Tests for get_license_status() -- accessor for internal license state."""

    def test_returns_none_when_no_state_set(self):
        """get_license_status() returns None when _license_state is None (no state set yet)."""
        assert get_license_status() is None

    def test_returns_valid_after_set(self, valid_license_info):
        """get_license_status() returns VALID after set_license_state() with valid info."""
        set_license_state(valid_license_info)
        assert get_license_status() == LicenseStatus.VALID

    def test_returns_grace_after_set(self, grace_license_info):
        """get_license_status() returns GRACE after set_license_state() with grace info."""
        set_license_state(grace_license_info)
        assert get_license_status() == LicenseStatus.GRACE

    def test_returns_invalid_after_set(self, invalid_license_info):
        """get_license_status() returns INVALID after set_license_state() with invalid info."""
        set_license_state(invalid_license_info)
        assert get_license_status() == LicenseStatus.INVALID


class TestSetLicenseState:
    """Tests for set_license_state() -- setter for internal license state."""

    def test_stores_license_info(self, valid_license_info):
        """set_license_state() stores a LicenseInfo in the module-level variable."""
        set_license_state(valid_license_info)
        assert license_manager._license_state is valid_license_info

    def test_overwrites_previous_state(self, valid_license_info, invalid_license_info):
        """set_license_state() overwrites any previously stored state."""
        set_license_state(valid_license_info)
        assert get_license_status() == LicenseStatus.VALID

        set_license_state(invalid_license_info)
        assert get_license_status() == LicenseStatus.INVALID


# =============================================================================
# Integrity verification tests
# =============================================================================


class TestVerifyIntegrity:
    """Tests for verify_integrity() -- SHA256 manifest verification."""

    def test_empty_manifest_returns_success(self, monkeypatch):
        """verify_integrity() returns (True, []) when _INTEGRITY_MANIFEST is empty (dev mode)."""
        monkeypatch.setattr(license_manager, "_INTEGRITY_MANIFEST", {})
        ok, failures = verify_integrity()
        assert ok is True
        assert failures == []

    def test_matching_hash_returns_success(self, monkeypatch, tmp_path):
        """verify_integrity() returns (True, []) when all file hashes match the manifest."""
        # Create a test file with known content
        test_file = tmp_path / "test.py"
        test_file.write_bytes(b"print('hello')")

        # Compute its SHA256
        expected_hash = hashlib.sha256(b"print('hello')").hexdigest()

        # Set the manifest
        monkeypatch.setattr(
            license_manager,
            "_INTEGRITY_MANIFEST",
            {"test.py": expected_hash},
        )

        ok, failures = verify_integrity(base_path=str(tmp_path))
        assert ok is True
        assert failures == []

    def test_mismatched_hash_returns_failure(self, monkeypatch, tmp_path):
        """verify_integrity() returns (False, [...]) when a file hash mismatches."""
        # Create a test file
        test_file = tmp_path / "file.py"
        test_file.write_bytes(b"modified content")

        # Set manifest with wrong hash
        monkeypatch.setattr(
            license_manager,
            "_INTEGRITY_MANIFEST",
            {"file.py": "0000000000000000000000000000000000000000000000000000000000000000"},
        )

        ok, failures = verify_integrity(base_path=str(tmp_path))
        assert ok is False
        assert len(failures) == 1
        assert "file.py has been modified" in failures[0]

    def test_missing_file_returns_failure(self, monkeypatch, tmp_path):
        """verify_integrity() returns (False, [...]) when a manifest file is missing."""
        monkeypatch.setattr(
            license_manager,
            "_INTEGRITY_MANIFEST",
            {"file.py": "abcd1234" * 8},
        )

        ok, failures = verify_integrity(base_path=str(tmp_path))
        assert ok is False
        assert len(failures) == 1
        assert "file.py: file not found" in failures[0]

    def test_multiple_failures(self, monkeypatch, tmp_path):
        """verify_integrity() reports all failures, not just the first."""
        # Create one file with wrong hash, leave another missing
        test_file = tmp_path / "exists.py"
        test_file.write_bytes(b"content")

        monkeypatch.setattr(
            license_manager,
            "_INTEGRITY_MANIFEST",
            {
                "exists.py": "0000000000000000000000000000000000000000000000000000000000000000",
                "missing.py": "1111111111111111111111111111111111111111111111111111111111111111",
            },
        )

        ok, failures = verify_integrity(base_path=str(tmp_path))
        assert ok is False
        assert len(failures) == 2


# =============================================================================
# Enforcement module tests (enforce() + middleware)
# =============================================================================


from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _make_license_info(status: LicenseStatus, customer_id: str = "test") -> LicenseInfo:
    """Helper to create LicenseInfo with a given status."""
    return LicenseInfo(
        customer_id=customer_id,
        fingerprint="a1b2c3d4e5f6a7b8",
        expires_at=datetime.now(timezone.utc) + timedelta(days=365),
        status=status,
        days_remaining=365 if status == LicenseStatus.VALID else -3,
        message=f"Status: {status.value}",
    )


class TestEnforce:
    """Tests for enforce(app) -- the single entry point for license enforcement."""

    def test_enforce_with_valid_license(self):
        """enforce(app) with a valid license calls set_license_state with VALID status."""
        from core.licensing.enforcement import enforce

        app = FastAPI()
        valid_info = _make_license_info(LicenseStatus.VALID)

        with patch("core.licensing.enforcement.validate_license", return_value=valid_info), \
             patch("core.licensing.enforcement.verify_integrity", return_value=(True, [])):
            enforce(app)

        assert get_license_status() == LicenseStatus.VALID

    def test_enforce_dev_mode_invalid_overrides_to_valid(self, monkeypatch):
        """enforce(app) in dev mode with invalid license overrides to VALID status."""
        monkeypatch.setenv("ENVIRONMENT", "development")

        # Need to reload the module to pick up the env change
        import core.licensing.enforcement as enf_mod
        monkeypatch.setattr(enf_mod, "_is_dev_mode", True)

        app = FastAPI()
        invalid_info = _make_license_info(LicenseStatus.INVALID)

        with patch("core.licensing.enforcement.validate_license", return_value=invalid_info), \
             patch("core.licensing.enforcement.verify_integrity", return_value=(True, [])):
            enf_mod.enforce(app)

        # Dev mode should override invalid to valid
        assert get_license_status() == LicenseStatus.VALID

    def test_enforce_production_invalid_stays_invalid(self, monkeypatch):
        """enforce(app) in production with invalid license calls set_license_state with INVALID."""
        import core.licensing.enforcement as enf_mod
        monkeypatch.setattr(enf_mod, "_is_dev_mode", False)

        app = FastAPI()
        invalid_info = _make_license_info(LicenseStatus.INVALID)

        with patch("core.licensing.enforcement.validate_license", return_value=invalid_info), \
             patch("core.licensing.enforcement.verify_integrity", return_value=(True, [])):
            enf_mod.enforce(app)

        assert get_license_status() == LicenseStatus.INVALID

    def test_enforce_registers_middleware(self):
        """enforce(app) registers an HTTP middleware on the app."""
        from core.licensing.enforcement import enforce

        app = FastAPI()

        @app.get("/test-endpoint")
        def test_endpoint():
            return {"status": "ok"}

        valid_info = _make_license_info(LicenseStatus.VALID)

        with patch("core.licensing.enforcement.validate_license", return_value=valid_info), \
             patch("core.licensing.enforcement.verify_integrity", return_value=(True, [])):
            enforce(app)

        # Verify middleware was registered by testing with a client
        # Should pass through since license is VALID
        client = TestClient(app)
        response = client.get("/test-endpoint")
        assert response.status_code == 200

        # Verify middleware is present in the user_middleware list
        assert len(app.user_middleware) > 0

    def test_enforce_skips_integrity_in_dev_mode(self, monkeypatch):
        """enforce(app) skips integrity verification in dev mode."""
        import core.licensing.enforcement as enf_mod
        monkeypatch.setattr(enf_mod, "_is_dev_mode", True)

        app = FastAPI()
        valid_info = _make_license_info(LicenseStatus.VALID)

        mock_verify = MagicMock(return_value=(True, []))

        with patch("core.licensing.enforcement.validate_license", return_value=valid_info), \
             patch("core.licensing.enforcement.verify_integrity", mock_verify):
            enf_mod.enforce(app)

        # verify_integrity should NOT have been called in dev mode
        mock_verify.assert_not_called()

    def test_enforce_integrity_failure_raises_system_exit(self, monkeypatch):
        """enforce(app) with integrity failures raises SystemExit in production."""
        import core.licensing.enforcement as enf_mod
        monkeypatch.setattr(enf_mod, "_is_dev_mode", False)

        app = FastAPI()
        valid_info = _make_license_info(LicenseStatus.VALID)

        with patch("core.licensing.enforcement.validate_license", return_value=valid_info), \
             patch("core.licensing.enforcement.verify_integrity", return_value=(False, ["main.py has been modified"])):
            with pytest.raises(SystemExit):
                enf_mod.enforce(app)


class TestEnforcementMiddleware:
    """Tests for the HTTP middleware registered by enforce()."""

    def _create_app_with_enforcement(self, license_status, monkeypatch, is_dev=True):
        """Helper: create a FastAPI app with enforce() called and controlled license status."""
        import core.licensing.enforcement as enf_mod
        monkeypatch.setattr(enf_mod, "_is_dev_mode", is_dev)

        app = FastAPI()

        @app.get("/test")
        def test_route():
            return {"status": "ok"}

        @app.get("/health")
        def health_route():
            return {"status": "healthy"}

        license_info = _make_license_info(license_status)

        with patch("core.licensing.enforcement.validate_license", return_value=license_info), \
             patch("core.licensing.enforcement.verify_integrity", return_value=(True, [])):
            enf_mod.enforce(app)

        return app

    def test_middleware_returns_503_when_invalid(self, monkeypatch):
        """The registered middleware returns 503 when get_license_status() is INVALID."""
        import core.licensing.enforcement as enf_mod
        monkeypatch.setattr(enf_mod, "_is_dev_mode", False)

        app = FastAPI()

        @app.get("/test")
        def test_route():
            return {"status": "ok"}

        invalid_info = _make_license_info(LicenseStatus.INVALID)

        with patch("core.licensing.enforcement.validate_license", return_value=invalid_info), \
             patch("core.licensing.enforcement.verify_integrity", return_value=(True, [])):
            enf_mod.enforce(app)

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 503
        assert response.json()["license_status"] == "invalid"

    def test_middleware_passes_through_when_valid(self, monkeypatch):
        """The registered middleware passes through when get_license_status() is VALID."""
        app = self._create_app_with_enforcement(LicenseStatus.VALID, monkeypatch)
        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200

    def test_middleware_adds_warning_header_when_grace(self, monkeypatch):
        """The registered middleware adds X-License-Warning header when GRACE."""
        import core.licensing.enforcement as enf_mod
        monkeypatch.setattr(enf_mod, "_is_dev_mode", False)

        app = FastAPI()

        @app.get("/test")
        def test_route():
            return {"status": "ok"}

        grace_info = _make_license_info(LicenseStatus.GRACE)

        with patch("core.licensing.enforcement.validate_license", return_value=grace_info), \
             patch("core.licensing.enforcement.verify_integrity", return_value=(True, [])):
            enf_mod.enforce(app)

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        assert "X-License-Warning" in response.headers

    def test_middleware_passes_through_when_none(self, monkeypatch):
        """The registered middleware passes through when get_license_status() is None."""
        import core.licensing.enforcement as enf_mod
        monkeypatch.setattr(enf_mod, "_is_dev_mode", True)

        app = FastAPI()

        @app.get("/test")
        def test_route():
            return {"status": "ok"}

        valid_info = _make_license_info(LicenseStatus.VALID)

        with patch("core.licensing.enforcement.validate_license", return_value=valid_info), \
             patch("core.licensing.enforcement.verify_integrity", return_value=(True, [])):
            enf_mod.enforce(app)

        # Reset state to None AFTER enforce() registered middleware
        license_manager._license_state = None

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200

    def test_middleware_always_allows_health(self, monkeypatch):
        """The registered middleware always allows /health endpoint."""
        import core.licensing.enforcement as enf_mod
        monkeypatch.setattr(enf_mod, "_is_dev_mode", False)

        app = FastAPI()

        @app.get("/health")
        def health_route():
            return {"status": "healthy"}

        invalid_info = _make_license_info(LicenseStatus.INVALID)

        with patch("core.licensing.enforcement.validate_license", return_value=invalid_info), \
             patch("core.licensing.enforcement.verify_integrity", return_value=(True, [])):
            enf_mod.enforce(app)

        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert "X-License-Status" in response.headers
        assert response.headers["X-License-Status"] == "invalid"


# =============================================================================
# Runtime re-validation middleware integration tests
# =============================================================================


class TestRuntimeRevalidation:
    """Tests for middleware integration with maybe_revalidate().

    Verifies that the enforcement middleware calls maybe_revalidate() on every
    request when license state is set, re-reads status afterward, and allows
    SystemExit to propagate for graceful shutdown.
    """

    @pytest.fixture(autouse=True)
    def reset_request_counter(self):
        """Reset the request counter before and after each test."""
        license_manager._request_counter = 0
        yield
        license_manager._request_counter = 0

    def _create_enforced_app(self, license_status, monkeypatch, is_dev=True):
        """Helper: create a FastAPI app with enforce() and controlled license status."""
        import core.licensing.enforcement as enf_mod
        monkeypatch.setattr(enf_mod, "_is_dev_mode", is_dev)

        app = FastAPI()

        @app.get("/test")
        def test_route():
            return {"status": "ok"}

        @app.get("/health")
        def health_route():
            return {"status": "healthy"}

        license_info = _make_license_info(license_status)

        with patch("core.licensing.enforcement.validate_license", return_value=license_info), \
             patch("core.licensing.enforcement.verify_integrity", return_value=(True, [])):
            enf_mod.enforce(app)

        return app

    def test_maybe_revalidate_called_when_state_set(self, monkeypatch):
        """Middleware calls maybe_revalidate() when license state is not None."""
        app = self._create_enforced_app(LicenseStatus.VALID, monkeypatch)

        with patch("core.licensing.enforcement.maybe_revalidate") as mock_reval:
            client = TestClient(app)
            client.get("/test")
            mock_reval.assert_called_once()

    def test_maybe_revalidate_not_called_when_state_none(self, monkeypatch):
        """Middleware does NOT call maybe_revalidate() when license state is None."""
        app = self._create_enforced_app(LicenseStatus.VALID, monkeypatch)

        # Reset state to None AFTER enforce() registered middleware
        license_manager._license_state = None

        with patch("core.licensing.enforcement.maybe_revalidate") as mock_reval:
            client = TestClient(app)
            client.get("/test")
            mock_reval.assert_not_called()

    def test_middleware_rereads_status_after_revalidate(self, monkeypatch):
        """Middleware re-reads get_license_status() after maybe_revalidate(),
        so status changes from maybe_revalidate() are reflected in the same request."""
        app = self._create_enforced_app(LicenseStatus.VALID, monkeypatch)

        # When maybe_revalidate() fires, degrade state from VALID to GRACE
        def degrade_to_grace():
            grace_info = _make_license_info(LicenseStatus.GRACE)
            set_license_state(grace_info)

        with patch("core.licensing.enforcement.maybe_revalidate", side_effect=degrade_to_grace):
            client = TestClient(app)
            response = client.get("/test")

        # The response should reflect GRACE (X-License-Warning header)
        # because middleware re-reads status after maybe_revalidate()
        assert response.status_code == 200
        assert "X-License-Warning" in response.headers

    def test_valid_to_grace_degradation_adds_warning_header(self, monkeypatch):
        """If maybe_revalidate() degrades VALID->GRACE, the same request gets X-License-Warning."""
        app = self._create_enforced_app(LicenseStatus.VALID, monkeypatch)

        def degrade_to_grace():
            grace_info = _make_license_info(LicenseStatus.GRACE)
            set_license_state(grace_info)

        with patch("core.licensing.enforcement.maybe_revalidate", side_effect=degrade_to_grace):
            client = TestClient(app)
            response = client.get("/test")

        assert response.status_code == 200
        assert response.headers.get("X-License-Warning") == "License in grace period"

    def test_grace_to_invalid_degradation_returns_503(self, monkeypatch):
        """If maybe_revalidate() degrades GRACE->INVALID, the same request gets 503."""
        import core.licensing.enforcement as enf_mod
        monkeypatch.setattr(enf_mod, "_is_dev_mode", False)

        app = FastAPI()

        @app.get("/test")
        def test_route():
            return {"status": "ok"}

        grace_info = _make_license_info(LicenseStatus.GRACE)

        with patch("core.licensing.enforcement.validate_license", return_value=grace_info), \
             patch("core.licensing.enforcement.verify_integrity", return_value=(True, [])):
            enf_mod.enforce(app)

        def degrade_to_invalid():
            invalid_info = _make_license_info(LicenseStatus.INVALID)
            set_license_state(invalid_info)

        with patch("core.licensing.enforcement.maybe_revalidate", side_effect=degrade_to_invalid):
            client = TestClient(app)
            response = client.get("/test")

        assert response.status_code == 503
        assert response.json()["license_status"] == "invalid"

    def test_system_exit_from_revalidate_propagates(self, monkeypatch):
        """SystemExit raised by maybe_revalidate() propagates through middleware (not caught).

        Note: Starlette/anyio may wrap SystemExit in a BaseExceptionGroup, so we
        check for either SystemExit directly or a group containing one.
        """
        app = self._create_enforced_app(LicenseStatus.VALID, monkeypatch)

        with patch("core.licensing.enforcement.maybe_revalidate", side_effect=SystemExit("integrity failure")):
            client = TestClient(app, raise_server_exceptions=True)
            try:
                client.get("/test")
                pytest.fail("Expected SystemExit to propagate")
            except SystemExit:
                pass  # Direct propagation
            except BaseExceptionGroup as eg:
                # anyio wraps SystemExit in an ExceptionGroup
                system_exits = eg.subgroup(SystemExit)
                assert system_exits is not None, f"Expected SystemExit in group, got: {eg}"

    def test_existing_valid_passthrough_unchanged(self, monkeypatch):
        """Existing behavior: VALID license passes through with 200 (no regression)."""
        app = self._create_enforced_app(LicenseStatus.VALID, monkeypatch)

        # Use real maybe_revalidate (no mock) -- should be a no-op in dev mode
        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        assert "X-License-Warning" not in response.headers

    def test_health_endpoint_still_bypasses_after_revalidate(self, monkeypatch):
        """Health endpoint bypass works correctly even with maybe_revalidate() in the path."""
        import core.licensing.enforcement as enf_mod
        monkeypatch.setattr(enf_mod, "_is_dev_mode", False)

        app = FastAPI()

        @app.get("/health")
        def health_route():
            return {"status": "healthy"}

        grace_info = _make_license_info(LicenseStatus.GRACE)

        with patch("core.licensing.enforcement.validate_license", return_value=grace_info), \
             patch("core.licensing.enforcement.verify_integrity", return_value=(True, [])):
            enf_mod.enforce(app)

        with patch("core.licensing.enforcement.maybe_revalidate") as mock_reval:
            client = TestClient(app)
            response = client.get("/health")
            # maybe_revalidate() should still be called (counter increments on all requests)
            mock_reval.assert_called_once()

        assert response.status_code == 200
        assert response.headers.get("X-License-Status") == "grace"
