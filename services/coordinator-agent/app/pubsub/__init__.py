"""Pub/Sub sub-package — ADT subscription consumer for coordinator agent.

Exports:
  ADTSubscriber — async-capable Pub/Sub pull subscriber with FlowControl,
                  graceful shutdown, and ACK/NACK lifecycle management.

Design refs:
    ADR-001  — event-driven architecture: agents as independent Pub/Sub consumers
    TR-005   — ADT event throughput ≥5,000 events/day
    TR-015   — zero message loss: nack on shutdown for redelivery
    TR-017   — graceful shutdown: drain in-flight, exit within 30 s
"""
from app.pubsub.adt_subscriber import ADTSubscriber

__all__ = ["ADTSubscriber"]
