from fastapi import APIRouter, Depends, HTTPException
from app.auth import get_current_user, require_role
from app.db import get_db
from app.utils import now
from app.schemas import ActionRequest
from bson import ObjectId
import csv, io, datetime, time, os
from app.metrics_registry import db_query_latency_seconds, errors_total
from app.config import settings
from openai import AsyncOpenAI
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
router = APIRouter(prefix="/v1/actions", tags=["actions"])

openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def run_openai_agent(prompt: str, mode: str) -> str:
    """
    Helper to call OpenAI model and return text output.
    """
    try:
        response = await openai_client.responses.create(
            model="gpt-4o-mini",
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt,
                        }
                    ],
                }
            ],
        )
        output_text = ""
        for item in response.output:
            if item.type == "message":
                for block in item.content:
                    if block.type == "output_text":
                        output_text += block.text or ""
        return output_text.strip() or f"[No output generated for {mode}]"
    except Exception as e:
        errors_total.inc()
        return f"[OpenAI Error during {mode}: {str(e)}]"
    
@router.post("/run", summary="Run scoped AI actions")
async def run_actions(payload: ActionRequest, user=Depends(get_current_user)):
    db = get_db()
    start_time = time.time()

    # --- Step 1: Record credit usage ---
    await db.usage.insert_one({
        "userId": user.sub,
        "credits_used": settings.CREDITS_PER_ACTION,
        "action": payload.actions,
        "createdAt": now(),
    })

    # --- Step 2: Validate scope ---
    scope = payload.scope
    if scope.type not in {"folder", "tag"}:
        raise HTTPException(status_code=400, detail="Unsupported scope type")

    # --- Step 3: Collect documents in scope ---
    docs_query = {}
    tag_id = None

    if scope.type == "folder" and scope.name:
        docs_query = {"folder": scope.name}

    elif scope.type == "tag" and scope.name:
        tag = await db.tags.find_one({"name": scope.name, "ownerId": user.sub})
        if not tag:
            raise HTTPException(status_code=404, detail="Tag not found")
        tag_id = tag["_id"]
        doc_tags = await db.document_tags.find({"tagId": tag_id}).to_list(None)
        doc_ids = [ObjectId(d["documentId"]) for d in doc_tags if ObjectId.is_valid(d["documentId"])]
        docs_query = {"_id": {"$in": doc_ids}}

    else:
        raise HTTPException(status_code=400, detail="Invalid scope input")

    docs = await db.documents.find(docs_query).to_list(None)
    db_query_latency_seconds.observe(time.time() - start_time)

    if not docs:
        raise HTTPException(status_code=404, detail="No documents found for the given scope")

    # --- Step 4: Build context from OCR text ---
    context_parts = []
    for d in docs:
        filename = d.get("filename", "unknown")
        text = (d.get("textContent") or "").strip()
        snippet = text[:1200] if isinstance(text, str) else ""
        context_parts.append(f"📄 File: {filename}\n{text[:1200]}")

    context_text = "\n\n".join(context_parts)
    user_prompt = payload.messages[0]["content"] if payload.messages else "Summarize these documents."
    full_prompt = (
        f"{user_prompt}\n\n"
        f"Here are the OCR-extracted texts from {len(docs)} documents:\n"
        f"{context_text}\n\n"
        f"Generate insights, summaries, or CSV data as requested."
    )

    # --- Step 5: Run OpenAI tasks ---
    text_output, csv_output = None, None
    if "make_document" in payload.actions:
        text_output = await run_openai_agent(full_prompt, "make_document")

    if "make_csv" in payload.actions:
        csv_prompt = full_prompt + "\n\nOutput a CSV with headers and rows summarizing vendor totals or key data."
        csv_output = await run_openai_agent(csv_prompt, "make_csv")

    # --- Step 6: Save AI outputs ---
    new_docs = []

    if text_output:
        doc = {
            "ownerId": user.sub,
            "filename": f"summary_{scope.name or 'scope'}.txt",
            "mime": "text/plain",
            "textContent": text_output,
            "createdAt": now(),
        }
        res = await db.documents.insert_one(doc)
        new_docs.append(str(res.inserted_id))

        # --- Tag inheritance (attach same tag/folder to generated doc) ---
        if tag_id:
            await db.document_tags.insert_one({
                "documentId": str(res.inserted_id),
                "tagId": str(tag_id),
                "isPrimary": False,
                "createdAt": now(),
            })

    if csv_output:
        csv_bytes = csv_output.encode("utf-8")
        fs = AsyncIOMotorGridFSBucket(db)
        upload_stream = fs.open_upload_stream(
            f"report_{scope.name or 'scope'}.csv",
            metadata={"ownerId": user.sub, "contentType": "text/csv"},
        )
        await upload_stream.write(csv_bytes)
        await upload_stream.close()
        gridfs_id = upload_stream._id

        doc = {
            "ownerId": user.sub,
            "filename": f"report_{scope.name or 'scope'}.csv",
            "mime": "text/csv",
            "gridfsId": gridfs_id,
            "createdAt": now(),
        }
        res = await db.documents.insert_one(doc)
        new_docs.append(str(res.inserted_id))

        if tag_id:
            await db.document_tags.insert_one({
                "documentId": str(res.inserted_id),
                "tagId": str(tag_id),
                "isPrimary": False,
                "createdAt": now(),
            })

    # --- Step 7: Audit ---
    await db.audit_logs.insert_one({
        "at": now(),
        "userId": user.sub,
        "action": "run_actions",
        "entityType": "scope",
        "metadata": {
            "scope": scope.model_dump(),
            "actions": payload.actions,
            "newDocs": new_docs,
        },
    })

    return {
        "message": "OpenAI Actions executed successfully",
        "new_docs": new_docs,
        "credits_used": settings.CREDITS_PER_ACTION,
    }


@router.get("/usage/month", dependencies=[Depends(require_role("user", "admin"))])
async def usage_month(user=Depends(get_current_user)):
    db = get_db()
    now_dt = datetime.datetime.utcnow()
    start_of_month = datetime.datetime(now_dt.year, now_dt.month, 1)

    pipeline = [
        {"$match": {"userId": user.sub, "createdAt": {"$gte": start_of_month}}},
        {"$group": {"_id": "$userId", "total_credits": {"$sum": "$credits_used"}}}
    ]
    result = await db.usage.aggregate(pipeline).to_list(None)

    return result[0] if result else {"userId": user.sub, "total_credits": 0}
