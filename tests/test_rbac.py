import pytest

async def test_user_cannot_access_others_docs(client, test_db, make_token):
    # User A uploads doc
    token_a = make_token("a1", "a@test.com", "user")
    token_b = make_token("b1", "b@test.com", "user")

    resp = await client.post(
        "/v1/docs",
        headers={"Authorization": f"Bearer {token_a}"},
        data={"primaryTag": "finance"},
        files={"file": ("x.png", b"img", "image/png")}
    )
    doc_id = resp.json()["id"]

    # User B tries to view it
    resp = await client.get(
        f"/v1/docs/{doc_id}",
        headers={"Authorization": f"Bearer {token_b}"}
    )
    assert resp.status_code == 403
