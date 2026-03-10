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
