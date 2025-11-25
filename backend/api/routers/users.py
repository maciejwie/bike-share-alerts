from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from auth import get_current_user
from db import get_db

router = APIRouter()


class DeviceTokenRequest(BaseModel):
    device_token: str


@router.post("/users/device-token")
def register_device_token(
    request: DeviceTokenRequest,
    user_email: str = Depends(get_current_user),
    conn=Depends(get_db),
):
    """
    Register or update the APNs device token for the authenticated user.
    This token is used to send push notifications to the user's device.
    """
    cur = conn.cursor()

    try:
        # Update or insert device token for user
        cur.execute(
            """
            UPDATE users
            SET device_token = %s
            WHERE user_email = %s
            """,
            (request.device_token, user_email),
        )

        # If user doesn't exist, create them
        if cur.rowcount == 0:
            cur.execute(
                """
                INSERT INTO users (user_email, device_token)
                VALUES (%s, %s)
                """,
                (user_email, request.device_token),
            )

        conn.commit()
        cur.close()

        return {
            "status": "success",
            "message": "Device token registered successfully",
        }

    except Exception as e:
        conn.rollback()
        cur.close()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register device token: {e!s}",
        ) from e


@router.delete("/users/device-token")
def unregister_device_token(
    user_email: str = Depends(get_current_user),
    conn=Depends(get_db),
):
    """
    Remove the APNs device token for the authenticated user.
    This will stop push notifications from being sent.
    """
    cur = conn.cursor()

    try:
        cur.execute(
            """
            UPDATE users
            SET device_token = NULL
            WHERE user_email = %s
            """,
            (user_email,),
        )

        conn.commit()
        cur.close()

        return {
            "status": "success",
            "message": "Device token removed successfully",
        }

    except Exception as e:
        conn.rollback()
        cur.close()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove device token: {e!s}",
        ) from e
