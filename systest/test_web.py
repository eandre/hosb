"""The web service, behind the api gateway: the Vite app, and the API at /api
on the same origin, which it passes on to the community service."""

from __future__ import annotations

import re

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
    """A client of the api gateway, as the world reaches the app."""
    async with httpx.AsyncClient(
        base_url=system.url("api"), headers=system.headers(), timeout=60
    ) as client:
        yield client


async def test_serves_the_app(web: httpx.AsyncClient):
    page = await web.get("/")
    if page.status_code == 503 and "hasn't been built" in page.text:
        # Builds run the app's build (the prebuild hook); tests don't, so a
        # checkout that hasn't built it serves this. site_test.go covers
        # the serving without it.
        pytest.skip("the app isn't built in this checkout: run `bun run build` in frontend/")
    assert page.status_code == 200, page.text[:300]
    assert page.headers["content-type"].startswith("text/html")
    assert "<title>House of Soft Beasts · Calendar</title>" in page.text

    # The app's own routes get its page, which decides what's at them.
    for path in ("/events/2026-11-26-house-dinner", "/s/x-abc", "/settings", "/legal/privacy", "/legal/tos"):
        routed = await web.get(path)
        assert routed.status_code == 200
        assert "<title>House of Soft Beasts · Calendar</title>" in routed.text

    # Its scripts, which are cached for good, and nothing for what's missing.
    script = re.search(r'src="(/assets/[^"]+\.js)"', page.text)
    assert script, page.text[:500]
    asset = await web.get(script[1])
    assert asset.status_code == 200
    assert "immutable" in asset.headers["cache-control"]
    assert (await web.get("/assets/no-such-file.js")).status_code == 404


async def test_the_api_is_on_the_apps_origin(gateway: httpx.AsyncClient):
    assert (await gateway.get("/api/health")).json() == {"ok": True}

    # Statuses and headers come back as the API gave them.
    anonymous = await gateway.get("/api/events")
    assert anonymous.status_code == 401
    assert anonymous.headers["www-authenticate"] == "Bearer"

    # Bodies, methods and query strings go through, with the member's token.
    admin = {"Authorization": f"Bearer {session_token('user_erin', name='Erin', admin=True)}"}
    created = await gateway.post(
        "/api/events",
        headers=admin,
        json={"title": "Stitch & Bitch", "startsAt": "2030-01-05T18:00:00+00:00"},
    )
    assert created.status_code == 201, created.text
    event = created.json()
    listed = await gateway.get("/api/events", headers=admin, params={"scope": "upcoming"})
    assert [e["id"] for e in listed.json()["events"]] == [event["id"]]
    deleted = await gateway.delete(f"/api/events/{event['id']}", headers=admin)
    assert deleted.status_code == 204


@pytest.mark.parametrize(
    "path",
    [
        "/internal/google-calendar/sync",
        "/api/internal/google-calendar/sync",
        "/api/../internal/google-calendar/sync",
    ],
)
async def test_the_internal_routes_stay_in(gateway: httpx.AsyncClient, path: str):
    # Encore calls the cron jobs' routes on the community service itself;
    # through the gateway they're the app's pages (which take no POST), or
    # the API's (which has no such route).
    assert (await gateway.post(path)).status_code in (404, 405)


async def test_event_pages_have_link_previews(web: httpx.AsyncClient, gateway: httpx.AsyncClient):
    if (await web.get("/")).status_code == 503:
        pytest.skip("the app isn't built in this checkout: run `bun run build` in frontend/")
    admin = {"Authorization": f"Bearer {session_token('user_erin', name='Erin Host', admin=True)}"}
    created = await gateway.post(
        "/api/events",
        headers=admin,
        json={
            "title": "Supper & Song",
            "startsAt": "2030-01-05T17:00:00+00:00",
            "endsAt": "2030-01-05T21:00:00+00:00",
        },
    )
    assert created.status_code == 201, created.text
    event = created.json()

    # What WhatsApp and the like read, signed in or not: the page's own HTML.
    page = (await web.get(f"/events/{event['slug']}")).text
    assert '<meta property="og:title" content="Supper &amp; Song" />' in page
    assert "Saturday 5 January 2030, 18:00–22:00" in page
    assert "<title>Supper &amp; Song · House of Soft Beasts</title>" in page

    # A shareable link's says who invites.
    link = await gateway.post(
        f"/api/events/{event['id']}/share-links",
        headers=admin,
        json={"name": "Flyer", "invitedBy": "Lisa"},
    )
    assert link.status_code == 201, link.text
    shared = (await web.get(link.json()["path"])).text
    assert "Lisa invites you · Saturday 5 January 2030" in shared

    # An event that isn't there: the calendar's own.
    unknown = (await web.get("/events/2030-01-01-no-such-event")).text
    assert '<meta property="og:title" content="House of Soft Beasts · Calendar" />' in unknown
