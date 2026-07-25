"""
Factory for generating deterministic test EncounterContext instances
with varying clinical complexity for performance testing.
"""
from __future__ import annotations

import random
from typing import List

from agents.documentation.fhir_fetcher import (
    DiagnosisContext,
    EncounterContext,
    MedicationContext,
)

# Sample ICD-10 codes representing common inpatient diagnoses
_SAMPLE_DIAGNOSES = [
    ("E11.9", "Type 2 diabetes mellitus without complications"),
    ("I10", "Essential (primary) hypertension"),
    ("I50.9", "Heart failure, unspecified"),
    ("J18.9", "Pneumonia, unspecified organism"),
    ("N18.3", "Chronic kidney disease, stage 3"),
    ("K92.1", "Melena"),
    ("F32.1", "Major depressive disorder, single episode, moderate"),
    ("M54.5", "Low back pain"),
]

# Sample generic drug names
_SAMPLE_MEDICATIONS = [
    ("metformin", "500 mg", "twice daily", "oral", "860975"),
    ("lisinopril", "10 mg", "once daily", "oral", "29046"),
    ("atorvastatin", "40 mg", "once daily at bedtime", "oral", "617310"),
    ("furosemide", "40 mg", "once daily", "oral", "202991"),
    ("amlodipine", "5 mg", "once daily", "oral", "17767"),
    ("omeprazole", "20 mg", "once daily before breakfast", "oral", "40790"),
    ("aspirin", "81 mg", "once daily", "oral", "1191"),
    ("warfarin", "5 mg", "once daily", "oral", "11289"),
    ("insulin glargine", "20 units", "once daily at bedtime", "subcutaneous", "274783"),
    ("albuterol", "2.5 mg", "every 4-6 hours as needed", "inhaled", "435"),
    ("prednisone", "20 mg", "once daily", "oral", "8787"),
    ("sertraline", "50 mg", "once daily", "oral", "36437"),
]


def build_test_encounters(count: int, seed: int = 42) -> List[EncounterContext]:
    """
    Generate `count` EncounterContext instances with deterministic randomness.

    Args:
        count: Number of encounter contexts to generate.
        seed: Random seed for reproducibility across test runs.

    Returns:
        List of EncounterContext instances with varying diagnosis and
        medication counts.
    """
    rng = random.Random(seed)
    encounters = []

    for i in range(count):
        num_diagnoses = rng.randint(1, 8)
        num_medications = rng.randint(1, 12)
        los = rng.randint(1, 14)

        selected_dx = rng.choices(_SAMPLE_DIAGNOSES, k=num_diagnoses)
        selected_meds = rng.choices(_SAMPLE_MEDICATIONS, k=num_medications)

        diagnoses = [
            DiagnosisContext(
                icd10_code=dx[0],
                description=dx[1],
                is_primary=(j == 0),
            )
            for j, dx in enumerate(selected_dx)
        ]
        medications = [
            MedicationContext(
                drug_name=med[0],
                dose=med[1],
                frequency=med[2],
                route=med[3],
                rxnorm_code=med[4],
            )
            for med in selected_meds
        ]

        encounters.append(
            EncounterContext(
                encounter_id=f"PERF-ENC-{i + 1:04d}",
                admission_reason=selected_dx[0][1],
                encounter_type="inpatient",
                discharge_disposition="Home",
                length_of_stay_days=los,
                diagnoses=diagnoses,
                medications=medications,
            )
        )

    return encounters
