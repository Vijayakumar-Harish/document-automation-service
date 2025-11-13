# tests/test_folders.py
import pytest

async def test_list_folders(client, make_token):
    token = make_token("u1", "u1@test.com", "user")

    resp = await client.get(
        "/v1/folders",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
