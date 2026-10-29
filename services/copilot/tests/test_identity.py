from pathlib import Path

import httpx
import pytest

from copilot.config import load_dir
from copilot.identity import HostIdentity, IdentityUnavailable, Unauthenticated, bearer_token

HOST = load_dir(Path(__file__).resolve().parent.parent / "config").host
USER = {"id": "u1", "name": "A", "role": "analyst", "permissions": ["data.read", "review.read"]}


def identity(handler):
    client = httpx.AsyncClient(base_url=HOST.base_url, transport=httpx.MockTransport(handler))
    return HostIdentity(HOST, client)


async def test_resolves_principal_and_forwards_token():
    seen = {}

    def handler(req):
        seen["auth"], seen["path"] = req.headers["authorization"], req.url.path
        return httpx.Response(200, json=USER)

    p = await identity(handler).resolve("tok")
    assert (seen["auth"], seen["path"]) == ("Bearer tok", HOST.identity_path)
    assert p.user_id == "u1" and p.role == "analyst" and p.token == "tok"
    assert p.can(["data.read", "review.read"]) and not p.can(["data.read", "case.read.all"])
    assert "tok" not in repr(p)


@pytest.mark.parametrize("status", [401, 403])
async def test_refused_token(status):
    with pytest.raises(Unauthenticated):
        await identity(lambda r: httpx.Response(status)).resolve("bad")


async def test_missing_token_never_calls_host():
    def handler(req):
        raise AssertionError("host called")

    with pytest.raises(Unauthenticated):
        await identity(handler).resolve(None)


async def test_host_down_or_odd_answers_are_unavailable():
    def boom(req):
        raise httpx.ConnectError("x")

    for h in (boom, lambda r: httpx.Response(500), lambda r: httpx.Response(200, json={"id": "u"}), lambda r: httpx.Response(200, text="no"),
              lambda r: httpx.Response(200, json={**USER, "permissions": "data.read"})):
        with pytest.raises(IdentityUnavailable):
            await identity(h).resolve("t")


def test_bearer_token_parsing():
    assert bearer_token("Bearer abc") == "abc"
    assert bearer_token("bearer abc") == "abc"
    assert bearer_token("Basic abc") is None and bearer_token("Bearer ") is None and bearer_token(None) is None
