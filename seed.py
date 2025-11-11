import asyncio
from app.db import get_client, get_db
from datetime import datetime

async def seed():
    db = get_db()
    await db.users.delete_many({})
    await db.documents.delete_many({})
    await db.tags.delete_many({})
    await db.document_tags.delete_many({})
    await db.usage.delete_many({})
    await db.tasks.delete_many({})
    await db.audit_logs.delete_many({})
    await db.users.insert_many([
        {"_id":"user1","email":"harish@oneshot.com", "role":"user"},
        {"_id":"user2","email":"bharath@oneshot.com", "role":"support"},
        {"_id":"admin","email":"admin@oneshot.com", "role":"admin"},
    ])
    t = {"name":"invoices-2025","ownerId":"user1","createdAt":datetime.utcnow()}
    tr = await db.tags.insert_one(t)
    d = {"ownerId":"user1", "filename":"inv-jan.pdf", "mime":"application/pdf","textContent":"Invoice 1 amount due 100","raw":"", "createdAt":datetime.utcnow()}
    dr = await db.documents.insert_one(d)
    await db.document_tags.insert_one({"documentId":dr.inserted_id,"tagId":tr.inserted_id, "isPrimary":True})
    print("Seed is successful")

if __name__ == "__main__":
    asyncio.run(seed())