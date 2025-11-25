import hashlib
import os
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from db import get_db

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security), conn=Depends(get_db)
) -> str:
    """
    Validates the API key and returns the user_email.
    """
    token = credentials.credentials

    # Hash the token to match DB storage
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    cur = conn.cursor()
    cur.execute("SELECT user_email FROM api_keys WHERE key_value = %s", (token_hash,))
    row = cur.fetchone()

    if not row:
        cur.close()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_email = row[0]

    # Update last_used_at timestamp
    cur.execute("UPDATE api_keys SET last_used_at = NOW() WHERE key_value = %s", (token_hash,))
    conn.commit()
    cur.close()

    return user_email


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


def verify_cron_secret(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Validates the CRON_SECRET from Cloudflare Worker.
    """
    token = credentials.credentials
    cron_secret = os.environ.get("CRON_SECRET")

    if not cron_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cron secret not configured",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not secrets.compare_digest(token, cron_secret):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid cron secret",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return True
