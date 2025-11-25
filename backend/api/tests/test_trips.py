from datetime import UTC, datetime, time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from routers.trips import (
    activate_scheduled_routes,
    check_end_stations,
    check_start_stations,
    monitor_active_trips,
)


@pytest.mark.asyncio
class TestActivateScheduledRoutes:
    """Tests for activate_scheduled_routes function"""

    async def test_activates_route_in_time_window(self):
        """Should create trip when current time is within alert window"""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()

        # Mock route data: target 9:00 AM, 15 min lead time = alert at 8:45 AM
        route_id = str(uuid4())
        mock_cursor.fetchall.return_value = [(route_id, "test@example.com", time(9, 0), 15)]
        mock_cursor.fetchone.return_value = [str(uuid4())]  # trip_id

        # Current time: 8:50 AM (within alert window)
        test_time = datetime(2025, 1, 15, 8, 50, 0, tzinfo=UTC)  # Wednesday

        with patch("routers.trips.check_start_stations", new_callable=AsyncMock) as mock_check:
            activated = await activate_scheduled_routes(mock_cursor, mock_conn, test_time)

        assert activated == 1
        # Verify trip was created
        assert mock_cursor.execute.call_count == 2  # SELECT + INSERT
        mock_conn.commit.assert_called_once()
        mock_check.assert_awaited_once()

    async def test_does_not_activate_before_alert_window(self):
        """Should not create trip before alert window starts"""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()

        route_id = str(uuid4())
        mock_cursor.fetchall.return_value = [(route_id, "test@example.com", time(9, 0), 15)]

        # Current time: 8:30 AM (before 8:45 AM alert window)
        test_time = datetime(2025, 1, 15, 8, 30, 0, tzinfo=UTC)

        activated = await activate_scheduled_routes(mock_cursor, mock_conn, test_time)

        assert activated == 0
        # Only SELECT query, no INSERT
        assert mock_cursor.execute.call_count == 1

    async def test_does_not_activate_after_alert_window(self):
        """Should not create trip after alert window expires"""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()

        route_id = str(uuid4())
        mock_cursor.fetchall.return_value = [(route_id, "test@example.com", time(9, 0), 15)]

        # Current time: 10:15 AM (more than 60 min after target)
        test_time = datetime(2025, 1, 15, 10, 15, 0, tzinfo=UTC)

        activated = await activate_scheduled_routes(mock_cursor, mock_conn, test_time)

        assert activated == 0

    async def test_converts_weekday_correctly(self):
        """Should correctly convert Python weekday (Mon=0) to our format (Sun=0)"""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()

        # Wednesday in Python (weekday=2) should convert to 3 in our format
        test_time = datetime(2025, 1, 15, 9, 0, 0, tzinfo=UTC)  # Wednesday

        await activate_scheduled_routes(mock_cursor, mock_conn, test_time)

        # Check that weekday=3 was used in the query
        call_args = mock_cursor.execute.call_args[0]
        assert call_args[1][0] == 3  # (2 + 1) % 7 = 3

    async def test_activates_multiple_routes(self):
        """Should activate multiple routes in same time window"""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()

        route1_id = str(uuid4())
        route2_id = str(uuid4())
        mock_cursor.fetchall.return_value = [
            (route1_id, "user1@example.com", time(9, 0), 15),
            (route2_id, "user2@example.com", time(9, 0), 15),
        ]
        mock_cursor.fetchone.side_effect = [str(uuid4()), str(uuid4())]

        test_time = datetime(2025, 1, 15, 8, 50, 0, tzinfo=UTC)

        with patch("routers.trips.check_start_stations", new_callable=AsyncMock) as mock_check:
            activated = await activate_scheduled_routes(mock_cursor, mock_conn, test_time)

        assert activated == 2
        assert mock_check.await_count == 2


@pytest.mark.asyncio
class TestCheckStartStations:
    """Tests for check_start_stations function"""

    async def test_sends_alert_on_first_check(self):
        """Should always send alert on first check (focused_station_id=None)"""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()

        trip_id = str(uuid4())
        route_id = str(uuid4())

        # Mock route config
        mock_cursor.fetchone.return_value = ([123, 456], 2)  # stations, threshold

        # Mock station statuses
        mock_cursor.fetchall.return_value = [
            (123, 5),  # 5 bikes at station 123
            (456, 1),  # 1 bike at station 456
        ]

        with patch("routers.trips.send_bike_alert", new_callable=AsyncMock) as mock_alert:
            await check_start_stations(
                mock_cursor, mock_conn, trip_id, route_id, "test@example.com", None, None
            )

        # Should send alert
        mock_alert.assert_awaited_once()
        # Should update trip with new focused station
        assert any("UPDATE trips" in str(call) for call in mock_cursor.execute.call_args_list)

    async def test_sends_alert_when_bike_count_changes(self):
        """Should send alert when bike count changes at focused station"""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()

        trip_id = str(uuid4())
        route_id = str(uuid4())

        mock_cursor.fetchone.return_value = ([123, 456], 2)
        mock_cursor.fetchall.return_value = [(123, 3), (456, 1)]  # Now 3 bikes (was 5)

        with patch("routers.trips.send_bike_alert", new_callable=AsyncMock) as mock_alert:
            await check_start_stations(
                mock_cursor, mock_conn, trip_id, route_id, "test@example.com", 123, 5
            )

        # Should send alert because count changed 5 -> 3
        mock_alert.assert_awaited_once()

    async def test_no_alert_when_nothing_changes(self):
        """Should not send alert when bike count is unchanged"""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()

        trip_id = str(uuid4())
        route_id = str(uuid4())

        mock_cursor.fetchone.return_value = ([123, 456], 2)
        mock_cursor.fetchall.return_value = [(123, 5), (456, 1)]  # Same as before

        with patch("routers.trips.send_bike_alert", new_callable=AsyncMock) as mock_alert:
            await check_start_stations(
                mock_cursor, mock_conn, trip_id, route_id, "test@example.com", 123, 5
            )

        # Should NOT send alert
        mock_alert.assert_not_awaited()
        # Should still update last_checked_at
        assert any("UPDATE trips" in str(call) for call in mock_cursor.execute.call_args_list)

    async def test_focuses_on_first_station_above_threshold(self):
        """Should focus on first station meeting threshold"""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()

        trip_id = str(uuid4())
        route_id = str(uuid4())

        mock_cursor.fetchone.return_value = ([123, 456, 789], 3)  # threshold=3
        mock_cursor.fetchall.return_value = [
            (123, 1),  # Below threshold
            (456, 5),  # Above threshold ← should focus here
            (789, 10),  # Also above, but not preferred
        ]

        with patch("routers.trips.send_bike_alert", new_callable=AsyncMock) as mock_alert:
            await check_start_stations(
                mock_cursor, mock_conn, trip_id, route_id, "test@example.com", None, None
            )

        # Should focus on station 456 (first above threshold)
        args = mock_alert.call_args[0]
        assert args[3] == 456  # focused_station_id (offset by 1 for cur param)
        assert args[4] == 5  # bike_count

    async def test_focuses_on_first_station_when_none_meet_threshold(self):
        """Should focus on first station even if none meet threshold"""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()

        trip_id = str(uuid4())
        route_id = str(uuid4())

        mock_cursor.fetchone.return_value = ([123, 456], 5)  # threshold=5
        mock_cursor.fetchall.return_value = [
            (123, 2),  # Below threshold
            (456, 1),  # Also below threshold
        ]

        with patch("routers.trips.send_bike_alert", new_callable=AsyncMock) as mock_alert:
            await check_start_stations(
                mock_cursor, mock_conn, trip_id, route_id, "test@example.com", None, None
            )

        # Should focus on first station by default
        args = mock_alert.call_args[0]
        assert args[3] == 123  # focused_station_id (offset by 1 for cur param)
        assert args[4] == 2  # bike_count

    async def test_sends_alert_when_focused_station_changes(self):
        """Should send alert when focused station changes"""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()

        trip_id = str(uuid4())
        route_id = str(uuid4())

        mock_cursor.fetchone.return_value = ([123, 456], 2)
        mock_cursor.fetchall.return_value = [
            (123, 0),  # Now depleted
            (456, 5),  # Now has bikes
        ]

        with patch("routers.trips.send_bike_alert", new_callable=AsyncMock) as mock_alert:
            # Was focused on 123, should switch to 456
            await check_start_stations(
                mock_cursor, mock_conn, trip_id, route_id, "test@example.com", 123, 5
            )

        mock_alert.assert_awaited_once()
        args = mock_alert.call_args[0]
        assert args[3] == 456  # New focused station (offset by 1 for cur param)


@pytest.mark.asyncio
class TestCheckEndStations:
    """Tests for check_end_stations function"""

    async def test_sends_alert_on_first_check(self):
        """Should always send alert on first dock check"""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()

        trip_id = str(uuid4())
        route_id = str(uuid4())

        mock_cursor.fetchone.return_value = ([123, 456], 3)  # stations, threshold
        mock_cursor.fetchall.return_value = [
            (123, 5),  # 5 docks at preferred station
            (456, 2),
        ]

        with patch("routers.trips.send_dock_alert", new_callable=AsyncMock) as mock_alert:
            await check_end_stations(
                mock_cursor, mock_conn, trip_id, route_id, "test@example.com", None, None
            )

        mock_alert.assert_awaited_once()

    async def test_sends_alert_when_dock_count_changes(self):
        """Should send alert when dock count changes"""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()

        trip_id = str(uuid4())
        route_id = str(uuid4())

        mock_cursor.fetchone.return_value = ([123], 3)
        mock_cursor.fetchall.return_value = [(123, 2)]  # Now 2 docks (was 5)

        with patch("routers.trips.send_dock_alert", new_callable=AsyncMock) as mock_alert:
            await check_end_stations(
                mock_cursor, mock_conn, trip_id, route_id, "test@example.com", 123, 5
            )

        mock_alert.assert_awaited_once()

    async def test_alert_level_based_on_station_preference(self):
        """Alert level should reflect which preferred station has docks"""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()

        trip_id = str(uuid4())
        route_id = str(uuid4())

        mock_cursor.fetchone.return_value = ([123, 456, 789], 3)
        mock_cursor.fetchall.return_value = [
            (123, 0),  # Preferred - no docks
            (456, 0),  # 2nd choice - no docks
            (789, 5),  # 3rd choice - has docks
        ]

        with patch("routers.trips.send_dock_alert", new_callable=AsyncMock) as mock_alert:
            await check_end_stations(
                mock_cursor, mock_conn, trip_id, route_id, "test@example.com", None, None
            )

        # Should focus on station 789 (3rd choice)
        args = mock_alert.call_args[0]
        assert args[3] == 789  # focused_station_id (offset by 1 for cur param)


@pytest.mark.asyncio
class TestMonitorActiveTrips:
    """Tests for monitor_active_trips function"""

    async def test_monitors_starting_trips(self):
        """Should check start stations for all STARTING trips"""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()

        trip1_id = str(uuid4())
        trip2_id = str(uuid4())
        route_id = str(uuid4())

        # Mock STARTING trips query
        mock_cursor.fetchall.side_effect = [
            # STARTING trips
            [
                (trip1_id, route_id, "user1@example.com", 123, 5),
                (trip2_id, route_id, "user2@example.com", 456, 3),
            ],
            # DOCKING trips (empty)
            [],
        ]

        with patch("routers.trips.check_start_stations", new_callable=AsyncMock) as mock_check:
            stats = await monitor_active_trips(mock_cursor, mock_conn)

        assert stats["starting"] == 2
        assert stats["docking"] == 0
        assert mock_check.await_count == 2

    async def test_monitors_docking_trips(self):
        """Should check end stations for all DOCKING trips"""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()

        trip_id = str(uuid4())
        route_id = str(uuid4())

        mock_cursor.fetchall.side_effect = [
            # STARTING trips (empty)
            [],
            # DOCKING trips
            [(trip_id, route_id, "user@example.com", 123, 5)],
        ]

        with patch("routers.trips.check_end_stations", new_callable=AsyncMock) as mock_check:
            stats = await monitor_active_trips(mock_cursor, mock_conn)

        assert stats["starting"] == 0
        assert stats["docking"] == 1
        mock_check.assert_awaited_once()

    async def test_monitors_both_states(self):
        """Should monitor both STARTING and DOCKING trips"""
        mock_cursor = MagicMock()
        mock_conn = MagicMock()

        mock_cursor.fetchall.side_effect = [
            [(str(uuid4()), str(uuid4()), "user@example.com", 123, 5)],  # 1 STARTING
            [(str(uuid4()), str(uuid4()), "user@example.com", 456, 3)],  # 1 DOCKING
        ]

        with (
            patch("routers.trips.check_start_stations", new_callable=AsyncMock),
            patch("routers.trips.check_end_stations", new_callable=AsyncMock),
        ):
            stats = await monitor_active_trips(mock_cursor, mock_conn)

        assert stats["starting"] == 1
        assert stats["docking"] == 1
