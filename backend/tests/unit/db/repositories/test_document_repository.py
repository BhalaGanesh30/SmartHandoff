"""Unit tests for DocumentRepository.create_discharge_document().

Tests cover US-025 acceptance criteria:
- Document created with status=PENDING_APPROVAL
- generation_type persisted correctly (AI or TEMPLATE)
- SignalR notification sent after commit
- Content encrypted via EncryptedText
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from app.db.repositories.document_repository import DocumentRepository
from agents.documentation.schemas import (
    DischargeSummarySchema,
    GenerationType,
    DiagnosisEntry,
    MedicationEntry,
    FollowUpInstruction,
)


# Minimal valid discharge summary for testing
MINIMAL_SUMMARY = DischargeSummarySchema(
    encounter_id="ENC-001",
    diagnosis_summary=[
        DiagnosisEntry(
            icd10_code="E11.9",
            description="Type 2 diabetes",
            is_primary=True,
        )
    ],
    medications_at_discharge=[
        MedicationEntry(
            drug_name="metformin",
            dose="500 mg",
            frequency="twice daily",
            route="oral",
        )
    ],
    follow_up_instructions=[
        FollowUpInstruction(
            instruction="Follow up with PCP within 7 days"
        )
    ],
    warning_signs=["Shortness of breath"],
    activity_restrictions=["No heavy lifting"],
    generation_type=GenerationType.AI,
)


@pytest.fixture
def mock_session():
    """Mock SQLAlchemy AsyncSession."""
    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_signalr():
    """Mock SignalR hub client."""
    client = MagicMock()
    client.send_to_group = AsyncMock()
    return client


@pytest.fixture
def repo(mock_session, mock_signalr):
    """DocumentRepository instance with mocked dependencies."""
    return DocumentRepository(session=mock_session, signalr_hub=mock_signalr)


@pytest.mark.asyncio
async def test_create_discharge_document_sets_pending_approval(repo, mock_session):
    """US-025 AC Scenario 1: Document created with status=PENDING_APPROVAL."""
    await repo.create_discharge_document("ENC-001", MINIMAL_SUMMARY)
    
    # Verify Document was added to session
    assert mock_session.add.called
    added_doc = mock_session.add.call_args[0][0]
    assert added_doc.status == "pending_approval"


@pytest.mark.asyncio
async def test_create_discharge_document_sets_generation_type_ai(repo, mock_session):
    """US-025 AC Scenario 1: generation_type=AI persisted for AI-generated documents."""
    await repo.create_discharge_document("ENC-001", MINIMAL_SUMMARY)
    
    added_doc = mock_session.add.call_args[0][0]
    assert added_doc.generation_type == "AI"


@pytest.mark.asyncio
async def test_create_discharge_document_template_sets_generation_type_template(repo, mock_session):
    """US-025 AC Scenario 2: generation_type=TEMPLATE persisted for fallback documents."""
    template_summary = MINIMAL_SUMMARY.model_copy(
        update={"generation_type": GenerationType.TEMPLATE}
    )
    await repo.create_discharge_document("ENC-001", template_summary)
    
    added_doc = mock_session.add.call_args[0][0]
    assert added_doc.generation_type == "TEMPLATE"


@pytest.mark.asyncio
async def test_create_discharge_document_sets_document_type(repo, mock_session):
    """Verify document_type is set to 'discharge_summary'."""
    await repo.create_discharge_document("ENC-001", MINIMAL_SUMMARY)
    
    added_doc = mock_session.add.call_args[0][0]
    assert added_doc.document_type == "discharge_summary"


@pytest.mark.asyncio
async def test_create_discharge_document_encrypts_content(repo, mock_session):
    """Verify content is stored as JSON string (EncryptedText handles encryption at ORM layer)."""
    await repo.create_discharge_document("ENC-001", MINIMAL_SUMMARY)
    
    added_doc = mock_session.add.call_args[0][0]
    # Content should be a JSON string
    assert isinstance(added_doc.content, str)
    assert "E11.9" in added_doc.content  # ICD-10 code should be in the JSON


@pytest.mark.asyncio
async def test_signalr_push_sent_after_commit(repo, mock_signalr):
    """US-025 DoD: SignalR push sent to encounter group after commit."""
    await repo.create_discharge_document("ENC-001", MINIMAL_SUMMARY)
    
    # Verify SignalR notification was sent
    mock_signalr.send_to_group.assert_awaited_once()
    call_kwargs = mock_signalr.send_to_group.call_args.kwargs
    
    assert call_kwargs["group"] == "encounter-ENC-001"
    assert call_kwargs["event"] == "DocumentReady"
    assert call_kwargs["payload"]["document_type"] == "discharge_summary"
    assert call_kwargs["payload"]["status"] == "pending_approval"
    assert call_kwargs["payload"]["generation_type"] == "AI"


@pytest.mark.asyncio
async def test_signalr_push_includes_document_id(repo, mock_session, mock_signalr):
    """Verify SignalR payload includes document_id."""
    # Mock the document ID that would be generated
    mock_doc_id = uuid4()
    
    async def mock_refresh(doc):
        doc.id = mock_doc_id
    
    mock_session.refresh = AsyncMock(side_effect=mock_refresh)
    
    await repo.create_discharge_document("ENC-001", MINIMAL_SUMMARY)
    
    call_kwargs = mock_signalr.send_to_group.call_args.kwargs
    assert "document_id" in call_kwargs["payload"]


@pytest.mark.asyncio
async def test_create_discharge_document_commits_session(repo, mock_session):
    """Verify session.commit() is called."""
    await repo.create_discharge_document("ENC-001", MINIMAL_SUMMARY)
    
    mock_session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_discharge_document_refreshes_document(repo, mock_session):
    """Verify session.refresh() is called to get generated ID."""
    await repo.create_discharge_document("ENC-001", MINIMAL_SUMMARY)
    
    mock_session.refresh.assert_awaited_once()
    # Verify the refreshed object is the document that was added
    refreshed_doc = mock_session.refresh.call_args[0][0]
    added_doc = mock_session.add.call_args[0][0]
    assert refreshed_doc is added_doc
