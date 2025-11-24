from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from auth import get_admin_user, get_current_user
from index import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def mock_db():
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("db.get_db_connection", return_value=mock_conn):
        yield mock_cursor


@pytest.fixture
def mock_auth():
    test_user_email = "test@example.com"
    app.dependency_overrides[get_current_user] = lambda: test_user_email
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def mock_admin_auth():
    app.dependency_overrides[get_admin_user] = lambda: True
    yield
    app.dependency_overrides.pop(get_admin_user, None)
