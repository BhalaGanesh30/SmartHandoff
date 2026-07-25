"""
Staging environment validation script for performance testing.

Validates that all required environment variables and services are configured
before running performance tests.
"""
import os
import sys
from typing import Tuple


def check_env_var(name: str, description: str) -> Tuple[bool, str]:
    """Check if an environment variable is set."""
    value = os.environ.get(name, "")
    if value:
        return True, f"✓ {name} is set"
    else:
        return False, f"✗ {name} is NOT set - {description}"


def validate_environment() -> int:
    """Validate staging environment configuration."""
    print()
    print("=" * 80)
    print("Staging Environment Validation for Performance Testing")
    print("=" * 80)
    print()
    
    checks = [
        ("STAGING_GCP_PROJECT_ID", "GCP project ID for Vertex AI"),
        ("STAGING_GCP_REGION", "GCP region (default: us-central1)"),
        ("STAGING_FHIR_BASE_URL", "FHIR R4 server base URL"),
        ("STAGING_FHIR_CLIENT_ID", "FHIR OAuth client ID"),
        ("STAGING_FHIR_CLIENT_SECRET", "FHIR OAuth client secret"),
        ("STAGING_DATABASE_URL", "PostgreSQL connection string"),
        ("GOOGLE_APPLICATION_CREDENTIALS", "Path to service account key JSON"),
    ]
    
    all_passed = True
    
    print("Environment Variables:")
    print("-" * 80)
    
    for env_var, description in checks:
        passed, message = check_env_var(env_var, description)
        print(message)
        all_passed = all_passed and passed
    
    print()
    print("=" * 80)
    
    if all_passed:
        print("✓ All environment variables are configured")
        print()
        print("Next steps:")
        print("  1. Verify Vertex AI API is enabled:")
        print("     gcloud services list --enabled --filter='name:aiplatform.googleapis.com'")
        print()
        print("  2. Verify FHIR server connectivity:")
        print("     curl -I $STAGING_FHIR_BASE_URL/metadata")
        print()
        print("  3. Verify Cloud SQL connectivity:")
        print("     psql $STAGING_DATABASE_URL -c 'SELECT 1'")
        print()
        print("  4. Run performance test:")
        print("     pytest tests/performance/test_discharge_summary_p95.py -v")
        print()
        return 0
    else:
        print("✗ Some environment variables are missing")
        print()
        print("Please set the missing environment variables. See:")
        print("  tests/performance/STAGING-SETUP.md")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(validate_environment())
