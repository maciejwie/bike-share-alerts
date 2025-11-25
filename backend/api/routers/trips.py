from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import apns
from auth import get_current_user
from db import get_db

router = APIRouter()

# Store background tasks to prevent them from being garbage collected
# _background_tasks: set[asyncio.Task] = set()


class LocationUpdate(BaseModel):
    lat: float
    lon: float


class TripResponse(BaseModel):
    trip_id: str
    route_id: str
    state: str
    started_at: datetime
    cycling_started_at: datetime | None = None
    docking_started_at: datetime | None = None
    completed_at: datetime | None = None


# Public functions for cron orchestration
async def activate_scheduled_routes(cur, conn, now: datetime) -> int:
    """
    Finds routes that should start monitoring based on schedule.
    Creates trip records for routes where:
    - is_active = true
    - today's weekday matches days_of_week
    - current time >= (target_departure_time - alert_lead_time_minutes)
    - no active trip exists for this user

    Returns number of activated routes.
    """
    # Get current day of week (0=Monday in Python, but we use 0=Sunday)
    weekday = (now.weekday() + 1) % 7  # Convert to 0=Sunday

    # Extract current time
    current_time = now.time()

    # Find routes to activate
    cur.execute(
        """
        SELECT r.route_id, r.user_email, r.target_departure_time, r.alert_lead_time_minutes
        FROM routes r
        LEFT JOIN trips t ON t.user_email = r.user_email AND t.completed_at IS NULL
        WHERE r.is_active = TRUE
        AND t.trip_id IS NULL
        AND %s = ANY(r.days_of_week)
        AND r.target_departure_time IS NOT NULL
    """,
        (weekday,),
    )

    routes_to_activate = cur.fetchall()
    activated = 0

    for route_id, user_email, target_time, lead_minutes in routes_to_activate:
        # Calculate alert time (target_time - lead_minutes)
        target_minutes = target_time.hour * 60 + target_time.minute
        alert_minutes = target_minutes - lead_minutes
        current_minutes = current_time.hour * 60 + current_time.minute

        # Check if we're in the alert window
        if current_minutes >= alert_minutes and current_minutes < target_minutes + 60:
            # Create new trip
            cur.execute(
                """
                INSERT INTO trips (route_id, user_email, state)
                VALUES (%s, %s, 'STARTING')
                RETURNING trip_id
            """,
                (route_id, user_email),
            )

            trip_id = cur.fetchone()[0]
            conn.commit()

            # Send initial alert
            await check_start_stations(cur, conn, trip_id, route_id, user_email, None, None)
            activated += 1

    return activated


async def monitor_active_trips(cur, conn) -> dict:
    """
    Monitors all active trips in STARTING and DOCKING states.
    Returns statistics about monitored trips.
    """
    # Monitor active trips in STARTING state
    cur.execute("""
        SELECT trip_id, route_id, user_email, focused_station_id, last_bike_count
        FROM trips
        WHERE completed_at IS NULL
        AND state = 'STARTING'
    """)
    starting_trips = cur.fetchall()

    for trip_row in starting_trips:
        trip_id, route_id, user_email, focused_station_id, last_bike_count = trip_row
        await check_start_stations(
            cur, conn, trip_id, route_id, user_email, focused_station_id, last_bike_count
        )

    # Monitor active trips in DOCKING state
    cur.execute("""
        SELECT trip_id, route_id, user_email, focused_station_id, last_dock_count
        FROM trips
        WHERE completed_at IS NULL
        AND state = 'DOCKING'
    """)
    docking_trips = cur.fetchall()

    for trip_row in docking_trips:
        trip_id, route_id, user_email, focused_station_id, last_dock_count = trip_row
        await check_end_stations(
            cur, conn, trip_id, route_id, user_email, focused_station_id, last_dock_count
        )

    return {
        "starting": len(starting_trips),
        "docking": len(docking_trips),
    }


async def check_start_stations(
    cur,
    conn,
    trip_id: str,
    route_id: str,
    user_email: str,
    focused_station_id: int | None,
    last_bike_count: int | None,
):
    """
    Checks bike availability at start stations.
    Sends alerts on initial check or when bike count changes.
    """
    # Get route configuration
    cur.execute(
        """
        SELECT start_station_ids, bikes_threshold
        FROM routes
        WHERE route_id = %s
    """,
        (route_id,),
    )

    route_data = cur.fetchone()
    if not route_data:
        return

    start_station_ids, bikes_threshold = route_data

    # Get current bike availability for all start stations
    cur.execute(
        """
        SELECT station_id, num_bikes_available
        FROM current_station_status
        WHERE station_id = ANY(%s)
        ORDER BY array_position(%s, station_id)
    """,
        (start_station_ids, start_station_ids),
    )

    station_statuses = cur.fetchall()

    # Find the focused station (first with bikes >= threshold, or first with any bikes)
    new_focused_station = None
    new_bike_count = 0

    for station_id, num_bikes in station_statuses:
        if new_focused_station is None:
            new_focused_station = station_id
            new_bike_count = num_bikes

        if num_bikes >= bikes_threshold:
            new_focused_station = station_id
            new_bike_count = num_bikes
            break

    # Check if we need to send an alert
    should_alert = False

    if focused_station_id is None:
        # First check - always alert
        should_alert = True
    elif new_focused_station != focused_station_id or new_bike_count != last_bike_count:
        # Station changed or bike count changed
        should_alert = True

    if should_alert:
        # Update trip record
        cur.execute(
            """
            UPDATE trips
            SET focused_station_id = %s,
                last_bike_count = %s,
                last_checked_at = %s
            WHERE trip_id = %s
        """,
            (new_focused_station, new_bike_count, datetime.now(UTC), trip_id),
        )
        conn.commit()

        # Send alert
        await send_bike_alert(
            cur,
            user_email,
            route_id,
            new_focused_station,
            new_bike_count,
            bikes_threshold,
            station_statuses,
        )
    else:
        # Just update last_checked_at
        cur.execute(
            """
            UPDATE trips
            SET last_checked_at = %s
            WHERE trip_id = %s
        """,
            (datetime.now(UTC), trip_id),
        )
        conn.commit()


async def check_end_stations(
    cur,
    conn,
    trip_id: str,
    route_id: str,
    user_email: str,
    focused_station_id: int | None,
    last_dock_count: int | None,
):
    """
    Checks dock availability at end stations.
    Sends alerts on initial check or when dock count changes.
    """
    # Get route configuration
    cur.execute(
        """
        SELECT end_station_ids, docks_threshold
        FROM routes
        WHERE route_id = %s
    """,
        (route_id,),
    )

    route_data = cur.fetchone()
    if not route_data:
        return

    end_station_ids, docks_threshold = route_data

    # Get current dock availability for all end stations
    cur.execute(
        """
        SELECT station_id, num_docks_available
        FROM current_station_status
        WHERE station_id = ANY(%s)
        ORDER BY array_position(%s, station_id)
    """,
        (end_station_ids, end_station_ids),
    )

    station_statuses = cur.fetchall()

    # Find the focused station (first with docks >= threshold)
    new_focused_station = None
    new_dock_count = 0

    for station_id, num_docks in station_statuses:
        if num_docks >= docks_threshold:
            new_focused_station = station_id
            new_dock_count = num_docks
            break

    # If no station meets threshold, use first station
    if new_focused_station is None and station_statuses:
        new_focused_station = station_statuses[0][0]
        new_dock_count = station_statuses[0][1]

    # Check if we need to send an alert
    should_alert = False

    if focused_station_id is None:
        # First check - always alert
        should_alert = True
    elif new_focused_station != focused_station_id or new_dock_count != last_dock_count:
        # Station changed or dock count changed
        should_alert = True

    if should_alert:
        # Update trip record
        cur.execute(
            """
            UPDATE trips
            SET focused_station_id = %s,
                last_dock_count = %s,
                last_checked_at = %s
            WHERE trip_id = %s
        """,
            (new_focused_station, new_dock_count, datetime.now(UTC), trip_id),
        )
        conn.commit()

        # Send alert
        await send_dock_alert(
            cur,
            user_email,
            route_id,
            new_focused_station,
            new_dock_count,
            docks_threshold,
            station_statuses,
        )
    else:
        # Just update last_checked_at
        cur.execute(
            """
            UPDATE trips
            SET last_checked_at = %s
            WHERE trip_id = %s
        """,
            (datetime.now(UTC), trip_id),
        )
        conn.commit()


async def send_bike_alert(
    cur,
    user_email: str,
    route_id: str,
    focused_station_id: int | None,
    bike_count: int,
    threshold: int,
    all_stations: list,
):
    """
    Send push notification via APNs about bike availability.
    """
    if focused_station_id is None:
        return

    # Get user's device token
    cur.execute(
        """
        SELECT device_token FROM users WHERE user_email = %s
        """,
        (user_email,),
    )
    result = cur.fetchone()
    if not result or not result[0]:
        print(f"No device token for user {user_email}")
        return

    device_token = result[0]

    # Get station name
    cur.execute(
        """
        SELECT name FROM stations WHERE station_id = %s
        """,
        (focused_station_id,),
    )
    station_result = cur.fetchone()
    station_name = station_result[0] if station_result else f"Station {focused_station_id}"

    # Send notification synchronously (await) to ensure it completes in serverless env
    try:
        await apns.send_bike_alert(device_token, station_name, bike_count, focused_station_id)
    except Exception as e:
        print(f"[ERROR] Failed to send bike alert to {user_email}: {e}")


async def send_dock_alert(
    cur,
    user_email: str,
    route_id: str,
    focused_station_id: int | None,
    dock_count: int,
    threshold: int,
    all_stations: list,
):
    """
    Send push notification via APNs about dock availability.
    Alert level depends on which station in preference order has docks.
    """
    if focused_station_id is None:
        return

    # Get user's device token
    cur.execute(
        """
        SELECT device_token FROM users WHERE user_email = %s
        """,
        (user_email,),
    )
    result = cur.fetchone()
    if not result or not result[0]:
        print(f"No device token for user {user_email}")
        return

    device_token = result[0]

    # Get station name
    cur.execute(
        """
        SELECT name FROM stations WHERE station_id = %s
        """,
        (focused_station_id,),
    )
    station_result = cur.fetchone()
    station_name = station_result[0] if station_result else f"Station {focused_station_id}"

    # Calculate alert level (0 = preferred station, 1 = 2nd choice, etc.)
    alert_level = next(
        (i for i, (sid, _) in enumerate(all_stations) if sid == focused_station_id), 0
    )

    # Send notification synchronously (await) to ensure it completes in serverless env
    try:
        await apns.send_dock_alert(
            device_token, station_name, dock_count, focused_station_id, alert_level
        )
    except Exception as e:
        print(f"[ERROR] Failed to send dock alert to {user_email}: {e}")


@router.post("/trips/{trip_id}/start")
def start_trip(trip_id: str, user_email: str = Depends(get_current_user), conn=Depends(get_db)):
    """
    Called by iOS app when user starts cycling.
    Transitions trip from STARTING -> CYCLING.
    """
    cur = conn.cursor()

    # Verify trip belongs to user and is in STARTING state
    cur.execute(
        """
        SELECT state FROM trips
        WHERE trip_id = %s AND user_email = %s AND completed_at IS NULL
    """,
        (trip_id, user_email),
    )

    result = cur.fetchone()
    if not result:
        cur.close()
        raise HTTPException(status_code=404, detail="Trip not found or already completed")

    current_state = result[0]
    if current_state != "STARTING":
        cur.close()
        raise HTTPException(
            status_code=400, detail=f"Trip is in {current_state} state, expected STARTING"
        )

    # Update state
    cur.execute(
        """
        UPDATE trips
        SET state = 'CYCLING',
            cycling_started_at = %s
        WHERE trip_id = %s
    """,
        (datetime.now(UTC), trip_id),
    )

    conn.commit()
    cur.close()

    return {"status": "ok", "trip_id": trip_id, "state": "CYCLING"}


@router.post("/trips/{trip_id}/enter-docking-zone")
async def enter_docking_zone(
    trip_id: str,
    location: LocationUpdate,
    user_email: str = Depends(get_current_user),
    conn=Depends(get_db),
):
    """
    Called by iOS app when geofence detects proximity to end stations.
    Transitions trip from CYCLING -> DOCKING and initiates dock monitoring.
    """
    cur = conn.cursor()

    # Verify trip belongs to user and is in CYCLING state
    cur.execute(
        """
        SELECT state, route_id FROM trips
        WHERE trip_id = %s AND user_email = %s AND completed_at IS NULL
    """,
        (trip_id, user_email),
    )

    result = cur.fetchone()
    if not result:
        cur.close()
        raise HTTPException(status_code=404, detail="Trip not found or already completed")

    current_state, route_id = result
    if current_state != "CYCLING":
        cur.close()
        raise HTTPException(
            status_code=400, detail=f"Trip is in {current_state} state, expected CYCLING"
        )

    # Update state and location
    now = datetime.now(UTC)
    cur.execute(
        """
        UPDATE trips
        SET state = 'DOCKING',
            docking_started_at = %s,
            last_known_lat = %s,
            last_known_lon = %s,
            last_location_update_at = %s
        WHERE trip_id = %s
    """,
        (now, location.lat, location.lon, now, trip_id),
    )

    conn.commit()

    # Immediately check dock availability
    await check_end_stations(cur, conn, trip_id, route_id, user_email, None, None)

    cur.close()

    return {"status": "ok", "trip_id": trip_id, "state": "DOCKING"}


@router.post("/trips/{trip_id}/end")
def end_trip(trip_id: str, user_email: str = Depends(get_current_user), conn=Depends(get_db)):
    """
    Called by iOS app when trip is complete.
    Marks trip as COMPLETE.
    """
    cur = conn.cursor()

    # Verify trip belongs to user and is not already completed
    cur.execute(
        """
        SELECT state FROM trips
        WHERE trip_id = %s AND user_email = %s AND completed_at IS NULL
    """,
        (trip_id, user_email),
    )

    result = cur.fetchone()
    if not result:
        cur.close()
        raise HTTPException(status_code=404, detail="Trip not found or already completed")

    # Update state
    cur.execute(
        """
        UPDATE trips
        SET state = 'COMPLETE',
            completed_at = %s
        WHERE trip_id = %s
    """,
        (datetime.now(UTC), trip_id),
    )

    conn.commit()
    cur.close()

    return {"status": "ok", "trip_id": trip_id, "state": "COMPLETE"}


@router.get("/trips/active")
def get_active_trip(user_email: str = Depends(get_current_user), conn=Depends(get_db)):
    """
    Returns the user's currently active trip, if any.
    """
    cur = conn.cursor()

    cur.execute(
        """
        SELECT trip_id, route_id, state, started_at, cycling_started_at, docking_started_at
        FROM trips
        WHERE user_email = %s AND completed_at IS NULL
        ORDER BY started_at DESC
        LIMIT 1
    """,
        (user_email,),
    )

    result = cur.fetchone()
    cur.close()

    if not result:
        return {"active_trip": None}

    trip_id, route_id, state, started_at, cycling_started_at, docking_started_at = result

    return {
        "active_trip": {
            "trip_id": trip_id,
            "route_id": route_id,
            "state": state,
            "started_at": started_at.isoformat(),
            "cycling_started_at": cycling_started_at.isoformat() if cycling_started_at else None,
            "docking_started_at": docking_started_at.isoformat() if docking_started_at else None,
        }
    }
