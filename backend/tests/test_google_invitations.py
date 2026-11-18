"""Calendar invitations' own logic: what the house's event looks like, and
what makes Google email its guests."""

from datetime import UTC, datetime, timedelta

from google_invitations import ANSWER_OF, RSVP_OF, hashes, invitation_body

STARTS = datetime(2026, 11, 26, 18, 0, tzinfo=UTC)
EVENT = {
    "id": 7,
    "slug": "2026-11-26-house-dinner",
    "title": "House Dinner",
    "description": "",
    "location": "",
    "starts_at": STARTS,
    "ends_at": STARTS + timedelta(hours=4),
}


def guests(**answers: str) -> list[dict[str, str]]:
    return [{"email": email, "responseStatus": answer} for email, answer in answers.items()]


def test_the_house_event_keeps_its_guests_apart():
    body = invitation_body(EVENT, guests(a="needsAction"), "https://www.hosb.se")
    assert body["attendees"] == [{"email": "a", "responseStatus": "needsAction"}]
    assert body["guestsCanSeeOtherGuests"] is False
    assert body["guestsCanInviteOthers"] is False
    assert body["guestsCanModify"] is False
    # Whether a guest is busy is their own calendar's to say.
    assert "transparency" not in body
    assert body["extendedProperties"] == {"private": {"hosbEventId": "7"}}


def test_an_answer_alone_doesnt_change_the_content():
    def of(**answers: str) -> tuple[str, str]:
        return hashes(invitation_body(EVENT, guests(**answers), "https://www.hosb.se"))

    content, answers = of(a="needsAction", b="accepted")
    # Another answer: the same event and guests, so no email.
    assert of(a="declined", b="accepted") == (content, of(a="declined", b="accepted")[1])
    assert of(a="declined", b="accepted")[1] != answers
    # Another guest: an email.
    assert of(a="needsAction", b="accepted", c="needsAction")[0] != content
    # The order of the guests doesn't matter.
    body = invitation_body(EVENT, guests(b="accepted", a="needsAction"), "https://www.hosb.se")
    assert hashes(body) == (content, answers)


def test_answers_and_rsvps_map_both_ways():
    for status in ("going", "maybe", "not_going"):
        assert RSVP_OF[ANSWER_OF[status]] == status
    assert ANSWER_OF[None] == "needsAction"
    assert "needsAction" not in RSVP_OF  # no answer withdraws nothing
