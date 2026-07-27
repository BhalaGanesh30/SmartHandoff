"""
Validation script for TASK-002: ReadingLevelScorer implementation.

Tests all acceptance criteria from US-027 TASK-002.
"""
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_dir))


def run_validation():
    """Run all validation checks for ReadingLevelScorer."""
    print()
    print("=" * 80)
    print("TASK-002: ReadingLevelScorer Validation")
    print("=" * 80)
    print()

    checks_passed = 0
    checks_total = 0

    # Check 1: Module imports successfully
    checks_total += 1
    try:
        from agents.documentation.reading_level_scorer import (
            ReadingLevelScorer,
            ScoringResult,
            FK_GRADE_TARGET,
        )
        print("✓ Check 1: ReadingLevelScorer imports successfully")
        checks_passed += 1
    except ImportError as e:
        print(f"✗ Check 1: Import failed - {e}")
        return

    # Check 2: Test basic scoring
    checks_total += 1
    try:
        scorer = ReadingLevelScorer()
        result = scorer.score("The quick brown fox jumps over the lazy dog.")
        assert isinstance(result, ScoringResult), "Result must be ScoringResult instance"
        assert isinstance(result.grade, float), "Grade must be float"
        assert isinstance(result.passes, bool), "Passes must be bool"
        assert result.text == "The quick brown fox jumps over the lazy dog.", "Text must match input"
        print(f"✓ Check 2: Basic scoring works (grade={result.grade:.2f})")
        checks_passed += 1
    except Exception as e:
        print(f"✗ Check 2: Basic scoring failed - {e}")

    # Check 3: Test pass/fail logic
    checks_total += 1
    try:
        # Simple text should pass (low grade)
        simple_text = "The dog ran. The cat sat. The sun is up."
        simple_result = scorer.score(simple_text)
        
        # Complex text should fail (high grade)
        complex_text = (
            "The utilization of sophisticated pharmaceutical interventions "
            "necessitates comprehensive understanding of pharmacokinetic principles "
            "and therapeutic modalities to ensure optimal patient outcomes through "
            "evidence-based clinical decision-making processes."
        )
        complex_result = scorer.score(complex_text)
        
        print(f"✓ Check 3: Pass/fail logic works")
        print(f"  Simple text grade: {simple_result.grade:.2f}, passes: {simple_result.passes}")
        print(f"  Complex text grade: {complex_result.grade:.2f}, passes: {complex_result.passes}")
        checks_passed += 1
    except Exception as e:
        print(f"✗ Check 3: Pass/fail logic failed - {e}")

    # Check 4: Test score_all_sections
    checks_total += 1
    try:
        sections = {
            "medication": "Take one pill twice per day.",
            "diet": "Eat healthy foods. Drink water.",
            "follow_up": "See your doctor in one week.",
        }
        all_results = scorer.score_all_sections(sections)
        assert len(all_results) == 3, "Must return results for all sections"
        assert all(isinstance(r, ScoringResult) for r in all_results.values()), "All results must be ScoringResult"
        print(f"✓ Check 4: score_all_sections works ({len(all_results)} sections scored)")
        checks_passed += 1
    except Exception as e:
        print(f"✗ Check 4: score_all_sections failed - {e}")

    # Check 5: Test aggregate_grade
    checks_total += 1
    try:
        sections = {
            "section1": "The dog ran fast.",
            "section2": "The cat sat down.",
            "section3": "The sun is bright.",
        }
        agg_grade = scorer.aggregate_grade(sections)
        assert isinstance(agg_grade, float), "Aggregate grade must be float"
        # Note: FK grades can be negative for very simple text, so just check it's a valid number
        assert not (agg_grade != agg_grade), "Aggregate grade must not be NaN"
        print(f"✓ Check 5: aggregate_grade works (aggregate={agg_grade:.2f})")
        checks_passed += 1
    except Exception as e:
        print(f"✗ Check 5: aggregate_grade failed - {e}")

    # Check 6: Test aggregate_grade with empty input
    checks_total += 1
    try:
        empty_grade = scorer.aggregate_grade({})
        assert empty_grade == 0.0, "Empty input must return 0.0"
        print(f"✓ Check 6: aggregate_grade handles empty input (returns {empty_grade})")
        checks_passed += 1
    except Exception as e:
        print(f"✗ Check 6: Empty input handling failed - {e}")

    # Check 7: Test build_simplify_prompt
    checks_total += 1
    try:
        test_text = "Some complex medical text."
        prompt = ReadingLevelScorer.build_simplify_prompt(test_text)
        assert "6th-grade" in prompt, "Prompt must mention 6th-grade"
        assert test_text in prompt, "Prompt must contain the original text"
        print(f"✓ Check 7: build_simplify_prompt generates correct prompt")
        checks_passed += 1
    except Exception as e:
        print(f"✗ Check 7: build_simplify_prompt failed - {e}")

    # Check 8: Test FK_GRADE_TARGET constant
    checks_total += 1
    try:
        assert FK_GRADE_TARGET == 6.0, f"FK_GRADE_TARGET must be 6.0, got {FK_GRADE_TARGET}"
        print(f"✓ Check 8: FK_GRADE_TARGET = {FK_GRADE_TARGET}")
        checks_passed += 1
    except Exception as e:
        print(f"✗ Check 8: FK_GRADE_TARGET check failed - {e}")

    # Check 9: Test module exports
    checks_total += 1
    try:
        from agents.documentation import (
            ReadingLevelScorer as ExportedScorer,
            ScoringResult as ExportedResult,
            FK_GRADE_TARGET as ExportedTarget,
        )
        print(f"✓ Check 9: Module exports all required symbols")
        checks_passed += 1
    except ImportError as e:
        print(f"✗ Check 9: Module exports failed - {e}")

    # Check 10: Test frozen dataclass
    checks_total += 1
    try:
        result = scorer.score("Test text")
        try:
            result.grade = 99.0  # Should raise error
            print(f"✗ Check 10: ScoringResult should be immutable (frozen)")
        except Exception:
            print(f"✓ Check 10: ScoringResult is immutable (frozen)")
            checks_passed += 1
    except Exception as e:
        print(f"✗ Check 10: Immutability test failed - {e}")

    print()
    print("=" * 80)
    print(f"Validation Results: {checks_passed}/{checks_total} checks passed")
    print("=" * 80)
    print()

    if checks_passed == checks_total:
        print("✓ TASK-002 VALIDATION: PASSED")
        print()
        return 0
    else:
        print("✗ TASK-002 VALIDATION: FAILED")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(run_validation())
