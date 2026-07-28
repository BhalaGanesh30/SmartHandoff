"""Discharge time prediction ML module.

This package implements the full training pipeline for US-036:
feature engineering, model training (GradientBoostingRegressor),
evaluation with quality gates, and GCS artefact upload.

Design refs:
    US-036 — Predicted discharge time ML model (MAE ≤2h, 80% within ±2h)
    design.md §3.1 — ML Inference Service with Scikit-learn
    design.md §4.1 — GCS ml-models bucket for model artefacts
"""
__version__ = "1.0.0"
