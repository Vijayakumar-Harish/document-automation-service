from fastapi import APIRouter, Depends
from app.auth import get_current_user, require_role
from app.db import get_db
from datetime import datetime, timezone

router = APIRouter(prefix="/v1/metrics", tags=["metrics"])

@router.get("", dependencies=[Depends(require_role("user", "admin", "support", "moderator"))])
async def metrics(user=Depends(get_current_user), db=Depends(get_db)):
    now = datetime.now(timezone.utc)
    start_month = datetime(now.year, now.month, 1)
    start_day = datetime(now.year, now.month, now.day)

    # ----------------------------------------------------
    # ADMIN → GLOBAL METRICS
    # ----------------------------------------------------
    if user.role in ("admin", "support"):
        docs_total = await db.documents.count_documents({})
        folders_total = await db.tags.count_documents({})

        pipeline = [
            {"$match": {
                "action": "run_actions",
                "at": {"$gte": start_month}
            }},
            {"$group": {"_id": None, "count": {"$sum": 1}}}
        ]
        ag = await db.audit_logs.aggregate(pipeline).to_list(length=1)
        actions_month = ag[0]["count"] if ag else 0

        tasks_today = await db.tasks.count_documents({
            "createdAt": {"$gte": start_day}
        })

    else:
        # ----------------------------------------------------
        # USER / SUPPORT → USER-SPECIFIC METRICS
        # ----------------------------------------------------
        docs_total = await db.documents.count_documents({"ownerId": user.sub})
        folders_total = await db.tags.count_documents({"ownerId": user.sub})

        pipeline = [
            {"$match": {
                "userId": user.sub,
                "action": "run_actions",
                "at": {"$gte": start_month}
            }},
            {"$group": {"_id": None, "count": {"$sum": 1}}}
        ]
        ag = await db.audit_logs.aggregate(pipeline).to_list(length=1)
        actions_month = ag[0]["count"] if ag else 0

        tasks_today = await db.tasks.count_documents({
            "userId": user.sub,
            "createdAt": {"$gte": start_day}
        })

    return {
        "docs_total": docs_total,
        "folders_total": folders_total,
        "actions_month": actions_month,
        "tasks_today": tasks_today
    }
