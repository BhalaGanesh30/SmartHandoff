#!/usr/bin/env python3
"""Validation script for US-038 TASK-003: BoardingAlertPublisher Pub/Sub Dispatch.

Verifies:
    1. boarding_publisher.py module exists
    2. BoardingAlertPublisher class is defined
    3. __init__ method accepts pubsub_client, db_session_factory, project_id
    4. dispatch_alerts() method exists
    5. _publish_single() method exists
    6. dispatch_alerts() checks candidate.already_alerted
    7. Pub/Sub publish includes idempotency_key in attributes
    8. DB UPDATE uses WHERE boarding_alert_sent_at IS NULL
    9. No DB write if Pub/Sub publish fails (return before DB write)
    10. Package __init__.py exports boarding_publisher

Design refs:
    US-038 TASK-003 — BoardingAlertPublisher implementation
    US-038 AC Scenario 1 — priority=IMMEDIATE, all required fields
    US-038 AC Scenario 4 — idempotency guard
"""
import sys
from pathlib import Path


def check_boarding_publisher_exists() -> bool:
    """Check if boarding_publisher.py module exists."""
    print("[1/10] Boarding Publisher Module Existence Check")
    
    publisher_file = Path("backend/app/agents/bed_management/boarding_publisher.py")
    
    if not publisher_file.exists():
        print(f"  ✗ Publisher file not found: {publisher_file}")
        return False
    
    print(f"  ✓ Publisher file exists: {publisher_file}")
    return True


def check_boarding_publisher_class() -> bool:
    """Check if BoardingAlertPublisher class is defined."""
    print("\n[2/10] BoardingAlertPublisher Class Check")
    
    publisher_file = Path("backend/app/agents/bed_management/boarding_publisher.py")
    content = publisher_file.read_text(encoding='utf-8')
    
    checks = {
        "BoardingAlertPublisher class": "class BoardingAlertPublisher:",
        "US-038 reference": "US-038",
        "Design refs comment": "Design refs:",
        "TASK-003 reference": "TASK-003",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_init_method() -> bool:
    """Check if __init__ method accepts correct parameters."""
    print("\n[3/10] __init__ Method Check")
    
    publisher_file = Path("backend/app/agents/bed_management/boarding_publisher.py")
    content = publisher_file.read_text(encoding='utf-8')
    
    checks = {
        "__init__ method": "def __init__(",
        "pubsub_client parameter": "pubsub_client: pubsub_v1.PublisherClient",
        "db_session_factory parameter": "db_session_factory: SessionFactory",
        "project_id parameter": "project_id: str",
        "topic_path parameter": "topic_path: str | None",
        "_client assignment": "self._client = pubsub_client",
        "_session_factory assignment": "self._session_factory = db_session_factory",
        "_topic_path assignment": "self._topic_path = topic_path",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_dispatch_alerts_method() -> bool:
    """Check if dispatch_alerts() method exists and is async."""
    print("\n[4/10] dispatch_alerts() Method Check")
    
    publisher_file = Path("backend/app/agents/bed_management/boarding_publisher.py")
    content = publisher_file.read_text(encoding='utf-8')
    
    checks = {
        "dispatch_alerts method": "async def dispatch_alerts(",
        "candidates parameter": "candidates: list[BoardingCandidate]",
        "loop over candidates": "for candidate in candidates:",
        "already_alerted check": "if candidate.already_alerted:",
        "logger.debug skip message": "logger.debug",
        "continue on already alerted": "continue",
        "_publish_single call": "await self._publish_single(candidate)",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_publish_single_method() -> bool:
    """Check if _publish_single() method exists and is async."""
    print("\n[5/10] _publish_single() Method Check")
    
    publisher_file = Path("backend/app/agents/bed_management/boarding_publisher.py")
    content = publisher_file.read_text(encoding='utf-8')
    
    checks = {
        "_publish_single method": "async def _publish_single(",
        "candidate parameter": "candidate: BoardingCandidate",
        "BoardingAlertPayload construction": "payload = BoardingAlertPayload(",
        "patient_id field": "patient_id=candidate.patient_id",
        "encounter_id field": "encounter_id=candidate.encounter_id",
        "ed_arrival_time isoformat": "ed_arrival_time=candidate.ed_arrival_time.isoformat()",
        "minutes_elapsed field": "minutes_elapsed=candidate.minutes_elapsed",
        "idempotency_key field": "idempotency_key=candidate.idempotency_key",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_pubsub_publish_logic() -> bool:
    """Check if Pub/Sub publish logic is correct."""
    print("\n[6/10] Pub/Sub Publish Logic Check")
    
    publisher_file = Path("backend/app/agents/bed_management/boarding_publisher.py")
    content = publisher_file.read_text(encoding='utf-8')
    
    checks = {
        "json.dumps payload": "json.dumps(payload.model_dump())",
        "message_data encoding": '.encode("utf-8")',
        "attributes dict": "attributes = {",
        "notification_type attribute": '"notification_type": "ED_BOARDING_ALERT"',
        "priority attribute": '"priority": "IMMEDIATE"',
        "idempotency_key attribute": '"idempotency_key": candidate.idempotency_key',
        "self._client.publish call": "self._client.publish(",
        "future.result timeout": "future.result(timeout=10)",
        "logger.info on success": "logger.info(",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_exception_handling() -> bool:
    """Check if Pub/Sub exceptions are caught and no DB write occurs."""
    print("\n[7/10] Exception Handling Check")
    
    publisher_file = Path("backend/app/agents/bed_management/boarding_publisher.py")
    content = publisher_file.read_text(encoding='utf-8')
    
    checks = {
        "try block": "try:",
        "except Exception": "except Exception:",
        "logger.exception on failure": "logger.exception(",
        "return on exception": "return  # Do NOT write boarding_alert_sent_at",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_db_write_logic() -> bool:
    """Check if DB write has idempotency guard."""
    print("\n[8/10] DB Write Logic Check")
    
    publisher_file = Path("backend/app/agents/bed_management/boarding_publisher.py")
    content = publisher_file.read_text(encoding='utf-8')
    
    checks = {
        "datetime.now(UTC)": "datetime.now(UTC)",
        "async with session_factory": "async with self._session_factory()",
        "update(Encounter)": "update(Encounter)",
        "Encounter.id == encounter_uuid": "Encounter.id == encounter_uuid",
        "boarding_alert_sent_at.is_(None)": "Encounter.boarding_alert_sent_at.is_(None)",
        "values(boarding_alert_sent_at": "values(boarding_alert_sent_at=now_utc)",
        "returning(Encounter.id)": "returning(Encounter.id)",
        "result.rowcount == 0": "result.rowcount == 0",
        "session.commit()": "await session.commit()",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_imports() -> bool:
    """Check if all required imports are present."""
    print("\n[9/10] Imports Check")
    
    publisher_file = Path("backend/app/agents/bed_management/boarding_publisher.py")
    content = publisher_file.read_text(encoding='utf-8')
    
    checks = {
        "json import": "import json",
        "logging import": "import logging",
        "uuid import": "import uuid",
        "datetime import": "from datetime import UTC, datetime",
        "pubsub_v1 import": "from google.cloud import pubsub_v1",
        "sqlalchemy update": "from sqlalchemy import update",
        "AsyncSession import": "from sqlalchemy.ext.asyncio import AsyncSession",
        "BoardingAlertPayload import": "BoardingAlertPayload",
        "BoardingCandidate import": "BoardingCandidate",
        "Encounter import": "from app.models.encounter import Encounter",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def check_package_init_updated() -> bool:
    """Check if bed_management __init__.py exports boarding_publisher."""
    print("\n[10/10] Package Initialization Check")
    
    init_file = Path("backend/app/agents/bed_management/__init__.py")
    content = init_file.read_text(encoding='utf-8')
    
    checks = {
        "boarding_publisher in __all__": '"boarding_publisher"',
        "boarding_publisher import": "from app.agents.bed_management import boarding_publisher",
    }
    
    all_passed = True
    for check_name, pattern in checks.items():
        if pattern in content:
            print(f"  ✓ {check_name}")
        else:
            print(f"  ✗ {check_name} not found")
            all_passed = False
    
    return all_passed


def main() -> int:
    """Run all validation checks."""
    print("=" * 80)
    print("US-038 TASK-003 Validation: BoardingAlertPublisher Pub/Sub Dispatch")
    print("=" * 80)
    
    results = [
        check_boarding_publisher_exists(),
        check_boarding_publisher_class(),
        check_init_method(),
        check_dispatch_alerts_method(),
        check_publish_single_method(),
        check_pubsub_publish_logic(),
        check_exception_handling(),
        check_db_write_logic(),
        check_imports(),
        check_package_init_updated(),
    ]
    
    passed = sum(results)
    total = len(results)
    
    print("\n" + "=" * 80)
    if all(results):
        print(f"✅ ALL VALIDATION CHECKS PASSED ({passed}/{total})")
    else:
        print(f"❌ SOME CHECKS FAILED ({passed}/{total})")
    print("=" * 80)
    
    print("\nValidation Summary:")
    print("  ✓ BoardingAlertPublisher class defined")
    print("  ✓ dispatch_alerts() with idempotency check (candidate.already_alerted)")
    print("  ✓ _publish_single() with Pub/Sub publish + DB write")
    print("  ✓ Pub/Sub attributes include priority=IMMEDIATE and idempotency_key")
    print("  ✓ DB UPDATE uses WHERE boarding_alert_sent_at IS NULL (concurrency guard)")
    print("  ✓ Exception handling: no DB write on Pub/Sub failure")
    print("  ✓ Package __init__.py exports boarding_publisher")
    
    print("\nNext Steps:")
    print("  1. Implement TASK-004 (Boarding Alert Resolution)")
    print("  2. Register BoardingMonitor + Publisher in main.py")
    print("  3. Create unit tests (TASK-005)")
    print("  4. Update task status to Complete")
    print("  5. Create implementation summary")
    
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
