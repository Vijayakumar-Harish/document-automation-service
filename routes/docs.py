from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from bson import ObjectId
from app.auth import get_current_user, require_role
from app.db import get_db
from app.utils import now
from app.config import settings
from app.models import DocumentModel, TagModel, TaskModel, AuditLogModel
from app.metrics_registry import (
    upload_requests_total,
    db_query_latency_seconds,
    ocr_requests_total,
    errors_total,
)
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from openai import AsyncOpenAI
from services.ocr_classifier import classify_text, extract_unsubscribe
import io, base64, os, time
from datetime import datetime, timezone
from prometheus_client import Counter
from bson import ObjectId

router = APIRouter(prefix="/v1/docs", tags=["docs"])
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_MIMES = {"image/png", "image/jpeg"}

list_requests_total = Counter(
    "list_requests_total", "Total number of document list requests", ["role"]
)

@router.post(
    "", summary="Upload document", dependencies=[Depends(require_role("user", "admin"))]
)
async def upload_doc(
    primaryTag: str = Query(...),
    secondaryTags: str = Query(None),
    file: UploadFile = File(...),
    user=Depends(get_current_user),
):
    upload_requests_total.inc()
    db = get_db()
    fs = AsyncIOMotorGridFSBucket(db)

    file_bytes = await file.read()

    if len(file_bytes) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=413, detail="File too large")
    if file.content_type not in ALLOWED_MIMES:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    upload_stream = fs.open_upload_stream(
        file.filename, metadata={"ownerId": user.sub, "contentType": file.content_type}
    )
    await upload_stream.write(file_bytes)
    await upload_stream.close()
    file_id = upload_stream._id

    start = time.time()
    doc = DocumentModel(
        ownerId=user.sub,
        filename=file.filename,
        mime=file.content_type,
        gridfsId=file_id,
        textContent=None,
        createdAt=now(),
    )
    result = await db.documents.insert_one(doc.model_dump(by_alias=True))
    db_query_latency_seconds.observe(time.time() - start)
    doc_id = result.inserted_id

    tag = await db.tags.find_one({"ownerId": user.sub, "name": primaryTag})
    if not tag:
        tag_doc = TagModel(name=primaryTag, ownerId=user.sub, createdAt=now())
        tag_result = await db.tags.insert_one(tag_doc.model_dump(by_alias=True))
        tag_id = tag_result.inserted_id
    else:
        tag_id = tag["_id"]

    await db.document_tags.insert_one(
        {"documentId": doc_id, "tagId": tag_id, "isPrimary": True}
    )

    if secondaryTags:
        for tname in [t.strip() for t in secondaryTags.split(",") if t.strip()]:
            existing = await db.tags.find_one({"ownerId": user.sub, "name": tname})
            if not existing:
                sec_tag = TagModel(name=tname, ownerId=user.sub, createdAt=now())
                tr = await db.tags.insert_one(sec_tag.model_dump(by_alias=True))
                tid = tr.inserted_id
            else:
                tid = existing["_id"]
            await db.document_tags.insert_one(
                {"documentId": doc_id, "tagId": tid, "isPrimary": False}
            )

    audit = AuditLogModel(
        userId=user.sub,
        action="upload",
        entityType="document",
        entityId=str(doc_id),
        metadata={"filename": file.filename, "gridfsId": str(file_id)},
        at=now(),
    )
    await db.audit_logs.insert_one(audit.model_dump(by_alias=True))

    return {"id": str(doc_id), "message": "File uploaded successfully to GridFS"}


@router.get(
    "/{id}",
    summary="Get a specific document metadata",
    dependencies=[Depends(require_role("user", "admin", "support", "moderator"))],
)


@router.get("/{id}", dependencies=[Depends(require_role("user", "admin", "support", "moderator"))])
async def get_doc(id: str, user=Depends(get_current_user)):
    db = get_db()

    doc_data = None
    if ObjectId.is_valid(id):
        doc_data = await db.documents.find_one({"_id": ObjectId(id)})
    if not doc_data:
        doc_data = await db.documents.find_one({"_id": id})

    if not doc_data:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc_data.get("ownerId") != user.sub and user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    return DocumentModel(**doc_data).model_dump()


@router.get(
    "/{id}/download",
    summary="Download the document",
    dependencies=[Depends(require_role("user", "admin"))],
)
async def download_doc(id: str, user=Depends(get_current_user)):
    db = get_db()
    doc_data = await db.documents.find_one({"_id": ObjectId(id)})
    if not doc_data:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc_data.get("ownerId") != user.sub and user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    fs = AsyncIOMotorGridFSBucket(db)
    gridfs_id = doc_data["gridfsId"]
    if isinstance(gridfs_id, str):
        gridfs_id = ObjectId(gridfs_id)

    download_stream = await fs.open_download_stream(gridfs_id)
    file_data = await download_stream.read()

    return StreamingResponse(
        io.BytesIO(file_data),
        media_type=doc_data.get("mime", "application/octet-stream"),
        headers={"Content-Disposition": f'attachment; filename="{doc_data["filename"]}"'},
    )

@router.post(
    "/ocr-scan",
    summary="Upload and OCR via OpenAI Vision",
    dependencies=[Depends(require_role("user", "admin"))],
)
async def ocr_scan_doc(file: UploadFile = File(...), user=Depends(get_current_user)):
    """
    OCR Ingestion Endpoint:
    - Uploads an image to GridFS
    - Runs OCR via OpenAI GPT-4o-mini Vision model
    - Extracts text, classifies it, tags the document automatically
    - Schedules tasks if applicable, logs all events
    """
    ocr_requests_total.inc()
    db = get_db()
    fs = AsyncIOMotorGridFSBucket(db)

    # --- Read and validate file ---
    file_bytes = await file.read()
    mime_type = file.content_type or "image/png"
    if not mime_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file is not an image")

    # --- Store file in GridFS ---
    upload_stream = fs.open_upload_stream(
        file.filename, metadata={"ownerId": user.sub, "contentType": mime_type}
    )
    await upload_stream.write(file_bytes)
    await upload_stream.close()
    file_id = upload_stream._id

    # --- Prepare image for OpenAI ---
    file_base64 = base64.b64encode(file_bytes).decode("utf-8")
    image_url = f"data:{mime_type};base64,{file_base64}"

    # --- Call OpenAI Vision OCR ---
    extracted_text = ""
    try:
        response = await openai_client.responses.create(
            model="gpt-4o-mini",
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Extract all visible text, numbers, totals, and table data "
                                "from this document clearly. Preserve layout meaningfully."
                            ),
                        },
                        {"type": "input_image", "image_url": image_url},
                    ],
                }
            ],
        )

        for item in response.output:
            if item.type == "message":
                for block in item.content:
                    if block.type == "output_text":
                        extracted_text += block.text or ""

        if not extracted_text.strip():
            extracted_text = "[OCR Extraction Empty or Unreadable]"

    except Exception as e:
        errors_total.inc()
        extracted_text = "[OCR Extraction Failed]"
        await db.audit_logs.insert_one(
            {
                "at": now(),
                "userId": user.sub,
                "action": "ocr_error",
                "entityType": "document",
                "metadata": {"error": str(e), "filename": file.filename},
            }
        )

    # --- Save extracted content in DB ---
    doc = DocumentModel(
        ownerId=user.sub,
        filename=file.filename,
        mime=mime_type,
        gridfsId=file_id,
        textContent=extracted_text,
        createdAt=now(),
    )
    result = await db.documents.insert_one(doc.model_dump(by_alias=True))
    print(result.inserted_id, type(result.inserted_id))
    doc_id = result.inserted_id

    # --- Classification & unsubscribe ---
    classification = classify_text(extracted_text)
    unsub = extract_unsubscribe(extracted_text)
    target = unsub.get("value") if unsub else None

    # --- Audit logging ---
    await db.audit_logs.insert_one(
        AuditLogModel(
            userId=user.sub,
            action="ocr_scan",
            entityType="document",
            entityId=str(doc_id),
            metadata={"classification": classification, "filename": file.filename},
            at=now(),
        ).model_dump(by_alias=True)
    )

    # --- Auto-tagging logic ---
    primary_tag_name = (classification or "other").lower()
    text_lower = extracted_text.lower()

    auto_tags = {primary_tag_name}
    if "invoice" in text_lower:
        auto_tags.add("invoice")
    if "unpaid" in text_lower or "due" in text_lower:
        auto_tags.add("unpaid")
    if "gst" in text_lower or "tax" in text_lower:
        auto_tags.add("tax")
    if "total" in text_lower or "amount" in text_lower:
        auto_tags.add("finance")
    if "thank you" in text_lower:
        auto_tags.add("customer")

    auto_tags = {t.lower().strip() for t in auto_tags}

    # --- Upsert + link tags ---
    for tag_name in auto_tags:
        tag_doc = await db.tags.find_one_and_update(
        {"ownerId": user.sub, "name": tag_name},
        {"$setOnInsert": {"createdAt": now()}},
        upsert=True,
        return_document=True,
    )
        await db.document_tags.insert_one({
        "documentId": doc_id,
        "tagId": tag_doc["_id"],
        "isPrimary": tag_name == primary_tag_name,
        "createdAt": now(),
    })

    # --- Rate limit + task generation ---
    if classification == "ad":
        today = datetime.now(timezone.utc)
        rate_key = f"{user.sub}:{file.filename}:{today.strftime('%Y-%m-%d')}"

        res = await db.rate_limits.find_one_and_update(
            {"key": rate_key},
            {"$inc": {"count": 1}, "$setOnInsert": {"createdAt": now()}},
            upsert=True,
            return_document=True,
        )

        if res and res.get("count", 0) > 3:
            await db.rate_limits.update_one(
                {"key": rate_key}, {"$inc": {"count": -1}}
            )
            return JSONResponse(
                {"status": "rate_limited", "remaining": 0}, status_code=429
            )

        task = TaskModel(
            userId=user.sub,
            sender="ocr_scan",
            status="pending",
            channel="email" if (unsub and unsub.get("type") == "email") else "web",
            target=target,
            payload={"fileId": str(file_id), "filename": file.filename},
            createdAt=now(),
        )
        task_res = await db.tasks.insert_one(task.model_dump(by_alias=True))

        await db.audit_logs.insert_one(
            AuditLogModel(
                userId=user.sub,
                action="task_create",
                entityType="task",
                entityId=str(task_res.inserted_id),
                metadata={"source": "ocr_scan"},
                at=now(),
            ).model_dump(by_alias=True)
        )

        return {
            "classification": classification,
            "tags": list(auto_tags),
            "taskId": str(task_res.inserted_id),
            "text_preview": extracted_text[:200],
        }

    # --- Return response ---
    return {
        "classification": classification,
        "tags": list(auto_tags),
        "text_preview": extracted_text[:200],
        "doc_id": str(doc_id),
    }

@router.get(
    "",
    summary="List all accessible documents",
    dependencies=[Depends(require_role("user", "admin", "support"))],
)
async def list_docs(user=Depends(get_current_user)):
    """
    Lists documents visible to the authenticated user.
    - Admin → sees all documents
    - User → sees only their own
    - Support → sees all metadata (read-only)
    """
    db = get_db()
    list_requests_total.labels(role=user.role).inc()

    query = {}
    if user.role == "user":
        query = {"ownerId": user.sub}

    docs = await db.documents.find(
        query, {"_id": 1, "filename": 1, "mime": 1, "ownerId": 1, "createdAt": 1}
    ).to_list(None)

    result = [DocumentModel(**d).model_dump() for d in docs]

    audit = AuditLogModel(
        userId=user.sub,
        action="list_docs",
        entityType="document",
        entityId="*",
        metadata={"count": len(result)},
        at=now(),
    )
    await db.audit_logs.insert_one(audit.model_dump(by_alias=True))

    return result
