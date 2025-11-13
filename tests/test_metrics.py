async def test_metrics_endpoint(client, make_token):
    token = make_token("admin1", "a@test.com", "admin")

    resp = await client.get(
        "/v1/metrics",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "docs_total" in body
    assert "folders_total" in body
    assert "actions_month" in body
    assert "tasks_today" in body
