"""The web service: the Next.js app, and the API at /api on its origin, which
it passes on to the community service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from encore.services import httpx as services

from conftest import session_token


@pytest.fixture
async def web() -> httpx.AsyncClient:
    # The service itself, rather than its frontend's address, which a test
    # session may not know yet when the suite starts. The client carries the
    # test along. Its first call waits for Next.js's dev server to compile.
    async with services.client("web", timeout=120) as client:
        yield client


async def test_serves_the_app(web: httpx.AsyncClient):
    page = await web.get("/")
    assert page.status_code == 200, page.text[:300]
    assert page.headers["content-type"].startswith("text/html")
    assert "<title>House of Soft Beasts · Calendar</title>" in page.text


async def test_passes_the_api_on(web: httpx.AsyncClient):
    assert (await web.get("/api/health")).json() == {"ok": True}

    # Statuses and headers come back as the API gave them.
    anonymous = await web.get("/api/events")
    assert anonymous.status_code == 401
    assert anonymous.headers["www-authenticate"] == "Bearer"

    # Bodies, methods and query strings go through.
    admin = {"Authorization": f"Bearer {session_token('user_erin', name='Erin', admin=True)}"}
    starts = datetime.now(UTC) + timedelta(days=3)
    created = await web.post(
        "/api/events",
        headers=admin,
        json={"title": "Stitch & Bitch", "startsAt": starts.isoformat()},
    )
    assert created.status_code == 201, created.text
    event = created.json()
    assert event["title"] == "Stitch & Bitch"

    listed = await web.get("/api/events", headers=admin, params={"scope": "upcoming"})
    assert [e["id"] for e in listed.json()["events"]] == [event["id"]]

    deleted = await web.delete(f"/api/events/{event['id']}", headers=admin)
    assert deleted.status_code == 204
    assert (await web.get(f"/api/events/{event['id']}", headers=admin)).status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "/api/internal/google-calendar/sync",
        "/api/%69nternal/google-calendar/sync",
        "//api//internal/google-calendar/sync",
        "/api/events/../internal/google-calendar/sync",
    ],
)
async def test_keeps_the_internal_routes_in(web: httpx.AsyncClient, path: str):
    # Encore calls the cron jobs' routes on the community service itself.
    assert (await web.post(path)).status_code == 404
