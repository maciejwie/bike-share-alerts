from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from auth import get_current_user, verify_cron_secret
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

    from unittest.mock import patch

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
    yield test_user_email
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def mock_cron_auth():
    app.dependency_overrides[verify_cron_secret] = lambda: True
    yield
    app.dependency_overrides.pop(verify_cron_secret, None)


class TestCronHeartbeat:
    """Tests for POST /cron/heartbeat endpoint"""

    def test_requires_authentication(self, client, mock_db):
        """Should require cron secret authentication"""
        # Don't override auth, so it requires real auth
        response = client.get("/cron/heartbeat")
        assert response.status_code == 403  # FastAPI returns 403 for missing auth

    def test_returns_monitoring_stats(self, client, mock_db, mock_cron_auth):
        """Should return stats about activated and monitored trips"""
        mock_cursor, _mock_conn = mock_db

        # Mock queries
        mock_cursor.fetchall.side_effect = [
            [],  # Routes to activate
            [],  # STARTING trips
            [],  # DOCKING trips
        ]

        response = client.get("/cron/heartbeat")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert "activated_routes" in data
        assert "monitoring_starting" in data
        assert "monitoring_docking" in data

    def test_activates_routes_and_monitors(self, client, mock_db, mock_cron_auth):
        """Should activate routes and monitor trips"""
        mock_cursor, _mock_conn = mock_db

        route_id = str(uuid4())
        trip_id = str(uuid4())

        mock_cursor.fetchall.side_effect = [
            # Routes to activate
            [(route_id, "user@example.com", datetime.now(UTC).time(), 15)],
            # Station statuses for check_start_stations (during activation)
            [(123, 5), (456, 2)],
            # STARTING trips
            [(trip_id, route_id, "user@example.com", 123, 5)],
            # Station statuses for monitoring STARTING trips
            [(123, 5), (456, 2)],
            # DOCKING trips
            [],
        ]
        mock_cursor.fetchone.side_effect = [
            trip_id,  # Created trip ID
            ([123, 456], 2),  # Route config for check_start_stations (during activation)
            ([123, 456], 2),  # Route config for check_start_stations (during monitoring)
        ]

        from unittest.mock import patch

        with patch("routers.trips.send_bike_alert"):
            response = client.get("/cron/heartbeat")

        assert response.status_code == 200
        data = response.json()
        assert data["activated_routes"] >= 0
        assert data["monitoring_starting"] >= 0


class TestTripStart:
    """Tests for POST /trips/{trip_id}/start endpoint"""

    def test_requires_authentication(self, client):
        """Should require user authentication"""
        trip_id = str(uuid4())
        response = client.post(f"/trips/{trip_id}/start")
        assert response.status_code == 403

    def test_transitions_starting_to_cycling(self, client, mock_db, mock_auth):
        """Should transition trip from STARTING to CYCLING"""
        mock_cursor, mock_conn = mock_db
        trip_id = str(uuid4())

        # Mock trip in STARTING state
        mock_cursor.fetchone.return_value = ["STARTING"]

        response = client.post(f"/trips/{trip_id}/start")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["trip_id"] == trip_id
        assert data["state"] == "CYCLING"

        # Verify UPDATE was called
        assert any("UPDATE trips" in str(call) for call in mock_cursor.execute.call_args_list)
        mock_conn.commit.assert_called()

    def test_rejects_trip_not_in_starting_state(self, client, mock_db, mock_auth):
        """Should reject if trip is not in STARTING state"""
        mock_cursor, _mock_conn = mock_db
        trip_id = str(uuid4())

        # Mock trip in CYCLING state
        mock_cursor.fetchone.return_value = ["CYCLING"]

        response = client.post(f"/trips/{trip_id}/start")

        assert response.status_code == 400
        assert "expected STARTING" in response.json()["detail"]

    def test_rejects_nonexistent_trip(self, client, mock_db, mock_auth):
        """Should reject if trip doesn't exist"""
        mock_cursor, _mock_conn = mock_db
        trip_id = str(uuid4())

        mock_cursor.fetchone.return_value = None

        response = client.post(f"/trips/{trip_id}/start")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestEnterDockingZone:
    """Tests for POST /trips/{trip_id}/enter-docking-zone endpoint"""

    def test_transitions_cycling_to_docking(self, client, mock_db, mock_auth):
        """Should transition trip from CYCLING to DOCKING"""
        mock_cursor, _mock_conn = mock_db
        trip_id = str(uuid4())
        route_id = str(uuid4())

        # Mock trip in CYCLING state
        mock_cursor.fetchone.side_effect = [
            ["CYCLING", route_id],  # Trip state check
            ([123], 3),  # Route config for check_end_stations
        ]
        mock_cursor.fetchall.return_value = [(123, 5)]  # Station status

        from unittest.mock import patch

        with patch("routers.trips.send_dock_alert"):
            response = client.post(
                f"/trips/{trip_id}/enter-docking-zone",
                json={"lat": 40.7589, "lon": -73.9851},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["state"] == "DOCKING"

        # Verify location was saved
        update_calls = [
            call for call in mock_cursor.execute.call_args_list if "UPDATE trips" in str(call)
        ]
        assert len(update_calls) > 0

    def test_rejects_trip_not_in_cycling_state(self, client, mock_db, mock_auth):
        """Should reject if trip is not in CYCLING state"""
        mock_cursor, _mock_conn = mock_db
        trip_id = str(uuid4())

        mock_cursor.fetchone.return_value = ["STARTING", str(uuid4())]

        response = client.post(
            f"/trips/{trip_id}/enter-docking-zone",
            json={"lat": 40.7589, "lon": -73.9851},
        )

        assert response.status_code == 400
        assert "expected CYCLING" in response.json()["detail"]

    def test_validates_location_data(self, client, mock_db, mock_auth):
        """Should validate location data format"""
        trip_id = str(uuid4())

        response = client.post(
            f"/trips/{trip_id}/enter-docking-zone",
            json={"lat": "invalid"},  # Missing lon, invalid type
        )

        assert response.status_code == 422  # Validation error


class TestEndTrip:
    """Tests for POST /trips/{trip_id}/end endpoint"""

    def test_marks_trip_complete(self, client, mock_db, mock_auth):
        """Should mark trip as COMPLETE"""
        mock_cursor, _mock_conn = mock_db
        trip_id = str(uuid4())

        mock_cursor.fetchone.return_value = ["DOCKING"]

        response = client.post(f"/trips/{trip_id}/end")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["state"] == "COMPLETE"

        # Verify UPDATE was called with COMPLETE state
        assert any("UPDATE trips" in str(call) for call in mock_cursor.execute.call_args_list)

    def test_rejects_already_completed_trip(self, client, mock_db, mock_auth):
        """Should reject if trip is already completed"""
        mock_cursor, _mock_conn = mock_db
        trip_id = str(uuid4())

        mock_cursor.fetchone.return_value = None  # Trip not found or completed

        response = client.post(f"/trips/{trip_id}/end")

        assert response.status_code == 404


class TestGetActiveTrip:
    """Tests for GET /trips/active endpoint"""

    def test_requires_authentication(self, client):
        """Should require user authentication"""
        response = client.get("/trips/active")
        assert response.status_code == 403

    def test_returns_active_trip(self, client, mock_db, mock_auth):
        """Should return user's active trip"""
        mock_cursor, _mock_conn = mock_db
        trip_id = str(uuid4())
        route_id = str(uuid4())

        mock_cursor.fetchone.return_value = [
            trip_id,
            route_id,
            "CYCLING",
            datetime.now(UTC),
            datetime.now(UTC),
            None,
        ]

        response = client.get("/trips/active")

        assert response.status_code == 200
        data = response.json()
        assert data["active_trip"] is not None
        assert data["active_trip"]["trip_id"] == trip_id
        assert data["active_trip"]["state"] == "CYCLING"

    def test_returns_null_when_no_active_trip(self, client, mock_db, mock_auth):
        """Should return null when user has no active trip"""
        mock_cursor, _mock_conn = mock_db
        mock_cursor.fetchone.return_value = None

        response = client.get("/trips/active")

        assert response.status_code == 200
        data = response.json()
        assert data["active_trip"] is None
