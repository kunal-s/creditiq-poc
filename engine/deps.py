"""FastAPI dependencies: a database connection per request, the signed-in
user, and permission checks (docs/functional-requirements.md F-03.1).

Every data endpoint depends on `require(<permission>)`: no session gives
401, a session without the permission gives 403.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Iterator

from fastapi import Depends, Header, HTTPException

from . import auth, db


def get_conn() -> Iterator[sqlite3.Connection]:
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


def bearer_token(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    return authorization.split(" ", 1)[1]


def current_user(token: str = Depends(bearer_token), conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    user = auth.session_user(conn, token)
    if user is None:
        raise HTTPException(status_code=401, detail="no active session")
    return user


def require(permission: str) -> Callable[..., dict]:
    def dependency(user: dict = Depends(current_user)) -> dict:
        if permission not in user["permissions"]:
            raise HTTPException(status_code=403, detail=f"role {user['role']!r} lacks {permission!r}")
        return user

    return dependency
