from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.auth import get_current_user, require_role
from app.db import get_db
from app.utils import now
from app.schemas import ActionRequest
from bson import ObjectId
import csv, io, datetime, time, base64
from app.metrics_registry import db_query_latency_seconds, errors_total
from app.config import settings
from openai import AsyncOpenAI
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

router = APIRouter(prefix="/v1/actions", tags=["actions"])
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

async def run_openai_agent(prompt: str, mode: str) -> str:
    try:
        response = await openai_client.responses.create(
            model="gpt-4o-mini",
            input=[{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
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

    # --- Record credit usage ---
    await db.usage.insert_one({
        "userId": user.sub,
        "credits_used": settings.CREDITS_PER_ACTION,
        "action": payload.actions,
        "createdAt": now(),
    })

    # --- Validate scope ---
    scope = payload.scope
    if scope.type not in {"folder", "tag"}:
        raise HTTPException(status_code=400, detail="Unsupported scope type")

    # --- Collect docs in scope ---
    if scope.type == "folder" and scope.name:
        docs_query = {"folder": scope.name}
    elif scope.type == "tag" and scope.name:
        tag = await db.tags.find_one({"name": scope.name, "ownerId": user.sub})
        if not tag:
            raise HTTPException(status_code=404, detail="Tag not found")
        tag_id = tag["_id"]

        doc_tags = await db.document_tags.find({
            "$or": [{"tagId": tag_id}, {"tagId": str(tag_id)}]
        }).to_list(None)
        if not doc_tags:
            raise HTTPException(status_code=404, detail="No linked documents for this tag")

        doc_ids = [
            ObjectId(d["documentId"]) if ObjectId.is_valid(str(d["documentId"])) else d["documentId"]
            for d in doc_tags
        ]
        docs_query = {"_id": {"$in": doc_ids}}
    else:
        raise HTTPException(status_code=400, detail="Invalid scope input")

    # --- Query docs ---
    docs = await db.documents.find(docs_query).to_list(None)
    db_query_latency_seconds.observe(time.time() - start_time)
    if not docs:
        raise HTTPException(status_code=404, detail="No documents found for scope")

    # --- Build AI context ---
    context_parts = []
    for d in docs:
        filename = d.get("filename", "unknown")
        text = (d.get("textContent") or "").strip()
        context_parts.append(f"📄 File: {filename}\n{text[:1200]}")
    context_text = "\n\n".join(context_parts)

    # --- User prompt ---
    user_prompt = payload.messages[0]["content"] if payload.messages else "Summarize these documents."
    full_prompt = (
        f"{user_prompt}\n\n"
        f"Here are OCR-extracted texts from {len(docs)} documents:\n"
        f"{context_text}\n\n"
        f"Generate insights, summaries, or CSV data as requested."
    )

    # --- Run OpenAI tasks ---
    text_output, csv_output = None, None
    if "make_document" in payload.actions:
        text_output = await run_openai_agent(full_prompt, "make_document")
    if "make_csv" in payload.actions:
        csv_prompt = full_prompt + "\n\nOutput a CSV with headers summarizing key totals or data."
        csv_output = await run_openai_agent(csv_prompt, "make_csv")

    fs = AsyncIOMotorGridFSBucket(db)
    response_payload = {
        "message": "OpenAI Actions executed successfully",
        "credits_used": settings.CREDITS_PER_ACTION,
        "new_docs": [],
        "downloads": {},
    }

    # --- Save Text Output ---
    if text_output:
        filename_txt = f"summary_{scope.name or 'scope'}.txt"
        text_bytes = text_output.encode("utf-8")
        upload_stream = fs.open_upload_stream(
            filename_txt,
            metadata={"ownerId": user.sub, "contentType": "text/plain"},
        )
        await upload_stream.write(text_bytes)
        await upload_stream.close()
        gridfs_id = upload_stream._id

        result = await db.documents.insert_one({
            "ownerId": user.sub,
            "filename": filename_txt,
            "mime": "text/plain",
            "gridfsId": gridfs_id,
            "createdAt": now(),
        })
        doc_id = str(result.inserted_id)
        response_payload["new_docs"].append(doc_id)
        response_payload["downloads"]["text"] = f"/v1/docs/{doc_id}/download"

    # --- Save CSV Output ---
    if csv_output:
        filename_csv = f"report_{scope.name or 'scope'}.csv"
        csv_bytes = csv_output.encode("utf-8")
        upload_stream = fs.open_upload_stream(
            filename_csv,
            metadata={"ownerId": user.sub, "contentType": "text/csv"},
        )
        await upload_stream.write(csv_bytes)
        await upload_stream.close()
        gridfs_id = upload_stream._id

        result = await db.documents.insert_one({
            "ownerId": user.sub,
            "filename": filename_csv,
            "mime": "text/csv",
            "gridfsId": gridfs_id,
            "createdAt": now(),
        })
        doc_id = str(result.inserted_id)
        response_payload["new_docs"].append(doc_id)
        response_payload["downloads"]["csv"] = f"/v1/docs/{doc_id}/download"

    # --- Audit log ---
    await db.audit_logs.insert_one({
        "at": now(),
        "userId": user.sub,
        "action": "run_actions",
        "entityType": "scope",
        "metadata": {
            "scope": scope.model_dump(),
            "actions": payload.actions,
            "newDocs": response_payload["new_docs"],
        },
    })

    return response_payload
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
