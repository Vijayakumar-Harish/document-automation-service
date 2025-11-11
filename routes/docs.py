from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from bson import ObjectId
from app.auth import get_current_user, require_role
from app.db import get_db
from app.utils import now
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi.responses import JSONResponse
from services.ocr_classifier import classify_text, extract_unsubscribe
from openai import AsyncOpenAI
import io, base64, os
from datetime import datetime

openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
router = APIRouter(prefix="/v1/docs", tags=["docs"])

@router.post("", summary="Upload document", dependencies=[Depends(require_role("user", "admin"))])
async def upload_doc(
    primaryTag: str = Query(...),
    secondaryTags: str = Query(None),
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):
    db = get_db()
    fs = AsyncIOMotorGridFSBucket(db)

    file_bytes = await file.read()

    upload_stream = fs.open_upload_stream(
    file.filename,
    metadata={"ownerId": user.sub, "contentType": file.content_type}
)
    await upload_stream.write(file_bytes)
    await upload_stream.close()
    file_id = upload_stream._id

    doc = {
        "ownerId": user.sub,
        "filename": file.filename,
        "mime": file.content_type,
        "gridfsId": file_id,
        "textContent": None,
        "createdAt": now(),
    }
    r = await db.documents.insert_one(doc)
    doc_id = r.inserted_id

    tag = await db.tags.find_one({"ownerId": user.sub, "name": primaryTag})
    if not tag:
        tr = await db.tags.insert_one({"name": primaryTag, "ownerId": user.sub, "createdAt": now()})
        tag_id = tr.inserted_id
    else:
        tag_id = tag["_id"]

    await db.document_tags.insert_one({"documentId": doc_id, "tagId": tag_id, "isPrimary": True})

    if secondaryTags:
        for tname in [t.strip() for t in secondaryTags.split(",") if t.strip()]:
            tt = await db.tags.find_one({"ownerId": user.sub, "name": tname})
            if not tt:
                tr = await db.tags.insert_one({"name": tname, "ownerId": user.sub, "createdAt": now()})
                tid = tr.inserted_id
            else:
                tid = tt["_id"]
            await db.document_tags.insert_one({"documentId": doc_id, "tagId": tid, "isPrimary": False})

    await db.audit_logs.insert_one({
        "at": now(),
        "userId": user.sub,
        "action": "upload",
        "entityType": "document",
        "entityId": str(doc_id),
        "metadata": {"filename": file.filename, "gridfsId": str(file_id)}
    })

    return {"id": str(doc_id), "message": "File uploaded successfully to GridFS"}


@router.get("/{id}", dependencies=[Depends(require_role("user", "admin", "support", "moderator"))])
async def get_doc(id: str, user=Depends(get_current_user)):
    db = get_db()
    doc = await db.documents.find_one({"_id": ObjectId(id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.get("ownerId") != user.sub and user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    doc["id"] = str(doc["_id"])
    doc["gridfsId"] = str(doc["gridfsId"])
    doc.pop("_id", None)
    return doc


@router.get("/{id}/download", summary="Download the document", dependencies=[Depends(require_role("user", "admin"))])
async def download_doc(id: str, user=Depends(get_current_user)):
    db = get_db()
    fs = AsyncIOMotorGridFSBucket(db)
    download_stream = await fs.open_download_stream(doc["gridfsId"])
    content = await download_stream.read()

    doc = await db.documents.find_one({"_id": ObjectId(id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.get("ownerId") != user.sub and user.role != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")

    grid_out = fs.get(doc["gridfsId"])
    content = grid_out.read()

    return StreamingResponse(
        io.BytesIO(content),
        media_type=doc["mime"],
        headers={"Content-Disposition": f"attachment; filename={doc['filename']}"}
    )

@router.post("/ocr-scan", summary="Upload document and OCR via OpenAI Vision",
             dependencies=[Depends(require_role("user", "admin"))])
async def ocr_scan_doc(
    file: UploadFile = File(...),
    user=Depends(get_current_user)
):
    db = get_db()
    fs = AsyncIOMotorGridFSBucket(db)

    # Read the file
    file_bytes = await file.read()
    mime_type = file.content_type

    # Save file to GridFS
    upload_stream = fs.open_upload_stream(
        file.filename,
        metadata={"ownerId": user.sub, "contentType": mime_type}
    )
    await upload_stream.write(file_bytes)
    await upload_stream.close()
    file_id = upload_stream._id

    # Convert to Base64 for OpenAI vision API
    file_base64 = base64.b64encode(file_bytes).decode("utf-8")
    image_url = f"data:{mime_type};base64,{file_base64}"

    # 🔍 Extract text using OpenAI Vision
    try:
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",  # Supports image input
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract all visible text from this image or document:"},
                        {"type": "image_url", "image_url": {"url": image_url}}
                    ]
                }
            ]
        )
        extracted_text = response.choices[0].message.content.strip()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR extraction failed: {str(e)}")

    # Store document metadata
    doc = {
        "ownerId": user.sub,
        "filename": file.filename,
        "mime": mime_type,
        "gridfsId": file_id,
        "textContent": extracted_text,
        "createdAt": now(),
    }
    result = await db.documents.insert_one(doc)
    doc_id = result.inserted_id

    # 🔠 Classify and process OCR text
    classification = classify_text(extracted_text)
    unsub = extract_unsubscribe(extracted_text)
    target = unsub.get("value") if unsub else None

    # Audit log
    await db.audit_logs.insert_one({
        "at": now(),
        "userId": user.sub,
        "action": "ocr_scan",
        "entityType": "document",
        "entityId": str(doc_id),
        "metadata": {"classification": classification, "filename": file.filename}
    })

    # 🚦 Rate limiting + task creation (for ads)
    if classification == "ad":
        today = datetime.utcnow()
        rate_key = f"{user.sub}:{file.filename}:{today.strftime('%Y-%m-%d')}"
        res = await db.rate_limits.find_one_and_update(
            {"key": rate_key},
            {"$inc": {"count": 1}, "$setOnInsert": {"createdAt": now()}},
            upsert=True,
            return_document=True
        )
        if res and res.get("count", 0) > 3:
            await db.rate_limits.update_one({"key": rate_key}, {"$inc": {"count": -1}})
            return JSONResponse({"status": "rate_limited", "remaining": 0}, status_code=429)

        task = {
            "userId": user.sub,
            "sender": "ocr_scan",
            "status": "pending",
            "channel": "email" if (unsub and unsub.get("type") == "email") else "web",
            "target": target,
            "payload": {"fileId": str(file_id), "filename": file.filename},
            "createdAt": now()
        }
        r = await db.tasks.insert_one(task)
        await db.audit_logs.insert_one({
            "at": now(),
            "userId": user.sub,
            "action": "task_create",
            "entityType": "task",
            "entityId": str(r.inserted_id),
            "metadata": {"source": "ocr_scan"}
        })
        return {"classification": classification, "taskId": str(r.inserted_id)}

    return {"classification": classification, "text_preview": extracted_text[:200]}