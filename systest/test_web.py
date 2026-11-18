"""The web service: the Vite app, served from the frontend's own origin, and
the API it calls on the api gateway."""

from __future__ import annotations

import re
from urllib.parse import urlsplit

import httpx
import pytest
from encore.services import httpx as services
from encore.testing import system

from conftest import session_token


@pytest.fixture
async def web() -> httpx.AsyncClient:
    # The service itself, which the client carries the test to.
    async with services.client("web", timeout=60) as client:
        yield client


@pytest.fixture
async def gateway() -> httpx.AsyncClient:
    """A client of the api gateway, as the world reaches it: from the
    frontend's page, across origins."""
    async with httpx.AsyncClient(
        base_url=system.url("api"), headers=system.headers(), timeout=60
    ) as client:
        yield client


async def test_serves_the_app_and_tells_it_where_the_api_is(web: httpx.AsyncClient):
    page = await web.get("/")
    assert page.status_code == 200, page.text[:300]
    assert page.headers["content-type"].startswith("text/html")
    assert "<title>House of Soft Beasts · Calendar</title>" in page.text
    config = re.search(r'<script>window.hosb = \{"apiURL":"([^"]+)"\}</script>', page.text)
    assert config, page.text[:500]
    # The api gateway's origin: here, its name on the session's app port.
    told, session = urlsplit(config[1]), urlsplit(system.url("api"))
    assert (told.hostname, told.port) == ("api.localhost", session.port), config[1]

    # The app's own routes get its page, which decides what's at them.
    for path in ("/events/2026-11-26-house-dinner", "/s/x-abc", "/settings"):
        routed = await web.get(path)
        assert routed.status_code == 200
        assert "window.hosb" in routed.text

    # Its scripts, which are cached for good, and nothing for what's missing.
    script = re.search(r'src="(/assets/[^"]+\.js)"', page.text)
    assert script, page.text[:500]
    asset = await web.get(script[1])
    assert asset.status_code == 200
    assert "immutable" in asset.headers["cache-control"]
    assert (await web.get("/assets/no-such-file.js")).status_code == 404


async def test_the_gateway_exposes_the_api_to_the_frontend(gateway: httpx.AsyncClient):
    assert (await gateway.get("/api/health")).json() == {"ok": True}
    assert (await gateway.get("/api/events")).status_code == 401

    # The page calls it from the frontend's origin, with the member's token.
    token = session_token("user_erin", name="Erin", admin=True)
    preflight = await gateway.options(
        "/api/events",
        headers={
            "Origin": system.url("web"),
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )
    assert preflight.headers.get("access-control-allow-origin") == system.url("web")
    assert "authorization" in preflight.headers.get("access-control-allow-headers", "").lower()
    listed = await gateway.get(
        "/api/events",
        headers={"Authorization": f"Bearer {token}", "Origin": system.url("web")},
    )
    assert listed.status_code == 200, listed.text
    assert listed.headers.get("access-control-allow-origin") == system.url("web")

    # An origin that isn't the app's gets no such leave.
    other = await gateway.get("/api/health", headers={"Origin": "https://evil.example"})
    assert other.headers.get("access-control-allow-origin") != "https://evil.example"


@pytest.mark.parametrize(
    "path",
    [
        "/internal/google-calendar/sync",
        "/api/internal/google-calendar/sync",
        "/api/../internal/google-calendar/sync",
    ],
)
async def test_the_gateway_keeps_the_internal_routes_in(gateway: httpx.AsyncClient, path: str):
    # Encore calls the cron jobs' routes on the community service itself.
    assert (await gateway.post(path)).status_code == 404
