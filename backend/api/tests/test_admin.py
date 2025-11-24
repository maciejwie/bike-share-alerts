def test_create_key(client, mock_db, mock_admin_auth):
    # First call checks for existing key (returns None)
    # Second call inserts new key
    mock_db.fetchone.side_effect = [None, ["new_key_id"]]

    response = client.post(
        "/admin/keys", json={"user_email": "test@example.com", "label": "Test Key"}
    )
    assert response.status_code == 201
    data = response.json()
    assert "key" in data
    assert data["key"].startswith("sk_live_")
    assert data["key_id"] == "new_key_id"
    assert data["existed"] is False

    # Verify that what was inserted was hashed
    insert_call = mock_db.execute.call_args_list[1]  # Second call is the INSERT
    inserted_key = insert_call[0][1][1]
    assert inserted_key != data["key"]
    assert len(inserted_key) == 64


def test_list_keys(client, mock_db, mock_admin_auth):
    mock_db.fetchall.return_value = []
    response = client.get("/admin/keys")
    assert response.status_code == 200
    assert response.json() == {"keys": []}


def test_revoke_key(client, mock_db, mock_admin_auth):
    mock_db.rowcount = 1
    response = client.delete("/admin/keys/some_id")
    assert response.status_code == 204
