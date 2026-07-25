"""
Unit tests for resolve_patient_language().

Validates supported language detection, unsupported language fallback,
and absent communication field handling.
"""
import pytest
from agents.documentation.language_utils import resolve_patient_language
from agents.documentation.patient_instructions_schemas import SupportedLanguage


class TestResolvePatientLanguage:
    """Tests for FHIR Patient.communication language resolution."""

    def _make_fhir_patient(self, lang_code: str) -> dict:
        """Build a minimal FHIR Patient resource with a single preferred language."""
        return {
            "communication": [
                {
                    "language": {
                        "coding": [{"code": lang_code}]
                    },
                    "preferred": True,
                }
            ]
        }

    def test_spanish_returns_es(self) -> None:
        """Spanish patient should resolve to SupportedLanguage.ES without fallback."""
        patient = self._make_fhir_patient("es")
        lang, fallback, requested = resolve_patient_language(patient)
        assert lang == SupportedLanguage.ES
        assert fallback is False
        assert requested is None

    def test_french_returns_fr(self) -> None:
        patient = self._make_fhir_patient("fr")
        lang, fallback, requested = resolve_patient_language(patient)
        assert lang == SupportedLanguage.FR
        assert fallback is False

    def test_chinese_returns_zh(self) -> None:
        patient = self._make_fhir_patient("zh")
        lang, fallback, requested = resolve_patient_language(patient)
        assert lang == SupportedLanguage.ZH
        assert fallback is False

    def test_portuguese_returns_pt(self) -> None:
        patient = self._make_fhir_patient("pt")
        lang, fallback, requested = resolve_patient_language(patient)
        assert lang == SupportedLanguage.PT
        assert fallback is False

    def test_japanese_falls_back_to_english(self) -> None:
        """US-027 Scenario 4: Japanese is not supported — must fall back to English."""
        patient = self._make_fhir_patient("ja")
        lang, fallback, requested = resolve_patient_language(patient)
        assert lang == SupportedLanguage.EN
        assert fallback is True
        assert requested == "ja"

    def test_absent_communication_returns_english_no_fallback(self) -> None:
        """Patient with no communication field defaults to English without fallback."""
        patient: dict = {}
        lang, fallback, requested = resolve_patient_language(patient)
        assert lang == SupportedLanguage.EN
        assert fallback is False
        assert requested is None

    def test_bcp47_subtag_normalised(self) -> None:
        """'zh-CN' should normalise to 'zh' and resolve to SupportedLanguage.ZH."""
        patient = self._make_fhir_patient("zh-CN")
        lang, fallback, requested = resolve_patient_language(patient)
        assert lang == SupportedLanguage.ZH
        assert fallback is False

    def test_english_explicit_preference(self) -> None:
        """Explicit 'en' preference resolves to English without fallback."""
        patient = self._make_fhir_patient("en")
        lang, fallback, requested = resolve_patient_language(patient)
        assert lang == SupportedLanguage.EN
        assert fallback is False

    def test_malformed_communication_returns_english(self) -> None:
        """Malformed communication field must not raise — returns English."""
        patient = {"communication": [{"language": {}}]}  # Missing 'coding'
        lang, fallback, requested = resolve_patient_language(patient)
        assert lang == SupportedLanguage.EN
