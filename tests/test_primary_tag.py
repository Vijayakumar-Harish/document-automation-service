async def test_upload_creates_primary(client, user_token):
    files = {"file":("t.txt", b"hello", "text/plain")}
    r = await client.post("/v1/docs?primaryTag=invoices-2025", files=files, headers={"authorization":f"Bearer {user_token}"})
    assert r.status_code == 200
    assert "id" in r.json()