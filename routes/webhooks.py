from fastapi import APIRouter, Depends
from app.auth import get_current_user, require_role
from app.db import get_db
from app.utils import now
from app.schemas import OCRPayload
from services.ocr_classifier import classify_text, extract_unsubscribe
from datetime import datetime

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])

@router.post("/ocr",dependencies=[Depends(require_role("user", "admin"))])
async def ocr_webhook(payload: OCRPayload, user=Depends(get_current_user)):
    db = get_db()
    classification = classify_text(payload.text)
    await db.audit_logs.insert_one({"at":now(), "userId":user.sub, "action":"webhook_ocr", "entityType":"webhook","entityId":payload.imageId, "metadata":{"classification":classification}})
    if classification == "ad":
        unsub = extract_unsubscribe(payload.text)
        target = unsub.get("value") if unsub else None
        today = datetime.utcnow()
        start = datetime(today.year, today.month, today.day)
        cnt = await db.tasks.count_documents({"userId":user.sub, "sender":payload.source, "createdAt":{"$gte":start}})
        if cnt >= 3:
            return {"status":"rate_limited"}
        task = {"userId":user.sub,"sender":payload.source,"status":"pending", "channel":"email" if (unsub and unsub.get("type")=="email") else "web", "target":target, "payload":payload.dict(), "createdAt":now()}
        r = await db.tasks.insert_one(task)
        await db.audit_logs.insert_one({"at":now(), "userId":user.sub, "action":"task_create", "entityType":"task", "entityId": str(r.inserted_id), "metadata":{}})
        return {"taskId":str(r.inserted_id)}
    return {"classification": classification}