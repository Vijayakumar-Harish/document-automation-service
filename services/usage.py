from app.db import get_db
from datetime import datetime

async def charge_user(user_id: str, credits: int):
    db = get_db()
    await db.usage.insert_one({"userId":user_id, "credits":credits, "at":datetime.utcnow()})

async def get_monthly_usage(user_id: str):
    db = get_db()
    from datetime import datetime
    now = datetime.utcnow()
    start = datetime(now.year, now.month, 1)
    pipeline = [
        {"$match": {"userId":user_id, "at": {"$gte": start}}},
        {"$group": {"_id":None, "total": {"$sum":"$credits"}}}
    ]
    res = await db.usage.aggregate(pipeline).to_list(length=1)
    return res[0]["total"] if res else 0