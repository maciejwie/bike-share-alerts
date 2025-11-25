import hashlib

import pytest
from fastapi.testclient import TestClient

from index import app


@pytest.fixture
def client():
    return TestClient(app)


def test_valid_api_key_updates_last_used(client, mock_db):
    """Test that a valid API key allows access and updates last_used_at"""
    mock_cursor, _ = mock_db
    test_key = "sk_live_test123"
    key_hash = hashlib.sha256(test_key.encode()).hexdigest()

    # Mock the SELECT query to return a valid user (email)
    test_user_email = "test@example.com"

    # First call is auth check (returns user), second call is routes fetch (returns empty list)
    mock_cursor.fetchone.return_value = [test_user_email]
    mock_cursor.fetchall.return_value = []

    response = client.get("/routes", headers={"Authorization": f"Bearer {test_key}"})

    assert response.status_code == 200

    # Verify the cursor was used for SELECT (auth), UPDATE (auth), and SELECT (routes)
    assert mock_cursor.execute.call_count >= 2

    # Verify SELECT was called in auth
    select_call = mock_cursor.execute.call_args_list[0]
    assert "SELECT user_email FROM api_keys" in select_call[0][0]
    assert key_hash in select_call[0][1]

    # Verify UPDATE was called in auth
    update_call = mock_cursor.execute.call_args_list[1]
    assert "UPDATE api_keys SET last_used_at" in update_call[0][0]


def test_invalid_api_key_returns_401(client, mock_db):
    """Test that an invalid API key returns 401"""
    mock_cursor, _ = mock_db
    test_key = "sk_live_invalid"

    # Mock the SELECT query to return no user
    mock_cursor.fetchone.return_value = None

    response = client.get("/routes", headers={"Authorization": f"Bearer {test_key}"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API Key"


def test_missing_auth_header_returns_403(client):
    """Test that missing auth header returns 403"""
    response = client.get("/routes")

    assert response.status_code == 403
