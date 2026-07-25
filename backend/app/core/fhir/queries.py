"""FHIR Patient search query builders (US-019 TASK-001).

Constructs FHIR R4 compliant search queries for patient identity resolution
via MRN primary lookup and name+DOB fallback.

Design refs:
    US-019 AC1: MRN primary lookup via identifier search
    US-019 AC2: Name+DOB fallback via name and birthdate parameters
    DR-024: Patient identity resolution requirements
"""
from __future__ import annotations

from datetime import datetime
from urllib.parse import quote


def build_mrn_query(mrn: str, system_uri: str) -> str:
    """Build FHIR Patient search query by MRN identifier.
    
    Constructs a FHIR R4 search query using the identifier parameter with
    system|value syntax for precise MRN matching.
    
    Args:
        mrn: Medical Record Number (plaintext)
        system_uri: FHIR identifier system URI (e.g., "http://hospital.org/mrn")
    
    Returns:
        FHIR search query string (e.g., "Patient?identifier=http://hospital.org/mrn|MRN-789")
    
    Example:
        >>> build_mrn_query("MRN-789", "http://hospital.org/mrn")
        'Patient?identifier=http%3A%2F%2Fhospital.org%2Fmrn%7CMRN-789'
    
    Raises:
        ValueError: If mrn or system_uri is empty
    
    Design refs:
        US-019 AC1: Constructs Patient?identifier={system}|{mrn}
        FHIR R4 spec: https://www.hl7.org/fhir/patient.html#search
    """
    if not mrn:
        raise ValueError("MRN cannot be empty")
    if not system_uri:
        raise ValueError("System URI cannot be empty")
    
    # URL-encode system URI to handle special characters (://)
    # Use safe=':/' to keep the URI readable but encode pipe separator
    encoded_identifier = f"{quote(system_uri, safe=':/')}|{quote(mrn, safe='')}"
    return f"Patient?identifier={encoded_identifier}"


def build_name_dob_query(family: str, given: str, dob: str) -> str:
    """Build FHIR Patient search query by name and date of birth.
    
    Constructs a FHIR R4 search query using family, given, and birthdate parameters
    for fallback patient resolution when MRN is unavailable.
    
    Args:
        family: Family (last) name
        given: Given (first) name
        dob: Date of birth in YYYY-MM-DD format
    
    Returns:
        FHIR search query string (e.g., "Patient?family=Smith&given=John&birthdate=1980-01-15")
    
    Example:
        >>> build_name_dob_query("Smith", "John", "1980-01-15")
        'Patient?family=Smith&given=John&birthdate=1980-01-15'
        
        >>> build_name_dob_query("O'Brien", "Mary", "1990-05-20")
        'Patient?family=O%27Brien&given=Mary&birthdate=1990-05-20'
    
    Raises:
        ValueError: If any parameter is empty or dob format is invalid
    
    Design refs:
        US-019 AC2: Constructs Patient?family={family}&given={given}&birthdate={dob}
        FHIR R4 spec: https://www.hl7.org/fhir/patient.html#search
    """
    if not family:
        raise ValueError("Family name cannot be empty")
    if not given:
        raise ValueError("Given name cannot be empty")
    if not dob:
        raise ValueError("Date of birth cannot be empty")
    
    # Validate date format
    if not _is_valid_date_format(dob):
        raise ValueError(f"Invalid date format: {dob}. Expected YYYY-MM-DD.")
    
    # URL-encode names to handle special characters (e.g., O'Brien → O%27Brien)
    # Dates are already in valid format, no encoding needed
    encoded_family = quote(family, safe='')
    encoded_given = quote(given, safe='')
    
    return f"Patient?family={encoded_family}&given={encoded_given}&birthdate={dob}"


def _is_valid_date_format(date_str: str) -> bool:
    """Validate that date string is in YYYY-MM-DD format.
    
    Args:
        date_str: Date string to validate
    
    Returns:
        True if date is in YYYY-MM-DD format, False otherwise
    
    Example:
        >>> _is_valid_date_format("1980-01-15")
        True
        >>> _is_valid_date_format("01/15/1980")
        False
    """
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False
