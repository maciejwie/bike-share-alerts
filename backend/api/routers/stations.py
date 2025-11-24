from fastapi import APIRouter, Depends
from auth import get_current_user
from db import get_db

router = APIRouter()


@router.get("/stations")
def get_stations(user_id: str = Depends(get_current_user), conn=Depends(get_db)):
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
