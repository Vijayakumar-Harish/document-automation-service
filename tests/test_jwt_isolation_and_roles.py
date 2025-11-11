async def test_user_cannot_read_others(client, user_token, admin_token):
    files = {"file": ("adm.txt", b"secret", "text/plain")}
    r = await client.post("/v1/docs?primaryTag=private", files=files, headers={"authorization":f"Bearer {admin_token}"})
    assert r.status_code == 200
    docid = r.json()["id"]
    r2 = await client.get(f"/v1/docs/{docid}", headers={"authorization":f"Bearer {user_token}"})
    assert r2.status_code == 403