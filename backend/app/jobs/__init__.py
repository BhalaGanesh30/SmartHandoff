"""Cloud Run Job entry points for scheduled background tasks.

Each module in this package provides a standalone Python script that can be
executed as a Cloud Run Job triggered by Cloud Scheduler.

Design refs:
    ADR-002 — Cloud Run stateless jobs for batch processing
    TR-011  — Cloud Scheduler cron triggers
"""
