from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user, require_role
from app.db import get_db
from app.utils import now
from app.schemas import OCRPayload
from app.models import AuditLogModel, TaskModel, RateLimitModel
from services.ocr_classifier import classify_text, extract_unsubscribe
from datetime import datetime, timezone
from pymongo import ReturnDocument
from app.metrics_registry import webhook_calls_total
from app.metrics_registry import errors_total

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


@router.post("/ocr", dependencies=[Depends(require_role("user", "admin"))])
async def ocr_webhook(payload: OCRPayload, user=Depends(get_current_user),db=Depends(get_db)):
    """
    Handles OCR ingestion webhook.
    - Classifies OCR text (e.g., ad, official, spam)
    - Enforces rate limiting for "ad" type
    - Creates follow-up processing task
    - Logs all actions to audit trail
    """
    webhook_calls_total.inc()
    # db = get_db()

    try:
        # Classify OCR text
        classification = classify_text(payload.text)

        #  Audit classification
        audit_entry = AuditLogModel(
            userId=user.sub,
            action="webhook_ocr",
            entityType="webhook",
            entityId=payload.imageId,
            metadata={"classification": classification},
            at=now(),
        )
        await db.audit_logs.insert_one(audit_entry.model_dump(by_alias=True))

        #  Handle non-ad classifications quickly
        if classification != "ad":
            return {"classification": classification}

        #  Handle unsubscribe extraction for ads
        unsub = extract_unsubscribe(payload.text)
        target = unsub.get("value") if unsub else None

        #  Rate limiting (3 per day)
        today = datetime.now(timezone.utc)
        rate_key = f"{user.sub}:{payload.source}:{today.strftime('%Y-%m-%d')}"

        res = await db.rate_limits.find_one_and_update(
            {"key": rate_key},
            {"$inc": {"count": 1}, "$setOnInsert": {"createdAt": now()}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )

        count = res.get("count", 0) if res else 1
        if count > 3:
            # rollback increment for fairness
            await db.rate_limits.update_one({"key": rate_key}, {"$inc": {"count": -1}})
            return {"status": "rate_limited", "remaining": 0}

        remaining = max(0, 3 - count)

        #  Create a new task for processing the ad
        task = TaskModel(
            userId=user.sub,
            sender=payload.source,
            status="pending",
            channel="email" if (unsub and unsub.get("type") == "email") else "web",
            target=target,
            payload=payload.model_dump(),
            createdAt=now(),
        )
        task_result = await db.tasks.insert_one(task.model_dump(by_alias=True))

        #  Audit the new task creation
        task_audit = AuditLogModel(
            userId=user.sub,
            action="task_create",
            entityType="task",
            entityId=str(task_result.inserted_id),
            metadata={"rate_count": count, "source": payload.source},
            at=now(),
        )
        await db.audit_logs.insert_one(task_audit.model_dump(by_alias=True))

        #  Response
        return {
            "taskId": str(task_result.inserted_id),
            "remaining": remaining,
            "classification": classification,
        }

    except Exception as e:
        errors_total.inc()
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")
