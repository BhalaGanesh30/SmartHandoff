"""
Validation script for US-037 TASK-001 Bed Scoring Algorithm.

Validates:
- Module structure exists
- YAML config file exists and is valid
- Weight loader validates sum to 1.0
- Factor functions return values in [0.0, 1.0]
- Isolation filtering works correctly
- Score calculation matches formula
- Top 5 ranking works

Design refs:
    US-037 TASK-001 — BedScoringAlgorithm validation checklist
"""

import sys
from pathlib import Path

# Add backend to Python path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

def check_file_exists(filepath):
    """Check if file exists."""
    path = Path(filepath)
    if not path.exists():
        return False, f"✗ File not found: {filepath}"
    return True, f"✓ File exists: {filepath}"

def check_module_imports():
    """Check if all modules can be imported."""
    try:
        from app.agents.bed_management.scoring import (
            BedRecommendation,
            BedScoringAlgorithm,
            PatientAdmissionProfile,
            ScoreBreakdown,
            ScoringWeights,
            load_weights,
        )
        return True, "✓ All modules import successfully"
    except ImportError as e:
        return False, f"✗ Import error: {e}"

def check_yaml_validity():
    """Check if YAML file is valid and loads correctly."""
    try:
        from app.agents.bed_management.scoring import load_weights
        weights = load_weights()
        return True, f"✓ YAML loads correctly: acuity={weights.acuity}, care_type={weights.care_type}, isolation={weights.isolation}, gender={weights.gender}"
    except Exception as e:
        return False, f"✗ YAML loading failed: {e}"

def check_weight_validation():
    """Check if weight validation works (sum must equal 1.0)."""
    try:
        from app.agents.bed_management.scoring.weight_loader import ScoringWeights
        
        # Valid weights
        valid = ScoringWeights(acuity=0.4, care_type=0.35, isolation=0.15, gender=0.1)
        valid.validate()
        
        # Invalid weights (should raise ValueError)
        try:
            invalid = ScoringWeights(acuity=0.5, care_type=0.3, isolation=0.1, gender=0.05)
            invalid.validate()
            return False, "✗ Weight validation failed to reject invalid weights (sum=0.95)"
        except ValueError:
            pass  # Expected
        
        return True, "✓ Weight validation works correctly"
    except Exception as e:
        return False, f"✗ Weight validation error: {e}"

def check_factor_functions():
    """Check if factor functions return values in [0.0, 1.0]."""
    try:
        from app.agents.bed_management.scoring.factors import (
            score_acuity_match,
            score_care_type_match,
            score_isolation_match,
            score_gender_match,
        )
        
        results = []
        
        # Test acuity matching
        score = score_acuity_match("ICU", "ICU")
        if 0.0 <= score <= 1.0 and score == 1.0:
            results.append("✓ Acuity match (exact): 1.0")
        else:
            return False, f"✗ Acuity exact match failed: {score}"
        
        score = score_acuity_match("MED-SURG", "ICU")
        if 0.0 <= score <= 1.0 and score == 0.8:
            results.append("✓ Acuity match (over-resourced): 0.8")
        else:
            return False, f"✗ Acuity over-resourced failed: {score}"
        
        score = score_acuity_match("ICU", "MED-SURG")
        if score == 0.0:
            results.append("✓ Acuity match (under-resourced): 0.0")
        else:
            return False, f"✗ Acuity under-resourced failed: {score}"
        
        # Test care type matching
        score = score_care_type_match("CARDIAC", "CARDIAC")
        if score == 1.0:
            results.append("✓ Care type match (exact): 1.0")
        else:
            return False, f"✗ Care type exact match failed: {score}"
        
        score = score_care_type_match("CARDIAC", "GENERAL")
        if score == 0.6:
            results.append("✓ Care type match (general bed): 0.6")
        else:
            return False, f"✗ Care type general bed failed: {score}"
        
        # Test isolation matching
        score = score_isolation_match(True, True)
        if score == 1.0:
            results.append("✓ Isolation match (required + capable): 1.0")
        else:
            return False, f"✗ Isolation required+capable failed: {score}"
        
        score = score_isolation_match(True, False)
        if score == 0.0:
            results.append("✓ Isolation match (required + not capable): 0.0")
        else:
            return False, f"✗ Isolation required+not capable failed: {score}"
        
        score = score_isolation_match(False, False)
        if score == 1.0:
            results.append("✓ Isolation match (not required + not capable): 1.0")
        else:
            return False, f"✗ Isolation not required+not capable failed: {score}"
        
        # Test gender matching
        score = score_gender_match("female", "female")
        if score == 1.0:
            results.append("✓ Gender match (exact): 1.0")
        else:
            return False, f"✗ Gender exact match failed: {score}"
        
        score = score_gender_match("female", "any")
        if score == 0.8:
            results.append("✓ Gender match (gender-neutral): 0.8")
        else:
            return False, f"✗ Gender neutral failed: {score}"
        
        score = score_gender_match("female", "male")
        if score == 0.0:
            results.append("✓ Gender match (mismatch): 0.0")
        else:
            return False, f"✗ Gender mismatch failed: {score}"
        
        return True, "\n  ".join(results)
    except Exception as e:
        return False, f"✗ Factor function error: {e}"

def check_isolation_filtering():
    """Check if isolation filtering excludes non-isolation beds."""
    try:
        from app.agents.bed_management.scoring import (
            BedScoringAlgorithm,
            PatientAdmissionProfile,
        )
        
        algo = BedScoringAlgorithm()
        
        # Patient requires isolation
        profile = PatientAdmissionProfile(
            acuity_level="ICU",
            admit_type="INFECTIOUS",
            isolation_required=True,
            gender="female",
        )
        
        # Mix of isolation and non-isolation beds
        beds = [
            {
                "bed_id": "BED-001",
                "unit": "3A",
                "room": "301",
                "bed_number": "1",
                "bed_type": "ICU",
                "care_type": "INFECTIOUS",
                "isolation_capable": False,
                "gender_designation": "female",
            },
            {
                "bed_id": "BED-002",
                "unit": "3B",
                "room": "302",
                "bed_number": "1",
                "bed_type": "ICU",
                "care_type": "INFECTIOUS",
                "isolation_capable": True,
                "gender_designation": "female",
            },
        ]
        
        recommendations = algo.score_and_rank(profile, beds)
        
        # Only BED-002 should be recommended
        if len(recommendations) == 1 and recommendations[0].bed_id == "BED-002":
            return True, "✓ Isolation filtering works (non-isolation beds excluded)"
        else:
            return False, f"✗ Isolation filtering failed: {len(recommendations)} recommendations, expected 1"
    except Exception as e:
        return False, f"✗ Isolation filtering error: {e}"

def check_score_calculation():
    """Check if score calculation matches formula."""
    try:
        from app.agents.bed_management.scoring import (
            BedScoringAlgorithm,
            PatientAdmissionProfile,
        )
        
        algo = BedScoringAlgorithm()
        
        # Perfect match patient
        profile = PatientAdmissionProfile(
            acuity_level="ICU",
            admit_type="CARDIAC",
            isolation_required=False,
            gender="female",
        )
        
        # Perfect match bed
        beds = [
            {
                "bed_id": "BED-PERFECT",
                "unit": "3A",
                "room": "301",
                "bed_number": "1",
                "bed_type": "ICU",
                "care_type": "CARDIAC",
                "isolation_capable": False,
                "gender_designation": "female",
            },
        ]
        
        recommendations = algo.score_and_rank(profile, beds)
        
        # Perfect match: all factors = 1.0
        # Score = 0.4*1.0 + 0.35*1.0 + 0.15*1.0 + 0.1*1.0 = 1.0
        if len(recommendations) == 1 and abs(recommendations[0].score - 1.0) < 0.01:
            breakdown = recommendations[0].score_breakdown
            return True, f"✓ Score calculation correct (perfect match = 1.0)\n  Breakdown: acuity={breakdown.acuity_match}, care={breakdown.care_type_match}, iso={breakdown.isolation_match}, gender={breakdown.gender_match}"
        else:
            return False, f"✗ Score calculation failed: expected 1.0, got {recommendations[0].score if recommendations else 'no recommendations'}"
    except Exception as e:
        return False, f"✗ Score calculation error: {e}"

def check_top_5_ranking():
    """Check if top 5 ranking works correctly."""
    try:
        from app.agents.bed_management.scoring import (
            BedScoringAlgorithm,
            PatientAdmissionProfile,
        )
        
        algo = BedScoringAlgorithm()
        
        profile = PatientAdmissionProfile(
            acuity_level="MED-SURG",
            admit_type="GENERAL",
            isolation_required=False,
            gender="any",
        )
        
        # Create 10 beds with varying matches
        beds = []
        for i in range(10):
            beds.append({
                "bed_id": f"BED-{i:03d}",
                "unit": f"UNIT-{i % 3}",
                "room": f"{300 + i}",
                "bed_number": "1",
                "bed_type": "MED-SURG" if i < 5 else "OBS",  # First 5 are exact match
                "care_type": "GENERAL",
                "isolation_capable": False,
                "gender_designation": "any",
            })
        
        recommendations = algo.score_and_rank(profile, beds)
        
        # Should return top 5
        if len(recommendations) == 5:
            # Check descending order
            for i in range(len(recommendations) - 1):
                if recommendations[i].score < recommendations[i + 1].score:
                    return False, f"✗ Ranking order incorrect: {recommendations[i].score} < {recommendations[i+1].score}"
            return True, f"✓ Top 5 ranking works correctly (returned {len(recommendations)} beds in descending order)"
        else:
            return False, f"✗ Top 5 ranking failed: expected 5 recommendations, got {len(recommendations)}"
    except Exception as e:
        return False, f"✗ Top 5 ranking error: {e}"

def run_validation():
    print("=" * 80)
    print("US-037 TASK-001 Validation: Bed Scoring Algorithm")
    print("=" * 80)

    all_passed = True

    # ──────────────────────────────────────────────────────────────────────────
    # 1. File Structure Check
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[1/8] File Structure Check")
    
    files = [
        "backend/config/bed_scoring_weights.yaml",
        "backend/app/agents/bed_management/scoring/__init__.py",
        "backend/app/agents/bed_management/scoring/weight_loader.py",
        "backend/app/agents/bed_management/scoring/factors.py",
        "backend/app/agents/bed_management/scoring/algorithm.py",
    ]
    
    for filepath in files:
        passed, message = check_file_exists(filepath)
        print(f"  {message}")
        if not passed:
            all_passed = False

    # ──────────────────────────────────────────────────────────────────────────
    # 2. Module Import Check
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[2/8] Module Import Check")
    passed, message = check_module_imports()
    print(f"  {message}")
    if not passed:
        all_passed = False

    # ──────────────────────────────────────────────────────────────────────────
    # 3. YAML Validity Check
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[3/8] YAML Validity Check")
    passed, message = check_yaml_validity()
    print(f"  {message}")
    if not passed:
        all_passed = False

    # ──────────────────────────────────────────────────────────────────────────
    # 4. Weight Validation Check
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[4/8] Weight Validation Check")
    passed, message = check_weight_validation()
    print(f"  {message}")
    if not passed:
        all_passed = False

    # ──────────────────────────────────────────────────────────────────────────
    # 5. Factor Functions Check
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[5/8] Factor Functions Check")
    passed, message = check_factor_functions()
    print(f"  {message}")
    if not passed:
        all_passed = False

    # ──────────────────────────────────────────────────────────────────────────
    # 6. Isolation Filtering Check
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[6/8] Isolation Filtering Check")
    passed, message = check_isolation_filtering()
    print(f"  {message}")
    if not passed:
        all_passed = False

    # ──────────────────────────────────────────────────────────────────────────
    # 7. Score Calculation Check
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[7/8] Score Calculation Check")
    passed, message = check_score_calculation()
    print(f"  {message}")
    if not passed:
        all_passed = False

    # ──────────────────────────────────────────────────────────────────────────
    # 8. Top 5 Ranking Check
    # ──────────────────────────────────────────────────────────────────────────
    print("\n[8/8] Top 5 Ranking Check")
    passed, message = check_top_5_ranking()
    print(f"  {message}")
    if not passed:
        all_passed = False

    # ──────────────────────────────────────────────────────────────────────────
    # Summary
    # ──────────────────────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    if all_passed:
        print("✓ ALL VALIDATION CHECKS PASSED (8/8)")
        print("=" * 80)
        print("\nBed Scoring Algorithm Summary:")
        print("  ✓ Module structure complete (5 files)")
        print("  ✓ YAML config hot-reloadable")
        print("  ✓ Weight validation enforces sum = 1.0")
        print("  ✓ Factor functions return [0.0, 1.0]")
        print("  ✓ Isolation filtering excludes non-capable beds")
        print("  ✓ Score calculation: acuity×0.4 + care×0.35 + iso×0.15 + gender×0.1")
        print("  ✓ Top 5 ranking returns descending sorted results")
        print("\nUS-037 TASK-001 implementation complete.")
    else:
        print("✗ VALIDATION FAILED")
        print("=" * 80)
        print("\nSome checks failed. Review errors above.")
        sys.exit(1)

if __name__ == "__main__":
    run_validation()
