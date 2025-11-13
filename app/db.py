from fastapi import Request, Depends
from motor.motor_asyncio import AsyncIOMotorClient
from .config import settings

_client = None

def get_client():
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.MONGO_URI)
    return _client

async def get_db(request: Request):
    # # If pytest override injected a test DB:
    # if hasattr(request.app, "override_db") and request.app.override_db:
    #     return request.app.override_db

    # # Use db attached by lifespan
    # if hasattr(request.app, "db") and request.app.db:
    #     return request.app.db

    # # Fallback (should not happen in tests)
    return get_client()[settings.DB_NAME]
