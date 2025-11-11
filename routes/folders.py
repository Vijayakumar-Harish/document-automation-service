from fastapi import APIRouter, Depends
from app.auth import get_current_user, require_role
from app.db import get_db
from bson import ObjectId

router = APIRouter(prefix="/v1/folders", tags=["folders"])

@router.get("",dependencies=[Depends(require_role("user", "admin", "support", "moderator"))])
async def list_folders(user=Depends(get_current_user)):
    db = get_db()
    pipeline = [
        {"$match":{"ownerId":user.sub}},
        {"$lookup":{"from":"document_tags","localField":"_id", "foreignField":"tagId", "as":"dts"}},
        {"$addFields":{"count":{"$size":"$dts"}}},
        {"$project":{"name":1, "count":1}}
    ]
    cur = db.tags.aggregate(pipeline)
    res = await cur.to_list(length=100)
    return [{"name":r["name"], "count": r.get("count",0)} for r in res]

@router.get("/{tag}/docs",dependencies=[Depends(require_role("user", "admin", "support", "moderator"))])
async def docs_in_folder(tag: str, user=Depends(get_current_user)):
    db = get_db()
    t = await db.tags.find_one({"ownerId":user.sub, "name":tag})
    if not t:
        return []
    dts = await db.document_tags.find({"tagId":t["_id"], "isPrimary":True}).to_list(length=100)
    ids = [d["documentId"] for d in dts]
    docs = await db.documents.find({"_id": {"$in":ids}}).to_list(length=100)
    for d in docs:
        d["id"] = str(d["_id"]); d.pop("_id", None)
    return docs