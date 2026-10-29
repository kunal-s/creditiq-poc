"""Identity port: the host is the only authority on who the user is and what they may do.

The bearer token the browser sends is forwarded to the host's identity endpoint. The result is a Principal that
the runtime injects into tool calls; the model never supplies or sees it.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from .config import HostConfig


class Unauthenticated(Exception):
    """The host did not accept the token."""


class IdentityUnavailable(Exception):
    """The host could not be asked, or answered with something unusable."""


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: str
    permissions: frozenset[str]
    token: str = ""  # forwarded to the host by tools; never logged

    def can(self, needed: list[str] | tuple[str, ...]) -> bool:
        return set(needed) <= self.permissions

    def __repr__(self) -> str:
        return f"Principal({self.user_id!r}, role={self.role!r})"


def bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    return token.strip() or None if scheme.lower() == "bearer" else None


class HostIdentity:
    def __init__(self, host: HostConfig, client: httpx.AsyncClient | None = None):
        self._host = host
        self._client = client or httpx.AsyncClient(base_url=host.base_url, timeout=host.identity_timeout_s)

    async def resolve(self, token: str | None) -> Principal:
        if not token:
            raise Unauthenticated("no token")
        try:
            r = await self._client.get(self._host.identity_path, headers={"Authorization": f"Bearer {token}"})
        except httpx.HTTPError as e:
            raise IdentityUnavailable(type(e).__name__) from None
        if r.status_code in (401, 403):
            raise Unauthenticated("token refused")
        if r.status_code != 200:
            raise IdentityUnavailable(f"host answered {r.status_code}")
        f = self._host.identity_fields
        try:
            body = r.json()
            perms = body[f.permissions]
            if not isinstance(perms, list) or not all(isinstance(x, str) for x in perms):
                raise ValueError("permissions must be a list of strings")
            return Principal(str(body[f.id]), str(body[f.role]), frozenset(perms), token)
        except (ValueError, KeyError, TypeError):
            raise IdentityUnavailable("unexpected identity response") from None

    async def aclose(self) -> None:
        await self._client.aclose()
