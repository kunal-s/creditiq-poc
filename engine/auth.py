"""Sign-in for the POC: one shared password (config/roles.yaml), hashed and
verified server-side, real bearer-token sessions (no runtime state persists
across process restarts — Stage A has no session store yet)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from .config import find_user, load_roles_config, role_label

PBKDF2_ITERATIONS = 200_000


def _verify_password(password: str, stored_hash: str) -> bool:
    algo, iterations, salt_b64, digest_b64 = stored_hash.split("$")
    assert algo == "pbkdf2_sha256"
    salt = base64.b64decode(salt_b64)
    expected = base64.b64decode(digest_b64)
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
    return hmac.compare_digest(actual, expected)


# token -> user id. In-memory only: a service restart signs everyone out,
# which is correct for a POC with no persisted session store yet.
_SESSIONS: dict[str, str] = {}


def initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    return "".join(p[0] for p in parts[:2]).upper()


def _user_payload(user: dict) -> dict:
    nav_by_role = load_roles_config()["navByRole"]
    return {
        "id": user["id"],
        "name": user["name"],
        "role": user["role"],
        "roleLabel": role_label(user["role"]),
        "email": user["email"],
        "branch": user["branch"],
        "initials": initials(user["name"]),
        "navGroups": nav_by_role.get(user["role"], []),
    }


def login(email: str, password: str) -> dict | None:
    user = find_user(email)
    if user is None:
        return None
    stored_hash = load_roles_config()["auth"]["demoPasswordHash"]
    if not _verify_password(password, stored_hash):
        return None
    token = secrets.token_urlsafe(32)
    _SESSIONS[token] = user["id"]
    return {"token": token, "user": _user_payload(user)}


def session_user(token: str) -> dict | None:
    user_id = _SESSIONS.get(token)
    if user_id is None:
        return None
    for user in load_roles_config()["users"]:
        if user["id"] == user_id:
            return _user_payload(user)
    return None


def logout(token: str) -> None:
    _SESSIONS.pop(token, None)
