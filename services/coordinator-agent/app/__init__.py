"""Coordinator Agent application package.

The Coordinator Agent is responsible for consuming ADT events from Pub/Sub,
creating AgentTask records, and dispatching tasks to downstream specialist agents.

Package structure:
    pubsub/      — Pub/Sub subscription consumer (ADT events)
    coordinator/ — Core coordination logic and task mapping
    models/      — Domain models and database schemas
"""
