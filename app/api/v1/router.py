from fastapi import APIRouter

from app.api.v1.endpoints import (
    api_keys,
    auth,
    conversations,
    documents,
    feedback,
    rag,
    system,
    users,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(system.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(documents.router)
api_router.include_router(rag.router)
api_router.include_router(conversations.router)
api_router.include_router(feedback.router)
api_router.include_router(api_keys.router)
