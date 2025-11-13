# tests/test_actions.py
from bson import ObjectId

async def test_actions_tag_scope_requires_docs(client, test_db, make_token):
    token = make_token("u1", "u1@test.com", "user")

    payload = {
        "scope": {"type": "tag", "name": "unknown"},
        "messages": [{"role": "user", "content": "summarize"}],
        "actions": ["make_document"]
    }

    resp = await client.post(
        "/v1/actions/run",
        headers={"Authorization": f"Bearer {token}"},
        json=payload
    )
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Tag not found"


async def test_credits_consumed(client, test_db, make_token):
    token = make_token("uX", "u@test.com", "user")

    # Upload 1 doc
    await client.post(
        "/v1/docs",
        headers={"Authorization": f"Bearer {token}"},
        data={"primaryTag": "demo"},
        files={"file": ("x.png", b"img", "image/png")}
    )

    # Run action
    payload = {
        "scope": {"type": "tag", "name": "demo"},
        "messages": [{"role": "user", "content": "summarize"}],
        "actions": ["make_document"]
    }
    resp = await client.post(
        "/v1/actions/run",
        headers={"Authorization": f"Bearer {token}"},
        json=payload
    )
    assert resp.status_code == 200

    # Check usage collection
    usage = await test_db.usage.find_one({"userId": "uX"})
    assert usage is not None
    assert usage["credits"] == 5  # default
