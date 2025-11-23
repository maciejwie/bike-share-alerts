from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
import uuid
import hashlib
from auth import get_admin_user
from db import get_db

router = APIRouter(
    prefix="/admin", tags=["admin"], dependencies=[Depends(get_admin_user)]
)


class CreateKeyRequest(BaseModel):
    user_id: str
    label: Optional[str] = None


@router.post("/keys", status_code=201)
def create_api_key(req: CreateKeyRequest, conn=Depends(get_db)):
    # Generate a random key
    raw_key = f"sk_live_{uuid.uuid4()}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO api_keys (user_id, key_value, label)
        VALUES (%s, %s, %s)
        RETURNING key_id
    """,
        (req.user_id, key_hash, req.label),
    )

    key_id = cur.fetchone()[0]
    conn.commit()
    cur.close()

    return {"key": raw_key, "key_id": key_id}


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
        "SELECT key_id, user_id, label, created_at, last_used_at FROM api_keys ORDER BY created_at DESC"
    )
    rows = cur.fetchall()
    cur.close()

    keys = []
    for row in rows:
        keys.append(
            {
                "key_id": row[0],
                "user_id": row[1],
                "label": row[2],
                "created_at": row[3],
                "last_used_at": row[4],
            }
        )
    return {"keys": keys}
