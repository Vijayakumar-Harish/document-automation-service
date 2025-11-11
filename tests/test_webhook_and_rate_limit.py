async def test_webhook_rate_limit_atomic(client, user_token):
    payload = {
        "source": "scanner-01",
        "imageId": "img_1",
        "text": "Limited time SALE unsubscribe: mailto:stop@brand.com",
        "meta": {}
    }
    for i in range(5):
        r = await client.post("/v1/webhooks/ocr", json=payload, headers={"authorization": f"Bearer {user_token}"})
        assert r.status_code == 200
        if i < 3:
            assert "taskId" in r.json()
        else:
            assert r.json().get("status") == "rate_limited"
