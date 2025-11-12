from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from routes import docs, folders, actions, webhooks, metrics
from app.config import settings
from app.metrics_registry import active_users_gauge, errors_total
from prometheus_fastapi_instrumentator import Instrumentator
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import asyncio, time
from app.routers import auth_routes
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.mongodb_client = None
    app.db = None

    async def connect_mongo():
        for attempt in range(10):
            try:
                client = AsyncIOMotorClient(settings.MONGO_URI, serverSelectionTimeoutMS=2000)
                await client.admin.command('ping')
                app.mongodb_client = client
                app.db = client[settings.DB_NAME]
                print("✅ MongoDB connected successfully!")
                return
            except Exception as e:
                print(f"⏳ Mongo not ready yet (attempt {attempt+1})... waiting 2s")
                await asyncio.sleep(2)
        print("❌ MongoDB connection failed after 10 attempts")

    
    await connect_mongo()

    yield

    if app.mongodb_client:
        app.mongodb_client.close()
        print("🧹 MongoDB connection closed")

app = FastAPI(title="Senior Backend Assignment", lifespan=lifespan)

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Rate limiter ---
RATE_LIMITS = {
    "/v1/docs": {"rate": 5, "per_seconds": 60},
    "/v1/docs/ocr-scan": {"rate": 3, "per_seconds": 60},
}
rate_counters = {}

@app.middleware("http")
async def rate_limiter(request: Request, call_next):
    path = request.url.path
    user = request.headers.get("Authorization", "anonymous")

    for key, cfg in RATE_LIMITS.items():
        if path.startswith(key):
            limit_key = f"{user}:{key}"
            now_ts = time.time()

            counter = rate_counters.get(limit_key, {"count": 0, "reset": now_ts + cfg["per_seconds"]})
            if now_ts > counter["reset"]:
                counter = {"count": 0, "reset": now_ts + cfg["per_seconds"]}

            if counter["count"] >= cfg["rate"]:
                retry_after = int(counter["reset"] - now_ts)
                errors_total.inc()
                return JSONResponse(
                    {"detail": f"Rate limit exceeded. Try again in {retry_after}s."},
                    status_code=429,
                    headers={"Retry-After": str(retry_after)},
                )

            counter["count"] += 1
            rate_counters[limit_key] = counter

    return await call_next(request)


@app.middleware("http")
async def track_active_users(request: Request, call_next):
    user = request.headers.get("Authorization")
    if user:
        active_users_gauge.inc()
    try:
        response = await call_next(request)
    finally:
        if user:
            active_users_gauge.dec()
    return response

app.include_router(auth_routes.router)
app.include_router(docs.router)
app.include_router(folders.router)
app.include_router(actions.router)
app.include_router(webhooks.router)
app.include_router(metrics.router)


@app.get("/health")
async def health(request: Request):
    db_client = getattr(request.app, "mongodb_client", None)
    db_status = "not_ready"

    try:
        if db_client:
            await asyncio.wait_for(db_client.admin.command("ping"), timeout=1.5)
            db_status = "connected"
        else:
            db_status = "client_missing"

        return {
            "status": "ok",
            "db": db_status,
            "ts": datetime.now(timezone.utc).isoformat(),
        }

    except asyncio.TimeoutError:
        return {
            "status": "error",
            "detail": "Ping timed out",
            "ts": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        return {
            "status": "error",
            "detail": str(e),
            "ts": datetime.now(timezone.utc).isoformat(),
        }

# --- Prometheus ---
instrumentator = Instrumentator().instrument(app)
instrumentator.expose(app, endpoint="/metrics", include_in_schema=False)


app.mount("/", StaticFiles(directory="app/static", html=True), name="static")