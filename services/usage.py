from app.db import get_client
from app.config import settings
from datetime import datetime, timezone

DEFAULT_CREDIT_LIMIT = 50


def _fallback_db():
    return get_client()[settings.DB_NAME]


async def charge_user(user_id: str, credits: int, db=None):
    if db is None:
        db = _fallback_db()

    await db.usage.insert_one({
        "userId": user_id,
        "credits": credits,
        "at": datetime.now(timezone.utc)
    })


async def get_monthly_usage(user_id: str, db=None):
    if db is None:
        db = _fallback_db()

    now = datetime.now(timezone.utc)
    start = datetime(now.year, now.month, 1)

    cursor = db.usage.find({
        "userId": user_id,
        "at": {"$gte": start}
    })

    total = 0
    async for doc in cursor:
        total += doc.get("credits", 0)

    return total


async def get_remaining_credits(user_id: str, db=None) -> int:
    if db is None:
        db = _fallback_db()

    used = await get_monthly_usage(user_id, db=db)
    return max(0, DEFAULT_CREDIT_LIMIT - used)
