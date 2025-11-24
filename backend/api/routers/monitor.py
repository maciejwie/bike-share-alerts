from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user
from db import get_db

router = APIRouter()


class MonitorRequest(BaseModel):
    route_id: int


@router.post("/monitor")
def check_route_status(
    req: MonitorRequest, user_email: str = Depends(get_current_user), conn=Depends(get_db)
):
    cur = conn.cursor()

    # Get route details (verify ownership)
    cur.execute(
        "SELECT start_station_ids, end_station_ids, bikes_threshold, docks_threshold FROM routes WHERE route_id = %s AND user_email = %s",
        (req.route_id, user_email),
    )
    route = cur.fetchone()

    if not route:
        cur.close()
        raise HTTPException(status_code=404, detail="Route not found")

    start_ids, end_ids, bikes_threshold, docks_threshold = route
    start_ids = start_ids or []
    end_ids = end_ids or []

    # Validate that we have both start and end stations
    if not start_ids or not end_ids:
        cur.close()
        return {
            "alert": True,
            "message": "Route must have both start and end stations configured",
            "data": {},
        }

    # Collect all station IDs to check
    all_station_ids = list(set(start_ids + end_ids))

    # Check status for all stations
    query = """
        SELECT DISTINCT ON (station_id) station_id, num_bikes_available, num_docks_available
        FROM station_status
        WHERE station_id = ANY(%s)
        ORDER BY station_id, time DESC
    """

    cur.execute(query, (all_station_ids,))
    rows = cur.fetchall()
    cur.close()

    status_map = {}
    for r in rows:
        status_map[r[0]] = {"bikes": r[1], "docks": r[2]}

    alert = False
    message = []

    # Check start stations (in preference order)
    found_good_start = False
    for idx, start_id in enumerate(start_ids):
        start_status = status_map.get(start_id)

        # Primary (first) station alert - requires change of plans
        if idx == 0:
            if not start_status:
                alert = True
                message.append("No status data for primary start station")
            elif start_status["bikes"] < bikes_threshold:
                alert = True
                message.append(
                    f"Primary start station low on bikes ({start_status['bikes']} avail, need {bikes_threshold})"
                )

        # Found a station with sufficient bikes
        if start_status and start_status["bikes"] >= bikes_threshold:
            found_good_start = True
            # If it's not the primary station but has bikes, note it
            if idx > 0:
                message.append(f"Note: Using backup start station #{idx + 1}")
            break

    # If we never found a good station, alert
    if not found_good_start and len(start_ids) > 1:
        best_bikes = max((status_map.get(sid, {}).get("bikes", 0) for sid in start_ids), default=0)
        alert = True
        message.append(
            f"All start stations low on bikes (best: {best_bikes} avail, need {bikes_threshold})"
        )

    # Check end stations (in preference order)
    found_good_end = False
    for idx, end_id in enumerate(end_ids):
        end_status = status_map.get(end_id)

        # Primary (first) station alert - requires change of plans
        if idx == 0:
            if not end_status:
                alert = True
                message.append("No status data for primary end station")
            elif end_status["docks"] < docks_threshold:
                alert = True
                message.append(
                    f"Primary end station low on docks ({end_status['docks']} avail, need {docks_threshold})"
                )

        # Found a station with sufficient docks
        if end_status and end_status["docks"] >= docks_threshold:
            found_good_end = True
            # If it's not the primary station but has docks, note it
            if idx > 0:
                message.append(f"Note: Using backup end station #{idx + 1}")
            break

    # If we never found a good station, alert
    if not found_good_end and len(end_ids) > 1:
        best_docks = max((status_map.get(eid, {}).get("docks", 0) for eid in end_ids), default=0)
        alert = True
        message.append(
            f"All end stations low on docks (best: {best_docks} avail, need {docks_threshold})"
        )

    return {
        "alert": alert,
        "message": "; ".join(message) if message else "Good to go",
        "data": status_map,
    }
