"""Cloud Run entrypoint for the Follow-up Care Agent service.

Wires together:
    - FollowUpCareAgent (this task)
    - CareEscalationMonitor (US-042 TASK-002)
    - ReEscalationJob (US-042 TASK-003)
    - BaseAgent Pub/Sub pull loop (US-024)
    - FHIRClient (US-017)
    - DB session factories (write → primary; read → replica)

Design refs:
    US-039 TASK-004 — FollowUpCareAgent implementation
    US-042 TASK-002 — CareEscalationMonitor implementation
    US-042 TASK-003 — ReEscalationJob APScheduler job
    design.md §9.2 — followup-agent Cloud Run configuration
"""
import asyncio
import logging
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from google.cloud import pubsub_v1

from app.agents.followup_care.agent import FollowUpCareAgent
from app.agents.followup_care.escalation.monitor import CareEscalationMonitor
from app.agents.followup_care.escalation.reescalation_job import ReEscalationJob
from app.agents.followup_care.notification_publisher import NotificationPublisher
from app.config.care_pathways import load_care_pathways
from app.core.config import get_settings
from app.core.dependencies import get_read_db, get_write_db
from app.core.fhir_client import FHIRClient
from app.services.care_pathway_service import CarePathwayService

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))


async def main() -> None:
    """Initialize and run the FollowUpCareAgent service."""
    settings = get_settings()
    
    # Initialize FHIR client (US-017)
    fhir_client = FHIRClient(
        base_url=os.environ["FHIR_BASE_URL"],
        client_id=os.environ["FHIR_CLIENT_ID"],
        client_secret=os.environ["FHIR_CLIENT_SECRET"],
    )
    
    # Load care pathway configuration (US-040/TASK-002)
    care_pathway_config = load_care_pathways()
    
    # Initialize care pathway service (US-040/TASK-003)
    care_pathway_service = CarePathwayService(pathways=care_pathway_config)
    
    # Initialize notification publisher (US-040/TASK-004)
    notification_publisher = NotificationPublisher(
        project_id=os.environ.get("GCP_PROJECT_ID", "smarthandoff-dev"),
        topic_id=os.environ.get("NOTIFICATION_REQUESTS_TOPIC", "notification-requests"),
    )
    
    # Initialize agent with all dependencies
    agent = FollowUpCareAgent(
        db_session_factory=get_write_db,
        read_session_factory=get_read_db,
        fhir_client=fhir_client,
        care_pathway_service=care_pathway_service,
        notification_publisher=notification_publisher,
        care_pathway_config=care_pathway_config,
    )
    
    # Initialize Pub/Sub publisher for escalation notifications (US-042)
    publisher = pubsub_v1.PublisherClient()
    
    # Initialize escalation monitor (US-042 TASK-002)
    escalation_monitor = CareEscalationMonitor(
        session_factory=get_write_db(),
        publisher=publisher,
        notification_topic=settings.NOTIFICATION_REQUESTS_TOPIC,
    )
    
    # Initialize Pub/Sub subscriber for urgency escalation events (US-042)
    subscriber = pubsub_v1.SubscriberClient()
    urgency_subscription_path = settings.URGENCY_ESCALATION_SUBSCRIPTION
    
    # Register the escalation monitor callback
    urgency_future = subscriber.subscribe(
        urgency_subscription_path,
        callback=lambda message: asyncio.create_task(
            escalation_monitor.handle_urgency_flag_set(message)
        ),
    )
    
    # Initialize APScheduler for periodic jobs (US-042 TASK-003)
    scheduler = AsyncIOScheduler()
    
    # Initialize re-escalation job (US-042 TASK-003)
    reescalation_job = ReEscalationJob(
        session_factory=get_write_db(),
        publisher=publisher,
        notification_topic=settings.NOTIFICATION_REQUESTS_TOPIC,
    )
    
    # Register re-escalation job: runs every 60 seconds
    scheduler.add_job(
        reescalation_job.run,
        trigger="interval",
        seconds=60,
        id="care_escalation_reescalation_monitor",
        replace_existing=True,
        misfire_grace_time=30,  # Allow up to 30s of scheduler drift
    )
    
    # Start the scheduler
    scheduler.start()
    
    logging.info(
        "followup_care_agent.started",
        extra={
            "urgency_subscription": urgency_subscription_path,
            "notification_topic": settings.NOTIFICATION_REQUESTS_TOPIC,
            "scheduler_jobs": ["care_escalation_reescalation_monitor"],
        },
    )
    
    # Run both the agent and the escalation monitor concurrently
    try:
        await asyncio.gather(
            agent.run(),  # BaseAgent pull loop — blocks until shutdown signal
            asyncio.to_thread(urgency_future.result),  # Block on subscriber future
        )
    except KeyboardInterrupt:
        logging.info("followup_care_agent.shutdown_requested")
        scheduler.shutdown(wait=True)
        urgency_future.cancel()


if __name__ == "__main__":
    asyncio.run(main())
