"""Unit tests for FHIR custom exceptions."""
from __future__ import annotations

import pytest

from app.core.fhir.exceptions import FHIRAuthenticationError


class TestFHIRAuthenticationError:
    """Test suite for FHIRAuthenticationError exception."""

    def test_exception_with_message_only(self):
        """Test exception with only message."""
        error = FHIRAuthenticationError("Authentication failed")

        assert str(error) == "Authentication failed"
        assert error.message == "Authentication failed"
        assert error.status_code is None
        assert error.response_body is None

    def test_exception_with_status_code(self):
        """Test exception with message and status code."""
        error = FHIRAuthenticationError("Authentication failed", status_code=401)

        assert str(error) == "Authentication failed (HTTP 401)"
        assert error.message == "Authentication failed"
        assert error.status_code == 401
        assert error.response_body is None

    def test_exception_with_all_attributes(self):
        """Test exception with all attributes."""
        error = FHIRAuthenticationError(
            "Authentication failed",
            status_code=403,
            response_body='{"error": "forbidden"}',
        )

        assert str(error) == "Authentication failed (HTTP 403)"
        assert error.message == "Authentication failed"
        assert error.status_code == 403
        assert error.response_body == '{"error": "forbidden"}'

    def test_exception_inheritance(self):
        """Test that FHIRAuthenticationError inherits from Exception."""
        error = FHIRAuthenticationError("Test error")

        assert isinstance(error, Exception)

    def test_exception_can_be_raised(self):
        """Test that exception can be raised and caught."""
        with pytest.raises(FHIRAuthenticationError) as exc_info:
            raise FHIRAuthenticationError("Test error", status_code=500)

        assert exc_info.value.message == "Test error"
        assert exc_info.value.status_code == 500

    def test_exception_no_phi_in_message(self):
        """Test that exception message contains no PHI (design requirement)."""
        # This is a behavioral test - messages should never contain PHI
        error = FHIRAuthenticationError(
            "SMART configuration discovery failed",
            status_code=404,
            response_body="Not Found",
        )

        # Verify message is generic and safe for logging
        assert "patient" not in error.message.lower()
        assert "mrn" not in error.message.lower()
        assert "ssn" not in error.message.lower()
        assert str(error) == "SMART configuration discovery failed (HTTP 404)"
