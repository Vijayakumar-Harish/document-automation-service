from fastapi import APIRouter, Depends, HTTPException
from app.db import get_db
from app.auth import get_current_user, require_role
from app.utils import now
from bson import ObjectId

router = APIRouter(prefix="/v1/folders", tags=["folders"])

@router.get("", summary="List all primary-tag folders", dependencies=[Depends(require_role("user", "admin", "support"))])
async def list_folders(user=Depends(get_current_user)):
    """
    Returns a list of all tags (primary-tag folders).
    - Normal users: only their own tags.
    - Admins: tags from all users (global view).
    """
    db = get_db()

    match_stage = {}
    if user.role == "user":  # regular user sees only their own folders
        match_stage["ownerId"] = user.sub

    pipeline = []
    if match_stage:
        pipeline.append({"$match": match_stage})

    pipeline.extend([
        {
            "$lookup": {
                "from": "document_tags",
                "localField": "_id",
                "foreignField": "tagId",
                "as": "linked_docs"
            }
        },
        {
            "$project": {
                "_id": 1,
                "name": 1,
                "ownerId": 1,
                "count": {
                    "$size": {
                        "$filter": {
                            "input": "$linked_docs",
                            "as": "link",
                            "cond": {"$eq": ["$$link.isPrimary", True]}
                        }
                    }
                }
            }
        },
        {"$sort": {"name": 1}}
    ])

    folders = await db.tags.aggregate(pipeline).to_list(None)

    if user.role != "admin":
        folders = [f for f in folders if f["count"] > 0]

    return [
        {
            "id": str(f["_id"]),
            "name": f["name"],
            "count": f.get("count", 0),
            "ownerId": f.get("ownerId")
        }
        for f in folders
    ]


@router.get("/{tag}/docs", summary="List documents for a specific tag", dependencies=[Depends(require_role("user", "admin"))])
async def list_docs_by_tag(tag: str, user=Depends(get_current_user)):
    """
    Returns all documents where the given tag is the primary tag (folder view).
    """
    db = get_db()

    tag_filter = {"name": tag}
    if user.role != "admin":
        tag_filter["ownerId"] = user.sub

    tag_doc = await db.tags.find_one(tag_filter)
    if not tag_doc:
        raise HTTPException(status_code=404, detail="Tag not found")
    tag_id = tag_doc["_id"]
    doc_tags = await db.document_tags.find({"tagId": tag_id, "isPrimary": True}).to_list(None)
    doc_ids = [ObjectId(d["documentId"]) for d in doc_tags if ObjectId.is_valid(d["documentId"])]

    docs = await db.documents.find({"_id": {"$in": doc_ids}}).to_list(None)

    return [
        {
            "id": str(d["_id"]),
            "filename": d.get("filename"),
            "mime": d.get("mime"),
            "createdAt": d.get("createdAt"),
            "tags": [tag],
        }
        for d in docs
    ]
