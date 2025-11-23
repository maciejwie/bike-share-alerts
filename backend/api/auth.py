import os
import hashlib
import secrets
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from db import get_db

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security), conn=Depends(get_db)
):
    """
    Validates the API key and returns the user_id.
    """
    token = credentials.credentials

    # Hash the token to match DB storage
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    cur = conn.cursor()
    cur.execute("SELECT user_id FROM api_keys WHERE key_value = %s", (token_hash,))
    row = cur.fetchone()
    cur.close()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = row[0]

    # Update last_used_at timestamp
    cur.execute(
        "UPDATE api_keys SET last_used_at = NOW() WHERE key_value = %s", (token_hash,)
    )
    conn.commit()
    cur.close()

    return user_id


def get_admin_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Validates the Admin API Key.
    """
    token = credentials.credentials
    admin_key = os.environ.get("ADMIN_API_KEY")

    if not admin_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin API key not configured",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not secrets.compare_digest(token, admin_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Admin API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True
