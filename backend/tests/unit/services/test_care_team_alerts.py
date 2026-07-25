"""Unit tests for CareTeamAlertService."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from app.services.care_team_alerts import CareTeamAlertService
from app.models.patient import PatientResolutionStatus
from app.models.encounter import Encounter


@pytest.fixture
def mock_pubsub_publisher():
    """Mock GCP Pub/Sub publisher."""
    publisher = MagicMock()
    future = MagicMock()
    future.result.return_value = "message-id-123"
    publisher.publish.return_value = future
    return publisher


@pytest.fixture
def alert_service(mock_pubsub_publisher):
    """CareTeamAlertService with mocked publisher."""
    return CareTeamAlertService(publisher=mock_pubsub_publisher)


@pytest.fixture
def sample_encounter():
    """Sample encounter instance."""
    encounter = Encounter()
    encounter.id = "enc-001"
    return encounter


@pytest.mark.asyncio
async def test_send_ambiguous_alert_payload(
    alert_service,
    mock_pubsub_publisher,
    sample_encounter
):
    """Test AMBIGUOUS alert has correct payload structure."""
    await alert_service.send_patient_resolution_alert(
        encounter=sample_encounter,
        status=PatientResolutionStatus.AMBIGUOUS,
        metadata={
            "mrn": "MRN-789",
            "name": {"family": "Smith", "given": "John"},
            "dob": "1980-01-15",
            "match_count": 3
        }
    )
    
    # Verify publish called
    assert mock_pubsub_publisher.publish.called
    call_args = mock_pubsub_publisher.publish.call_args
    
    # Verify payload structure
    payload_str = call_args[1]["data"].decode("utf-8")
    payload = json.loads(payload_str)
    
    assert payload["type"] == "PATIENT_RESOLUTION_ALERT"
    assert payload["status"] == "AMBIGUOUS"
    assert payload["encounter_id"] == "enc-001"
    assert payload["match_count"] == 3
    assert "3" in payload["message"] or "multiple" in payload["message"]


@pytest.mark.asyncio
async def test_send_unresolved_alert_payload(
    alert_service,
    mock_pubsub_publisher,
    sample_encounter
):
    """Test UNRESOLVED alert has correct payload structure."""
    await alert_service.send_patient_resolution_alert(
        encounter=sample_encounter,
        status=PatientResolutionStatus.UNRESOLVED,
        metadata={
            "mrn": "MRN-UNKNOWN",
            "name": {"family": "Unknown", "given": "Patient"},
            "dob": "2000-01-01"
        }
    )
    
    call_args = mock_pubsub_publisher.publish.call_args
    payload_str = call_args[1]["data"].decode("utf-8")
    payload = json.loads(payload_str)
    
    assert payload["status"] == "UNRESOLVED"
    assert payload["mrn"] == "MRN-UNKNOWN"
    assert "not found" in payload["message"].lower() or "manual lookup" in payload["message"].lower()


@pytest.mark.asyncio
async def test_alert_pubsub_topic_and_attributes(
    alert_service,
    mock_pubsub_publisher,
    sample_encounter
):
    """Test alert published to correct Pub/Sub topic with attributes."""
    await alert_service.send_patient_resolution_alert(
        encounter=sample_encounter,
        status=PatientResolutionStatus.AMBIGUOUS,
        metadata={"mrn": "MRN-789", "name": {}, "dob": "", "match_count": 3}
    )
    
    # Verify topic path
    topic_path = mock_pubsub_publisher.publish.call_args[0][0]
    assert "notification-requests" in topic_path
    
    # Verify message attributes
    call_kwargs = mock_pubsub_publisher.publish.call_args[1]
    assert call_kwargs["type"] == "PATIENT_RESOLUTION_ALERT"
    assert call_kwargs["priority"] == "HIGH"
    assert call_kwargs["encounter_id"] == "enc-001"


@pytest.mark.asyncio
async def test_alert_dispatch_failure_non_blocking(
    alert_service,
    mock_pubsub_publisher,
    sample_encounter
):
    """Test alert dispatch failure logs error but doesn't raise."""
    mock_pubsub_publisher.publish.side_effect = Exception("Pub/Sub timeout")
    
    with patch('app.services.care_team_alerts.logger') as mock_logger:
        # Should not raise exception
        await alert_service.send_patient_resolution_alert(
            encounter=sample_encounter,
            status=PatientResolutionStatus.AMBIGUOUS,
            metadata={"mrn": "MRN-789", "name": {}, "dob": "", "match_count": 3}
        )
        
        # Verify error logged
        mock_logger.error.assert_called_once()
        error_msg = mock_logger.error.call_args[0][0]
        assert "Failed to dispatch care team alert" in error_msg
        assert "enc-001" in error_msg
