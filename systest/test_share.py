"""Events' slugs, shareable links, and the guests who sign up through them."""

from __future__ import annotations

import csv
import io
import re
from datetime import UTC, datetime, timedelta

import httpx

from conftest import Member


def at(days: float = 0, hours: float = 0) -> str:
    return (datetime.now(UTC) + timedelta(days=days, hours=hours)).isoformat()


async def create_event(admin: Member, **fields) -> dict:
    body = {"title": "House Dinner", "startsAt": at(days=7), **fields}
    response = await admin.client.post("/api/events", json=body)
    assert response.status_code == 201, response.text
    return response.json()


def expect(response: httpx.Response, status: int) -> dict:
    assert response.status_code == status, f"{response.status_code}: {response.text}"
    return response.json() if response.content else {}


async def member_link(member: Member, event: dict) -> dict:
    response = await member.client.post(f"/api/events/{event['id']}/share-links")
    assert response.status_code in (200, 201), response.text
    return response.json()


# --- slugs -------------------------------------------------------------------


async def test_events_have_slugs_from_their_date_and_title(admin: Member, ada: Member):
    first = await create_event(admin, startsAt="2030-03-14T18:00:00Z")
    assert first["slug"] == "2030-03-14-house-dinner"
    # Another of the same name and day.
    second = await create_event(admin, startsAt="2030-03-14T20:00:00Z")
    assert second["slug"] == "2030-03-14-house-dinner-2"
    # The day is Stockholm's: 23:30 UTC is the next day there.
    late = await create_event(admin, title="Stitch & Bitch", startsAt="2030-03-14T23:30:00Z")
    assert late["slug"] == "2030-03-15-stitch-bitch"

    # A page is found by its slug, or its id.
    by_slug = expect(await ada.client.get(f"/api/events/{first['slug']}"), 200)
    assert by_slug["id"] == first["id"]
    assert expect(await ada.client.get(f"/api/events/{first['id']}"), 200)["slug"] == first["slug"]
    assert (await ada.client.get("/api/events/2030-03-14-no-such-thing")).status_code == 404

    # A new title makes a new slug, and the old one still leads to the event.
    renamed = expect(
        await admin.client.put(
            f"/api/events/{first['id']}",
            json={"title": "Candlelit Dinner", "startsAt": first["startsAt"]},
        ),
        200,
    )
    assert renamed["slug"] == "2030-03-14-candlelit-dinner"
    old = expect(await ada.client.get("/api/events/2030-03-14-house-dinner"), 200)
    assert old["id"] == first["id"]
    # So no other event is given it.
    third = await create_event(admin, startsAt="2030-03-14T19:00:00Z")
    assert third["slug"] == "2030-03-14-house-dinner-3"
    # Saving an event unchanged keeps its slug.
    kept = expect(
        await admin.client.put(
            f"/api/events/{second['id']}",
            json={"title": "House Dinner", "startsAt": second["startsAt"], "capacity": 8},
        ),
        200,
    )
    assert kept["slug"] == "2030-03-14-house-dinner-2"


# --- links -------------------------------------------------------------------


async def test_a_member_has_one_link_to_an_event(admin: Member, ada: Member, grace: Member):
    event = await create_event(admin, shareSignupCap=3)
    created = await ada.client.post(f"/api/events/{event['id']}/share-links")
    assert created.status_code == 201
    link = created.json()
    assert link["kind"] == "member"
    assert link["path"] == f"/s/{event['slug']}-{link['token']}"
    assert link["createdBy"] == "user_ada"
    assert link["eventSlug"] == event["slug"]
    assert link["signupCap"] == 3  # the event's

    # Asking again gives the same link, even with a name and a cap.
    again = await ada.client.post(
        f"/api/events/{event['id']}/share-links", json={"name": "Mine", "signupCap": 99}
    )
    assert again.status_code == 200
    assert again.json()["token"] == link["token"]
    assert again.json()["signupCap"] == 3

    # Another member has one of their own.
    assert (await member_link(grace, event))["token"] != link["token"]
    assert (await ada.client.post("/api/events/999999/share-links")).status_code == 404

    # Only admins see the links.
    assert (await ada.client.get(f"/api/events/{event['id']}/share-links")).status_code == 403
    assert (await ada.client.get("/api/admin/share-links")).status_code == 403


async def test_an_admin_makes_named_links_with_caps(admin: Member, ada: Member):
    event = await create_event(admin, shareSignupCap=5)
    path = f"/api/events/{event['id']}/share-links"
    assert (await admin.client.post(path, json={"name": "  "})).status_code == 422
    assert (await admin.client.post(path, json={"name": "x", "signupCap": 0})).status_code == 422

    flyer = expect(await admin.client.post(path, json={"name": "Flyer", "signupCap": 10}), 201)
    open_ = expect(await admin.client.post(path, json={"name": "Instagram"}), 201)
    assert flyer["kind"] == "admin"
    assert flyer["signupCap"] == 10
    assert open_["signupCap"] is None  # no limit, whatever the event's default
    assert flyer["token"] != open_["token"]

    await member_link(ada, event)
    links = expect(await admin.client.get(path), 200)["links"]
    assert [(link["name"], link["kind"]) for link in links] == [
        ("Flyer", "admin"),
        ("Instagram", "admin"),
        ("", "member"),
    ]
    everything = expect(await admin.client.get("/api/admin/share-links"), 200)["links"]
    assert {link["token"] for link in everything} == {link["token"] for link in links}


async def test_an_admins_link_can_invite_in_someone_elses_name(
    admin: Member, ada: Member, anonymous: httpx.AsyncClient
):
    event = await create_event(admin)
    path = f"/api/events/{event['id']}/share-links"
    too_long = {"name": "DJ", "invitedBy": "x" * 101}
    assert (await admin.client.post(path, json=too_long)).status_code == 422

    own = expect(await admin.client.post(path, json={"name": "Flyer", "invitedBy": "  "}), 201)
    for_lisa = expect(
        await admin.client.post(path, json={"name": "DJ", "invitedBy": " Lisa  Svensson "}), 201
    )
    assert own["invitedBy"] is None
    assert for_lisa["invitedBy"] == "Lisa Svensson"
    # A member's link is always in their own name: there is nothing to set.
    assert (await member_link(ada, event))["invitedBy"] is None

    # Guests read whose invitation it is: the admin's first name, or Lisa's.
    shared = expect(await anonymous.get(f"/api/share/{own['token']}"), 200)
    assert shared["invitedBy"] == "Erin"
    shared = expect(await anonymous.get(f"/api/share/{for_lisa['token']}"), 200)
    assert shared["invitedBy"] == "Lisa Svensson"

    # Members see that Lisa's guest came by her.
    guest = {"name": "Linus Gast", "email": "linus@example.test"}
    expect(await anonymous.post(f"/api/share/{for_lisa['token']}/signups", json=guest), 201)
    detail = expect(await ada.client.get(f"/api/events/{event['slug']}"), 200)
    assert [(g["name"], g["invitedBy"]) for g in detail["guestSignups"]] == [
        ("Linus Gast", "Lisa Svensson")
    ]
    links = expect(await admin.client.get(path), 200)["links"]
    assert [(link["name"], link["invitedBy"]) for link in links] == [
        ("Flyer", None),
        ("DJ", "Lisa Svensson"),
        ("", None),
    ]


async def test_a_link_is_the_events_slug_and_an_unguessable_token(
    admin: Member, ada: Member, anonymous: httpx.AsyncClient
):
    event = await create_event(admin, startsAt="2030-03-14T18:00:00Z")
    link = await member_link(ada, event)
    token = link["token"]
    assert re.fullmatch(r"[abcdefghjkmnpqrstuvwxyz23456789]{16}", token)
    assert link["path"] == f"/s/2030-03-14-house-dinner-{token}"

    # The path after /s/ finds the link, as does its token alone: the slug is
    # for reading.
    ref = link["path"].removeprefix("/s/")
    assert expect(await anonymous.get(f"/api/share/{ref}"), 200)["path"] == link["path"]
    assert expect(await anonymous.get(f"/api/share/{token}"), 200)["path"] == link["path"]
    # The right slug doesn't make a wrong token right.
    assert (
        await anonymous.get("/api/share/2030-03-14-house-dinner-aaaaaaaaaaaaaaaa")
    ).status_code == 404

    # Renamed, the event's link still leads to it, and says how it reads now.
    expect(
        await admin.client.put(
            f"/api/events/{event['id']}",
            json={"title": "Candlelit Dinner", "startsAt": event["startsAt"]},
        ),
        200,
    )
    renamed = expect(await anonymous.get(f"/api/share/{ref}"), 200)
    assert renamed["path"] == f"/s/2030-03-14-candlelit-dinner-{token}"
    assert (await member_link(ada, event))["path"] == renamed["path"]


# --- guests ------------------------------------------------------------------


async def test_a_link_shows_its_event_and_nothing_else(
    admin: Member, ada: Member, anonymous: httpx.AsyncClient
):
    event = await create_event(
        admin,
        description="Bring something for the table.",
        location="The long table",
        capacity=20,
    )
    link = await member_link(ada, event)

    shared = expect(await anonymous.get(f"/api/share/{link['token']}"), 200)
    assert shared["invitedBy"] == "Ada"
    assert shared["signupsOpen"] is True
    assert shared["closedReason"] is None
    assert shared["event"]["slug"] == event["slug"]
    assert shared["event"]["title"] == "House Dinner"
    assert shared["event"]["location"] == "The long table"
    assert shared["event"]["placesLeft"] == 20
    assert shared["event"]["isOver"] is False
    # Who is coming is the members' to see, not a guest's.
    assert "attendees" not in shared["event"]

    assert (await anonymous.get("/api/share/no-such-link")).status_code == 404
    # The rest of the calendar needs a member.
    assert (await anonymous.get("/api/events")).status_code == 401
    assert (await anonymous.get(f"/api/events/{event['slug']}")).status_code == 401
    assert (await anonymous.post(f"/api/events/{event['id']}/share-links")).status_code == 401


async def test_views_are_counted_by_visitor(
    admin: Member, ada: Member, anonymous: httpx.AsyncClient
):
    event = await create_event(admin)
    link = await member_link(ada, event)
    views = f"/api/share/{link['token']}/views"
    for visitor in ("visitor-aaaa", "visitor-bbbb", "visitor-aaaa"):
        assert (await anonymous.post(views, json={"visitorId": visitor})).status_code == 204
    assert (await anonymous.post(views, json={"visitorId": "x"})).status_code == 422
    assert (await anonymous.post(views, json={"visitorId": "no spaces!"})).status_code == 422
    assert (
        await anonymous.post("/api/share/no-such-link/views", json={"visitorId": "visitor-aaaa"})
    ).status_code == 404

    again = await member_link(ada, event)
    assert (again["views"], again["totalViews"]) == (2, 3)


async def test_guests_sign_up_through_a_link(
    admin: Member, ada: Member, anonymous: httpx.AsyncClient
):
    event = await create_event(admin, capacity=10)
    link = await member_link(ada, event)
    signups = f"/api/share/{link['token']}/signups"

    for bad in (
        {"name": "Linus Gast"},
        {"email": "linus@example.test"},
        {"name": " ", "email": "linus@example.test"},
        {"name": "Linus Gast", "email": "not-an-email"},
    ):
        assert (await anonymous.post(signups, json=bad)).status_code == 422, bad

    joined = await anonymous.post(
        signups, json={"name": "  Linus   Gast ", "email": "Linus@Example.TEST"}
    )
    assert joined.status_code == 201
    assert joined.json() == {"status": "signed_up", "name": "Linus Gast"}
    # The same address again is the same guest.
    again = await anonymous.post(signups, json={"name": "L G", "email": "linus@example.test"})
    assert again.status_code == 200
    assert again.json() == {"status": "already_signed_up", "name": "Linus Gast"}

    # Members see the guest, and the guest takes a place.
    detail = expect(await ada.client.get(f"/api/events/{event['slug']}"), 200)
    assert detail["guestCount"] == 1
    assert detail["goingCount"] == 1
    assert [(g["name"], g["invitedBy"]) for g in detail["guestSignups"]] == [
        ("Linus Gast", "Ada Lovelace")
    ]
    shared = expect(await anonymous.get(f"/api/share/{link['token']}"), 200)
    assert shared["event"]["placesLeft"] == 9
    assert (await member_link(ada, event))["signups"] == 1

    # The door list has them, with their address.
    door = await admin.client.get(f"/api/admin/events/{event['id']}/attendees.csv")
    rows = list(csv.reader(io.StringIO(door.text)))
    assert [r[:4] for r in rows[1:]] == [["Linus Gast", "linus@example.test", "Guest sign-up", "0"]]


async def test_a_links_cap_and_the_events_places_hold(
    admin: Member, ada: Member, grace: Member, anonymous: httpx.AsyncClient
):
    event = await create_event(admin, capacity=3, shareSignupCap=1)
    adas = await member_link(ada, event)
    flyer = expect(
        await admin.client.post(
            f"/api/events/{event['id']}/share-links", json={"name": "Flyer", "signupCap": 5}
        ),
        201,
    )

    def guest(n: int) -> dict:
        return {"name": f"Guest Number{n}", "email": f"guest{n}@example.test"}

    # A member's link takes the event's cap: one guest.
    assert (
        await anonymous.post(f"/api/share/{adas['token']}/signups", json=guest(1))
    ).status_code == 201
    full_link = await anonymous.post(f"/api/share/{adas['token']}/signups", json=guest(2))
    assert full_link.status_code == 409
    assert full_link.json()["detail"] == "This link has no sign-ups left."
    shared = expect(await anonymous.get(f"/api/share/{adas['token']}"), 200)
    assert (shared["signupsOpen"], shared["closedReason"]) == (
        False,
        "This link has no sign-ups left.",
    )

    # An admin's link has its own; the event's places still hold.
    assert (
        await anonymous.post(f"/api/share/{flyer['token']}/signups", json=guest(2))
    ).status_code == 201
    expect(await grace.client.put(f"/api/events/{event['id']}/rsvp", json={"status": "going"}), 200)
    full_event = await anonymous.post(f"/api/share/{flyer['token']}/signups", json=guest(3))
    assert full_event.status_code == 409
    assert full_event.json()["detail"] == "The event is full."
    # And guests count when members RSVP.
    no_room = await ada.client.put(f"/api/events/{event['id']}/rsvp", json={"status": "going"})
    assert no_room.status_code == 409


async def test_no_one_signs_up_for_an_event_that_is_over(
    admin: Member, ada: Member, anonymous: httpx.AsyncClient
):
    event = await create_event(admin, startsAt=at(days=-2), endsAt=at(days=-2, hours=2))
    link = await member_link(ada, event)
    shared = expect(await anonymous.get(f"/api/share/{link['token']}"), 200)
    assert shared["event"]["isOver"] is True
    assert shared["closedReason"] == "The event is over."
    over = await anonymous.post(
        f"/api/share/{link['token']}/signups",
        json={"name": "Late Guest", "email": "late@example.test"},
    )
    assert over.status_code == 409
