"""Pydantic wrapper models for FHIR R4 resources.

These models wrap fhir.resources base classes with custom validation,
type-safe field access, and PHI-safe serialization for agent use.

Design refs:
    US-017 AC Scenario 1 — PatientModel with validated fields
    US-017 AC Scenario 4 — FHIRValidationError on invalid resource
    AIR-012              — FHIR data not persisted (transient models)
    DR-021               — FHIR data validation with fhir.resources

IMPORTANT: FHIR data is NEVER persisted to SmartHandoff database.
These models exist in agent memory only during task execution.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from enum import Enum
from typing import Any

from fhir.resources.allergyintolerance import AllergyIntolerance
from fhir.resources.condition import Condition
from fhir.resources.encounter import Encounter
from fhir.resources.medicationadministration import MedicationAdministration
from fhir.resources.medicationrequest import MedicationRequest
from fhir.resources.medicationstatement import MedicationStatement
from fhir.resources.patient import Patient
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class FHIRValidationError(Exception):
    """Raised when FHIR resource fails Pydantic validation.

    Attributes:
        resource_type: FHIR resource type (e.g., "Patient", "MedicationStatement")
        field_path: Dotted path to invalid field (e.g., "medication.reference")
        received_value: The invalid value received from FHIR server
        message: Human-readable error message (no PHI)
    """

    def __init__(
        self,
        message: str,
        resource_type: str | None = None,
        field_path: str | None = None,
        received_value: Any = None,
    ) -> None:
        super().__init__(message)
        self.resource_type = resource_type
        self.field_path = field_path
        self.received_value = received_value

    def __str__(self) -> str:
        if self.resource_type and self.field_path:
            return (
                f"FHIR validation error for {self.resource_type}.{self.field_path}: "
                f"{self.args[0]}"
            )
        return self.args[0]


class PatientResolutionMethod(str, Enum):
    """Patient resolution method enum."""

    MRN = "MRN"
    NAME_DOB = "NAME_DOB"
    UNRESOLVED = "UNRESOLVED"


class PatientModel(BaseModel):
    """Pydantic wrapper for FHIR R4 Patient resource.

    Fields:
        id: FHIR resource ID
        mrn: Medical Record Number from identifier
        family_name: Patient family name (last name)
        given_name: Patient given name (first name)
        birth_date: Patient date of birth
        gender: Patient administrative gender
        phone: Primary phone number (optional)
        email: Primary email address (optional)
        partial_match: True if resolved via name+DOB fallback (not MRN)
        resolution_method: How patient was resolved (MRN, NAME_DOB, UNRESOLVED)
    """

    id: str = Field(..., description="FHIR Patient resource ID")
    mrn: str | None = Field(None, description="Medical Record Number")
    family_name: str = Field(..., description="Patient family name (last name)")
    given_name: str = Field(..., description="Patient given name (first name)")
    birth_date: date = Field(..., description="Patient date of birth")
    gender: str = Field(..., description="Administrative gender (male/female/other/unknown)")
    phone: str | None = Field(None, description="Primary phone number")
    email: str | None = Field(None, description="Primary email address")
    partial_match: bool = Field(
        default=False,
        description="True if resolved via name+DOB fallback (not direct MRN match)",
    )
    resolution_method: PatientResolutionMethod = Field(
        default=PatientResolutionMethod.MRN,
        description="Method used to resolve patient identity",
    )

    @classmethod
    def from_fhir(cls, fhir_patient: Patient) -> PatientModel:
        """Convert FHIR Patient resource to PatientModel.

        Args:
            fhir_patient: FHIR R4 Patient resource from fhir.resources

        Returns:
            PatientModel with validated fields

        Raises:
            FHIRValidationError: If required fields missing or invalid
        """
        try:
            # Extract MRN from identifiers
            mrn = None
            if fhir_patient.identifier:
                for identifier in fhir_patient.identifier:
                    if identifier.type and identifier.type.coding:
                        for coding in identifier.type.coding:
                            if coding.code == "MR":  # Medical Record Number
                                mrn = identifier.value
                                break
                    if mrn:
                        break

            # Extract name components
            if not fhir_patient.name or len(fhir_patient.name) == 0:
                raise FHIRValidationError(
                    "Patient resource missing required 'name' field",
                    resource_type="Patient",
                    field_path="name",
                    received_value=None,
                )

            name = fhir_patient.name[0]  # Use first name entry
            family_name = name.family if name.family else ""
            given_name = name.given[0] if name.given and len(name.given) > 0 else ""

            if not family_name or not given_name:
                raise FHIRValidationError(
                    "Patient name must include both family and given names",
                    resource_type="Patient",
                    field_path="name",
                    received_value={"family": family_name, "given": given_name},
                )

            # Extract telecom (phone/email)
            phone = None
            email = None
            if fhir_patient.telecom:
                for telecom in fhir_patient.telecom:
                    if telecom.system == "phone" and not phone:
                        phone = telecom.value
                    elif telecom.system == "email" and not email:
                        email = telecom.value

            # Birth date is required
            if not fhir_patient.birthDate:
                raise FHIRValidationError(
                    "Patient resource missing required 'birthDate' field",
                    resource_type="Patient",
                    field_path="birthDate",
                    received_value=None,
                )

            # Gender is required
            if not fhir_patient.gender:
                raise FHIRValidationError(
                    "Patient resource missing required 'gender' field",
                    resource_type="Patient",
                    field_path="gender",
                    received_value=None,
                )

            return cls(
                id=fhir_patient.id,
                mrn=mrn,
                family_name=family_name,
                given_name=given_name,
                birth_date=fhir_patient.birthDate,
                gender=fhir_patient.gender,
                phone=phone,
                email=email,
            )

        except FHIRValidationError:
            raise
        except Exception as exc:
            logger.error(
                "Unexpected error parsing FHIR Patient resource",
                extra={"error": str(exc)},
            )
            raise FHIRValidationError(
                f"Failed to parse FHIR Patient: {exc}",
                resource_type="Patient",
            ) from exc


class EncounterModel(BaseModel):
    """Pydantic wrapper for FHIR R4 Encounter resource.

    Fields:
        id: FHIR resource ID
        patient_id: Reference to Patient resource
        status: Encounter status (planned/arrived/in-progress/finished/cancelled)
        class_code: Encounter class (inpatient/outpatient/emergency)
        period_start: Encounter start datetime
        period_end: Encounter end datetime (optional, null if ongoing)
    """

    id: str = Field(..., description="FHIR Encounter resource ID")
    patient_id: str = Field(..., description="Reference to Patient resource")
    status: str = Field(..., description="Encounter status")
    class_code: str = Field(..., description="Encounter class code")
    period_start: datetime | None = Field(None, description="Encounter start datetime")
    period_end: datetime | None = Field(None, description="Encounter end datetime")

    @classmethod
    def from_fhir(cls, fhir_encounter: Encounter) -> EncounterModel:
        """Convert FHIR Encounter resource to EncounterModel."""
        try:
            # Extract patient reference
            if not fhir_encounter.subject or not fhir_encounter.subject.reference:
                raise FHIRValidationError(
                    "Encounter resource missing required 'subject' reference",
                    resource_type="Encounter",
                    field_path="subject.reference",
                    received_value=None,
                )

            patient_id = fhir_encounter.subject.reference.split("/")[-1]

            # Extract class code
            class_code = "unknown"
            if fhir_encounter.class_fhir:
                # In fhir.resources 7.1.0+, class is a list
                if isinstance(fhir_encounter.class_fhir, list) and len(fhir_encounter.class_fhir) > 0:
                    class_item = fhir_encounter.class_fhir[0]
                    if class_item.coding and len(class_item.coding) > 0:
                        class_code = class_item.coding[0].code
                # Fallback for older structure
                elif hasattr(fhir_encounter.class_fhir, 'code'):
                    class_code = fhir_encounter.class_fhir.code

            return cls(
                id=fhir_encounter.id,
                patient_id=patient_id,
                status=fhir_encounter.status,
                class_code=class_code,
                period_start=None,
                period_end=None,
            )

        except FHIRValidationError:
            raise
        except Exception as exc:
            raise FHIRValidationError(
                f"Failed to parse FHIR Encounter: {exc}",
                resource_type="Encounter",
            ) from exc


class MedicationStatementModel(BaseModel):
    """Pydantic wrapper for FHIR R4 MedicationStatement resource.

    Fields:
        id: FHIR resource ID
        patient_id: Reference to Patient resource
        medication_display: Medication name (human-readable)
        medication_code: RxNorm code (optional)
        status: Statement status (active/completed/stopped)
        dosage_text: Dosage instruction (human-readable)
        effective_start: Start date of medication
    """

    id: str = Field(..., description="FHIR MedicationStatement resource ID")
    patient_id: str = Field(..., description="Reference to Patient resource")
    medication_display: str = Field(..., description="Medication name")
    medication_code: str | None = Field(None, description="RxNorm code")
    status: str = Field(..., description="Statement status")
    dosage_text: str | None = Field(None, description="Dosage instruction text")
    effective_start: datetime | None = Field(None, description="Medication start date")

    @classmethod
    def from_fhir(cls, fhir_med_statement: MedicationStatement) -> MedicationStatementModel:
        """Convert FHIR MedicationStatement resource to MedicationStatementModel."""
        try:
            # Extract patient reference
            if not fhir_med_statement.subject or not fhir_med_statement.subject.reference:
                raise FHIRValidationError(
                    "MedicationStatement missing required 'subject' reference",
                    resource_type="MedicationStatement",
                    field_path="subject.reference",
                    received_value=None,
                )

            patient_id = fhir_med_statement.subject.reference.split("/")[-1]

            # Extract medication
            medication_display = "Unknown"
            medication_code = None
            
            # In fhir.resources 7.1.0+, medication is a BackboneElement with concept attribute
            medication_concept = None
            if hasattr(fhir_med_statement, 'medication') and fhir_med_statement.medication:
                if hasattr(fhir_med_statement.medication, 'concept'):
                    medication_concept = fhir_med_statement.medication.concept
            # Fallback for older medicationCodeableConcept structure
            elif hasattr(fhir_med_statement, 'medicationCodeableConcept') and fhir_med_statement.medicationCodeableConcept:
                medication_concept = fhir_med_statement.medicationCodeableConcept
            
            if medication_concept:
                if medication_concept.text:
                    medication_display = medication_concept.text
                if medication_concept.coding:
                    for coding in medication_concept.coding:
                        if coding.system and "rxnorm" in coding.system.lower():
                            medication_code = coding.code
                            break

            # Extract dosage
            dosage_text = None
            if fhir_med_statement.dosage and len(fhir_med_statement.dosage) > 0:
                dosage_text = fhir_med_statement.dosage[0].text

            # Extract effective period
            effective_start = None
            if fhir_med_statement.effectivePeriod:
                effective_start = fhir_med_statement.effectivePeriod.start

            return cls(
                id=fhir_med_statement.id,
                patient_id=patient_id,
                medication_display=medication_display,
                medication_code=medication_code,
                status=fhir_med_statement.status,
                dosage_text=dosage_text,
                effective_start=effective_start,
            )

        except FHIRValidationError:
            raise
        except Exception as exc:
            raise FHIRValidationError(
                f"Failed to parse FHIR MedicationStatement: {exc}",
                resource_type="MedicationStatement",
            ) from exc


class MedicationAdministrationModel(BaseModel):
    """Pydantic wrapper for FHIR R4 MedicationAdministration resource.

    Fields:
        id: FHIR resource ID
        patient_id: Reference to Patient resource
        encounter_id: Reference to Encounter resource (optional)
        medication_display: Medication name
        medication_code: RxNorm code (optional)
        status: Administration status (in-progress/completed/stopped)
        effective_datetime: When medication was administered
    """

    id: str = Field(..., description="FHIR MedicationAdministration resource ID")
    patient_id: str = Field(..., description="Reference to Patient resource")
    encounter_id: str | None = Field(None, description="Reference to Encounter resource")
    medication_display: str = Field(..., description="Medication name")
    medication_code: str | None = Field(None, description="RxNorm code")
    status: str = Field(..., description="Administration status")
    effective_datetime: datetime | None = Field(None, description="Administration datetime")

    @classmethod
    def from_fhir(cls, fhir_med_admin: MedicationAdministration) -> MedicationAdministrationModel:
        """Convert FHIR MedicationAdministration resource to MedicationAdministrationModel."""
        try:
            # Extract patient reference
            if not fhir_med_admin.subject or not fhir_med_admin.subject.reference:
                raise FHIRValidationError(
                    "MedicationAdministration missing required 'subject' reference",
                    resource_type="MedicationAdministration",
                    field_path="subject.reference",
                    received_value=None,
                )

            patient_id = fhir_med_admin.subject.reference.split("/")[-1]

            # Extract encounter reference (optional)
            encounter_id = None
            if fhir_med_admin.context and fhir_med_admin.context.reference:
                encounter_id = fhir_med_admin.context.reference.split("/")[-1]

            # Extract medication
            medication_display = "Unknown"
            medication_code = None
            
            # In fhir.resources 7.1.0+, medication is a BackboneElement with concept attribute
            medication_concept = None
            if hasattr(fhir_med_admin, 'medication') and fhir_med_admin.medication:
                if hasattr(fhir_med_admin.medication, 'concept'):
                    medication_concept = fhir_med_admin.medication.concept
            # Fallback for older medicationCodeableConcept structure
            elif hasattr(fhir_med_admin, 'medicationCodeableConcept') and fhir_med_admin.medicationCodeableConcept:
                medication_concept = fhir_med_admin.medicationCodeableConcept
            
            if medication_concept:
                if medication_concept.text:
                    medication_display = medication_concept.text
                if medication_concept.coding:
                    for coding in medication_concept.coding:
                        if coding.system and "rxnorm" in coding.system.lower():
                            medication_code = coding.code
                            break

            # Extract effective datetime
            effective_datetime = None
            if fhir_med_admin.effectiveDateTime:
                effective_datetime = fhir_med_admin.effectiveDateTime

            return cls(
                id=fhir_med_admin.id,
                patient_id=patient_id,
                encounter_id=encounter_id,
                medication_display=medication_display,
                medication_code=medication_code,
                status=fhir_med_admin.status,
                effective_datetime=effective_datetime,
            )

        except FHIRValidationError:
            raise
        except Exception as exc:
            raise FHIRValidationError(
                f"Failed to parse FHIR MedicationAdministration: {exc}",
                resource_type="MedicationAdministration",
            ) from exc


class MedicationRequestModel(BaseModel):
    """Pydantic wrapper for FHIR R4 MedicationRequest resource.

    Fields:
        id: FHIR resource ID
        patient_id: Reference to Patient resource
        medication_display: Medication name
        medication_code: RxNorm code (optional)
        status: Request status (active/completed/cancelled)
        intent: Request intent (order/plan/proposal)
        dosage_instruction: Dosage instruction text
        authored_on: When request was created
    """

    id: str = Field(..., description="FHIR MedicationRequest resource ID")
    patient_id: str = Field(..., description="Reference to Patient resource")
    medication_display: str = Field(..., description="Medication name")
    medication_code: str | None = Field(None, description="RxNorm code")
    status: str = Field(..., description="Request status")
    intent: str = Field(..., description="Request intent")
    dosage_instruction: str | None = Field(None, description="Dosage instruction text")
    authored_on: datetime | None = Field(None, description="Request creation datetime")

    @classmethod
    def from_fhir(cls, fhir_med_request: MedicationRequest) -> MedicationRequestModel:
        """Convert FHIR MedicationRequest resource to MedicationRequestModel."""
        try:
            # Extract patient reference
            if not fhir_med_request.subject or not fhir_med_request.subject.reference:
                raise FHIRValidationError(
                    "MedicationRequest missing required 'subject' reference",
                    resource_type="MedicationRequest",
                    field_path="subject.reference",
                    received_value=None,
                )

            patient_id = fhir_med_request.subject.reference.split("/")[-1]

            # Extract medication
            medication_display = "Unknown"
            medication_code = None
            
            # In fhir.resources 7.1.0+, medication is a BackboneElement with concept attribute
            medication_concept = None
            if hasattr(fhir_med_request, 'medication') and fhir_med_request.medication:
                if hasattr(fhir_med_request.medication, 'concept'):
                    medication_concept = fhir_med_request.medication.concept
            # Fallback for older medicationCodeableConcept structure
            elif hasattr(fhir_med_request, 'medicationCodeableConcept') and fhir_med_request.medicationCodeableConcept:
                medication_concept = fhir_med_request.medicationCodeableConcept
            
            if medication_concept:
                if medication_concept.text:
                    medication_display = medication_concept.text
                if medication_concept.coding:
                    for coding in medication_concept.coding:
                        if coding.system and "rxnorm" in coding.system.lower():
                            medication_code = coding.code
                            break

            # Extract dosage instruction
            dosage_instruction = None
            if fhir_med_request.dosageInstruction and len(fhir_med_request.dosageInstruction) > 0:
                dosage_instruction = fhir_med_request.dosageInstruction[0].text

            return cls(
                id=fhir_med_request.id,
                patient_id=patient_id,
                medication_display=medication_display,
                medication_code=medication_code,
                status=fhir_med_request.status,
                intent=fhir_med_request.intent,
                dosage_instruction=dosage_instruction,
                authored_on=fhir_med_request.authoredOn,
            )

        except FHIRValidationError:
            raise
        except Exception as exc:
            raise FHIRValidationError(
                f"Failed to parse FHIR MedicationRequest: {exc}",
                resource_type="MedicationRequest",
            ) from exc


class AllergyIntoleranceModel(BaseModel):
    """Pydantic wrapper for FHIR R4 AllergyIntolerance resource.

    Fields:
        id: FHIR resource ID
        patient_id: Reference to Patient resource
        clinical_status: Clinical status (active/inactive/resolved)
        verification_status: Verification status (confirmed/unconfirmed/refuted)
        type: Type (allergy/intolerance)
        category: Category (food/medication/environment/biologic)
        criticality: Criticality (low/high/unable-to-assess)
        code_display: Allergen name (human-readable)
        onset_datetime: When allergy was first noted
    """

    id: str = Field(..., description="FHIR AllergyIntolerance resource ID")
    patient_id: str = Field(..., description="Reference to Patient resource")
    clinical_status: str | None = Field(None, description="Clinical status")
    verification_status: str | None = Field(None, description="Verification status")
    type: str | None = Field(None, description="Allergy or intolerance")
    category: list[str] | None = Field(None, description="Category list")
    criticality: str | None = Field(None, description="Criticality")
    code_display: str = Field(..., description="Allergen name")
    onset_datetime: datetime | None = Field(None, description="Onset datetime")

    @classmethod
    def from_fhir(cls, fhir_allergy: AllergyIntolerance) -> AllergyIntoleranceModel:
        """Convert FHIR AllergyIntolerance resource to AllergyIntoleranceModel."""
        try:
            # Extract patient reference
            if not fhir_allergy.patient or not fhir_allergy.patient.reference:
                raise FHIRValidationError(
                    "AllergyIntolerance missing required 'patient' reference",
                    resource_type="AllergyIntolerance",
                    field_path="patient.reference",
                    received_value=None,
                )

            patient_id = fhir_allergy.patient.reference.split("/")[-1]

            # Extract clinical status
            clinical_status = None
            if fhir_allergy.clinicalStatus and fhir_allergy.clinicalStatus.coding:
                clinical_status = fhir_allergy.clinicalStatus.coding[0].code

            # Extract verification status
            verification_status = None
            if fhir_allergy.verificationStatus and fhir_allergy.verificationStatus.coding:
                verification_status = fhir_allergy.verificationStatus.coding[0].code

            # Extract allergen code
            code_display = "Unknown"
            if fhir_allergy.code:
                if fhir_allergy.code.text:
                    code_display = fhir_allergy.code.text
                elif fhir_allergy.code.coding and len(fhir_allergy.code.coding) > 0:
                    code_display = fhir_allergy.code.coding[0].display or "Unknown"

            return cls(
                id=fhir_allergy.id,
                patient_id=patient_id,
                clinical_status=clinical_status,
                verification_status=verification_status,
                type=fhir_allergy.type,
                category=fhir_allergy.category,
                criticality=fhir_allergy.criticality,
                code_display=code_display,
                onset_datetime=fhir_allergy.onsetDateTime,
            )

        except FHIRValidationError:
            raise
        except Exception as exc:
            raise FHIRValidationError(
                f"Failed to parse FHIR AllergyIntolerance: {exc}",
                resource_type="AllergyIntolerance",
            ) from exc


class ConditionModel(BaseModel):
    """Pydantic wrapper for FHIR R4 Condition resource.

    Fields:
        id: FHIR resource ID
        patient_id: Reference to Patient resource
        clinical_status: Clinical status (active/recurrence/relapse/inactive/remission/resolved)
        verification_status: Verification status (confirmed/provisional/differential/refuted)
        category: Category (problem-list-item/encounter-diagnosis)
        severity: Severity (severe/moderate/mild)
        code_display: Condition name (human-readable)
        code_system: Code system (ICD-10/SNOMED CT)
        code_value: Condition code
        onset_datetime: When condition was first noted
    """

    id: str = Field(..., description="FHIR Condition resource ID")
    patient_id: str = Field(..., description="Reference to Patient resource")
    clinical_status: str | None = Field(None, description="Clinical status")
    verification_status: str | None = Field(None, description="Verification status")
    category: list[str] | None = Field(None, description="Category list")
    severity: str | None = Field(None, description="Severity")
    code_display: str = Field(..., description="Condition name")
    code_system: str | None = Field(None, description="Code system")
    code_value: str | None = Field(None, description="Condition code")
    onset_datetime: datetime | None = Field(None, description="Onset datetime")

    @classmethod
    def from_fhir(cls, fhir_condition: Condition) -> ConditionModel:
        """Convert FHIR Condition resource to ConditionModel."""
        try:
            # Extract patient reference
            if not fhir_condition.subject or not fhir_condition.subject.reference:
                raise FHIRValidationError(
                    "Condition missing required 'subject' reference",
                    resource_type="Condition",
                    field_path="subject.reference",
                    received_value=None,
                )

            patient_id = fhir_condition.subject.reference.split("/")[-1]

            # Extract clinical status
            clinical_status = None
            if fhir_condition.clinicalStatus and fhir_condition.clinicalStatus.coding:
                clinical_status = fhir_condition.clinicalStatus.coding[0].code

            # Extract verification status
            verification_status = None
            if fhir_condition.verificationStatus and fhir_condition.verificationStatus.coding:
                verification_status = fhir_condition.verificationStatus.coding[0].code

            # Extract category
            category = None
            if fhir_condition.category:
                category = []
                for cat in fhir_condition.category:
                    if cat.coding and len(cat.coding) > 0:
                        category.append(cat.coding[0].code)

            # Extract severity
            severity = None
            if fhir_condition.severity and fhir_condition.severity.coding:
                severity = fhir_condition.severity.coding[0].code

            # Extract condition code
            code_display = "Unknown"
            code_system = None
            code_value = None
            if fhir_condition.code:
                if fhir_condition.code.text:
                    code_display = fhir_condition.code.text
                if fhir_condition.code.coding and len(fhir_condition.code.coding) > 0:
                    coding = fhir_condition.code.coding[0]
                    code_display = coding.display or code_display
                    code_system = coding.system
                    code_value = coding.code

            return cls(
                id=fhir_condition.id,
                patient_id=patient_id,
                clinical_status=clinical_status,
                verification_status=verification_status,
                category=category,
                severity=severity,
                code_display=code_display,
                code_system=code_system,
                code_value=code_value,
                onset_datetime=fhir_condition.onsetDateTime,
            )

        except FHIRValidationError:
            raise
        except Exception as exc:
            raise FHIRValidationError(
                f"Failed to parse FHIR Condition: {exc}",
                resource_type="Condition",
            ) from exc
