"""Cloud Run entrypoint for the Bed Management Agent service."""
from __future__ import annotations

import asyncio
import logging
import os

from app.agents.bed_management.agent import BedManagementAgent
from app.agents.bed_management.notifier import HousekeepingNotifier
from app.agents.bed_management.prediction_service import DischargePredictionService
from app.agents.bed_management.refresh_service import BedBoardRefreshService
from app.agents.bed_management.seeder import BedInventorySeeder

logging.basicConfig(level=logging.INFO)


# def _build_authenticated_http_client() -> httpx.AsyncClient:
#     """Create an httpx.AsyncClient that sends a service account ID token on each request.
#     
#     Uses Google Application Default Credentials (ADC) to obtain a service account
#     token. The token is automatically refreshed before each request.
#     
#     Returns:
#         httpx.AsyncClient with Bearer token authentication.
#     """
#     import httpx
#     import google.auth
#     import google.auth.transport.requests
#     
#     credentials, _ = google.auth.default(
#         scopes=["https://www.googleapis.com/auth/cloud-platform"]
#     )
#     auth_req = google.auth.transport.requests.Request()
#     
#     class _GoogleAuthTransport(httpx.AsyncBaseTransport):
#         """Injects Bearer token from refreshed credentials on each request."""
#         async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
#             credentials.refresh(auth_req)
#             request.headers["Authorization"] = f"Bearer {credentials.token}"
#             async with httpx.AsyncClient() as client:
#                 return await client.send(request)
#     
#     return httpx.AsyncClient(transport=_GoogleAuthTransport())


async def main() -> None:
    """Initialize and run the BedManagementAgent.
    
    TASK-002 Status: BedBoardRefreshService implemented ✅
    TASK-003 Status: BedInventorySeeder implemented ✅
    TASK-004 Status: HousekeepingNotifier implemented ✅
    US-036 TASK-004 Status: DischargePredictionService implemented ✅
    
    Startup sequence:
    1. Seed bed inventory from config/bed_inventory.yaml (idempotent)
    2. Refresh mv_bed_board synchronously (blocks until ready)
    3. Initialize prediction service with authenticated HTTP client (US-036)
    4. Start agent Pub/Sub pull loop
    
    Pending full integration (requires DB dependencies from backend core):
    - Configure write_session_factory (get_write_db)
    - Configure read_session_factory (get_read_db)
    - Configure Pub/Sub client (get_pubsub_client)
    
    Subscription ID: bed-mgmt-agent-sub (dedicated Pub/Sub subscription per ADR-001)
    """
    # Validate ML Inference Service URL (US-036 TASK-004)
    if not os.environ.get("ML_INFERENCE_SERVICE_URL"):
        logging.warning(
            "ML_INFERENCE_SERVICE_URL not set — discharge predictions will be skipped."
        )
    
    # TASK-002 & TASK-003 & TASK-004 & US-036 TASK-004: All services ready
    # refresh_service = BedBoardRefreshService(write_session_factory=get_write_db)
    # seeder = BedInventorySeeder(
    #     session_factory=get_write_db,
    #     refresh_service=refresh_service,
    # )
    # await seeder.seed()  # Idempotent seeding + sync MV refresh
    # 
    # housekeeping_notifier = HousekeepingNotifier(
    #     pubsub_client=get_pubsub_client(),
    #     project_id=settings.GCP_PROJECT_ID,
    #     read_session_factory=get_read_db,
    # )
    # 
    # # US-036 TASK-004: Initialize prediction service with authenticated HTTP client
    # http_client = _build_authenticated_http_client()
    # prediction_service = DischargePredictionService(http_client=http_client)
    # 
    # agent = BedManagementAgent(
    #     db_session_factory=get_write_db,
    #     refresh_service=refresh_service,
    #     housekeeping_notifier=housekeeping_notifier,
    #     prediction_service=prediction_service,  # US-036 TASK-004
    # )
    # await agent.run()  # BaseAgent pull loop
    
    logging.info(
        "BedManagementAgent main() - subscription: bed-mgmt-agent-sub - "
        "TASK-002 BedBoardRefreshService ready - "
        "TASK-003 BedInventorySeeder ready - "
        "TASK-004 HousekeepingNotifier ready - "
        "US-036 TASK-004 DischargePredictionService ready - "
        "waiting for DB dependencies and Pub/Sub client"
    )
    await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
