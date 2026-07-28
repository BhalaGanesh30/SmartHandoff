"""Follow-up Care Agent module for readmission risk assessment.

This agent processes A03 (discharge) events, extracts features, calls the
ML Inference Service, and persists risk scores to the database.

US-039 TASK-004: FollowUpCareAgent implementation
"""
