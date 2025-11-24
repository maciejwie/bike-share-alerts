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

    # Get route details
    cur.execute(
        "SELECT start_station_id, end_station_id FROM routes WHERE route_id = %s",
        (req.route_id,),
    )
    route = cur.fetchone()

    if not route:
        cur.close()
        raise HTTPException(status_code=404, detail="Route not found")

    start_id, end_id = route

    # Check status
    query = """
        SELECT DISTINCT ON (station_id) station_id, num_bikes_available, num_docks_available
        FROM station_status
        WHERE station_id IN (%s, %s)
        ORDER BY station_id, time DESC
    """

    cur.execute(query, (start_id, end_id))
    rows = cur.fetchall()
    cur.close()

    status_map = {}
    for r in rows:
        status_map[r[0]] = {"bikes": r[1], "docks": r[2]}

    alert = False
    message = []

    start_status = status_map.get(start_id)
    end_status = status_map.get(end_id)

    if start_status and start_status["bikes"] < 2:
        alert = True
        message.append(f"Low bikes at start ({start_status['bikes']} avail)")

    if end_status and end_status["docks"] < 2:
        alert = True
        message.append(f"Low docks at dest ({end_status['docks']} avail)")

    return {
        "alert": alert,
        "message": "; ".join(message) if message else "Good to go",
        "data": status_map,
    }
