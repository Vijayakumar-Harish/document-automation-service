async def test_webhook_rate_limit(client, user_token):
    payload = {"source":"scanner-01","imageId":"img_1","text":"Limited-time SALE unsubscribe: mailto:stop@brand.com", "meta":{}}
    for i in range(3):
        r = await client.post("/v1/webhooks/ocr", json=payload, headers={"authorization":f"Bearer {user_token}"})
        assert r.status_code == 200
    r = await client.post("/v1/webhooks/ocr", json=payload, headers={"authorization":f"Bearer {user_token}"})
    assert r.status_code == 200
    assert r.json().get("status") == "rate_limited"