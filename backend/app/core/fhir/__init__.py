"""FHIR authentication and API client.

Provides SMART on FHIR OAuth 2.0 authentication with token caching,
Pydantic wrapper models for FHIR R4 resources, and async resource fetch methods.
"""
from app.core.fhir.auth import FHIRAuthClient
from app.core.fhir.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitBreakerState,
    circuit_breaker,
    get_circuit_breaker,
)
from app.core.fhir.client import FHIRClient
from app.core.fhir.discovery import discover_smart_config, get_token_endpoint
from app.core.fhir.exceptions import (
    FHIRAuthenticationError,
    FHIRClientError,
    FHIRNetworkError,
    FHIRServerError,
)
from app.core.fhir import metrics
from app.core.fhir.models import (
    AllergyIntoleranceModel,
    ConditionModel,
    EncounterModel,
    FHIRValidationError,
    MedicationAdministrationModel,
    MedicationRequestModel,
    MedicationStatementModel,
    PatientModel,
    PatientResolutionMethod,
)
from app.core.fhir.rate_limiter import TokenBucketRateLimiter, rate_limited
from app.core.fhir.token_cache import TokenCache, TokenCacheEntry

__all__ = [
    "FHIRAuthClient",
    "FHIRAuthenticationError",
    "FHIRClientError",
    "FHIRNetworkError",
    "FHIRServerError",
    "FHIRValidationError",
    "FHIRClient",
    "TokenCache",
    "TokenCacheEntry",
    "TokenBucketRateLimiter",
    "rate_limited",
    "CircuitBreaker",
    "CircuitBreakerState",
    "CircuitBreakerError",
    "circuit_breaker",
    "get_circuit_breaker",
    "discover_smart_config",
    "get_token_endpoint",
    "metrics",
    # Models
    "PatientModel",
    "EncounterModel",
    "MedicationStatementModel",
    "MedicationAdministrationModel",
    "MedicationRequestModel",
    "AllergyIntoleranceModel",
    "ConditionModel",
    "PatientResolutionMethod",
]
