"""
Unit tests for DocumentationAgent.

Tests the core agent orchestration logic: FHIR fetch → prompt render → 
Gemini 1.5 Pro call → Document DB write.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from agents.documentation.agent import DocumentationAgent
from agents.documentation.schemas import DischargeSummarySchema, GenerationType


MOCK_EVENT_A03 = {
    "event_type": "A03",
    "encounter_id": "ENC-001",
    "occurred_at": "2026-07-14T10:00:00Z",
}

MOCK_SUMMARY = DischargeSummarySchema(
    encounter_id="ENC-001",
    diagnosis_summary=[{"icd10_code": "E11.9", "description": "Type 2 diabetes", "is_primary": True}],
    procedures=[],
    medications_at_discharge=[{"drug_name": "metformin", "dose": "500 mg", "frequency": "twice daily", "route": "oral"}],
    follow_up_instructions=[{"instruction": "Follow up with PCP within 7 days"}],
    warning_signs=["Shortness of breath"],
    activity_restrictions=["No heavy lifting"],
)


@pytest.fixture
def mock_fhir_client():
    """Mock FHIR client."""
    return MagicMock()


@pytest.fixture
def mock_doc_repo():
    """Mock DocumentRepository."""
    repo = MagicMock()
    repo.create_discharge_document = AsyncMock()
    return repo


@pytest.fixture
def agent(mock_fhir_client, mock_doc_repo):
    """Create a DocumentationAgent with mocked dependencies."""
    with patch("agents.documentation.agent.ChatVertexAI"):
        doc_agent = DocumentationAgent(
            fhir_client=mock_fhir_client,
            document_repository=mock_doc_repo,
            project_id="test-project",
        )
        # Mock the chain to return our test summary
        doc_agent._chain = AsyncMock(return_value=MOCK_SUMMARY)
        # Mock the fetcher
        doc_agent._fetcher.fetch = AsyncMock(return_value=MagicMock(encounter_id="ENC-001"))
        # Mock the renderer
        doc_agent._renderer.render_discharge_summary = MagicMock(return_value="rendered prompt")
        return doc_agent


def test_can_handle_a03(agent):
    """Test that agent handles A03 (discharge) events."""
    assert agent.can_handle("A03") is True


def test_can_handle_a02(agent):
    """Test that agent handles A02 (transfer) events."""
    assert agent.can_handle("A02") is True


def test_cannot_handle_a01(agent):
    """Test that agent does not handle A01 (admission) events."""
    assert agent.can_handle("A01") is False


@pytest.mark.asyncio
async def test_process_creates_document(agent, mock_doc_repo):
    """Test that process() orchestrates all steps and creates a document."""
    await agent.process(MOCK_EVENT_A03)
    
    # Verify DocumentRepository.create_discharge_document was called
    mock_doc_repo.create_discharge_document.assert_awaited_once()
    
    # Verify the call arguments
    call_kwargs = mock_doc_repo.create_discharge_document.call_args.kwargs
    assert call_kwargs["encounter_id"] == "ENC-001"
    assert call_kwargs["summary"].generation_type == GenerationType.AI
