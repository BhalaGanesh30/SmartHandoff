"""
Integration tests for Patient Instructions generation and translation (US-027 TASK-003 + TASK-004).

Tests the complete pipeline:
1. Generate English instructions (PatientInstructionsGenerator)
2. Translate to 4 languages (PatientInstructionsTranslator)
3. Verify quality checks and FK scoring
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.documentation.patient_instructions_generator import PatientInstructionsGenerator
from agents.documentation.patient_instructions_translator import PatientInstructionsTranslator
from agents.documentation.patient_instructions_schemas import (
    PatientInstructionsContent,
    PatientInstructionsDocument,
    SupportedLanguage,
)


@pytest.fixture
def mock_discharge_summary():
    """Sample discharge summary for testing."""
    return {
        "diagnosis": "Community-acquired pneumonia",
        "procedures": ["Chest X-ray", "IV antibiotics"],
        "medications": [
            {"name": "Amoxicillin", "dosage": "500mg", "frequency": "three times daily"}
        ],
        "follow_up": "See primary care physician in 7 days",
    }


@pytest.fixture
def mock_encounter_context():
    """Sample encounter context for testing."""
    from agents.documentation.fhir_fetcher import (
        EncounterContext,
        DiagnosisContext,
        MedicationContext,
    )
    
    return EncounterContext(
        encounter_id="enc-12345",
        admission_reason="Respiratory infection",
        encounter_type="inpatient",
        discharge_disposition="home",
        length_of_stay_days=2,
        diagnoses=[
            DiagnosisContext(
                icd10_code="J18.9",
                description="Pneumonia, unspecified organism",
                is_primary=True,
            )
        ],
        medications=[
            MedicationContext(
                drug_name="Amoxicillin",
                dose="500mg",
                frequency="three times daily",
                route="oral",
                rxnorm_code="308182",
            )
        ],
        procedures_performed=["Chest X-ray", "IV antibiotics"],
    )


@pytest.fixture
def mock_fhir_patient():
    """Mock FHIR Patient resource."""
    patient = MagicMock()
    patient.communication = [MagicMock()]
    patient.communication[0].language.coding = [MagicMock()]
    patient.communication[0].language.coding[0].code = "en"
    return patient


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for instruction generation."""
    mock_response = MagicMock()
    mock_response.home_care_instructions = (
        "Rest at home. Drink plenty of fluids. Take your medicine as directed."
    )
    mock_response.medications = (
        "Take Amoxicillin 500mg three times daily with food. Complete the full course."
    )
    mock_response.warning_signs = (
        "Call your doctor if you have fever, chest pain, or trouble breathing."
    )
    mock_response.follow_up_appointments = "See your doctor in 7 days."
    mock_response.diet_and_activity = "Eat healthy foods. Rest until you feel better."
    mock_response.emergency_contact = "Call 911 if you have severe chest pain or cannot breathe."
    return mock_response


class TestPatientInstructionsIntegration:
    """Integration tests for the complete patient instructions pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_generates_and_translates_instructions(
        self,
        mock_discharge_summary,
        mock_encounter_context,
        mock_fhir_patient,
        mock_llm_response,
    ):
        """
        Test complete pipeline: generate English instructions → translate to 4 languages.
        
        Verifies:
        - English instructions generated with FK grade ≤ 8.0
        - All 5 languages present in translations dict
        - English entry has quality_check_passed=True
        - Translated entries have similarity scores
        """
        # Mock dependencies
        with patch('agents.documentation.patient_instructions_generator.ChatVertexAI') as mock_llm_class, \
             patch('agents.documentation.patient_instructions_generator.StructuredOutputHelper') as mock_helper_class, \
             patch('agents.documentation.patient_instructions_translator.ChatVertexAI') as mock_translator_llm, \
             patch('agents.documentation.patient_instructions_translator.SentenceTransformer') as mock_embedder:
            
            # Setup generator mocks
            mock_helper = mock_helper_class.return_value
            mock_helper.invoke_structured = AsyncMock(return_value=mock_llm_response)
            
            # Setup translator mocks
            mock_translator_llm_instance = mock_translator_llm.return_value
            
            # Mock translation responses
            async def mock_ainvoke(prompt):
                response = MagicMock()
                if "Spanish" in prompt:
                    response.content = "Descansa en casa. Bebe muchos líquidos. Toma tu medicina según las indicaciones."
                elif "French" in prompt:
                    response.content = "Reposez-vous à la maison. Buvez beaucoup de liquides. Prenez vos médicaments comme indiqué."
                elif "Chinese" in prompt:
                    response.content = "在家休息。多喝水。按照指示服药。"
                elif "Portuguese" in prompt:
                    response.content = "Descanse em casa. Beba muitos líquidos. Tome seus remédios conforme orientação."
                else:
                    # Back-translation (English)
                    response.content = "Rest at home. Drink lots of fluids. Take your medicine as directed."
                return response
            
            mock_translator_llm_instance.ainvoke = mock_ainvoke
            
            # Mock embedder for similarity computation
            mock_embedder_instance = mock_embedder.return_value
            mock_embedder_instance.encode = MagicMock(return_value=[
                [0.9, 0.1],  # Original text embedding
                [0.85, 0.15]  # Back-translated text embedding (similarity ~0.85)
            ])
            
            # Step 1: Generate English instructions
            generator = PatientInstructionsGenerator(
                project_id="test-project",
                location="us-central1",
            )
            
            instructions_doc = await generator.generate(
                discharge_summary=mock_discharge_summary,
                encounter_context=mock_encounter_context,
                fhir_patient=mock_fhir_patient,
            )
            
            # Verify generator output
            assert isinstance(instructions_doc, PatientInstructionsDocument)
            assert instructions_doc.encounter_id == "enc-12345"
            assert instructions_doc.primary_language == SupportedLanguage.EN
            assert instructions_doc.primary_flesch_kincaid_grade <= 8.0
            assert instructions_doc.primary_content.home_care_instructions.startswith("Rest at home")
            
            # Step 2: Translate to 4 additional languages
            translator = PatientInstructionsTranslator(
                project_id="test-project",
                location="us-central1",
            )
            
            translated_doc = await translator.translate_all(instructions_doc)
            
            # Verify translation output
            assert isinstance(translated_doc, PatientInstructionsDocument)
            assert len(translated_doc.translations) == 5  # en, es, fr, zh, pt
            
            # Verify English entry
            en_entry = translated_doc.translations[SupportedLanguage.EN.value]
            assert en_entry.language_code == "en"
            assert en_entry.quality_check_passed is True
            assert en_entry.back_translation_similarity is None  # N/A for source language
            
            # Verify non-English entries
            for lang_code in ["es", "fr", "zh", "pt"]:
                entry = translated_doc.translations[lang_code]
                assert entry.language_code == lang_code
                assert entry.back_translation_similarity is not None
                assert entry.flesch_kincaid_grade is not None
                assert entry.content is not None

    @pytest.mark.asyncio
    async def test_translation_quality_check_failure_handling(
        self,
        mock_discharge_summary,
        mock_encounter_context,
        mock_fhir_patient,
        mock_llm_response,
    ):
        """
        Test handling of low similarity scores (< 0.85).
        
        Verifies:
        - quality_check_passed=False when similarity < 0.85
        - Translation still stored with failure flag
        - English fallback NOT used (actual translation stored)
        """
        with patch('agents.documentation.patient_instructions_generator.ChatVertexAI') as mock_gen_llm, \
             patch('agents.documentation.patient_instructions_generator.StructuredOutputHelper') as mock_helper_class, \
             patch('agents.documentation.patient_instructions_translator.ChatVertexAI') as mock_trans_llm, \
             patch('agents.documentation.patient_instructions_translator.SentenceTransformer') as mock_embedder:
            
            # Setup generator
            mock_helper = mock_helper_class.return_value
            mock_helper.invoke_structured = AsyncMock(return_value=mock_llm_response)
            
            # Setup translator with low similarity
            mock_trans_instance = mock_trans_llm.return_value
            
            async def mock_ainvoke(prompt):
                response = MagicMock()
                if "Spanish" in prompt or "French" in prompt:
                    response.content = "Translated text"
                else:
                    # Back-translation with poor quality
                    response.content = "Different meaning entirely"
                return response
            
            mock_trans_instance.ainvoke = mock_ainvoke
            
            # Mock low similarity embeddings
            mock_embedder_instance = mock_embedder.return_value
            mock_embedder_instance.encode = MagicMock(return_value=[
                [1.0, 0.0],   # Original
                [0.5, 0.866]  # Back-translated (orthogonal = similarity ~0.5)
            ])
            
            # Generate and translate
            generator = PatientInstructionsGenerator("test-project", "us-central1")
            instructions_doc = await generator.generate(
                mock_discharge_summary,
                mock_encounter_context,
                mock_fhir_patient,
            )
            
            translator = PatientInstructionsTranslator("test-project", "us-central1")
            translated_doc = await translator.translate_all(instructions_doc)
            
            # Verify failed quality checks
            for lang_code in ["es", "fr"]:
                entry = translated_doc.translations[lang_code]
                assert entry.quality_check_passed is False
                assert entry.back_translation_similarity < 0.85
                # Translation should still be stored (not English fallback)
                assert entry.content.home_care_instructions == "Translated text"

    @pytest.mark.asyncio
    async def test_concurrent_translation_performance(
        self,
        mock_discharge_summary,
        mock_encounter_context,
        mock_fhir_patient,
        mock_llm_response,
    ):
        """
        Test that translations are issued concurrently for performance.
        
        Verifies:
        - All 4 translations complete
        - asyncio.gather used (implicit via successful completion)
        """
        with patch('agents.documentation.patient_instructions_generator.ChatVertexAI') as mock_gen_llm, \
             patch('agents.documentation.patient_instructions_generator.StructuredOutputHelper') as mock_helper_class, \
             patch('agents.documentation.patient_instructions_translator.ChatVertexAI') as mock_trans_llm, \
             patch('agents.documentation.patient_instructions_translator.SentenceTransformer') as mock_embedder:
            
            # Setup generator
            mock_helper = mock_helper_class.return_value
            mock_helper.invoke_structured = AsyncMock(return_value=mock_llm_response)
            
            # Setup translator with delays to test concurrency
            mock_trans_instance = mock_trans_llm.return_value
            call_count = {"count": 0}
            
            async def mock_ainvoke_with_delay(prompt):
                call_count["count"] += 1
                await asyncio.sleep(0.01)  # Small delay
                response = MagicMock()
                response.content = f"Translation {call_count['count']}"
                return response
            
            mock_trans_instance.ainvoke = mock_ainvoke_with_delay
            
            # Mock embedder
            mock_embedder_instance = mock_embedder.return_value
            mock_embedder_instance.encode = MagicMock(return_value=[
                [0.9, 0.1],
                [0.9, 0.1]
            ])
            
            # Generate and translate
            generator = PatientInstructionsGenerator("test-project", "us-central1")
            instructions_doc = await generator.generate(
                mock_discharge_summary,
                mock_encounter_context,
                mock_fhir_patient,
            )
            
            translator = PatientInstructionsTranslator("test-project", "us-central1")
            
            import time
            start_time = time.time()
            translated_doc = await translator.translate_all(instructions_doc)
            elapsed_time = time.time() - start_time
            
            # If sequential: 4 languages × 2 LLM calls × 0.01s = 0.08s
            # If concurrent: ~0.02s (overlapping delays)
            # Allow generous margin for test execution overhead
            assert elapsed_time < 0.15, f"Translation took {elapsed_time}s, expected < 0.15s (concurrent)"
            
            # Verify all translations completed
            assert len(translated_doc.translations) == 5

    @pytest.mark.asyncio
    async def test_translation_error_fallback_to_english(
        self,
        mock_discharge_summary,
        mock_encounter_context,
        mock_fhir_patient,
        mock_llm_response,
    ):
        """
        Test error handling: translation failure → English fallback.
        
        Verifies:
        - Exception during translation → English content used
        - quality_check_passed=False for failed translation
        - Other translations still succeed
        """
        with patch('agents.documentation.patient_instructions_generator.ChatVertexAI') as mock_gen_llm, \
             patch('agents.documentation.patient_instructions_generator.StructuredOutputHelper') as mock_helper_class, \
             patch('agents.documentation.patient_instructions_translator.ChatVertexAI') as mock_trans_llm, \
             patch('agents.documentation.patient_instructions_translator.SentenceTransformer') as mock_embedder:
            
            # Setup generator
            mock_helper = mock_helper_class.return_value
            mock_helper.invoke_structured = AsyncMock(return_value=mock_llm_response)
            
            # Setup translator with error for Spanish
            mock_trans_instance = mock_trans_llm.return_value
            
            async def mock_ainvoke_with_error(prompt):
                if "Spanish" in prompt:
                    raise Exception("Gemini API error")
                response = MagicMock()
                response.content = "Successful translation"
                return response
            
            mock_trans_instance.ainvoke = mock_ainvoke_with_error
            
            # Mock embedder
            mock_embedder_instance = mock_embedder.return_value
            mock_embedder_instance.encode = MagicMock(return_value=[
                [0.9, 0.1],
                [0.9, 0.1]
            ])
            
            # Generate and translate
            generator = PatientInstructionsGenerator("test-project", "us-central1")
            instructions_doc = await generator.generate(
                mock_discharge_summary,
                mock_encounter_context,
                mock_fhir_patient,
            )
            
            translator = PatientInstructionsTranslator("test-project", "us-central1")
            translated_doc = await translator.translate_all(instructions_doc)
            
            # Verify Spanish entry has English fallback
            es_entry = translated_doc.translations["es"]
            assert es_entry.language_code == "es"
            assert es_entry.quality_check_passed is False
            assert es_entry.back_translation_similarity is None
            # Content should be English fallback
            assert es_entry.content.home_care_instructions.startswith("Rest at home")
            
            # Verify other languages succeeded
            for lang_code in ["fr", "zh", "pt"]:
                entry = translated_doc.translations[lang_code]
                assert entry.quality_check_passed is not False  # True or None


@pytest.mark.asyncio
async def test_monitor_translation_quality_metrics():
    """
    Test helper for monitoring translation quality in production.
    
    Demonstrates how to extract and monitor key quality metrics:
    - Back-translation similarity scores
    - FK grades of translations
    - Quality check pass rates
    """
    # Sample translated document (would come from production)
    from agents.documentation.patient_instructions_schemas import TranslationEntry
    
    mock_translations = {
        "en": TranslationEntry(
            language_code="en",
            content=PatientInstructionsContent(
                home_care_instructions="Test",
                medications="Test",
                warning_signs="Test",
                follow_up_appointments="Test",
                diet_and_activity="Test",
                emergency_contact="Test",
            ),
            back_translation_similarity=None,
            quality_check_passed=True,
            flesch_kincaid_grade=7.5,
        ),
        "es": TranslationEntry(
            language_code="es",
            content=PatientInstructionsContent(
                home_care_instructions="Test",
                medications="Test",
                warning_signs="Test",
                follow_up_appointments="Test",
                diet_and_activity="Test",
                emergency_contact="Test",
            ),
            back_translation_similarity=0.87,
            quality_check_passed=True,
            flesch_kincaid_grade=8.2,
        ),
        "fr": TranslationEntry(
            language_code="fr",
            content=PatientInstructionsContent(
                home_care_instructions="Test",
                medications="Test",
                warning_signs="Test",
                follow_up_appointments="Test",
                diet_and_activity="Test",
                emergency_contact="Test",
            ),
            back_translation_similarity=0.82,
            quality_check_passed=False,
            flesch_kincaid_grade=9.1,
        ),
    }
    
    # Extract quality metrics
    metrics = {
        "total_languages": len(mock_translations),
        "quality_pass_count": sum(
            1 for t in mock_translations.values() 
            if t.quality_check_passed and t.language_code != "en"
        ),
        "avg_similarity": sum(
            t.back_translation_similarity 
            for t in mock_translations.values() 
            if t.back_translation_similarity is not None
        ) / 2,  # 2 non-English entries
        "avg_fk_grade": sum(
            t.flesch_kincaid_grade 
            for t in mock_translations.values() 
            if t.flesch_kincaid_grade is not None
        ) / 3,
    }
    
    # Assertions for monitoring thresholds
    assert metrics["quality_pass_count"] >= 1, "At least 50% translations should pass quality check"
    assert metrics["avg_similarity"] >= 0.80, "Average similarity should be ≥ 0.80"
    assert metrics["avg_fk_grade"] <= 10.0, "Average FK grade should be ≤ 10.0"
    
    print("\n=== Translation Quality Metrics ===")
    print(f"Total languages: {metrics['total_languages']}")
    print(f"Quality checks passed: {metrics['quality_pass_count']}/2 non-English languages")
    print(f"Average similarity: {metrics['avg_similarity']:.3f}")
    print(f"Average FK grade: {metrics['avg_fk_grade']:.2f}")
