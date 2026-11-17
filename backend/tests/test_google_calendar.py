"""Google Calendar sync's own logic: what an event looks like in a calendar,
which origins Google may send members back to, and the tokens it keeps.

Under test, settings.test.config.toml allows the origin http://localhost:4000
only, and secrets.test.toml gives the GoogleTokenKey secret a test value.
"""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from google_calendar import (
    ADDRESS,
    SettingsIn,
    check_origin,
    content_hash,
    event_body,
    id_token_email,
    seal,
    unseal,
)

STARTS = datetime(2026, 11, 26, 18, 0, tzinfo=UTC)


def event(**fields) -> dict:
    return {
        "id": 7,
        "slug": "2026-11-26-house-dinner",
        "title": "House Dinner",
        "description": "Bring something for the table.",
        "location": "The long table",
        "starts_at": STARTS,
        "ends_at": STARTS + timedelta(hours=4),
        "my_status": "going",
    } | fields


def test_an_event_in_a_calendar():
    body = event_body(event(), "https://www.hosb.se")
    link = "https://www.hosb.se/events/2026-11-26-house-dinner"
    assert body["summary"] == "House Dinner"
    assert body["description"] == f"Bring something for the table.\n\n{link}"
    assert body["location"] == f"The long table, {ADDRESS}"
    assert body["start"] == {"dateTime": "2026-11-26T18:00:00+00:00", "timeZone": "Europe/Stockholm"}
    assert body["end"] == {"dateTime": "2026-11-26T22:00:00+00:00", "timeZone": "Europe/Stockholm"}
    assert body["source"] == {"title": "House of Soft Beasts", "url": link}
    assert body["extendedProperties"] == {"private": {"hosbEventId": "7"}}


def test_an_event_without_an_end_description_or_place():
    body = event_body(
        event(ends_at=None, description="  ", location=""), "http://localhost:4000"
    )
    # Three hours, as the calendar counts an event without an end.
    assert body["end"]["dateTime"] == "2026-11-26T21:00:00+00:00"
    assert body["description"] == "http://localhost:4000/events/2026-11-26-house-dinner"
    assert body["location"] == ADDRESS


@pytest.mark.parametrize(
    ("status", "transparency"),
    [("going", "opaque"), ("maybe", "transparent"), ("not_going", "transparent"), (None, "transparent")],
)
def test_only_what_the_member_is_going_to_makes_them_busy(status, transparency):
    assert event_body(event(my_status=status), "https://www.hosb.se")["transparency"] == transparency


def test_the_hash_changes_with_what_is_sent_only():
    body = event_body(event(), "https://www.hosb.se")
    assert content_hash(body) == content_hash(event_body(event(), "https://www.hosb.se"))
    assert content_hash(body) != content_hash(event_body(event(title="Supper"), "https://www.hosb.se"))
    assert content_hash(body) != content_hash(event_body(event(my_status="maybe"), "https://www.hosb.se"))


def test_google_sends_members_back_to_the_apps_own_origins():
    assert check_origin("http://localhost:4000") == "http://localhost:4000"
    assert check_origin(" http://localhost:4000/ ") == "http://localhost:4000"
    for bad in ("https://evil.example", "localhost:4000", "javascript:alert(1)", "http://localhost:4000/x"):
        with pytest.raises(HTTPException) as err:
            check_origin(bad)
        assert err.value.status_code == 422, bad


def test_tokens_are_kept_encrypted():
    sealed = seal("ya29.a-token")
    assert "ya29" not in sealed
    assert unseal(sealed) == "ya29.a-token"


def test_the_google_account_is_read_from_the_id_token():
    assert id_token_email(jwt.encode({"email": "ada@gmail.com"}, "k" * 32, algorithm="HS256")) == "ada@gmail.com"
    assert id_token_email(None) == ""
    assert id_token_email("not a token") == ""


def test_settings_name_one_calendar():
    assert SettingsIn.model_validate({"mode": "all", "calendarId": "primary"}).calendar_id == "primary"
    assert SettingsIn.model_validate({"mode": "rsvp", "newCalendar": True}).new_calendar
    for bad in (
        {"mode": "rsvp"},
        {"mode": "rsvp", "calendarId": "primary", "newCalendar": True},
        {"mode": "everything", "calendarId": "primary"},
    ):
        with pytest.raises(ValidationError):
            SettingsIn.model_validate(bad)
