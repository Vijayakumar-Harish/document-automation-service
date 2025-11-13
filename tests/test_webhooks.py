# tests/test_webhooks.py

async def test_webhook_classification(client, make_token):
    token = make_token("u1", "u@test.com", "user")

    payload = {
        "source": "scanner",
        "imageId": "img1",
        "text": "LIMITED TIME SALE! unsubscribe: mailto:test@brand.com",
        "meta": {}
    }

    resp = await client.post(
        "/v1/webhooks/ocr",
        headers={"Authorization": f"Bearer {token}"},
        json=payload
    )
    assert resp.status_code == 200
    assert resp.json()["classification"] == "ad"


async def test_webhook_rate_limit(client, make_token):
    token = make_token("u2", "u2@test.com", "user")

    payload = {
        "source": "scanner",
        "imageId": "i1",
        "text": "SALE unsubscribe: mailto:x@y.com",
    }

    # call 3 times OK
    for _ in range(3):
        resp = await client.post(
            "/v1/webhooks/ocr",
            headers={"Authorization": f"Bearer {token}"},
            json=payload
        )
        assert resp.status_code == 200

    # 4th → rate limited
    resp = await client.post(
        "/v1/webhooks/ocr",
        headers={"Authorization": f"Bearer {token}"},
        json=payload
    )
    assert resp.json()["status"] == "rate_limited"
