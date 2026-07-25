"""
Unit tests for TemplateFallbackRenderer.

Tests cover:
- Fallback renders without exception (never raises)
- generation_type=TEMPLATE set correctly
- All mandatory sections populated
- FHIR data mapping (diagnoses, medications)
- Default section generation (follow-up, warning signs, activity restrictions)
- Integration test with agent timeout simulation
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.documentation.fallback_renderer import TemplateFallbackRenderer
from agents.documentation.fhir_fetcher import (
    DiagnosisContext,
    EncounterContext,
    MedicationContext,
)
from agents.documentation.schemas import GenerationType


@pytest.fixture
def sample_context():
    """Sample EncounterContext with diagnoses and medications."""
    return EncounterContext(
        encounter_id="ENC-001",
        admission_reason="Diabetes management",
        encounter_type="inpatient",
        discharge_disposition="Home",
        length_of_stay_days=3,
        diagnoses=[
            DiagnosisContext(
                icd10_code="E11.9",
                description="Type 2 diabetes mellitus without complications",
                is_primary=True,
            )
        ],
        medications=[
            MedicationContext(
                drug_name="metformin",
                dose="500 mg",
                frequency="twice daily",
                route="oral",
                rxnorm_code="6809",
            )
        ],
        procedures_performed=["Blood glucose monitoring", "Patient education"],
    )


@pytest.fixture
def minimal_context():
    """Minimal EncounterContext with no diagnoses/medications."""
    return EncounterContext(
        encounter_id="ENC-002",
        admission_reason="Observation",
        encounter_type="observation",
        discharge_disposition="Home",
        length_of_stay_days=1,
        diagnoses=[],
        medications=[],
        procedures_performed=[],
    )


def test_fallback_renders_without_exception(sample_context):
    """Fallback renderer never raises an exception."""
    renderer = TemplateFallbackRenderer()
    result = renderer.render(sample_context)
    assert result is not None


def test_fallback_generation_type_is_template(sample_context):
    """Verify generation_type=TEMPLATE is set correctly."""
    renderer = TemplateFallbackRenderer()
    result = renderer.render(sample_context)
    assert result.generation_type == GenerationType.TEMPLATE


def test_fallback_all_mandatory_sections_populated(sample_context):
    """All six mandatory sections must be populated."""
    renderer = TemplateFallbackRenderer()
    result = renderer.render(sample_context)
    
    assert len(result.diagnosis_summary) >= 1
    assert len(result.medications_at_discharge) >= 1
    assert len(result.follow_up_instructions) >= 1
    assert len(result.warning_signs) >= 1
    assert len(result.activity_restrictions) >= 1
    # procedures can be empty list but must exist
    assert result.procedures is not None


def test_fallback_maps_fhir_diagnoses(sample_context):
    """FHIR diagnoses are mapped correctly."""
    renderer = TemplateFallbackRenderer()
    result = renderer.render(sample_context)
    
    assert result.diagnosis_summary[0].icd10_code == "E11.9"
    assert "Type 2 diabetes" in result.diagnosis_summary[0].description
    assert result.diagnosis_summary[0].is_primary is True


def test_fallback_maps_fhir_medications(sample_context):
    """FHIR medications are mapped correctly."""
    renderer = TemplateFallbackRenderer()
    result = renderer.render(sample_context)
    
    assert result.medications_at_discharge[0].drug_name == "metformin"
    assert result.medications_at_discharge[0].dose == "500 mg"
    assert result.medications_at_discharge[0].frequency == "twice daily"
    assert result.medications_at_discharge[0].route == "oral"
    assert result.medications_at_discharge[0].rxnorm_code == "6809"


def test_fallback_provides_default_diagnosis_when_empty(minimal_context):
    """When no diagnoses, provide safe default."""
    renderer = TemplateFallbackRenderer()
    result = renderer.render(minimal_context)
    
    assert len(result.diagnosis_summary) == 1
    assert result.diagnosis_summary[0].icd10_code == "Z99.89"
    assert "to be completed by physician" in result.diagnosis_summary[0].description


def test_fallback_provides_default_medication_when_empty(minimal_context):
    """When no medications, provide safe default."""
    renderer = TemplateFallbackRenderer()
    result = renderer.render(minimal_context)
    
    assert len(result.medications_at_discharge) == 1
    assert result.medications_at_discharge[0].drug_name == "As prescribed"


def test_fallback_generates_default_follow_up(sample_context):
    """Default follow-up instructions are generated."""
    renderer = TemplateFallbackRenderer()
    result = renderer.render(sample_context)
    
    assert len(result.follow_up_instructions) >= 1
    assert any("primary care physician" in inst.instruction.lower() 
              for inst in result.follow_up_instructions)


def test_fallback_generates_default_warning_signs(sample_context):
    """Default warning signs are generated."""
    renderer = TemplateFallbackRenderer()
    result = renderer.render(sample_context)
    
    assert len(result.warning_signs) >= 1
    assert any("911" in sign or "emergency" in sign.lower() 
              for sign in result.warning_signs)


def test_fallback_activity_restrictions_vary_by_los(sample_context, minimal_context):
    """Activity restrictions vary based on length of stay."""
    renderer = TemplateFallbackRenderer()
    
    # Long stay (≥3 days) should have more restrictive guidance
    result_long = renderer.render(sample_context)  # LOS=3
    assert any("rest" in restriction.lower() or "avoid strenuous" in restriction.lower()
              for restriction in result_long.activity_restrictions)
    
    # Short stay (<3 days) should have lighter restrictions
    result_short = renderer.render(minimal_context)  # LOS=1
    assert any("resume normal activities" in restriction.lower()
              for restriction in result_short.activity_restrictions)


def test_fallback_maps_procedures(sample_context):
    """FHIR procedures are mapped correctly."""
    renderer = TemplateFallbackRenderer()
    result = renderer.render(sample_context)
    
    assert len(result.procedures) == 2
    assert result.procedures[0].description == "Blood glucose monitoring"
    assert result.procedures[1].description == "Patient education"


@pytest.mark.asyncio
async def test_agent_activates_fallback_on_timeout():
    """Integration: agent falls back when chain.ainvoke times out."""
    from agents.documentation.agent import DocumentationAgent
    
    # Mock dependencies
    mock_fhir_client = MagicMock()
    mock_doc_repo = MagicMock()
    mock_doc_repo.create_discharge_document = AsyncMock()
    
    async def slow_invoke(_):
        """Simulate a 30-second timeout."""
        await asyncio.sleep(30)
    
    with patch("agents.documentation.agent.ChatVertexAI"):
        agent = DocumentationAgent(
            fhir_client=mock_fhir_client,
            document_repository=mock_doc_repo,
            project_id="test-project",
        )
        
        # Mock the chain to timeout
        agent._chain = MagicMock()
        agent._chain.ainvoke = slow_invoke
        
        # Mock the fetcher to return sample data
        agent._fetcher.fetch = AsyncMock(
            return_value=EncounterContext(
                encounter_id="ENC-001",
                admission_reason="Test",
                encounter_type="inpatient",
                discharge_disposition=None,
                length_of_stay_days=1,
                diagnoses=[
                    DiagnosisContext("E11.9", "Type 2 diabetes", True)
                ],
                medications=[
                    MedicationContext("metformin", "500 mg", "twice daily", "oral")
                ],
            )
        )
        
        # Mock the prompt renderer
        agent._renderer.render_discharge_summary = MagicMock(return_value="prompt text")
        
        # Process event - should trigger timeout and fallback
        await agent.process({
            "event_type": "A03",
            "encounter_id": "ENC-001",
            "occurred_at": "2026-07-14T10:00:00Z",
        })
    
    # Verify fallback was used
    call_kwargs = mock_doc_repo.create_discharge_document.call_args.kwargs
    assert call_kwargs["summary"].generation_type == GenerationType.TEMPLATE


@pytest.mark.asyncio
async def test_agent_activates_fallback_on_llm_error():
    """Integration: agent falls back when LLM raises an exception."""
    from agents.documentation.agent import DocumentationAgent
    
    mock_fhir_client = MagicMock()
    mock_doc_repo = MagicMock()
    mock_doc_repo.create_discharge_document = AsyncMock()
    
    async def failing_invoke(_):
        """Simulate an LLM error."""
        raise RuntimeError("Gemini API error")
    
    with patch("agents.documentation.agent.ChatVertexAI"):
        agent = DocumentationAgent(
            fhir_client=mock_fhir_client,
            document_repository=mock_doc_repo,
            project_id="test-project",
        )
        
        agent._chain = MagicMock()
        agent._chain.ainvoke = failing_invoke
        
        agent._fetcher.fetch = AsyncMock(
            return_value=EncounterContext(
                encounter_id="ENC-002",
                admission_reason="Test error handling",
                encounter_type="inpatient",
                discharge_disposition=None,
                length_of_stay_days=2,
                diagnoses=[DiagnosisContext("Z99.89", "Other specified health status", False)],
                medications=[MedicationContext("aspirin", "81 mg", "daily", "oral")],
            )
        )
        
        agent._renderer.render_discharge_summary = MagicMock(return_value="prompt text")
        
        # Process event - should trigger error and fallback
        await agent.process({
            "event_type": "A03",
            "encounter_id": "ENC-002",
            "occurred_at": "2026-07-14T11:00:00Z",
        })
    
    # Verify fallback was used
    call_kwargs = mock_doc_repo.create_discharge_document.call_args.kwargs
    assert call_kwargs["summary"].generation_type == GenerationType.TEMPLATE
