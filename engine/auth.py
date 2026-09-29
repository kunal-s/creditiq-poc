"""Sign-in and sessions (docs/functional-requirements.md F-03).

One shared password for the PoC directory (config/roles.yaml), verified
server-side. Sessions live in SQLite, stored as a hash of the token, so they
survive a restart (F-03.3) and expire after the configured idle and absolute
limits (config/app.yaml). Named credentials per user are a later change.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

from .config import find_user, find_user_by_id, load_app_config, load_roles_config, role_label, role_permissions
from .db import log_decision


def _verify_password(password: str, stored_hash: str) -> bool:
    algo, iterations, salt_b64, digest_b64 = stored_hash.split("$")
    if algo != "pbkdf2_sha256":
        return False
    salt = base64.b64decode(salt_b64)
    expected = base64.b64decode(digest_b64)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
    return hmac.compare_digest(actual, expected)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    return "".join(p[0] for p in parts[:2]).upper()


def user_payload(user: dict) -> dict:
    return {
        "id": user["id"],
        "name": user["name"],
        "role": user["role"],
        "roleLabel": role_label(user["role"]),
        "email": user["email"],
        "branch": user["branch"],
        "initials": initials(user["name"]),
        "navGroups": load_roles_config()["navByRole"].get(user["role"], []),
        "permissions": role_permissions(user["role"]),
    }


def login(conn: sqlite3.Connection, email: str, password: str) -> dict | None:
    user = find_user(email)
    if user is None:
        return None
    if not _verify_password(password, load_roles_config()["auth"]["demoPasswordHash"]):
        return None
    token = secrets.token_urlsafe(32)
    now = _now().isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, created_at, last_seen) VALUES (?, ?, ?, ?)",
        (_token_hash(token), user["id"], now, now),
    )
    log_decision(conn, at=now, actor=user["id"], case_id=None, action="session.signed_in")
    return {"token": token, "user": user_payload(user)}


def session_user(conn: sqlite3.Connection, token: str) -> dict | None:
    """The signed-in user for a token, or None if unknown or expired.
    A valid call refreshes the idle timer."""
    row = conn.execute("SELECT * FROM sessions WHERE token_hash = ?", (_token_hash(token),)).fetchone()
    if row is None:
        return None
    limits = load_app_config()["sessions"]
    now = _now()
    created = datetime.fromisoformat(row["created_at"])
    last_seen = datetime.fromisoformat(row["last_seen"])
    if now - last_seen > timedelta(minutes=limits["idle_minutes"]) or now - created > timedelta(
        hours=limits["absolute_hours"]
    ):
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (row["token_hash"],))
        return None
    conn.execute(
        "UPDATE sessions SET last_seen = ? WHERE token_hash = ?",
        (now.isoformat(timespec="seconds"), row["token_hash"]),
    )
    user = find_user_by_id(row["user_id"])
    return user_payload(user) if user else None


def logout(conn: sqlite3.Connection, token: str) -> None:
    conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_token_hash(token),))
