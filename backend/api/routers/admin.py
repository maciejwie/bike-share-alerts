from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import uuid
import hashlib
from auth import get_admin_user
from db import get_db

router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(get_admin_user)]
)


class CreateUserRequest(BaseModel):
    user_email: str
    user_firstname: str
    user_lastname: str


class CreateKeyRequest(BaseModel):
    user_email: str
    label: str


class RollKeyRequest(BaseModel):
    user_email: str
    key_label: str


@router.post("/users", status_code=201)
def create_or_get_user(req: CreateUserRequest, conn=Depends(get_db)):
    """Create a new user or return existing user with the same email"""
    cur = conn.cursor()

    # Check if user with this email already exists
    cur.execute("SELECT user_email FROM users WHERE user_email = %s", (req.user_email,))
    existing = cur.fetchone()

    if existing:
        cur.close()
        return {"user_email": existing[0], "existed": True}

    # Create new user
    cur.execute(
        """
        INSERT INTO users (user_email, user_firstname, user_lastname)
        VALUES (%s, %s, %s)
        RETURNING user_email
        """,
        (req.user_email, req.user_firstname, req.user_lastname),
    )

    created_user_email = cur.fetchone()[0]
    conn.commit()
    cur.close()

    return {"user_email": created_user_email, "existed": False}


@router.get("/users")
def list_users(conn=Depends(get_db)):
    """List all users"""
    cur = conn.cursor()
    cur.execute(
        "SELECT user_email, user_firstname, user_lastname, device_token, created_at FROM users ORDER BY created_at DESC"
    )
    rows = cur.fetchall()
    cur.close()

    users = []
    for row in rows:
        users.append(
            {
                "user_email": row[0],
                "user_firstname": row[1],
                "user_lastname": row[2],
                "device_token": row[3],
                "created_at": row[4],
            }
        )
    return {"users": users}


@router.get("/users/by-email/{email}")
def get_user_by_email(email: str, conn=Depends(get_db)):
    """Get user info by email"""
    cur = conn.cursor()
    cur.execute(
        "SELECT user_email, user_firstname, user_lastname, device_token, created_at FROM users WHERE user_email = %s",
        (email,)
    )
    row = cur.fetchone()
    cur.close()

    if not row:
        raise HTTPException(status_code=404, detail=f"User not found with email: {email}")

    return {
        "user_email": row[0],
        "user_firstname": row[1],
        "user_lastname": row[2],
        "device_token": row[3],
        "created_at": row[4],
    }


@router.delete("/users/{email}", status_code=204)
def delete_user(email: str, conn=Depends(get_db)):
    """Delete a user and all associated data (API keys, routes)"""
    cur = conn.cursor()
    cur.execute("DELETE FROM users WHERE user_email = %s", (email,))
    if cur.rowcount == 0:
        cur.close()
        raise HTTPException(status_code=404, detail="User not found")
    conn.commit()
    cur.close()
    return


@router.post("/keys", status_code=201)
def create_or_get_api_key(req: CreateKeyRequest, conn=Depends(get_db)):
    """Create a new API key or return existing key info if one exists with the same user_email and label"""
    cur = conn.cursor()

    # Check if key with this user_email and label already exists
    cur.execute(
        "SELECT key_id FROM api_keys WHERE user_email = %s AND label = %s",
        (req.user_email, req.label),
    )
    existing = cur.fetchone()

    if existing:
        cur.close()
        return {
            "key_id": existing[0],
            "existed": True,
            "message": "Key already exists. Use POST /admin/keys/roll to regenerate."
        }

    # Generate a random key
    raw_key = f"sk_live_{uuid.uuid4()}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    cur.execute(
        """
        INSERT INTO api_keys (user_email, key_value, label)
        VALUES (%s, %s, %s)
        RETURNING key_id
    """,
        (req.user_email, key_hash, req.label),
    )

    key_id = cur.fetchone()[0]
    conn.commit()
    cur.close()

    return {"key": raw_key, "key_id": key_id, "existed": False}


@router.post("/keys/roll", status_code=201)
def roll_api_key(req: RollKeyRequest, conn=Depends(get_db)):
    """Roll (regenerate) an API key by user email and key label"""
    cur = conn.cursor()

    # Verify user exists
    cur.execute("SELECT user_email FROM users WHERE user_email = %s", (req.user_email,))
    user_row = cur.fetchone()

    if not user_row:
        cur.close()
        raise HTTPException(status_code=404, detail=f"User not found with email: {req.user_email}")

    # Find the existing key by user_email and label
    cur.execute(
        "SELECT key_id FROM api_keys WHERE user_email = %s AND label = %s",
        (req.user_email, req.key_label),
    )
    key_row = cur.fetchone()

    if not key_row:
        cur.close()
        raise HTTPException(
            status_code=404,
            detail=f"Key not found for user '{req.user_email}' with label '{req.key_label}'"
        )

    key_id = key_row[0]

    # Generate a new key
    raw_key = f"sk_live_{uuid.uuid4()}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    # Update the existing key
    cur.execute(
        "UPDATE api_keys SET key_value = %s, created_at = NOW(), last_used_at = NULL WHERE key_id = %s",
        (key_hash, key_id),
    )

    conn.commit()
    cur.close()

    return {"key": raw_key, "key_id": key_id, "user_email": req.user_email}


@router.delete("/keys/{key_id}", status_code=204)
def revoke_api_key(key_id: str, conn=Depends(get_db)):
    cur = conn.cursor()
    cur.execute("DELETE FROM api_keys WHERE key_id = %s", (key_id,))
    if cur.rowcount == 0:
        cur.close()
        raise HTTPException(status_code=404, detail="Key not found")
    conn.commit()
    cur.close()
    return


@router.get("/keys")
def list_api_keys(conn=Depends(get_db)):
    cur = conn.cursor()
    cur.execute(
        "SELECT key_id, user_email, label, created_at, last_used_at FROM api_keys ORDER BY created_at DESC"
    )
    rows = cur.fetchall()
    cur.close()

    keys = []
    for row in rows:
        keys.append(
            {
                "key_id": row[0],
                "user_email": row[1],
                "label": row[2],
                "created_at": row[3],
                "last_used_at": row[4],
            }
        )
    return {"keys": keys}
