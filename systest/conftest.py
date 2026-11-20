"""Helpers for the system tests: Clerk-style session tokens and API clients.

The tests can't sign in through Clerk, so they sign session tokens of their
own, shaped as the Clerk instance's are once its session token is customized
(see backend/auth.py), with clerk_test_key.pem. The app verifies them with the
key's public half, which secrets.test.toml gives it as the ClerkJWTKey secret.
"""

from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
import jwt
import pytest
from encore.services import httpx as services
from encore.storage import postgres

from fake_google import FakeGoogle, serve

TEST_KEY = (Path(__file__).parent / "clerk_test_key.pem").read_text()

community = postgres.Database.named("community")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip every test in CI: they need the whole app running, with Encore.
    CI counts as set unless it is empty, "0" or "false"."""
    if os.environ.get("CI", "").strip().lower() in ("", "0", "false"):
        return
    skip = pytest.mark.skip(reason="system tests don't run in CI (CI is set)")
    for item in items:
        item.add_marker(skip)


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
async def anonymous() -> AsyncIterator[httpx.AsyncClient]:
    """A client of the community service with no session token. The gateway
    doesn't route to it (the web service passes /api on to it), so the tests
    call it directly, as a service client carrying the test."""
    async with services.client("community", timeout=60) as client:
        yield client


@pytest.fixture
async def sign_in() -> AsyncIterator[Callable[..., Member]]:
    """Signs a member in: sign_in("user_ada", "Ada", admin=True). Their
    account's address is <user_id>@example.test, unless email says another
    ("" for none)."""
    clients: list[httpx.AsyncClient] = []

    def sign_in(user_id: str, name: str, *, admin: bool = False, email: str | None = None) -> Member:
        address = f"{user_id}@example.test" if email is None else email
        token = session_token(user_id, name=name, email=address, admin=admin)
        client = services.client(
            "community", headers={"Authorization": f"Bearer {token}"}, timeout=60
        )
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


@pytest.fixture(scope="session")
def fake() -> Iterator[FakeGoogle]:
    """The fake Google (fake_google.py), on the port the test config gives the
    backend: one for the session, as the port is."""
    google = FakeGoogle()
    server = serve(google)
    yield google
    server.shutdown()
