from fastapi import APIRouter

from app.api.v1.endpoints import alerts, chat, approvals, status

api_router = APIRouter()

api_router.include_router(alerts.router, prefix="/alerts", tags=["alerts"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(approvals.router, prefix="/approvals", tags=["approvals"])
api_router.include_router(status.router, prefix="/status", tags=["status"])