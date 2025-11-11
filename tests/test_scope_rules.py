async def test_scope_folder_and_ids_invalid(client, user_token):
    payload = {"scope":{"type":"folder","name":"invoices","ids":["a"]},"messages":[],"actions":["make_document"]}
    r = await client.post("/v1/actions/run", json=payload, headers={"authorization":f"Bearer {user_token}"})
    assert r.status_code == 400