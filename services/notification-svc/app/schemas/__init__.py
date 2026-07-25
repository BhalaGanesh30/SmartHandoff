"""Pydantic schemas for the notification service.

This module exports:
- NotificationRequest schemas for Pub/Sub message validation
- NotificationMessage schemas for Pub/Sub message payload (US-067)
- SendGrid Dynamic Template substitution schemas
"""

# Notification request schemas (existing functionality)
from .notification_request import (
    NotificationPriority,
    NotificationRequest,
    NotificationTypeEnum,
)

# Notification message schemas (US-067)
from .notification_message import (
    NotificationChannel,
    NotificationMessage,
)

# SendGrid template substitution schemas (US-066)
from .sendgrid_templates import (
    AppointmentReminderSchema,
    BaseTemplateSchema,
    CareTeamEscalationSchema,
    EDBoardingAlertSchema,
    HousekeepingNotificationSchema,
    MedicationReminderSchema,
    PatientPortalLinkSchema,
    TEMPLATE_SCHEMA_REGISTRY,
)

__all__ = [
    # Notification request schemas
    "NotificationPriority",
    "NotificationRequest",
    "NotificationTypeEnum",
    # Notification message schemas (US-067)
    "NotificationChannel",
    "NotificationMessage",
    # SendGrid template schemas
    "AppointmentReminderSchema",
    "BaseTemplateSchema",
    "CareTeamEscalationSchema",
    "EDBoardingAlertSchema",
    "HousekeepingNotificationSchema",
    "MedicationReminderSchema",
    "PatientPortalLinkSchema",
    "TEMPLATE_SCHEMA_REGISTRY",
]
