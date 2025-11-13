# tests/test_docs.py
import base64
import io
from bson import ObjectId

async def test_upload_document(client, make_token):
    token = make_token("u1", "user1@test.com", "user")

    file_content = b"fake-image"
    files = {
        "file": ("sample.png", file_content, "image/png")
    }
    data = {
        "primaryTag": "invoice"
    }

    resp = await client.post(
        "/v1/docs",
        headers={"Authorization": f"Bearer {token}"},
        data=data,
        files=files
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "id" in body


async def test_primary_tag_uniqueness(client, test_db, make_token):
    """Ensure exactly ONE primary tag per document"""
    token = make_token("u1", "user1@test.com", "user")

    # Upload
    file_data = ("x.png", b"123", "image/png")
    resp = await client.post(
        "/v1/docs",
        headers={"Authorization": f"Bearer {token}"},
        data={"primaryTag": "finance"},
        files={"file": file_data},
    )
    doc_id = resp.json()["id"]

    # Check DB
    links = await test_db.document_tags.find({"documentId": ObjectId(doc_id)}).to_list(None)
    primaries = [x for x in links if x["isPrimary"]]
    assert len(primaries) == 1
