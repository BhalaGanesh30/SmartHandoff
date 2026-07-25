"""Pydantic v2 substitution schemas for SendGrid Dynamic Email Templates.

Each model maps 1-to-1 with a template JSON file in
``notifications/templates/``. The field names match the Handlebars
``{{variable}}`` tokens in the corresponding template HTML.

PHI minimisation policy (US-066 DoD / HIPAA minimum-necessary):
    Patient-facing templates: ``first_name`` only.
    ``last_name``, ``mrn``, ``dob`` are intentionally absent.
    Staff-facing templates (care_team_escalation, ed_boarding_alert):
        ``encounter_id`` is permitted — not classified as PHI.

Design refs:
    US-066 DoD, US-066 Technical Notes, ADR-007, design.md §4.1
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BaseTemplateSchema(BaseModel):
    """Common base for all SendGrid Dynamic Template substitution schemas.

    ``template_name`` is used by ``upload_sendgrid_templates.py`` to resolve
    the correct template JSON file and by the notification dispatcher to look
    up the SendGrid template ID from ``config/sendgrid_templates.yaml``.
    """

    model_config = ConfigDict(frozen=True)

    template_name: str = Field(
        ...,
        description="Key matching an entry in config/sendgrid_templates.yaml",
    )


# ---------------------------------------------------------------------------
# 1. Patient portal link
# ---------------------------------------------------------------------------

class PatientPortalLinkSchema(BaseTemplateSchema):
    """Substitution data for the ``patient_portal_link`` template.

    Rendered when a patient is sent their discharge portal access link.

    PHI: ``first_name`` only (US-066 DoD).
    """

    template_name: str = Field(default="patient_portal_link", frozen=True)

    first_name: str = Field(..., min_length=1, max_length=100)
    portal_link: AnyHttpUrl = Field(
        ..., description="Authenticated, time-limited portal URL (HTTPS)"
    )
    discharge_date: Optional[date] = Field(
        default=None, description="Confirmed or estimated discharge date (optional)"
    )
    hospital_name: str = Field(..., min_length=1, max_length=200)
    hospital_phone: str = Field(
        ...,
        pattern=r"^\+?[1-9]\d{1,14}$",
        description="E.164 or local format hospital contact number",
    )


# ---------------------------------------------------------------------------
# 2. Appointment reminder
# ---------------------------------------------------------------------------

class AppointmentReminderSchema(BaseTemplateSchema):
    """Substitution data for the ``appointment_reminder`` template.

    Rendered for post-discharge follow-up appointment reminders.

    PHI: ``first_name`` only (US-066 DoD).
    """

    template_name: str = Field(default="appointment_reminder", frozen=True)

    first_name: str = Field(..., min_length=1, max_length=100)
    appointment_date: str = Field(
        ..., description="Human-readable appointment date/time, e.g. 'Monday 21 July at 10:00 AM'"
    )
    provider_name: str = Field(..., min_length=1, max_length=200)
    clinic_name: str = Field(..., min_length=1, max_length=200)
    clinic_address: str = Field(..., min_length=1, max_length=500)
    clinic_phone: str = Field(
        ..., pattern=r"^\+?[1-9]\d{1,14}$"
    )


# ---------------------------------------------------------------------------
# 3. Medication reminder
# ---------------------------------------------------------------------------

class MedicationReminderSchema(BaseTemplateSchema):
    """Substitution data for the ``medication_reminder`` template.

    Rendered when the Follow-up Care Agent dispatches a medication schedule
    reminder (US-066 AC Scenario 4).

    PHI: ``first_name`` only. Drug details are clinical data, not PHI.
    """

    template_name: str = Field(default="medication_reminder", frozen=True)

    first_name: str = Field(..., min_length=1, max_length=100)
    drug_name: str = Field(..., min_length=1, max_length=200)
    dose: str = Field(..., min_length=1, max_length=100, description="e.g. '500mg'")
    frequency: str = Field(
        ..., min_length=1, max_length=200, description="e.g. 'twice daily'"
    )
    instructions: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Special instructions, e.g. 'take with food'",
    )
    care_team_phone: str = Field(
        ...,
        pattern=r"^\+?[1-9]\d{1,14}$",
        description="Care team contact for questions section",
    )


# ---------------------------------------------------------------------------
# 4. Care team escalation (staff-facing)
# ---------------------------------------------------------------------------

class CareTeamEscalationSchema(BaseTemplateSchema):
    """Substitution data for the ``care_team_escalation`` template.

    Staff-facing: sent to clinicians when the Patient Communication Agent
    detects a high-urgency patient message requiring immediate action.

    ``encounter_id`` is permitted per US-066 Technical Notes — not PHI.
    No patient name, MRN, or DOB included.
    """

    template_name: str = Field(default="care_team_escalation", frozen=True)

    encounter_id: str = Field(
        ..., min_length=1, max_length=100, description="Encounter identifier (not PHI)"
    )
    urgency_level: str = Field(
        ..., pattern=r"^(HIGH|CRITICAL)$", description="Urgency classification"
    )
    escalation_reason: str = Field(..., min_length=1, max_length=1000)
    unit_name: str = Field(..., min_length=1, max_length=200)
    escalated_at: str = Field(
        ..., description="ISO 8601 timestamp of escalation trigger"
    )
    dashboard_link: AnyHttpUrl = Field(
        ..., description="Direct link to the encounter in SmartHandoff dashboard"
    )


# ---------------------------------------------------------------------------
# 5. ED boarding alert (staff-facing)
# ---------------------------------------------------------------------------

class EDBoardingAlertSchema(BaseTemplateSchema):
    """Substitution data for the ``ed_boarding_alert`` template.

    Staff-facing: sent to bed management staff when the Bed Management Agent
    predicts or detects an ED boarding breach.

    ``encounter_id`` is permitted per US-066 Technical Notes — not PHI.
    """

    template_name: str = Field(default="ed_boarding_alert", frozen=True)

    encounter_id: str = Field(
        ..., min_length=1, max_length=100, description="Encounter identifier (not PHI)"
    )
    boarding_hours: float = Field(
        ..., ge=0.0, description="Hours patient has been boarding in ED"
    )
    predicted_discharge_hours: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="ML-predicted hours until discharge (Bed Management Agent)",
    )
    unit_name: str = Field(..., min_length=1, max_length=200)
    alert_triggered_at: str = Field(
        ..., description="ISO 8601 timestamp when alert was raised"
    )
    dashboard_link: AnyHttpUrl = Field(
        ..., description="Direct link to bed board in SmartHandoff dashboard"
    )


# ---------------------------------------------------------------------------
# 6. Housekeeping notification (staff-facing)
# ---------------------------------------------------------------------------

class HousekeepingNotificationSchema(BaseTemplateSchema):
    """Substitution data for the ``housekeeping_notification`` template.

    Staff-facing: sent to housekeeping staff when a bed is ready for
    terminal cleaning after patient discharge.

    ``encounter_id`` is permitted per US-066 Technical Notes — not PHI.
    """

    template_name: str = Field(default="housekeeping_notification", frozen=True)

    encounter_id: str = Field(
        ..., min_length=1, max_length=100, description="Encounter identifier (not PHI)"
    )
    bed_identifier: str = Field(
        ..., min_length=1, max_length=100, description="e.g. 'Ward 4B - Bed 12'"
    )
    unit_name: str = Field(..., min_length=1, max_length=200)
    discharge_confirmed_at: str = Field(
        ..., description="ISO 8601 timestamp of confirmed discharge"
    )
    priority: str = Field(
        ..., pattern=r"^(ROUTINE|URGENT)$", description="Cleaning priority level"
    )


# ---------------------------------------------------------------------------
# Registry — used by dispatcher and upload script
# ---------------------------------------------------------------------------

TEMPLATE_SCHEMA_REGISTRY: dict[str, type[BaseTemplateSchema]] = {
    "patient_portal_link": PatientPortalLinkSchema,
    "appointment_reminder": AppointmentReminderSchema,
    "medication_reminder": MedicationReminderSchema,
    "care_team_escalation": CareTeamEscalationSchema,
    "ed_boarding_alert": EDBoardingAlertSchema,
    "housekeeping_notification": HousekeepingNotificationSchema,
}
"""Mapping of template name → Pydantic schema class.

Used by the notification dispatcher (US-064) to validate substitution data
before calling ``SendGridAPIClient.send()``, and by the unit tests to
parameterise schema validation tests.
"""
