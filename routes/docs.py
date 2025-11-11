from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from bson import ObjectId
from app.auth import get_current_user, require_role
from app.db import get_db
from app.utils import now

router = APIRouter(prefix="/v1/docs", tags=["docs"])

@router.post("", summary="Upload document", dependencies=[Depends(require_role("user","admin"))])
async def upload_doc(primaryTag: str = Query(...), secondaryTags: str = Query(None), file: UploadFile = File(...), user=Depends(get_current_user)):
    db = get_db()
    data = await file.read()
    doc = {
        "ownerId": user.sub,
        "filename": file.filename,
        "mime": file.content_type,
        "textContent": None,
        "raw": data.decode("latin1") if isinstance(data, (bytes, bytearray)) else str(data),
        "createdAt": now()
    }
    r = await db.documents.insert_one(doc)
    doc_id = r.inserted_id

    # ensure primary tag exists
    tag = await db.tags.find_one({"ownerId": user.sub, "name": primaryTag})
    if not tag:
        tr = await db.tags.insert_one({"name": primaryTag, "ownerId": user.sub, "createdAt": now()})
        tag_id = tr.inserted_id
    else:
        tag_id = tag["_id"]

    # add document_tag as primary
    await db.document_tags.insert_one({"documentId": doc_id, "tagId": tag_id, "isPrimary": True})

    # secondary tags
    if secondaryTags:
        for tname in [t.strip() for t in secondaryTags.split(",") if t.strip()]:
            tt = await db.tags.find_one({"ownerId": user.sub, "name": tname})
            if not tt:
                tr = await db.tags.insert_one({"name": tname, "ownerId": user.sub, "createdAt": now()})
                tid = tr.inserted_id
            else:
                tid = tt["_id"]
            await db.document_tags.insert_one({"documentId": doc_id, "tagId": tid, "isPrimary": False})

    await db.audit_logs.insert_one({"at": now(), "userId": user.sub, "action": "upload", "entityType": "document", "entityId": str(doc_id), "metadata": {"filename": file.filename}})
    return {"id": str(doc_id)}

@router.get("/{id}",dependencies=[Depends(require_role("user", "admin", "support", "moderator"))])
async def get_doc(id: str, user=Depends(get_current_user)):
    db = get_db()
    doc = await db.documents.find_one({"_id": ObjectId(id)})
    if not doc:
        raise HTTPException(status_code=404, detail="not found")
    if doc.get("ownerId") != user.sub and user.role != "admin":
        raise HTTPException(status_code=403, detail="forbidden")
    doc["id"] = str(doc["_id"])
    doc.pop("_id", None)
    return doc
