from fastapi import APIRouter, Depends, HTTPException, Body
from bson import ObjectId
from app.auth import get_current_user, require_role
from app.db import get_db
from services.processor import mock_process
from services.usage import charge_user, get_monthly_usage
from app.utils import now

router = APIRouter(prefix="/v1/actions", tags=["actions"])

@router.post("/run",dependencies=[Depends(require_role("user", "admin"))])
async def run_action(payload: dict = Body(...), user=Depends(get_current_user)):
    scope = payload.get("scope", {})
    # rule: either folder or files
    if scope.get("type") == "folder" and scope.get("ids"):
        raise HTTPException(status_code=400, detail="scope must be folder OR ids, not both")
    db = get_db()
    docs = []
    if scope.get("type") == "folder":
        tag = await db.tags.find_one({"ownerId": user.sub, "name": scope.get("name")})
        if not tag:
            docs = []
        else:
            dts = await db.document_tags.find({"tagId": tag["_id"], "isPrimary": True}).to_list(length=100)
            ids = [d["documentId"] for d in dts]
            docs = await db.documents.find({"_id": {"$in": ids}}).to_list(length=100)
    elif scope.get("type") == "files":
        ids = [ObjectId(i) for i in (scope.get("ids") or [])]
        docs = await db.documents.find({"_id": {"$in": ids}}).to_list(length=100)
    else:
        raise HTTPException(status_code=400, detail="invalid scope")

    created = []
    for action in payload.get("actions", []):
        out = mock_process(payload.get("messages", []), action, {"documents": docs})
        if out:
            doc = {"ownerId": user.sub, "filename": out.get("filename"), "mime": out.get("mime"), "textContent": out.get("text"), "createdAt": now()}
            r = await db.documents.insert_one(doc)
            created.append(str(r.inserted_id))

    # charge credits
    await charge_user(user.sub, 5)
    await db.audit_logs.insert_one({"at": now(), "userId": user.sub, "action":"run_actions", "entityType":"actions", "entityId": None, "metadata": {"created": created}})
    return {"created": created}

@router.get("/usage/month", dependencies=[Depends(require_role("user", "admin", "support", "moderator"))])
async def usage_month(user=Depends(get_current_user)):
    total = await get_monthly_usage(user.sub)
    return {"userId": user.sub, "credits_this_month": total}
