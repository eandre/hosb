"""Calendar invitations, against the fake Google (fake_google.py): the house's
account sends every event to the members who ask, and their answers in their
calendars are their RSVPs."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest

from conftest import ORIGIN, Member, community
from fake_google import FakeGoogle
from test_google_calendar import create_event, eventually, eventually_async, expect

HOUSE = "house@hosb.test"
# The tests' members' addresses (conftest.sign_in).
ADA = "user_ada@example.test"
GRACE = "user_grace@example.test"


@pytest.fixture
async def google(fake: FakeGoogle) -> AsyncIterator[FakeGoogle]:
    for table in (
        "google_organizer",
        "invitation_subscribers",
        "invitation_events",
        "invitation_answers",
        "google_oauth_states",
    ):
        await community.exec(f"DELETE FROM {table}")
    fake.reset()
    fake.account(HOUSE)
    yield fake


async def connect_house(admin: Member, browser: httpx.AsyncClient, google: FakeGoogle) -> None:
    """An admin connects the house's account, as the admin page does."""
    started = expect(
        await admin.client.post("/api/admin/google-organizer/connect", json={"origin": ORIGIN}), 200
    )
    params = {k: v[0] for k, v in parse_qs(urlsplit(started["url"]).query).items()}
    assert "login_hint" not in params, "the house's account is the admin's to pick"
    code = google.consent(HOUSE, params["redirect_uri"])
    back = await browser.get(
        "/api/google/callback", params={"state": params["state"], "code": code}
    )
    assert back.headers["location"] == f"{ORIGIN}/admin?google=connected"


async def sync(admin: Member) -> dict[str, Any]:
    """Read the answers and send the invitations now, as "Sync now" does."""
    return expect(await admin.client.post("/api/admin/google-organizer/sync"), 200)


async def my_rsvp(member: Member, event: dict) -> str | None:
    detail = expect(await member.client.get(f"/api/events/{event['slug']}"), 200)
    return (detail["myRsvp"] or {}).get("status")


async def test_answers_in_the_calendar_are_rsvps(
    google: FakeGoogle, admin: Member, ada: Member, anonymous: httpx.AsyncClient
):
    status = expect(await ada.client.get("/api/invitations"), 200)
    assert status == {"available": False, "enabled": False, "email": ADA, "organizerEmail": ""}
    assert (await ada.client.put("/api/invitations", json={"enabled": True})).status_code == 409

    dinner = await create_event(admin, "House Dinner")
    await connect_house(admin, anonymous, google)
    organizer = expect(await admin.client.get("/api/admin/google-organizer"), 200)
    assert (organizer["connected"], organizer["googleEmail"]) == (True, HOUSE)

    enabled = expect(await ada.client.put("/api/invitations", json={"enabled": True}), 200)
    assert enabled == {"available": True, "enabled": True, "email": ADA, "organizerEmail": HOUSE}
    # Invited, with Google's email: no answer yet.
    await eventually(lambda: google.answers(HOUSE, "House Dinner") == {ADA: "needsAction"})
    invitation = google.invitation(HOUSE, "House Dinner")
    assert invitation["guestsCanSeeOtherGuests"] is False
    assert invitation["description"] == f"{ORIGIN}/events/{dinner['slug']}"
    assert google.writes_to(invitation["id"])[-1][1] == "all"

    # She says yes in her calendar: she's going.
    google.respond(HOUSE, invitation["id"], ADA, "accepted")
    await sync(admin)
    assert await my_rsvp(ada, dinner) == "going"
    google.respond(HOUSE, invitation["id"], ADA, "declined")
    await sync(admin)
    assert await my_rsvp(ada, dinner) == "not_going"

    # An RSVP in the app is her answer in the calendar, without an email.
    rsvp = f"/api/events/{dinner['id']}/rsvp"
    expect(await ada.client.put(rsvp, json={"status": "maybe"}), 200)
    await eventually(lambda: google.answers(HOUSE, "House Dinner") == {ADA: "tentative"})
    assert google.writes_to(invitation["id"])[-1] == ("PUT", "none")

    # A change to the event is sent to her, with an email.
    expect(
        await admin.client.put(
            f"/api/events/{dinner['id']}",
            json={"title": "Thanksgiving Dinner", "startsAt": dinner["startsAt"]},
        ),
        200,
    )
    await eventually(lambda: [e["summary"] for e in google.events(HOUSE)] == ["Thanksgiving Dinner"])
    assert google.writes_to(invitation["id"])[-1] == ("PUT", "all")
    assert google.answers(HOUSE, "Thanksgiving Dinner") == {ADA: "tentative"}


async def test_house_hours_invite_no_one(
    google: FakeGoogle, admin: Member, ada: Member, anonymous: httpx.AsyncClient
):
    await create_event(admin, "House Dinner")
    await create_event(admin, "House Hours", days=2)
    await connect_house(admin, anonymous, google)
    expect(await ada.client.put("/api/invitations", json={"enabled": True}), 200)

    # The house's calendar has them, without guests, so no one is emailed.
    await eventually(lambda: google.answers(HOUSE, "House Dinner") == {ADA: "needsAction"})
    await sync(admin)
    invitation = google.invitation(HOUSE, "House Hours")
    assert invitation.get("attendees", []) == []
    assert {u for _, u in google.writes_to(invitation["id"])} == {"none"}

    # One that was an invitation becomes House Hours: its guests are taken
    # off, without an email.
    supper = await create_event(admin, "Late Supper", days=3)
    await eventually(lambda: google.answers(HOUSE, "Late Supper") == {ADA: "needsAction"})
    supper_id = google.invitation(HOUSE, "Late Supper")["id"]
    renamed = {"title": "House Hours", "startsAt": supper["startsAt"]}
    expect(await admin.client.put(f"/api/events/{supper['id']}", json=renamed), 200)

    def renamed_without_guests() -> bool:
        [event] = [e for e in google.events(HOUSE) if e["id"] == supper_id]
        return event["summary"] == "House Hours" and not event.get("attendees")

    await eventually(renamed_without_guests)
    assert google.writes_to(supper_id)[-1] == ("PUT", "none")
    # And the House Dinner is still hers.
    assert google.answers(HOUSE, "House Dinner") == {ADA: "needsAction"}


async def test_a_yes_to_a_full_event_is_set_back(
    google: FakeGoogle, admin: Member, ada: Member, grace: Member, anonymous: httpx.AsyncClient
):
    supper = await create_event(admin, "Small Supper", capacity=1)
    await connect_house(admin, anonymous, google)
    expect(await ada.client.put("/api/invitations", json={"enabled": True}), 200)
    expect(await grace.client.put("/api/invitations", json={"enabled": True}), 200)
    await eventually(
        lambda: google.answers(HOUSE, "Small Supper") == {ADA: "needsAction", GRACE: "needsAction"}
    )

    expect(await grace.client.put(f"/api/events/{supper['id']}/rsvp", json={"status": "going"}), 200)
    await eventually(lambda: google.answers(HOUSE, "Small Supper")[GRACE] == "accepted")
    invitation = google.invitation(HOUSE, "Small Supper")
    google.respond(HOUSE, invitation["id"], ADA, "accepted")
    await sync(admin)
    # No place for her: her answer goes back to none.
    assert await my_rsvp(ada, supper) is None
    assert google.answers(HOUSE, "Small Supper") == {ADA: "needsAction", GRACE: "accepted"}


async def test_google_tells_of_answers(
    google: FakeGoogle, admin: Member, ada: Member, anonymous: httpx.AsyncClient
):
    dinner = await create_event(admin, "House Dinner")
    await connect_house(admin, anonymous, google)
    expect(await ada.client.put("/api/invitations", json={"enabled": True}), 200)
    await eventually(lambda: google.answers(HOUSE, "House Dinner") == {ADA: "needsAction"})
    # A channel, as Google makes over HTTPS (here the gateway has none).
    await community.exec(
        """
        UPDATE google_organizer SET channel_id = 'chan', channel_token = 'secret',
            channel_expires_at = now() + interval '1 day'
        """
    )

    def notice(token: str, state: str = "exists") -> dict[str, str]:
        return {
            "X-Goog-Channel-ID": "chan",
            "X-Goog-Channel-Token": token,
            "X-Goog-Resource-State": state,
        }

    path = "/api/google/notifications"
    assert (await anonymous.post(path, headers=notice("wrong"))).status_code == 404
    assert (await anonymous.post(path, headers=notice("secret", "sync"))).status_code == 200

    google.respond(HOUSE, google.invitation(HOUSE, "House Dinner")["id"], ADA, "tentative")
    assert (await anonymous.post(path, headers=notice("secret"))).status_code == 200

    # The sync it starts reads her answer.
    await eventually_async(lambda: my_rsvp(ada, dinner), lambda status: status == "maybe")


async def test_leaving_and_deleting_cancel_invitations(
    google: FakeGoogle, admin: Member, ada: Member, grace: Member, anonymous: httpx.AsyncClient
):
    dinner = await create_event(admin, "House Dinner")
    await create_event(admin, "Sauna Night")
    await connect_house(admin, anonymous, google)
    expect(await ada.client.put("/api/invitations", json={"enabled": True}), 200)
    expect(await grace.client.put("/api/invitations", json={"enabled": True}), 200)
    await eventually(
        lambda: all(
            google.answers(HOUSE, title) == {ADA: "needsAction", GRACE: "needsAction"}
            for title in ("House Dinner", "Sauna Night")
        )
    )

    # Grace no longer wants them: she's taken off, with Google's email.
    expect(await grace.client.put("/api/invitations", json={"enabled": False}), 200)
    await eventually(lambda: google.answers(HOUSE, "Sauna Night") == {ADA: "needsAction"})
    assert google.writes_to(google.invitation(HOUSE, "Sauna Night")["id"])[-1] == ("PUT", "all")

    # A deleted event's invitation is cancelled.
    gone = google.invitation(HOUSE, "House Dinner")["id"]
    expect(await admin.client.delete(f"/api/events/{dinner['id']}"), 204)
    await eventually(lambda: [e["summary"] for e in google.events(HOUSE)] == ["Sauna Night"])
    assert google.writes_to(gone)[-1] == ("DELETE", "all")

    # Disconnecting the house's account cancels the rest, and revokes it.
    assert (await ada.client.delete("/api/admin/google-organizer")).status_code == 403
    expect(await admin.client.delete("/api/admin/google-organizer"), 204)
    assert google.events(HOUSE) == []
    assert google.revoked
    status = expect(await ada.client.get("/api/invitations"), 200)
    # Her wish is kept, for when the house connects again.
    assert (status["available"], status["enabled"]) == (False, True)


async def test_members_choose_where_invitations_go(
    google: FakeGoogle, admin: Member, ada: Member, sign_in, anonymous: httpx.AsyncClient
):
    await create_event(admin, "House Dinner")
    await connect_house(admin, anonymous, google)

    # An account without an address: the field starts empty, and they give one.
    noemail = sign_in("user_noemail", "No Email", email="")
    status = expect(await noemail.client.get("/api/invitations"), 200)
    assert (status["enabled"], status["email"]) == (False, "")
    assert (await noemail.client.put("/api/invitations", json={"enabled": True})).status_code == 422
    bad = {"enabled": True, "email": "not-an-address"}
    assert (await noemail.client.put("/api/invitations", json=bad)).status_code == 422
    given = {"enabled": True, "email": "  Someone@Example.TEST "}
    assert expect(await noemail.client.put("/api/invitations", json=given), 200)["email"] == "someone@example.test"

    # An account with one: it's filled in, and kept unless they change it.
    assert expect(await ada.client.get("/api/invitations"), 200)["email"] == ADA
    expect(await ada.client.put("/api/invitations", json={"enabled": True}), 200)
    await eventually(
        lambda: google.answers(HOUSE, "House Dinner") == {ADA: "needsAction", "someone@example.test": "needsAction"}
    )

    # One address per member.
    taken = {"enabled": True, "email": "someone@example.test"}
    assert (await ada.client.put("/api/invitations", json=taken)).status_code == 409

    # A new address: the old one is taken off the guest list, the new one invited.
    moved = {"enabled": True, "email": "ada.private@example.test"}
    assert expect(await ada.client.put("/api/invitations", json=moved), 200)["email"] == "ada.private@example.test"
    await eventually(
        lambda: google.answers(HOUSE, "House Dinner")
        == {"ada.private@example.test": "needsAction", "someone@example.test": "needsAction"}
    )


async def test_only_admins_connect_the_house(google: FakeGoogle, ada: Member):
    assert (await ada.client.get("/api/admin/google-organizer")).status_code == 403
    connect = await ada.client.post("/api/admin/google-organizer/connect", json={"origin": ORIGIN})
    assert connect.status_code == 403
