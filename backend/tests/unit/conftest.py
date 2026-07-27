"""Pytest configuration for unit tests.

Unit tests should not require testcontainers or database setup.
This conftest overrides the root conftest for unit test isolation.
"""
from __future__ import annotations

import pytest


# Mark all tests in this directory as unit tests
def pytest_collection_modifyitems(items):
    """Automatically mark all tests in unit/ as unit tests."""
    for item in items:
        item.add_marker(pytest.mark.unit)
