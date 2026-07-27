"""
Unit tests for ReadingLevelScorer.

Validates FK grade computation, pass/fail threshold, and simplification prompt generation.
"""
import pytest
from agents.documentation.reading_level_scorer import (
    ReadingLevelScorer,
    FK_GRADE_TARGET,
    ScoringResult,
)


class TestReadingLevelScorer:
    """Tests for Flesch-Kincaid grade scoring."""

    def setup_method(self) -> None:
        self.scorer = ReadingLevelScorer()

    def test_simple_text_passes_grade_target(self) -> None:
        """Simple short sentences should score ≤ 6.0."""
        text = "Take one pill every day. Drink water. Rest at home."
        result = self.scorer.score(text)
        assert isinstance(result, ScoringResult)
        assert result.grade <= FK_GRADE_TARGET
        assert result.passes is True

    def test_complex_medical_text_fails_grade_target(self) -> None:
        """Complex medical jargon should exceed FK grade 6.0."""
        text = (
            "Administer the prescribed antihypertensive medication in accordance with "
            "the recommended pharmacological dosage and titration schedule to mitigate "
            "the risk of cardiovascular complications and cerebrovascular incidents."
        )
        result = self.scorer.score(text)
        assert result.grade > FK_GRADE_TARGET
        assert result.passes is False

    def test_aggregate_grade_empty_returns_zero(self) -> None:
        """aggregate_grade with empty dict must return 0.0 without raising."""
        grade = self.scorer.aggregate_grade({})
        assert grade == 0.0

    def test_aggregate_grade_multiple_sections(self) -> None:
        """aggregate_grade returns float average across sections."""
        sections = {
            "a": "Go home. Rest. Drink fluids.",
            "b": "Call your doctor if you feel worse.",
        }
        grade = self.scorer.aggregate_grade(sections)
        assert isinstance(grade, float)
        assert grade >= 0.0

    def test_build_simplify_prompt_contains_6th_grade(self) -> None:
        """Simplification prompt must reference '6th-grade'."""
        prompt = ReadingLevelScorer.build_simplify_prompt("Some complex text here.")
        assert "6th-grade" in prompt
        assert "Some complex text here." in prompt

    def test_score_all_sections_returns_per_section_results(self) -> None:
        """score_all_sections returns a result for each section key."""
        sections = {"intro": "Hello. Rest. Drink water.", "meds": "Take one tablet daily."}
        results = self.scorer.score_all_sections(sections)
        assert set(results.keys()) == {"intro", "meds"}
        assert all(isinstance(r, ScoringResult) for r in results.values())
