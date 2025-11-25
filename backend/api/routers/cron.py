from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from auth import verify_cron_secret
from db import get_db
from routers.trips import activate_scheduled_routes, monitor_active_trips

router = APIRouter()


@router.get("/cron/heartbeat")
async def heartbeat(conn=Depends(get_db), _auth=Depends(verify_cron_secret)):
    """
    Called by Cloudflare Worker every minute.
    Orchestrates scheduled route activation and active trip monitoring.
    """
    now = datetime.now(UTC)
    cur = conn.cursor()

    # Step 1: Activate scheduled routes
    activated_count = await activate_scheduled_routes(cur, conn, now)

    # Step 2: Monitor active trips
    monitoring_stats = await monitor_active_trips(cur, conn)

    cur.close()

    return {
        "status": "ok",
        "timestamp": now.isoformat(),
        "activated_routes": activated_count,
        "monitoring_starting": monitoring_stats["starting"],
        "monitoring_docking": monitoring_stats["docking"],
    }
