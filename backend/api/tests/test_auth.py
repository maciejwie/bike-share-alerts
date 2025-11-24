import hashlib
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
from index import app


@pytest.fixture
def client():
    return TestClient(app)


def test_valid_api_key_updates_last_used(client):
    """Test that a valid API key allows access and updates last_used_at"""
    test_key = "sk_live_test123"
    key_hash = hashlib.sha256(test_key.encode()).hexdigest()

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    # Mock the SELECT query to return a valid user
    mock_cursor.fetchone.return_value = ["test_user_id"]

    # Mock fetchall for the routes query
    mock_cursor.fetchall.return_value = []

    with patch("db.get_db_connection", return_value=mock_conn):
        response = client.get(
            "/routes",
            headers={"Authorization": f"Bearer {test_key}"}
        )

    assert response.status_code == 200

    # Verify the cursor was used for SELECT (auth), UPDATE (auth), and SELECT (routes)
    assert mock_cursor.execute.call_count >= 2

    # Verify SELECT was called in auth
    select_call = mock_cursor.execute.call_args_list[0]
    assert "SELECT user_id FROM api_keys" in select_call[0][0]
    assert key_hash in select_call[0][1]

    # Verify UPDATE was called in auth (this would fail with the bug)
    update_call = mock_cursor.execute.call_args_list[1]
    assert "UPDATE api_keys SET last_used_at" in update_call[0][0]

    # Verify cursor close was called (would be called twice - once in auth, once in routes)
    assert mock_cursor.close.call_count >= 1

    # Verify commit was called
    mock_conn.commit.assert_called()


def test_invalid_api_key_returns_401(client):
    """Test that an invalid API key returns 401"""
    test_key = "sk_live_invalid"

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    # Mock the SELECT query to return no user
    mock_cursor.fetchone.return_value = None

    with patch("db.get_db_connection", return_value=mock_conn):
        response = client.get(
            "/routes",
            headers={"Authorization": f"Bearer {test_key}"}
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API Key"

    # Verify cursor was closed even on error path
    mock_cursor.close.assert_called_once()


def test_missing_auth_header_returns_403(client):
    """Test that missing auth header returns 403"""
    response = client.get("/routes")

    assert response.status_code == 403
