from fastapi import APIRouter, Depends
from app.auth import get_current_user, require_role
from app.db import get_db
from app.utils import now
from app.schemas import OCRPayload
from services.ocr_classifier import classify_text, extract_unsubscribe
from datetime import datetime
from pymongo import ReturnDocument

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])

@router.post("/ocr", dependencies=[Depends(require_role("user", "admin"))])
async def ocr_webhook(payload: OCRPayload, user=Depends(get_current_user)):
    db = get_db()

    classification = classify_text(payload.text)
    await db.audit_logs.insert_one({
        "at": now(),
        "userId": user.sub,
        "action": "webhook_ocr",
        "entityType": "webhook",
        "entityId": payload.imageId,
        "metadata": {"classification": classification}
    })

    if classification == "ad":
        unsub = extract_unsubscribe(payload.text)
        target = unsub.get("value") if unsub else None

        today = datetime.utcnow()
        rate_key = f"{user.sub}:{payload.source}:{today.strftime('%Y-%m-%d')}"

        res = await db.rate_limits.find_one_and_update(
            {"key": rate_key},
            {
                "$inc": {"count": 1},
                "$setOnInsert": {"createdAt": now()}
            },
            upsert=True,
            return_document=ReturnDocument.AFTER
        )

        count = res.get("count", 0)
        if count > 3:
            # rollback increment for fairness
            await db.rate_limits.update_one({"key": rate_key}, {"$inc": {"count": -1}})
            return {"status": "rate_limited", "remaining": 0}

        remaining = max(0, 3 - count)

        task = {
            "userId": user.sub,
            "sender": payload.source,
            "status": "pending",
            "channel": "email" if unsub and unsub.get("type") == "email" else "web",
            "target": target,
            "payload": payload.dict(),
            "createdAt": now()
        }

        r = await db.tasks.insert_one(task)
        await db.audit_logs.insert_one({
            "at": now(),
            "userId": user.sub,
            "action": "task_create",
            "entityType": "task",
            "entityId": str(r.inserted_id),
            "metadata": {"rate_count": count}
        })

        return {
            "taskId": str(r.inserted_id),
            "remaining": remaining
        }

    return {"classification": classification}
