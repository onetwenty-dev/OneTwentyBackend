from fastapi import APIRouter
from app.api.v1.endpoints import entries, auth, status, doctors, websocket, chat, events, reports

api_router = APIRouter()
api_router.include_router(entries.router, tags=["entries"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(status.router, tags=["status"])
api_router.include_router(doctors.router, prefix="/doctors", tags=["doctors"])
api_router.include_router(websocket.router, tags=["websocket"])
api_router.include_router(events.router, prefix="/treatments", tags=["treatments", "OneTwenty"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat", "ai"])
api_router.include_router(reports.router, prefix="/reports", tags=["reports"])

