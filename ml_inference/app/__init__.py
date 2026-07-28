"""SmartHandoff ML Inference Service.

FastAPI Cloud Run service serving discharge time predictions from
GCS-hosted GradientBoostingRegressor model.

Design refs:
    US-036 TASK-002 — ML Inference Service
    design.md §3.1 — ML Inference Service: Python FastAPI + Scikit-learn
    design.md §5.1 (TR-007) — ML inference latency <500 ms
"""
__version__ = "1.0.0"
