"""Google Calendar sync, against a fake Google (fake_google.py): connecting,
choosing a calendar and which events go in it, keeping up with changes, and
disconnecting."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from encore.testing import system

from conftest import ORIGIN, Member, community
from fake_google import CLIENT_ID, FakeGoogle



@pytest.fixture
async def google(fake: FakeGoogle) -> AsyncIterator[FakeGoogle]:
    await community.exec("DELETE FROM google_connections")
    await community.exec("DELETE FROM google_oauth_states")
    fake.reset()
    yield fake


def expect(response: httpx.Response, status: int) -> Any:
    assert response.status_code == status, f"{response.status_code}: {response.text}"
    return response.json() if response.content else None


async def eventually(check: Callable[[], Any], timeout: float = 20) -> Any:
    """check()'s result once it holds: changes reach calendars through Pub/Sub."""
    deadline = time.monotonic() + timeout
    while True:
        result = check()
        if result:
            return result
        if time.monotonic() > deadline:
            raise AssertionError(f"still not so after {timeout}s")
        await asyncio.sleep(0.2)


async def eventually_async(
    fetch: Callable[[], Any], check: Callable[[Any], Any], timeout: float = 20
) -> Any:
    """What fetch() gives once check() holds of it."""
    deadline = time.monotonic() + timeout
    while True:
        result = await fetch()
        if check(result):
            return result
        if time.monotonic() > deadline:
            raise AssertionError(f"still not so after {timeout}s: {result}")
        await asyncio.sleep(0.2)


async def create_event(admin: Member, title: str, days: float = 7, **fields: Any) -> dict:
    starts = datetime.now(UTC) + timedelta(days=days)
    body = {"title": title, "startsAt": starts.isoformat(), **fields}
    return expect(await admin.client.post("/api/events", json=body), 201)


async def connect(
    member: Member, browser: httpx.AsyncClient, google: FakeGoogle, email: str, **consent: Any
) -> httpx.Response:
    """Connect as the settings page does, Google consenting for the account,
    and its answer to the browser coming back from Google."""
    started = expect(await member.client.post("/api/google/connect", json={"origin": ORIGIN}), 200)
    url = urlsplit(started["url"])
    params = {k: v[0] for k, v in parse_qs(url.query).items()}
    assert params["client_id"] == CLIENT_ID
    # Back to the callback, on the api gateway, which exposes the API.
    redirect = urlsplit(params["redirect_uri"])
    assert redirect.path == "/api/google/callback"
    assert redirect.hostname in ("api.localhost", urlsplit(system.url("api")).hostname)
    assert params["access_type"] == "offline"
    code = google.consent(email, params["redirect_uri"], **consent)
    # Google sends the browser back: no session token, the state says whose.
    return await browser.get(
        "/api/google/callback", params={"state": params["state"], "code": code}
    )


def titles(google: FakeGoogle, calendar_id: str) -> set[str]:
    return {e["summary"] for e in google.events(calendar_id)}


async def test_a_member_connects_and_their_rsvps_follow(
    google: FakeGoogle, admin: Member, ada: Member, anonymous: httpx.AsyncClient
):
    google.account("ada@gmail.com")
    status = expect(await ada.client.get("/api/google"), 200)
    assert status["enabled"] is True
    assert status["connected"] is False

    back = await connect(ada, anonymous, google, "ada@gmail.com")
    assert back.status_code == 303
    assert back.headers["location"] == f"{ORIGIN}/settings?google=connected"
    status = expect(await ada.client.get("/api/google"), 200)
    assert (status["connected"], status["googleEmail"], status["calendarId"]) == (
        True,
        "ada@gmail.com",
        None,
    )

    # The calendars she can add events to: not the one she can only read.
    calendars = expect(await ada.client.get("/api/google/calendars"), 200)["calendars"]
    assert calendars == [{"id": "ada@gmail.com", "name": "ada@gmail.com", "primary": True}]

    dinner = await create_event(admin, "House Dinner", description="Bring a dish.")
    await create_event(admin, "Sauna Night")
    rsvp = f"/api/events/{dinner['id']}/rsvp"
    expect(await ada.client.put(rsvp, json={"status": "going"}), 200)

    saved = expect(
        await ada.client.put("/api/google/settings", json={"mode": "rsvp", "calendarId": "ada@gmail.com"}),
        200,
    )
    assert (saved["calendarId"], saved["mode"], saved["lastError"]) == ("ada@gmail.com", "rsvp", "")
    assert saved["lastSyncedAt"] is not None
    # In at once, as she saved: only what she's going to.
    [event] = google.events("ada@gmail.com")
    assert event["summary"] == "House Dinner"
    assert event["transparency"] == "opaque"
    assert event["description"] == f"Bring a dish.\n\n{ORIGIN}/events/{dinner['slug']}"
    assert event["start"]["timeZone"] == "Europe/Stockholm"

    # Changes follow: the event's, and her RSVP's.
    expect(
        await admin.client.put(
            f"/api/events/{dinner['id']}",
            json={"title": "Thanksgiving Dinner", "startsAt": dinner["startsAt"]},
        ),
        200,
    )
    await eventually(lambda: titles(google, "ada@gmail.com") == {"Thanksgiving Dinner"})
    expect(await ada.client.put(rsvp, json={"status": "maybe"}), 200)
    await eventually(lambda: google.events("ada@gmail.com")[0]["transparency"] == "transparent")
    expect(await ada.client.put(rsvp, json={"status": "not_going"}), 200)
    await eventually(lambda: google.events("ada@gmail.com") == [])
    expect(await ada.client.put(rsvp, json={"status": "going"}), 200)
    await eventually(lambda: titles(google, "ada@gmail.com") == {"Thanksgiving Dinner"})
    expect(await ada.client.delete(rsvp), 200)
    await eventually(lambda: google.events("ada@gmail.com") == [])


async def test_all_events_in_a_new_calendar(
    google: FakeGoogle, admin: Member, grace: Member, anonymous: httpx.AsyncClient
):
    google.account("grace@gmail.com")
    dinner = await create_event(admin, "House Dinner")
    await create_event(admin, "Sauna Night")
    await create_event(admin, "Last Week's Party", days=-7)

    await connect(grace, anonymous, google, "grace@gmail.com")
    saved = expect(
        await grace.client.put("/api/google/settings", json={"mode": "all", "newCalendar": True}),
        200,
    )
    assert saved["calendarName"] == "House of Soft Beasts"
    [new] = [c for c in google.calendars_of("grace@gmail.com") if c.summary == "House of Soft Beasts"]
    assert saved["calendarId"] == new.id
    # Every event that isn't over, and free time: she's going to none.
    assert titles(google, new.id) == {"House Dinner", "Sauna Night"}
    assert {e["transparency"] for e in google.events(new.id)} == {"transparent"}
    assert saved["syncedEvents"] == 2

    await create_event(admin, "Movie Night")
    await eventually(lambda: "Movie Night" in titles(google, new.id))
    expect(await admin.client.delete(f"/api/events/{dinner['id']}"), 204)
    await eventually(lambda: titles(google, new.id) == {"Sauna Night", "Movie Night"})

    # Moving to her own calendar moves the events there.
    moved = expect(
        await grace.client.put(
            "/api/google/settings", json={"mode": "all", "calendarId": "grace@gmail.com"}
        ),
        200,
    )
    assert moved["calendarId"] == "grace@gmail.com"
    assert titles(google, "grace@gmail.com") == {"Sauna Night", "Movie Night"}
    assert google.events(new.id) == []


async def test_disconnecting_takes_the_events_out(
    google: FakeGoogle, admin: Member, ada: Member, anonymous: httpx.AsyncClient
):
    google.account("ada@gmail.com")
    await create_event(admin, "House Dinner")
    await connect(ada, anonymous, google, "ada@gmail.com")
    expect(
        await ada.client.put("/api/google/settings", json={"mode": "all", "calendarId": "ada@gmail.com"}),
        200,
    )
    assert titles(google, "ada@gmail.com") == {"House Dinner"}

    expect(await ada.client.delete("/api/google"), 204)
    assert google.events("ada@gmail.com") == []
    assert google.revoked, "the app's access is revoked"
    assert expect(await ada.client.get("/api/google"), 200)["connected"] is False
    # Disconnecting again is fine.
    expect(await ada.client.delete("/api/google"), 204)


async def test_a_member_reconnects_when_google_stops_accepting(
    google: FakeGoogle, admin: Member, ada: Member, anonymous: httpx.AsyncClient
):
    google.account("ada@gmail.com")
    await connect(ada, anonymous, google, "ada@gmail.com")
    expect(
        await ada.client.put("/api/google/settings", json={"mode": "all", "calendarId": "ada@gmail.com"}),
        200,
    )
    # She removes the app's access in her Google account; the next change
    # finds out.
    google.revoke_all("ada@gmail.com")
    await community.exec("UPDATE google_connections SET access_expires_at = now()")
    await create_event(admin, "Sauna Night")

    async def needs_reconnect() -> dict:
        return expect(await ada.client.get("/api/google"), 200)

    status = await eventually_async(needs_reconnect, lambda s: s["needsReconnect"])
    assert "no longer accepts" in status["lastError"]
    # Nothing to sync until she reconnects.
    assert (await ada.client.post("/api/google/sync")).status_code == 409

    # Connecting again picks up where it left off, in the same calendar.
    await connect(ada, anonymous, google, "ada@gmail.com")
    status = expect(await ada.client.get("/api/google"), 200)
    assert (status["needsReconnect"], status["calendarId"]) == (False, "ada@gmail.com")
    await eventually(lambda: titles(google, "ada@gmail.com") == {"Sauna Night"})


async def test_what_can_go_wrong_connecting(
    google: FakeGoogle, ada: Member, anonymous: httpx.AsyncClient
):
    google.account("ada@gmail.com")
    origin = await ada.client.post("/api/google/connect", json={"origin": "https://evil.example"})
    assert origin.status_code == 422

    # Calendar access left out at Google's consent screen.
    back = await connect(ada, anonymous, google, "ada@gmail.com", scope="openid email")
    assert back.headers["location"] == f"{ORIGIN}/settings?google=scopes"
    assert expect(await ada.client.get("/api/google"), 200)["connected"] is False

    # Declined.
    started = expect(await ada.client.post("/api/google/connect", json={"origin": ORIGIN}), 200)
    state = parse_qs(urlsplit(started["url"]).query)["state"][0]
    back = await anonymous.get("/api/google/callback", params={"state": state, "error": "access_denied"})
    assert back.headers["location"] == f"{ORIGIN}/settings?google=denied"
    # A state is good for one sign-in only, and an unknown one for none.
    again = await anonymous.get("/api/google/callback", params={"state": state, "code": "x"})
    assert again.status_code == 400
    assert (await anonymous.get("/api/google/callback", params={"state": "made-up"})).status_code == 400

    # Not connected: nothing to list, sync or choose.
    assert (await ada.client.get("/api/google/calendars")).status_code == 404
    assert (await ada.client.post("/api/google/sync")).status_code == 404
    bad = {"mode": "all", "calendarId": "ada@gmail.com", "newCalendar": True}
    assert (await ada.client.put("/api/google/settings", json=bad)).status_code == 422

    # A calendar she can only read can't be chosen.
    await connect(ada, anonymous, google, "ada@gmail.com")
    [holidays] = [c for c in google.calendars_of("ada@gmail.com") if c.summary == "Holidays"]
    readonly = {"mode": "all", "calendarId": holidays.id}
    assert (await ada.client.put("/api/google/settings", json=readonly)).status_code == 422


async def test_the_hourly_sync_catches_up(
    google: FakeGoogle, admin: Member, ada: Member, anonymous: httpx.AsyncClient
):
    google.account("ada@gmail.com")
    await connect(ada, anonymous, google, "ada@gmail.com")
    expect(
        await ada.client.put("/api/google/settings", json={"mode": "all", "calendarId": "ada@gmail.com"}),
        200,
    )
    # An event the calendar never heard of, as if its change were lost.
    await community.exec(
        """
        INSERT INTO events (title, starts_at, slug)
        VALUES ('Quiet Arrival', now() + interval '2 days', 'quiet-arrival')
        """
    )
    # The cron job's route, on the community service, where Encore calls it.
    expect(await anonymous.post("/internal/google-calendar/sync"), 204)
    assert titles(google, "ada@gmail.com") == {"Quiet Arrival"}
