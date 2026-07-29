"""Google Cloud Pub/Sub integration for asynchronous event publishing.

Design refs:
    ADR-001 — all domain events published to GCP Pub/Sub before side-effects
    TR-005  — async Pub/Sub publish confirmed before DB commit
"""
from app.core.pubsub.publisher import publish_message

__all__ = ["publish_message"]
