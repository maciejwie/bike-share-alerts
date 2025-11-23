import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from index import app
from auth import get_current_user, get_admin_user


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
    app.dependency_overrides[get_current_user] = lambda: "test_user_id"
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def mock_admin_auth():
    app.dependency_overrides[get_admin_user] = lambda: True
    yield
    app.dependency_overrides.pop(get_admin_user, None)
