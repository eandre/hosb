"""The admin page's API: stats, members and door lists, for admins only."""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime, timedelta

from encore.storage import postgres

from conftest import Member

community = postgres.Database.named("community")


def at(days: float = 0, hours: float = 0) -> str:
    return (datetime.now(UTC) + timedelta(days=days, hours=hours)).isoformat()


async def create_event(admin: Member, **fields) -> dict:
    body = {"title": "House Dinner", "startsAt": at(days=7), **fields}
    response = await admin.client.post("/api/events", json=body)
    assert response.status_code == 201, response.text
    return response.json()


async def rsvp(member: Member, event: dict, status: str, *guests: str) -> None:
    response = await member.client.put(
        f"/api/events/{event['id']}/rsvp",
        json={"status": status, "guests": len(guests), "guestNames": list(guests)},
    )
    assert response.status_code == 200, response.text


async def test_only_admins_see_the_admin_api(admin: Member, ada: Member):
    event = await create_event(admin)
    for path in (
        "/api/admin/stats",
        "/api/admin/members",
        f"/api/admin/events/{event['id']}/attendees.csv",
    ):
        assert (await ada.client.get(path)).status_code == 403, path
        assert (await admin.client.get(path)).status_code == 200, path


async def test_stats_and_members(admin: Member, ada: Member, grace: Member):
    dinner = await create_event(admin, title="House Dinner")
    ritual = await create_event(admin, title="Ritual", startsAt=at(days=3))
    past = await create_event(
        admin, title="Last dinner", startsAt=at(days=-10), endsAt=at(days=-10, hours=2)
    )
    await rsvp(ada, dinner, "going", "Charles Babbage", "Mary Somerville")
    await rsvp(ada, ritual, "going")
    await rsvp(grace, dinner, "maybe")
    # One went to the past event before it was over.
    await community.exec(
        "INSERT INTO rsvps (event_id, user_id, status) VALUES ($1, 'user_grace', 'going')",
        past["id"],
    )
    # One who hasn't been seen for a while.
    await community.exec(
        "INSERT INTO members (id, name, last_seen_at) VALUES ('user_gone', 'Gone', now() - interval '60 days')"
    )

    stats = (await admin.client.get("/api/admin/stats")).json()
    assert stats == {
        "members": 4,
        "activeMembers": 3,
        "upcomingEvents": 2,
        "upcomingGoing": 4,  # Ada and two guests to dinner, Ada to the ritual
    }

    members = (await admin.client.get("/api/admin/members")).json()["members"]
    by_id = {m["id"]: m for m in members}
    assert set(by_id) == {"user_erin", "user_ada", "user_grace", "user_gone"}
    assert members[-1]["id"] == "user_gone"  # last seen longest ago
    assert by_id["user_erin"]["admin"] is True
    assert by_id["user_ada"]["admin"] is False
    assert by_id["user_ada"]["email"] == "user_ada@example.test"
    assert (by_id["user_ada"]["upcomingGoing"], by_id["user_ada"]["pastGoing"]) == (2, 0)
    assert (by_id["user_grace"]["upcomingGoing"], by_id["user_grace"]["pastGoing"]) == (0, 1)


async def test_a_member_made_admin_shows_as_one(sign_in, admin: Member):
    ada = sign_in("user_ada", "Ada Lovelace")
    await ada.client.get("/api/me")
    # Made an admin in Clerk: their next token says so.
    promoted = sign_in("user_ada", "Ada Lovelace", admin=True)
    await promoted.client.get("/api/me")

    members = (await admin.client.get("/api/admin/members")).json()["members"]
    assert {m["id"]: m["admin"] for m in members}["user_ada"] is True


async def test_door_list_csv(admin: Member, ada: Member, grace: Member, sign_in):
    event = await create_event(admin, title="Performance Night!", startsAt="2030-03-14T18:00:00Z")
    await rsvp(grace, event, "maybe")
    await rsvp(ada, event, "going", "Charles Babbage")
    # A name that a spreadsheet would run as a formula.
    mallory = sign_in("user_mallory", '=HYPERLINK("https://evil.example")')
    await rsvp(mallory, event, "not_going")

    response = await admin.client.get(f"/api/admin/events/{event['id']}/attendees.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert (
        response.headers["content-disposition"]
        == 'attachment; filename="2030-03-14-performance-night.csv"'
    )
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == ["Name", "Email", "Answer", "Guests", "Answered at"]
    assert [r[:4] for r in rows[1:]] == [
        ["Ada Lovelace", "user_ada@example.test", "Going", "1"],
        # The guests a member named, on the door list after them.
        ["Charles Babbage", "", "Guest of Ada Lovelace", "0"],
        ["Grace Hopper", "user_grace@example.test", "Maybe", "0"],
        ['\'=HYPERLINK("https://evil.example")', "user_mallory@example.test", "Can't go", "0"],
    ]

    missing = await admin.client.get("/api/admin/events/999999/attendees.csv")
    assert missing.status_code == 404
