from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from datetime import datetime, timezone

from app.db import get_db
from app.auth import require_role, get_current_user

router = APIRouter(prefix="/admin", tags=["Admin"])

ALLOWED_ROLES = {"user", "support", "admin"}


@router.get("/users", dependencies=[Depends(require_role("admin"))])
async def list_all_users(db=Depends(get_db)):
    """
    List all users (admin only).
    """
    # db = get_db()
    users = await db.users.find({}, {"email": 1, "role": 1, "created_at": 1}).to_list(None)
    return [
        {
            "id": str(u["_id"]),
            "email": u["email"],
            "role": u.get("role", "user"),
            "createdAt": u.get("created_at"),
        }
        for u in users
    ]


@router.post("/users/{user_id}/role", dependencies=[Depends(require_role("admin"))])
async def change_user_role(user_id: str, new_role: str, admin=Depends(get_current_user),db=Depends(get_db)):
    # db = get_db()

    if new_role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role: {new_role}")

    if admin.sub == user_id:
        raise HTTPException(status_code=400, detail="Admins cannot change their own role")

    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"role": new_role}})

    await db.audit_logs.insert_one({
        "action": "change_user_role",
        "performedBy": str(admin.sub),
        "targetUser": user_id,
        "newRole": new_role,
        "at": datetime.now(timezone.utc),
    })

    return {"message": f"User {user['email']} role updated to {new_role}"}

