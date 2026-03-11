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


# =============================================================================
# Renewal enforcement tests (Phase 9 additions)
# =============================================================================


class TestRenewalEnforcement:
    """Tests for renewal.key processing in enforce().

    enforce() checks for renewal.key before calling validate_license().
    If renewal.key exists and is valid, it becomes the primary license.
    If invalid, falls through to normal license.key validation.
    """

    def test_enforce_loads_renewal_key_when_present(self, monkeypatch):
        """enforce() loads renewal.key when present and valid, sets state from renewal info."""
        import core.licensing.enforcement as enf_mod
        monkeypatch.setattr(enf_mod, "_is_dev_mode", False)

        app = FastAPI()
        renewal_info = _make_license_info(LicenseStatus.VALID, customer_id="renewed-customer")
        normal_info = _make_license_info(LicenseStatus.VALID, customer_id="original-customer")

        with patch.object(enf_mod, "_try_load_renewal_key", return_value=(renewal_info, "LPG-RENEWAL-KEY")), \
             patch.object(enf_mod, "_handle_post_renewal") as mock_handle, \
             patch("core.licensing.enforcement.validate_license", return_value=normal_info), \
             patch("core.licensing.enforcement.verify_integrity", return_value=(True, [])):
            enf_mod.enforce(app)

        # State should reflect the renewal, not the original license
        assert license_manager._license_state.customer_id == "renewed-customer"
        mock_handle.assert_called_once_with("LPG-RENEWAL-KEY")

    def test_enforce_ignores_missing_renewal_key(self, monkeypatch):
        """enforce() proceeds with normal validate_license() when no renewal.key exists."""
        import core.licensing.enforcement as enf_mod
        monkeypatch.setattr(enf_mod, "_is_dev_mode", False)

        app = FastAPI()
        normal_info = _make_license_info(LicenseStatus.VALID, customer_id="normal-customer")

        with patch.object(enf_mod, "_try_load_renewal_key", return_value=(None, None)), \
             patch("core.licensing.enforcement.validate_license", return_value=normal_info), \
             patch("core.licensing.enforcement.verify_integrity", return_value=(True, [])):
            enf_mod.enforce(app)

        # State should reflect the normal license
        assert license_manager._license_state.customer_id == "normal-customer"

    def test_enforce_fallback_on_invalid_renewal_key(self, monkeypatch):
        """enforce() falls through to normal validation when renewal.key is invalid."""
        import core.licensing.enforcement as enf_mod
        monkeypatch.setattr(enf_mod, "_is_dev_mode", False)

        app = FastAPI()
        normal_info = _make_license_info(LicenseStatus.VALID, customer_id="fallback-customer")

        # _try_load_renewal_key returns (None, None) for invalid keys
        with patch.object(enf_mod, "_try_load_renewal_key", return_value=(None, None)), \
             patch("core.licensing.enforcement.validate_license", return_value=normal_info), \
             patch("core.licensing.enforcement.verify_integrity", return_value=(True, [])):
            enf_mod.enforce(app)

        assert license_manager._license_state.customer_id == "fallback-customer"


class TestTryLoadRenewalKey:
    """Tests for _try_load_renewal_key() helper function."""

    def test_returns_valid_renewal_info(self, monkeypatch):
        """_try_load_renewal_key() returns (LicenseInfo, key) for a valid renewal.key."""
        import core.licensing.enforcement as enf_mod

        renewal_info = _make_license_info(LicenseStatus.VALID, customer_id="renewal-test")

        with patch("builtins.open", MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value="LPG-VALID-KEY\n"))),
            __exit__=MagicMock(return_value=False),
        ))), \
             patch("core.licensing.enforcement.validate_license", return_value=renewal_info):
            info, key_content = enf_mod._try_load_renewal_key()

        assert info is not None
        assert info.customer_id == "renewal-test"
        assert key_content == "LPG-VALID-KEY"

    def test_returns_none_when_no_file(self):
        """_try_load_renewal_key() returns (None, None) when no renewal.key file exists."""
        import core.licensing.enforcement as enf_mod

        with patch("builtins.open", side_effect=FileNotFoundError()):
            info, key_content = enf_mod._try_load_renewal_key()

        assert info is None
        assert key_content is None

    def test_returns_none_for_invalid_renewal_key(self, monkeypatch):
        """_try_load_renewal_key() returns (None, None) when renewal.key content is invalid."""
        import core.licensing.enforcement as enf_mod

        invalid_info = _make_license_info(LicenseStatus.INVALID, customer_id="bad-renewal")

        with patch("builtins.open", MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value="LPG-BAD-KEY\n"))),
            __exit__=MagicMock(return_value=False),
        ))), \
             patch("core.licensing.enforcement.validate_license", return_value=invalid_info):
            info, key_content = enf_mod._try_load_renewal_key()

        assert info is None
        assert key_content is None


class TestRenewalFileHandling:
    """Tests for _handle_post_renewal() -- file replacement after successful renewal."""

    def test_post_renewal_replaces_license_key(self, tmp_path):
        """_handle_post_renewal() writes key content to license.key and deletes renewal.key."""
        import core.licensing.enforcement as enf_mod

        license_file = tmp_path / "license.key"
        renewal_file = tmp_path / "renewal.key"
        license_file.write_text("OLD-KEY")
        renewal_file.write_text("NEW-KEY")

        with patch.object(enf_mod, "_LICENSE_KEY_PATHS", [str(license_file)]), \
             patch.object(enf_mod, "_RENEWAL_KEY_PATHS", [str(renewal_file)]):
            enf_mod._handle_post_renewal("NEW-RENEWAL-KEY-CONTENT")

        assert license_file.read_text() == "NEW-RENEWAL-KEY-CONTENT"
        assert not renewal_file.exists()

    def test_post_renewal_handles_readonly_gracefully(self, tmp_path, caplog):
        """_handle_post_renewal() handles OSError on write gracefully (warning, no crash)."""
        import logging
        import core.licensing.enforcement as enf_mod

        with patch.object(enf_mod, "_LICENSE_KEY_PATHS", ["/nonexistent/path/license.key"]), \
             patch.object(enf_mod, "_RENEWAL_KEY_PATHS", ["/nonexistent/path/renewal.key"]), \
             caplog.at_level(logging.WARNING, logger="core.licensing.enforcement"):
            # Should not raise -- best-effort file handling
            enf_mod._handle_post_renewal("SOME-KEY-CONTENT")

        # Should log warnings about the failures (not crash)
        # The warning is about failing to write, not about the renewal itself


# =============================================================================
# X-License-Expires-In header tests (Phase 9 Plan 02)
# =============================================================================


class TestExpiresInHeader:
    """Tests for X-License-Expires-In response header on all middleware paths.

    The header shows how many days until license expiry (positive for valid,
    negative for expired). It is omitted when no license state is set (dev mode).
    Days are recalculated from expires_at at response time for accuracy.
    """

    def _create_enforced_app_with_info(self, license_info, monkeypatch, is_dev=False):
        """Helper: create a FastAPI app with enforce() and a specific LicenseInfo."""
        import core.licensing.enforcement as enf_mod
        monkeypatch.setattr(enf_mod, "_is_dev_mode", is_dev)

        app = FastAPI()

        @app.get("/test")
        def test_route():
            return {"status": "ok"}

        @app.get("/health")
        def health_route():
            return {"status": "healthy"}

        with patch("core.licensing.enforcement.validate_license", return_value=license_info), \
             patch("core.licensing.enforcement.verify_integrity", return_value=(True, [])):
            enf_mod.enforce(app)

        return app

    def test_valid_license_includes_expires_header(self, monkeypatch):
        """VALID license response includes X-License-Expires-In with positive days like '365d'."""
        info = LicenseInfo(
            customer_id="test",
            fingerprint="a1b2c3d4e5f6a7b8",
            expires_at=datetime.now(timezone.utc) + timedelta(days=365),
            status=LicenseStatus.VALID,
            days_remaining=365,
            message="Valid",
        )
        app = self._create_enforced_app_with_info(info, monkeypatch)
        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        header = response.headers.get("X-License-Expires-In")
        assert header is not None, "X-License-Expires-In header missing"
        # Should be like "364d" or "365d"
        assert header.endswith("d")
        days_val = int(header[:-1])
        assert days_val > 300

    def test_grace_license_includes_negative_expires_header(self, monkeypatch):
        """GRACE license response includes X-License-Expires-In with negative days like '-3d'."""
        info = LicenseInfo(
            customer_id="test",
            fingerprint="a1b2c3d4e5f6a7b8",
            expires_at=datetime.now(timezone.utc) - timedelta(days=3),
            status=LicenseStatus.GRACE,
            days_remaining=-3,
            message="Grace",
        )
        app = self._create_enforced_app_with_info(info, monkeypatch)
        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        header = response.headers.get("X-License-Expires-In")
        assert header is not None, "X-License-Expires-In header missing"
        assert header.endswith("d")
        days_val = int(header[:-1])
        assert days_val < 0

    def test_invalid_503_includes_expires_header(self, monkeypatch):
        """INVALID 503 response includes X-License-Expires-In with negative days."""
        info = LicenseInfo(
            customer_id="test",
            fingerprint="a1b2c3d4e5f6a7b8",
            expires_at=datetime.now(timezone.utc) - timedelta(days=15),
            status=LicenseStatus.INVALID,
            days_remaining=-15,
            message="Invalid",
        )
        app = self._create_enforced_app_with_info(info, monkeypatch, is_dev=False)
        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 503
        header = response.headers.get("X-License-Expires-In")
        assert header is not None, "X-License-Expires-In header missing on 503"
        assert header.endswith("d")
        days_val = int(header[:-1])
        assert days_val < -10

    def test_health_includes_expires_header(self, monkeypatch):
        """/health response includes X-License-Expires-In header."""
        info = LicenseInfo(
            customer_id="test",
            fingerprint="a1b2c3d4e5f6a7b8",
            expires_at=datetime.now(timezone.utc) + timedelta(days=45),
            status=LicenseStatus.VALID,
            days_remaining=45,
            message="Valid",
        )
        app = self._create_enforced_app_with_info(info, monkeypatch)
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        header = response.headers.get("X-License-Expires-In")
        assert header is not None, "X-License-Expires-In header missing on /health"
        assert header.endswith("d")

    def test_dev_mode_no_expires_header(self, monkeypatch):
        """Dev mode (state is None) does NOT include X-License-Expires-In header."""
        info = LicenseInfo(
            customer_id="dev",
            fingerprint="",
            expires_at=datetime.now(timezone.utc) + timedelta(days=999),
            status=LicenseStatus.VALID,
            days_remaining=999,
            message="Dev mode",
        )
        app = self._create_enforced_app_with_info(info, monkeypatch, is_dev=True)

        # Reset state to None AFTER enforce() registered middleware
        license_manager._license_state = None

        client = TestClient(app)
        response = client.get("/test")
        assert response.status_code == 200
        assert "X-License-Expires-In" not in response.headers

    def test_expires_header_recalculates_from_expires_at(self, monkeypatch):
        """Header recalculates days from expires_at, not stale days_remaining."""
        # Set days_remaining to 999 (stale) but expires_at to 10 days from now
        info = LicenseInfo(
            customer_id="test",
            fingerprint="a1b2c3d4e5f6a7b8",
            expires_at=datetime.now(timezone.utc) + timedelta(days=10),
            status=LicenseStatus.VALID,
            days_remaining=999,  # Stale value -- should NOT appear in header
            message="Valid",
        )
        app = self._create_enforced_app_with_info(info, monkeypatch)
        client = TestClient(app)
        response = client.get("/test")
        header = response.headers.get("X-License-Expires-In")
        assert header is not None
        days_val = int(header[:-1])
        # Should be ~10, NOT 999 (the stale days_remaining)
        assert 8 <= days_val <= 11, f"Expected ~10d, got {days_val}d (stale days_remaining leaked?)"
