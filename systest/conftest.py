"""Helpers for the system tests: Clerk-style session tokens and API clients.

The tests can't sign in through Clerk, so they sign session tokens of their
own, shaped as the Clerk instance's are once its session token is customized
(see backend/auth.py), with clerk_test_key.pem. The app verifies them with the
key's public half, which secrets.test.toml gives it as the ClerkJWTKey secret.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import jwt
import pytest
from encore.storage import postgres
from encore.testing import system

TEST_KEY = (Path(__file__).parent / "clerk_test_key.pem").read_text()

community = postgres.Database.named("community")
# The origin settings.test.config.toml allows tokens to be issued for.
ORIGIN = "http://localhost:4000"


def session_token(
    user_id: str,
    *,
    name: str = "",
    email: str = "",
    admin: bool = False,
    key: str = TEST_KEY,
    lifetime: int = 60,
    azp: str = ORIGIN,
    **extra: Any,
) -> str:
    """A session token as Clerk would issue it for the user."""
    now = int(time.time())
    claims: dict[str, Any] = {
        "sub": user_id,
        "sid": f"sess_{user_id}",
        "iss": "https://clerk.example.test",
        "azp": azp,
        "iat": now,
        "nbf": now - 5,
        "exp": now + lifetime,
        "name": name,
        "email": email,
        "image": f"https://img.example.test/{user_id}.png",
        "metadata": {"admin": True} if admin else {},
        **extra,
    }
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "ins_test"})


@dataclass
class Member:
    """A signed-in member, with a client that sends their session token."""

    id: str
    name: str
    admin: bool
    client: httpx.AsyncClient = field(repr=False)


@pytest.fixture(autouse=True)
async def empty_calendar() -> None:
    """Each test starts from an empty calendar: the migrations import the old
    site's events, which a test's own would be mixed up with."""
    await community.exec("DELETE FROM events")


@pytest.fixture
def gateway_url() -> str:
    return system.url("api")


@pytest.fixture
async def anonymous(gateway_url: str) -> AsyncIterator[httpx.AsyncClient]:
    """A client with no session token."""
    async with httpx.AsyncClient(
        base_url=gateway_url, headers=system.headers(), timeout=60
    ) as client:
        yield client


@pytest.fixture
async def sign_in(gateway_url: str) -> AsyncIterator[Callable[..., Member]]:
    """Signs a member in: sign_in("user_ada", "Ada", admin=True)."""
    clients: list[httpx.AsyncClient] = []

    def sign_in(user_id: str, name: str, *, admin: bool = False) -> Member:
        token = session_token(user_id, name=name, email=f"{user_id}@example.test", admin=admin)
        headers = {**system.headers(), "Authorization": f"Bearer {token}"}
        client = httpx.AsyncClient(base_url=gateway_url, headers=headers, timeout=60)
        clients.append(client)
        return Member(id=user_id, name=name, admin=admin, client=client)

    yield sign_in
    for client in clients:
        await client.aclose()


@pytest.fixture
def admin(sign_in: Callable[..., Member]) -> Member:
    return sign_in("user_erin", "Erin Host", admin=True)


@pytest.fixture
def ada(sign_in: Callable[..., Member]) -> Member:
    return sign_in("user_ada", "Ada Lovelace")


@pytest.fixture
def grace(sign_in: Callable[..., Member]) -> Member:
    return sign_in("user_grace", "Grace Hopper")
