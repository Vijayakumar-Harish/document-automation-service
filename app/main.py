from fastapi import FastAPI
from contextlib import asynccontextmanager
from motor.motor_asyncio import AsyncIOMotorClient
from routes import docs, folders, actions, webhooks, metrics
from .config import settings
from .utils import now
import asyncio
from app.db_cleanup import safe_close_motor
import os

# Detect if we are running under pytest
IS_TESTING = "PYTEST_CURRENT_TEST" in os.environ

if IS_TESTING:
    import motor.frameworks.asyncio
    import types

    # Patch Motor to never call run_in_executor
    def _safe_run_on_executor(fn, *args, **kwargs):
        # Directly call function synchronously (no background threads)
        return fn(*args, **kwargs)

    motor.frameworks.asyncio.run_on_executor = _safe_run_on_executor
else:
    from motor.motor_asyncio import AsyncIOMotorClient
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.mongodb_client = AsyncIOMotorClient(settings.MONGO_URI)
    app.db = app.mongodb_client[settings.DB_NAME]

    await app.db.tags.create_index([("ownerId", 1), ("name", 1)])
    await app.db.document_tags.create_index([("documentId", 1), ("tagId", 1)])
    await app.db.audit_logs.create_index([("userId", 1), ("at", -1)])
    await app.db.tasks.create_index([("userId", 1), ("createdAt", 1)])
    await app.db.documents.create_index([("ownerId", 1)])
    await app.db.rate_limits.create_index("createdAt", expireAfterSeconds=86400)
    yield

    safe_close_motor(app.mongodb_client)

app = FastAPI(title="Senior Backend Assignment", lifespan=lifespan)
app.include_router(docs.router)
app.include_router(folders.router)
app.include_router(actions.router)
app.include_router(webhooks.router)
app.include_router(metrics.router)

@app.get("/health")
async def health():
    return {"status": "ok", "ts": now().isoformat()}
