from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional
from auth import get_current_user
from db import get_db

router = APIRouter()


class RouteBase(BaseModel):
    name: str
    start_station_id: str
    end_station_id: str
    target_arrival_time: Optional[str] = None
    alert_lead_time_minutes: int = 15
    days_of_week: List[int] = []


class RouteCreate(RouteBase):
    pass


class Route(RouteBase):
    id: int
    active: bool
    arrival_time: Optional[str] = None  # Normalized name


@router.get("/routes")
def get_routes(user_id: str = Depends(get_current_user), conn=Depends(get_db)):
    cur = conn.cursor()
    cur.execute(
        "SELECT route_id, name, start_station_id, end_station_id, target_arrival_time, alert_lead_time_minutes, days_of_week, is_active FROM routes WHERE user_id = %s",
        (user_id,),
    )
    rows = cur.fetchall()
    cur.close()

    routes = []
    for row in rows:
        routes.append(
            {
                "id": row[0],
                "name": row[1],
                "start_station_id": row[2],
                "end_station_id": row[3],
                "target_arrival_time": str(row[4]) if row[4] else None,
                "alert_lead_time_minutes": row[5],
                "days_of_week": row[6],
                "active": row[7],
            }
        )
    return {"routes": routes}


@router.post("/routes", status_code=201)
def create_route(
    route: RouteCreate, user_id: str = Depends(get_current_user), conn=Depends(get_db)
):
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO routes (user_id, name, start_station_id, end_station_id, target_arrival_time, alert_lead_time_minutes, days_of_week)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING route_id
    """,
        (
            user_id,
            route.name,
            route.start_station_id,
            route.end_station_id,
            route.target_arrival_time,
            route.alert_lead_time_minutes,
            route.days_of_week,
        ),
    )

    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()

    return {"route_id": new_id}
