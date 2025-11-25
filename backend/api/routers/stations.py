from fastapi import APIRouter, Depends

from auth import get_current_user
from db import get_db

router = APIRouter()


@router.get("/stations")
def get_stations(user_email: str = Depends(get_current_user), conn=Depends(get_db)):
    cur = conn.cursor()

    query = """
        SELECT DISTINCT ON (station_id)
            station_id, num_bikes_available, num_ebikes_available, num_docks_available, time
        FROM station_status
        ORDER BY station_id, time DESC
    """

    cur.execute(query)
    rows = cur.fetchall()
    cur.close()

    stations = []
    for row in rows:
        stations.append(
            {
                "id": row[0],
                "bikes": row[1],
                "ebikes": row[2],
                "docks": row[3],
                "last_updated": row[4].isoformat(),
            }
        )

    return {"stations": stations}


@router.get("/stations/all")
def get_all_stations_with_details(
    user_email: str = Depends(get_current_user), conn=Depends(get_db)
):
    """
    Get all stations with their names and coordinates for station picker UI.
    """
    cur = conn.cursor()

    cur.execute(
        """
        SELECT s.station_id, s.name, s.lat, s.lon, s.capacity,
               COALESCE(ss.num_bikes_available, 0) as bikes,
               COALESCE(ss.num_ebikes_available, 0) as ebikes,
               COALESCE(ss.num_docks_available, 0) as docks
        FROM stations s
        LEFT JOIN current_station_status ss ON s.station_id = ss.station_id
        ORDER BY s.name
        """
    )

    rows = cur.fetchall()
    cur.close()

    stations = []
    for row in rows:
        stations.append(
            {
                "id": row[0],
                "name": row[1],
                "lat": row[2],
                "lon": row[3],
                "capacity": row[4],
                "bikes": row[5],
                "ebikes": row[6],
                "docks": row[7],
            }
        )

    return {"stations": stations}


@router.get("/stations/{station_id}")
def get_station_details(
    station_id: str, user_email: str = Depends(get_current_user), conn=Depends(get_db)
):
    """
    Get detailed information for a specific station, including coordinates.
    """
    cur = conn.cursor()

    # Get station metadata and latest status
    cur.execute(
        """
        SELECT s.station_id, s.name, s.lat, s.lon, s.capacity,
               ss.num_bikes_available, ss.num_ebikes_available, ss.num_docks_available, ss.last_updated
        FROM stations s
        LEFT JOIN current_station_status ss ON s.station_id = ss.station_id
        WHERE s.station_id = %s
        """,
        (station_id,),
    )

    row = cur.fetchone()
    cur.close()

    if not row:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Station not found")

    return {
        "id": row[0],
        "name": row[1],
        "lat": row[2],
        "lon": row[3],
        "capacity": row[4],
        "bikes": row[5] if row[5] is not None else 0,
        "ebikes": row[6] if row[6] is not None else 0,
        "docks": row[7] if row[7] is not None else 0,
        "last_updated": row[8].isoformat() if row[8] else None,
    }
