"""Feature extraction for the 30-day readmission risk model.

Retrieves the 7 features required by the ML Inference Service from two sources:
    1. SmartHandoff DB (encounter record, patient record, medication count, prior admissions)
    2. FHIR R4 API (num_comorbidities from Condition resources via US-017 FHIRClient)

FHIR data is used transiently in the agent's working memory — not persisted (AIR-012, C-03).

Feature definitions:
    age                       : Patient age in years at admission (from patient.dob + encounter.admit_date)
    los_days                  : Length of stay = (discharge_date − admit_date).days
    num_comorbidities         : Count of active FHIR Condition resources for the patient
    num_prior_admissions_12mo : Count of DISCHARGED encounters in SmartHandoff DB (past 12 months, excl. current)
    medication_count          : Count of active medications linked to the encounter
    discharge_disposition     : Ordinal-encoded from encounter.discharge_disposition field
    primary_diagnosis_group   : Ordinal-encoded from encounter.admitting_diagnosis using ICD-10 group map

Design refs:
    US-039 Technical Notes — features: FHIR Condition → num_comorbidities; prior admissions from DB
    ml-inference/config/feature_labels.yaml — ordinal encoding reference
"""
from __future__ import annotations

import datetime
import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.fhir_client import FHIRClient
from app.models.encounter import Encounter
from app.models.medication import Medication
from app.models.patient import Patient

logger = logging.getLogger(__name__)

# Discharge disposition ordinal encoding — matches config/feature_labels.yaml
DISCHARGE_DISPOSITION_MAP: dict[str, int] = {
    "home": 0,
    "snf": 1,
    "rehab": 2,
    "home_health": 3,
    "ama": 4,
}

# ICD-10 chapter prefix → primary_diagnosis_group index (0–19)
# Matches ml-inference/config/feature_labels.yaml primary_diagnosis_group_encoding
ICD10_GROUP_MAP: dict[str, int] = {
    "I": 0,   # Circulatory System Disorders
    "J": 1,   # Respiratory System Disorders
    "M": 2,   # Musculoskeletal & Connective Tissue
    "G": 3,   # Nervous System Disorders
    "K": 4,   # Digestive System Disorders
    "E": 5,   # Endocrine, Nutritional & Metabolic
    "N": 6,   # Genitourinary System Disorders
    "A": 7,   # Infectious & Parasitic Diseases
    "B": 7,   # Infectious & Parasitic Diseases (also)
    "C": 8,   # Neoplasms
    "D": 8,   # Neoplasms (benign)
    "F": 9,   # Mental Health & Substance Use
    "S": 10,  # Injuries, Poisoning & Toxic Effects
    "T": 10,  # Injuries, Poisoning & Toxic Effects (also)
    "Z": 11,  # Factors Influencing Health Status
    "L": 12,  # Skin, Subcutaneous Tissue & Breast
    "H": 13,  # Blood & Blood-Forming Organs
    "Q": 14,  # Hepatobiliary & Pancreatic Disorders (congenital — approximate)
    "R": 14,  # Hepatobiliary & Pancreatic Disorders (symptoms — approximate)
    "U": 15,  # Kidney & Urinary Tract Disorders
    "O": 16,  # Female Reproductive System Disorders
    "P": 17,  # Male Reproductive System Disorders (neonatal — approximate)
    "V": 18,  # Burns
}
ICD10_GROUP_DEFAULT = 19  # "Other"


async def extract_features(
    session: AsyncSession,
    fhir_client: FHIRClient,
    encounter_id: str,
) -> dict[str, float]:
    """Assemble the 7-feature vector for the readmission risk model.

    Args:
        session: Async SQLAlchemy read session.
        fhir_client: FHIR R4 client (US-017).
        encounter_id: UUID of the discharged encounter.

    Returns:
        Dict mapping feature name → float value, keyed by FEATURE_NAMES order.

    Raises:
        ValueError: If the encounter is not found or is missing required fields.
    """
    # ── Load encounter + patient from DB ─────────────────────────────────────
    result = await session.execute(
        select(Encounter).where(Encounter.id == encounter_id)
    )
    encounter: Encounter | None = result.scalar_one_or_none()
    if encounter is None:
        raise ValueError(f"Encounter not found: {encounter_id}")

    patient_result = await session.execute(
        select(Patient).where(Patient.id == encounter.patient_id)
    )
    patient: Patient | None = patient_result.scalar_one_or_none()
    if patient is None:
        raise ValueError(f"Patient not found for encounter: {encounter_id}")

    # ── age ──────────────────────────────────────────────────────────────────
    admit_date = encounter.admit_date or datetime.datetime.utcnow()
    dob = patient.dob  # datetime.date from encrypted ORM field
    age = (admit_date.date() - dob).days / 365.25

    # ── los_days ─────────────────────────────────────────────────────────────
    discharge_date = encounter.discharge_date or datetime.datetime.utcnow()
    los_days = max(0.0, (discharge_date - admit_date).total_seconds() / 86400)

    # ── num_comorbidities (FHIR) ──────────────────────────────────────────────
    try:
        conditions = await fhir_client.get_conditions(patient_id=str(encounter.patient_id))
        num_comorbidities = float(len([c for c in conditions if c.clinical_status == "active"]))
    except Exception as exc:
        logger.warning(
            "FHIR Condition fetch failed for encounter_id=%s: %s. Defaulting to 0.",
            encounter_id,
            exc,
        )
        num_comorbidities = 0.0

    # ── num_prior_admissions_12mo (SmartHandoff DB) ──────────────────────────
    cutoff = admit_date - datetime.timedelta(days=365)
    prior_count_result = await session.execute(
        select(func.count(Encounter.id)).where(
            Encounter.patient_id == encounter.patient_id,
            Encounter.status == "DISCHARGED",
            Encounter.discharge_date >= cutoff,
            Encounter.id != encounter.id,
            Encounter.deleted_at.is_(None),
        )
    )
    num_prior_admissions_12mo = float(prior_count_result.scalar_one() or 0)

    # ── medication_count (SmartHandoff DB) ────────────────────────────────────
    med_count_result = await session.execute(
        select(func.count(Medication.id)).where(
            Medication.encounter_id == encounter.id,
            Medication.status == "active",
        )
    )
    medication_count = float(med_count_result.scalar_one() or 0)

    # ── discharge_disposition ─────────────────────────────────────────────────
    disposition_raw = (encounter.discharge_disposition or "home").lower()
    discharge_disposition = float(DISCHARGE_DISPOSITION_MAP.get(disposition_raw, 0))

    # ── primary_diagnosis_group ───────────────────────────────────────────────
    dx = (encounter.admitting_diagnosis or "").upper()
    icd_prefix = dx[0] if dx else ""
    primary_diagnosis_group = float(ICD10_GROUP_MAP.get(icd_prefix, ICD10_GROUP_DEFAULT))

    features = {
        "age": round(age, 2),
        "los_days": round(los_days, 2),
        "num_comorbidities": num_comorbidities,
        "num_prior_admissions_12mo": num_prior_admissions_12mo,
        "medication_count": medication_count,
        "discharge_disposition": discharge_disposition,
        "primary_diagnosis_group": primary_diagnosis_group,
    }

    logger.debug(
        "Features extracted for encounter_id=%s: %s",
        encounter_id,
        # Log only non-PHI values (numeric features)
        {k: v for k, v in features.items()},
    )
    return features
