"""Custom exceptions for FHIR authentication and API interactions.

Design refs:
    US-016 AC Scenario 4 — FHIRAuthenticationError raised on 401
    US-018 TASK-003      — FHIRClientError, FHIRServerError, FHIRNetworkError
    US-019 TASK-001      — PatientAmbiguousError, PatientNotFoundWarning
    SEC-011              — no PHI in exception messages or logs
"""
from __future__ import annotations


class FHIRAuthenticationError(Exception):
    """Raised when FHIR OAuth authentication fails.

    Attributes:
        status_code: HTTP status code from the auth server (e.g., 401, 403)
        response_body: Raw response body from the failed auth request (no PHI)
        message: Human-readable error message (no PHI, safe for logging)
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body

    def __str__(self) -> str:
        parts = [self.message]
        if self.status_code:
            parts.append(f"(HTTP {self.status_code})")
        return " ".join(parts)


class FHIRClientError(Exception):
    """Raised when FHIR API returns 4xx client error (no retry).
    
    US-018: Indicates invalid request, resource not found, or auth failure.
    These errors are NOT retried as they won't succeed on subsequent attempts.
    
    Attributes:
        status_code: HTTP status code (400, 404, 403, etc.)
        url: FHIR endpoint URL that failed
        response_body: Response body (if available)
    """
    
    def __init__(
        self,
        message: str,
        status_code: int,
        url: str,
        response_body: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url
        self.response_body = response_body

    def __str__(self) -> str:
        return f"{super().__str__()} (HTTP {self.status_code} at {self.url})"


class FHIRServerError(Exception):
    """Raised when FHIR API returns 5xx server error (retryable).
    
    US-018: Indicates transient server failure. Retry with exponential backoff.
    
    Attributes:
        status_code: HTTP status code (500, 503, etc.)
        url: FHIR endpoint URL that failed
        attempts: Number of retry attempts made
    """
    
    def __init__(
        self,
        message: str,
        status_code: int,
        url: str,
        attempts: int,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url
        self.attempts = attempts

    def __str__(self) -> str:
        return f"{super().__str__()} (HTTP {self.status_code} after {self.attempts} attempts)"


class FHIRNetworkError(Exception):
    """Raised when FHIR API call fails due to network issues (retryable).
    
    US-018: Timeouts, connection refused, DNS failures. Retry with backoff.
    
    Attributes:
        url: FHIR endpoint URL that failed
        attempts: Number of retry attempts made
        original_error: Original httpx exception
    """
    
    def __init__(
        self,
        message: str,
        url: str,
        attempts: int,
        original_error: Exception,
    ) -> None:
        super().__init__(message)
        self.url = url
        self.attempts = attempts
        self.original_error = original_error

    def __str__(self) -> str:
        return f"{super().__str__()} (after {self.attempts} attempts, caused by {type(self.original_error).__name__})"


class PatientAmbiguousError(Exception):
    """Raised when multiple patients match the resolution criteria (US-019).
    
    This indicates that the FHIR search returned more than one patient matching
    the provided criteria (name+DOB). Manual intervention is required to disambiguate.
    
    Attributes:
        match_count: Number of patients that matched the criteria
        criteria: Dictionary of search criteria used (e.g., {'family': 'Smith', 'dob': '1980-01-15'})
        message: Human-readable error message (no PHI)
    """
    
    def __init__(self, match_count: int, criteria: dict[str, str]) -> None:
        self.match_count = match_count
        self.criteria = criteria
        # Sanitize criteria to avoid logging PHI - only include field names, not values
        sanitized_criteria = {k: "***" for k in criteria.keys()}
        message = (
            f"Ambiguous patient match: {match_count} patients found for criteria {sanitized_criteria}. "
            "Manual resolution required."
        )
        super().__init__(message)
        self.message = message


class PatientNotFoundWarning(Warning):
    """Warning issued when no patients match the resolution criteria (US-019).
    
    This is a warning (not an exception) because the system allows partial
    encounter creation when patient identity cannot be resolved, enabling
    deferred resolution workflows.
    
    Use with Python's warnings module:
        warnings.warn("Patient not found", PatientNotFoundWarning)
    """
    pass
