"""SQLAlchemy declarative base for notification-service ORM models.

Mirrors backend/app/db/base.py — each Cloud Run service owns its
own metadata to avoid cross-service schema coupling.
"""
from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Notification-service declarative base."""
    pass
