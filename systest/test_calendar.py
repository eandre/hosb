"""End-to-end tests of the calendar: through the gateway, as the frontend
calls it, against the running app and its database."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from encore.storage import postgres
from encore.testing import system

from conftest import Member, session_token

community = postgres.Database.named("community")


def at(days: float = 0, hours: float = 0) -> str:
    """A time relative to now, as the frontend sends one."""
    return (datetime.now(UTC) + timedelta(days=days, hours=hours)).isoformat()


async def create_event(admin: Member, **fields) -> dict:
    body = {
        "title": "House Dinner",
        "description": "Our monthly dinner. Bring something for the table.",
        "location": "The long table",
        "startsAt": at(days=7),
        "endsAt": at(days=7, hours=3),
        **fields,
    }
    if "startsAt" in fields and "endsAt" not in fields:
        body["endsAt"] = None
    response = await admin.client.post("/api/events", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def expect(response: httpx.Response, status: int) -> dict:
    assert response.status_code == status, f"{response.status_code}: {response.text}"
    return response.json() if response.content else {}


# --- authentication ----------------------------------------------------------


async def test_requires_a_valid_clerk_session(anonymous: httpx.AsyncClient):
    assert expect(await anonymous.get("/api/events"), 401)["detail"] == "sign in to continue"

    async def with_token(token: str) -> httpx.Response:
        return await anonymous.get("/api/events", headers={"Authorization": f"Bearer {token}"})

    # Signed by another key than the Clerk instance's.
    other_key = (
        rsa.generate_private_key(public_exponent=65537, key_size=2048)
        .private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        .decode()
    )
    forged = await with_token(session_token("user_mallory", key=other_key))
    assert forged.status_code == 401
    assert "Signature verification failed" in forged.json()["detail"]

    expired = await with_token(session_token("user_ada", lifetime=-60))
    assert expired.status_code == 401
    assert "expired" in expired.json()["detail"]

    # Issued for a site that is not this one.
    elsewhere = await with_token(session_token("user_ada", azp="https://evil.example"))
    assert elsewhere.status_code == 401

    # Not even a JWT.
    assert (await with_token("not-a-token")).status_code == 401

    # A valid one is let in.
    assert (await with_token(session_token("user_ada"))).status_code == 200


async def test_me_says_who_is_an_admin(admin: Member, ada: Member):
    me = expect(await admin.client.get("/api/me"), 200)
    assert me == {
        "id": "user_erin",
        "name": "Erin Host",
        "email": "user_erin@example.test",
        "imageUrl": "https://img.example.test/user_erin.png",
        "admin": True,
    }
    assert expect(await ada.client.get("/api/me"), 200)["admin"] is False

    # Only "admin": true in the public metadata makes an admin.
    token = session_token("user_sneaky", metadata={"admin": "true"})
    sneaky = await ada.client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert expect(sneaky, 200)["admin"] is False

    # The members are recorded, for attendee lists.
    rows = await community.query("SELECT id, name FROM members ORDER BY id").all()
    assert [(r["id"], r["name"]) for r in rows] == [
        ("user_ada", "Ada Lovelace"),
        ("user_erin", "Erin Host"),
        ("user_sneaky", ""),
    ]


# --- events --------------------------------------------------------------------


async def test_only_admins_manage_events(admin: Member, ada: Member):
    body = {"title": "Sneaky party", "startsAt": at(days=1)}
    assert (await ada.client.post("/api/events", json=body)).status_code == 403

    event = await create_event(admin)
    path = f"/api/events/{event['id']}"
    assert (await ada.client.put(path, json=body)).status_code == 403
    assert (await ada.client.delete(path)).status_code == 403
    assert expect(await ada.client.get(path), 200)["title"] == "House Dinner"


async def test_admin_creates_changes_and_deletes_an_event(admin: Member, ada: Member):
    event = await create_event(admin, capacity=20)
    assert event["title"] == "House Dinner"
    assert event["location"] == "The long table"
    assert event["capacity"] == 20
    assert event["createdBy"] == "user_erin"
    assert event["goingCount"] == 0
    assert event["myRsvp"] is None
    assert event["attendees"] == []

    # Members see it among the upcoming events.
    listed = expect(await ada.client.get("/api/events"), 200)["events"]
    assert [e["id"] for e in listed] == [event["id"]]

    path = f"/api/events/{event['id']}"
    changed = expect(
        await admin.client.put(
            path,
            json={
                "title": "  Candlelit House Dinner ",
                "startsAt": event["startsAt"],
                "endsAt": event["endsAt"],
                "capacity": None,
            },
        ),
        200,
    )
    assert changed["title"] == "Candlelit House Dinner"
    assert changed["capacity"] is None
    assert changed["description"] == ""

    assert (await admin.client.delete(path)).status_code == 204
    assert (await ada.client.get(path)).status_code == 404
    assert (await admin.client.delete(path)).status_code == 404
    assert expect(await ada.client.get("/api/events"), 200)["events"] == []


async def test_rejects_invalid_events(admin: Member):
    async def create(**fields) -> httpx.Response:
        body = {"title": "Ritual", "startsAt": at(days=2), **fields}
        return await admin.client.post("/api/events", json=body)

    assert (await create(title="   ")).status_code == 422
    assert (await create(title="x" * 201)).status_code == 422
    assert (await create(endsAt=at(days=1))).status_code == 422  # ends before it starts
    assert (await create(startsAt="2026-12-01T19:00:00")).status_code == 422  # no time zone
    assert (await create(capacity=0)).status_code == 422
    assert (await create()).status_code == 201


async def test_lists_upcoming_past_and_ranges(admin: Member, ada: Member):
    soon = await create_event(admin, title="Slow work morning", startsAt=at(days=1), endsAt=None)
    later = await create_event(admin, title="Performance night", startsAt=at(days=10))
    ongoing = await create_event(admin, title="Ongoing", startsAt=at(hours=-1), endsAt=None)
    past = await create_event(
        admin, title="Last month's dinner", startsAt=at(days=-30), endsAt=at(days=-30, hours=3)
    )

    def titles(response: httpx.Response) -> list[str]:
        return [e["title"] for e in expect(response, 200)["events"]]

    # Upcoming: not yet over, soonest first. One without an end counts as
    # ongoing for three hours.
    assert titles(await ada.client.get("/api/events")) == [
        ongoing["title"],
        soon["title"],
        later["title"],
    ]
    assert titles(await ada.client.get("/api/events?scope=past")) == [past["title"]]

    # A range, as the month view asks: starting in [from, to).
    in_range = await ada.client.get("/api/events", params={"from": at(days=-31), "to": at(days=2)})
    assert titles(in_range) == [past["title"], ongoing["title"], soon["title"]]


# --- RSVPs ---------------------------------------------------------------------


async def test_members_rsvp_and_see_who_is_coming(admin: Member, ada: Member, grace: Member):
    event = await create_event(admin)
    rsvp = f"/api/events/{event['id']}/rsvp"

    two = {"status": "going", "guests": 2, "guestNames": ["Charles Babbage", "Mary Somerville"]}
    going = expect(await ada.client.put(rsvp, json=two), 200)
    assert going["myRsvp"] == two
    assert going["goingCount"] == 3  # Ada and her two guests

    maybe = expect(await grace.client.put(rsvp, json={"status": "maybe", "guests": 1}), 200)
    # Guests only count for those going.
    assert maybe["myRsvp"] == {"status": "maybe", "guests": 0, "guestNames": []}
    assert maybe["maybeCount"] == 1

    # Each member sees their own RSVP in the list, and everyone who is coming.
    [mine] = expect(await ada.client.get("/api/events"), 200)["events"]
    assert mine["myRsvp"] == two
    assert mine["goingCount"] == 3
    [theirs] = expect(await admin.client.get("/api/events"), 200)["events"]
    assert theirs["myRsvp"] is None

    detail = expect(await admin.client.get(f"/api/events/{event['id']}"), 200)
    assert [
        (a["name"], a["status"], a["guests"], a["guestNames"]) for a in detail["attendees"]
    ] == [
        ("Ada Lovelace", "going", 2, ["Charles Babbage", "Mary Somerville"]),
        ("Grace Hopper", "maybe", 0, []),
    ]

    # Changing one's mind.
    expect(await ada.client.put(rsvp, json={"status": "not_going"}), 200)
    withdrawn = expect(await grace.client.delete(rsvp), 200)
    assert withdrawn["myRsvp"] is None
    assert withdrawn["goingCount"] == 0
    assert [(a["name"], a["status"]) for a in withdrawn["attendees"]] == [
        ("Ada Lovelace", "not_going")
    ]

    rows = await community.query(
        "SELECT user_id, status FROM rsvps WHERE event_id = $1", event["id"]
    ).all()
    assert [(r["user_id"], r["status"]) for r in rows] == [("user_ada", "not_going")]


async def test_an_event_cannot_be_overfilled(admin: Member, ada: Member, grace: Member):
    event = await create_event(admin, capacity=3, guestNamesRequired=False)
    rsvp = f"/api/events/{event['id']}/rsvp"

    expect(await ada.client.put(rsvp, json={"status": "going", "guests": 1}), 200)
    full = await grace.client.put(rsvp, json={"status": "going", "guests": 1})
    assert full.status_code == 409
    assert full.json()["detail"] == "the event is full: 1 place(s) left"

    # The last place can be taken, and one's own place doesn't count against one.
    assert expect(await grace.client.put(rsvp, json={"status": "going"}), 200)["goingCount"] == 3
    assert (await ada.client.put(rsvp, json={"status": "going", "guests": 1})).status_code == 200
    assert (await ada.client.put(rsvp, json={"status": "going", "guests": 2})).status_code == 409

    # A place freed is a place to take.
    expect(await ada.client.put(rsvp, json={"status": "maybe"}), 200)
    assert (
        expect(await grace.client.put(rsvp, json={"status": "going", "guests": 2}), 200)[
            "goingCount"
        ]
        == 3
    )


async def test_rsvps_are_checked(admin: Member, ada: Member):
    over = await create_event(admin, startsAt=at(days=-2), endsAt=at(days=-2, hours=2))
    response = await ada.client.put(f"/api/events/{over['id']}/rsvp", json={"status": "going"})
    assert response.status_code == 409
    assert response.json()["detail"] == "the event is over"

    event = await create_event(admin)
    rsvp = f"/api/events/{event['id']}/rsvp"
    assert (await ada.client.put(rsvp, json={"status": "yes"})).status_code == 422
    assert (await ada.client.put(rsvp, json={"status": "going", "guests": 5})).status_code == 422
    assert (
        await ada.client.put("/api/events/999999/rsvp", json={"status": "going"})
    ).status_code == 404

    # Deleting an event deletes its RSVPs.
    expect(await ada.client.put(rsvp, json={"status": "going"}), 200)
    assert (await admin.client.delete(f"/api/events/{event['id']}")).status_code == 204
    row = await community.query("SELECT count(*) AS n FROM rsvps").one()
    assert row["n"] == 0


async def test_events_have_their_own_guest_rules(admin: Member, ada: Member):
    # By default: up to four guests, each with their full name.
    event = await create_event(admin)
    assert (event["maxGuests"], event["guestNamesRequired"]) == (4, True)
    rsvp = f"/api/events/{event['id']}/rsvp"

    def going(*names: str, guests: int | None = None) -> dict:
        n = len(names) if guests is None else guests
        return {"status": "going", "guests": n, "guestNames": list(names)}

    for body in (
        going(guests=1),  # unnamed
        going("Charles"),  # a first name alone
        going("Charles Babbage", "  ", guests=2),  # one of two
    ):
        unnamed = await ada.client.put(rsvp, json=body)
        assert unnamed.status_code == 422, body
        assert unnamed.json()["detail"] == "give each guest's full name, first and last"
    named = expect(await ada.client.put(rsvp, json=going("  Charles   Babbage ")), 200)
    assert named["myRsvp"]["guestNames"] == ["Charles Babbage"]
    too_many = await ada.client.put(rsvp, json=going(*[f"Guest {i} Smith" for i in range(5)]))
    assert too_many.status_code == 422
    # More names than guests is no RSVP either.
    assert (await ada.client.put(rsvp, json=going("A B", "C D", guests=1))).status_code == 422

    # An admin sets them: more guests, unnamed.
    changed = {"title": "House Dinner", "startsAt": at(days=7), "maxGuests": 6}
    changed = expect(
        await admin.client.put(
            f"/api/events/{event['id']}", json={**changed, "guestNamesRequired": False}
        ),
        200,
    )
    assert (changed["maxGuests"], changed["guestNamesRequired"]) == (6, False)
    six = expect(await ada.client.put(rsvp, json=going("Charles Babbage", guests=6)), 200)
    assert six["myRsvp"]["guests"] == 6
    assert six["myRsvp"]["guestNames"] == ["Charles Babbage"]
    assert six["goingCount"] == 7

    # Fewer than she brings: her RSVP stays as it was, but a new one keeps to it.
    none = {"title": "House Dinner", "startsAt": at(days=7), "maxGuests": 0}
    expect(await admin.client.put(f"/api/events/{event['id']}", json=none), 200)
    kept = expect(await ada.client.get(f"/api/events/{event['id']}"), 200)
    assert kept["myRsvp"]["guests"] == 6
    refused = await ada.client.put(rsvp, json=going("Charles Babbage"))
    assert refused.status_code == 422
    assert refused.json()["detail"] == "this event takes no guests"
    expect(await ada.client.put(rsvp, json=going()), 200)

    # At most twenty, for any event.
    assert (
        await admin.client.post("/api/events", json={**none, "maxGuests": 21})
    ).status_code == 422


async def test_the_app_reports_no_errors(admin: Member, ada: Member):
    """A whole flow, after which the app has logged no errors."""
    event = await create_event(admin)
    expect(await ada.client.put(f"/api/events/{event['id']}/rsvp", json={"status": "going"}), 200)
    expect(await ada.client.get(f"/api/events/{event['id']}"), 200)

    recorded = await system.telemetry()
    assert not recorded.errors(), recorded
