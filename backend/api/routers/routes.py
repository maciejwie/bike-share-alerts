from fastapi import APIRouter, Depends
from pydantic import BaseModel, field_validator
from typing import List, Optional
from datetime import time
from auth import get_current_user
from db import get_db

router = APIRouter()


class RouteBase(BaseModel):
    name: str
    start_station_ids: List[int]
    end_station_ids: List[int]
    target_departure_time: Optional[time] = None
    alert_lead_time_minutes: int = 15
    days_of_week: List[int] = []
    bikes_threshold: int = 2
    docks_threshold: int = 2


class RouteCreate(RouteBase):
    @field_validator('start_station_ids', 'end_station_ids')
    @classmethod
    def validate_station_ids(cls, v):
        if not v or len(v) == 0:
            raise ValueError('Must provide at least one station ID')
        if len(v) != len(set(v)):
            raise ValueError('Station IDs must be unique')
        return v

    @field_validator('days_of_week')
    @classmethod
    def validate_days(cls, v):
        if v and any(d < 0 or d > 6 for d in v):
            raise ValueError('Days of week must be 0-6 (Sunday=0)')
        return v


class Route(RouteBase):
    id: int
    active: bool


@router.get("/routes")
def get_routes(user_email: str = Depends(get_current_user), conn=Depends(get_db)):
    cur = conn.cursor()
    cur.execute(
        "SELECT route_id, name, start_station_ids, end_station_ids, target_departure_time, alert_lead_time_minutes, days_of_week, is_active, bikes_threshold, docks_threshold FROM routes WHERE user_email = %s",
        (user_email,),
    )
    rows = cur.fetchall()
    cur.close()

    routes = []
    for row in rows:
        routes.append(
            {
                "id": row[0],
                "name": row[1],
                "start_station_ids": row[2] or [],
                "end_station_ids": row[3] or [],
                "target_departure_time": row[4].isoformat() if row[4] else None,
                "alert_lead_time_minutes": row[5],
                "days_of_week": row[6] or [],
                "active": row[7],
                "bikes_threshold": row[8],
                "docks_threshold": row[9],
            }
        )
    return {"routes": routes}


@router.post("/routes", status_code=201)
def create_route(
    route: RouteCreate, user_email: str = Depends(get_current_user), conn=Depends(get_db)
):
    cur = conn.cursor()

    # Check if a route with the same name already exists for this user
    cur.execute(
        "SELECT route_id FROM routes WHERE user_email = %s AND name = %s",
        (user_email, route.name)
    )
    existing = cur.fetchone()

    if existing:
        cur.close()
        return {"route_id": existing[0], "existed": True}

    # Create new route
    cur.execute(
        """
        INSERT INTO routes (user_email, name, start_station_ids, end_station_ids, target_departure_time, alert_lead_time_minutes, days_of_week, bikes_threshold, docks_threshold)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING route_id
    """,
        (
            user_email,
            route.name,
            route.start_station_ids,
            route.end_station_ids,
            route.target_departure_time,
            route.alert_lead_time_minutes,
            route.days_of_week,
            route.bikes_threshold,
            route.docks_threshold,
        ),
    )

    new_id = cur.fetchone()[0]
    conn.commit()
    cur.close()

    return {"route_id": new_id, "existed": False}


@router.delete("/routes/{route_id}", status_code=204)
def delete_route(
    route_id: str, user_email: str = Depends(get_current_user), conn=Depends(get_db)
):
    """Delete a route (only if owned by the authenticated user)"""
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM routes WHERE route_id = %s AND user_email = %s",
        (route_id, user_email)
    )

    if cur.rowcount == 0:
        cur.close()
        conn.rollback()
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Route not found")

    conn.commit()
    cur.close()
