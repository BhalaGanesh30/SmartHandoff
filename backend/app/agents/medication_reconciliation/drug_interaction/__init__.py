"""Drug interaction detection and caching module.

Handles RxNav API integration, Redis caching, and drug-drug interaction detection
for medication reconciliation workflows.

Components:
    - cache: Redis cache wrapper with sorted CUI-pair keys
    - client: RxNav API client for interaction lookups
    - detector: High-level interaction detection logic

Design references:
    - US-031: Drug-drug interaction detection with Redis caching
    - design.md §4.1: Redis (Cloud Memorystore) as caching tier
"""
