import os
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

    # Mock commit/rollback/close to do nothing
    mock_conn.commit.return_value = None
    mock_conn.rollback.return_value = None
    mock_conn.close.return_value = None

    # Patch db._pool to return our mock pool
    mock_pool = MagicMock()
    mock_pool.getconn.return_value = mock_conn
    mock_pool.putconn.return_value = None

    # Reset global pool to ensure get_db_pool creates a new one (or uses our patch)
    import db

    db._pool = None

    # Patch both _pool (if already initialized) and ThreadedConnectionPool (if initializing)
    with (
        patch("db._pool", mock_pool),
        patch("psycopg2.pool.ThreadedConnectionPool", return_value=mock_pool),
    ):
        yield mock_cursor, mock_conn


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


@pytest.fixture(autouse=True)
def set_env():
    with (
        patch.dict(os.environ, {"DATABASE_URL": "postgresql://user:pass@localhost/db"}),
        patch("psycopg2.pool.ThreadedConnectionPool"),
    ):
        yield
