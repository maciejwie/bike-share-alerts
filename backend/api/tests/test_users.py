"""
Tests for user management endpoints.
"""


class TestDeviceTokenRegistration:
    def test_registers_device_token_for_existing_user(self, client, mock_db, mock_auth):
        """Should update device token for existing user"""
        mock_cursor, _ = mock_db
        mock_cursor.rowcount = 1

        response = client.post("/users/device-token", json={"device_token": "abc123token"})

        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # Verify UPDATE was called
        update_call = mock_cursor.execute.call_args_list[0]
        assert "UPDATE users" in update_call[0][0]
        assert update_call[0][1] == ("abc123token", "test@example.com")

    def test_creates_user_if_not_exists(self, client, mock_db, mock_auth):
        """Should create user if they don't exist"""
        mock_cursor, _ = mock_db
        mock_cursor.rowcount = 0  # UPDATE affected 0 rows

        response = client.post("/users/device-token", json={"device_token": "abc123token"})

        assert response.status_code == 200

        # Verify INSERT was called after UPDATE returned 0 rows
        insert_call = mock_cursor.execute.call_args_list[1]
        assert "INSERT INTO users" in insert_call[0][0]
        assert insert_call[0][1] == ("test@example.com", "abc123token")

    def test_requires_authentication(self, client):
        """Should require authentication"""
        response = client.post("/users/device-token", json={"device_token": "abc123token"})

        # Without mock_auth, should get 403 Forbidden
        assert response.status_code == 403

    def test_validates_device_token_format(self, client, mock_db, mock_auth):
        """Should validate device token is provided"""
        response = client.post("/users/device-token", json={})

        assert response.status_code == 422  # Validation error


class TestDeviceTokenRemoval:
    def test_removes_device_token(self, client, mock_db, mock_auth):
        """Should set device token to NULL"""
        mock_cursor, _ = mock_db
        response = client.delete("/users/device-token")

        assert response.status_code == 200
        assert response.json()["status"] == "success"

        # Verify UPDATE was called with NULL
        update_call = mock_cursor.execute.call_args_list[0]
        assert "UPDATE users" in update_call[0][0]
        assert "device_token = NULL" in update_call[0][0]
        assert update_call[0][1] == ("test@example.com",)

    def test_requires_authentication(self, client):
        """Should require authentication"""
        response = client.delete("/users/device-token")

        # Without mock_auth, should get 403 Forbidden
        assert response.status_code == 403
