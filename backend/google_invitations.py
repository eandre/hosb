"""Calendar invitations: every event as an invitation in members' calendars,
where their answer (yes, maybe, no) is their RSVP.

Google shows an event's guests its yes/maybe/no only when someone else
organizes it, so the invitations come from the house's own Google account,
which an admin connects on the admin page (the organizer). Each house event
is one event in its calendar, with every member who asked for invitations
as a guest, at the address they gave (their account's, unless they gave
another): they need no Google account themselves, as Google emails the
invitation to any address.

GET    /api/invitations                         the member's invitations, and whether
                                                there are any to be had
PUT    /api/invitations                         {"enabled": true|false, "email": "..."}: the
                                                address defaults to the account's
GET    /api/admin/google-organizer              the house's account (admin)
POST   /api/admin/google-organizer/connect      {"origin": "https://..."}: where to sign
                                                in to Google as the house (admin)
POST   /api/admin/google-organizer/sync         sync now (admin)
DELETE /api/admin/google-organizer              disconnect: the invitations are cancelled
POST   /api/google/notifications                Google telling of a change in the
                                                house's calendar (its push channel)

A sync, done one at a time:
1. Reads what changed in the house's calendar since the last read (Google's
   sync token): an attendee's answer that differs from the one Google last
   had (invitation_answers) is the member's, made in their calendar, and is
   saved as their RSVP. One the app refuses, as for an event that's full,
   is set back in the next step.
2. Brings the house's events up to date with the calendar's events and their
   RSVPs: new events and guests, and changes to the event, are sent with
   Google's emails to the guests; a changed RSVP alone, without.

Syncs follow the calendar-changes topic (an event's or an RSVP's change), and
the invitation-syncs topic: a member's asking for invitations or no longer,
the organizer connecting, and Google's push notifications. A cron job syncs
every ten minutes, catching up on what those missed, and renews the push
channel, which Google lets live a week. Google only calls an HTTPS address,
so there's no channel locally: the cron job and "Sync now" read the answers.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets as pysecrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from urllib.parse import quote

from encore import gateways, pubsub
from encore.cron import Job
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from calendar_changes import LOCAL_HANDLERS, CalendarChange, calendar_changes, run_soon
from db import db
from events import DEFAULT_DURATION_SQL, Admin, Member, Model, RSVPStatus, save_rsvp
from share import EMAIL
from google_calendar import (
    ON_CONNECTED,
    Connected,
    ConnectIn,
    ConnectOut,
    Google,
    GoogleError,
    ReauthNeeded,
    configured,
    event_body,
    require_setup,
    revoke,
    seal,
    sign_in_url,
    unseal,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")
internal = APIRouter(prefix="/internal")

Answer = Literal["needsAction", "accepted", "tentative", "declined"]

# An RSVP as an attendee's answer, and back.
ANSWER_OF: dict[str | None, Answer] = {
    "going": "accepted",
    "maybe": "tentative",
    "not_going": "declined",
    None: "needsAction",
}
RSVP_OF: dict[str, RSVPStatus] = {
    "accepted": "going",
    "tentative": "maybe",
    "declined": "not_going",
}

# How long before a push channel expires it is renewed, and for how long.
CHANNEL_RENEW = timedelta(days=1)
CHANNEL_TTL = timedelta(days=7)


class InvitationSync(BaseModel):
    """Bring the invitations up to date, after something no event's change
    says: a guest list's change, the organizer connecting, Google's notice."""

    reason: str = ""


invitation_syncs = pubsub.Topic[InvitationSync]("invitation-syncs")


async def request_sync(reason: str) -> None:
    """A sync, started here at once and published for the topic's delivery to
    do again (see calendar_changes.py). A failure is logged: the cron job
    catches up."""
    run_soon("invitations sync", sync_invitations())
    try:
        await invitation_syncs.publish(InvitationSync(reason=reason))
    except Exception:
        logger.exception("publishing an invitation sync", extra={"reason": reason})


# --- the house's account -------------------------------------------------------


async def save_organizer_token(sealed: str, expires: datetime) -> None:
    await db.exec(
        "UPDATE google_organizer SET access_token = $1, access_expires_at = $2",
        sealed,
        expires,
    )


def organizer_google(row: dict[str, Any]) -> Google:
    return Google(row, save_token=save_organizer_token)


async def lock_invitations(tx: Any) -> None:
    """Hold the invitations until the transaction ends: one sync at a time."""
    await tx.exec("SELECT pg_advisory_xact_lock(hashtext('google-invitations'))")


async def organizer_connected(c: Connected) -> None:
    """The house's account, connected or reconnected by an admin."""
    async with db.begin() as tx:
        await lock_invitations(tx)
        previous = await tx.query("SELECT google_email FROM google_organizer").first()
        if previous is not None and previous["google_email"] != c.email:
            # Another account: its events are the old account's, out of reach.
            await tx.exec("DELETE FROM invitation_events")
            await tx.exec("DELETE FROM invitation_answers")
        await tx.exec(
            """
            INSERT INTO google_organizer
                (google_email, refresh_token, access_token, access_expires_at, app_origin,
                 connected_by)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (id) DO UPDATE
                SET refresh_token = EXCLUDED.refresh_token,
                    access_token = EXCLUDED.access_token,
                    access_expires_at = EXCLUDED.access_expires_at,
                    app_origin = EXCLUDED.app_origin,
                    connected_by = EXCLUDED.connected_by,
                    status = 'ok', last_error = '', updated_at = now(),
                    sync_token = CASE WHEN google_organizer.google_email = EXCLUDED.google_email
                                      THEN google_organizer.sync_token END,
                    google_email = EXCLUDED.google_email
            """,
            c.email,
            seal(c.refresh_token),
            seal(c.access_token),
            c.expires,
            c.origin,
            c.user_id,
        )
    logger.info("connected the house's google account", extra={"by": c.user_id})
    await request_sync("the organizer connected")


ON_CONNECTED["organizer"] = organizer_connected


async def mark_organizer(status: str, error: str) -> None:
    await db.exec(
        "UPDATE google_organizer SET status = $1, last_error = $2, updated_at = now()",
        status,
        error,
    )


# --- reading answers -----------------------------------------------------------


async def list_changes(google: Google, calendar_id: str, sync_token: str | None) -> tuple[list[dict[str, Any]], str | None]:
    """The calendar's events changed since sync_token (all of them without
    one), and the token to read on from. A token Google no longer accepts
    starts over."""
    path = f"/calendars/{quote(calendar_id, safe='')}/events"
    items: list[dict[str, Any]] = []
    params: dict[str, str] = {"maxResults": "250"}
    if sync_token:
        params["syncToken"] = sync_token
    while True:
        page = await google.call("GET", path, params=params, missing_ok=True)
        if page is None:
            if "syncToken" not in params:
                raise GoogleError("the house's calendar can't be read")
            # Expired (410): read everything again.
            return await list_changes(google, calendar_id, None)
        items.extend(page.get("items", []))
        if page.get("nextPageToken"):
            params = {**params, "pageToken": page["nextPageToken"]}
            continue
        return items, page.get("nextSyncToken")


async def read_answers(google: Google, org: dict[str, Any]) -> set[int]:
    """Save the answers members gave in their calendars as their RSVPs.
    Returns the events whose answers were refused, to be set back."""
    refused: set[int] = set()
    items, token = await list_changes(google, org["calendar_id"], org["sync_token"])
    subscribers = {
        row["email"]: row["user_id"]
        for row in await db.query("SELECT user_id, email FROM invitation_subscribers").all()
    }
    for item in items:
        ref = item.get("extendedProperties", {}).get("private", {}).get("hosbEventId", "")
        if not ref.isdigit() or item.get("status") == "cancelled":
            continue
        event_id = int(ref)
        known = {
            row["user_id"]: row["answer"]
            for row in await db.query(
                "SELECT user_id, answer FROM invitation_answers WHERE event_id = $1", event_id
            ).all()
        }
        for attendee in item.get("attendees", []):
            user_id = subscribers.get(str(attendee.get("email", "")).lower())
            answer = attendee.get("responseStatus", "needsAction")
            if user_id is None or answer == known.get(user_id):
                continue
            # Theirs: Google has an answer the app didn't give it.
            await db.exec(
                """
                INSERT INTO invitation_answers (event_id, user_id, answer) VALUES ($1, $2, $3)
                ON CONFLICT (event_id, user_id) DO UPDATE SET answer = EXCLUDED.answer
                """,
                event_id,
                user_id,
                answer,
            )
            status = RSVP_OF.get(answer)
            if status is None:
                continue  # needsAction: no answer, which withdraws nothing
            try:
                guests = await current_guests(event_id, user_id) if status == "going" else 0
                await save_rsvp(event_id, user_id, status, guests)
                logger.info(
                    "took an invitation's answer as an rsvp",
                    extra={"user": user_id, "event_id": event_id, "status": status},
                )
            except HTTPException as err:
                # Full, or over: sent again, with their RSVP as it is.
                logger.info(
                    "an invitation's answer was refused",
                    extra={"user": user_id, "event_id": event_id, "reason": err.detail},
                )
                await db.exec(
                    "UPDATE invitation_events SET answers_hash = '' WHERE event_id = $1", event_id
                )
                refused.add(event_id)
    await db.exec("UPDATE google_organizer SET sync_token = $1", token)
    org["sync_token"] = token
    return refused


async def current_guests(event_id: int, user_id: str) -> int:
    """The guests a member already said they'd bring, which an invitation's
    yes keeps: Google has no say in them."""
    row = await db.query(
        "SELECT guests FROM rsvps WHERE event_id = $1 AND user_id = $2 AND status = 'going'",
        event_id,
        user_id,
    ).first()
    return 0 if row is None else row["guests"]


# --- sending invitations -------------------------------------------------------

# The events to invite to: those not over, with their {only} narrowing ($1).
WANTED_QUERY = f"""
SELECT id, slug, title, description, location, starts_at, ends_at
FROM events
WHERE COALESCE(ends_at, starts_at + {DEFAULT_DURATION_SQL}) >= now() {{only}}
"""


def invitation_body(
    event: dict[str, Any], guests: list[dict[str, str]], app_origin: str
) -> dict[str, Any]:
    """A house event as the organizer's event, with its guests and their
    answers."""
    body = event_body({**event, "my_status": None}, app_origin)
    # The guests' own calendars say whether they're busy.
    body.pop("transparency")
    return {
        **body,
        "attendees": guests,
        # Members see the house, not who else is invited.
        "guestsCanSeeOtherGuests": False,
        "guestsCanInviteOthers": False,
        "guestsCanModify": False,
    }


def hashes(body: dict[str, Any]) -> tuple[str, str]:
    """The event and who's invited, and their answers, apart."""
    answers = {a["email"]: a["responseStatus"] for a in body["attendees"]}
    content = {**body, "attendees": sorted(a["email"] for a in body["attendees"])}

    def digest(value: Any) -> str:
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    return digest(content), digest(answers)


async def send_invitations(google: Google, org: dict[str, Any], event_ids: list[int] | None) -> None:
    """Make the house's calendar hold every event not over, inviting every
    subscriber with their RSVP as their answer: of every event, or the ones
    given."""
    calendar = quote(org["calendar_id"], safe="")
    narrow = [] if event_ids is None else [event_ids]
    wanted = {
        row["id"]: row
        for row in await db.query(
            WANTED_QUERY.format(only="" if event_ids is None else "AND id = ANY($1)"), *narrow
        ).all()
    }
    sent = {
        row["event_id"]: row
        for row in await db.query(
            "SELECT event_id, google_event_id, content_hash, answers_hash FROM invitation_events"
            + ("" if event_ids is None else " WHERE event_id = ANY($1)"),
            *narrow,
        ).all()
    }
    subscribers = await db.query(
        "SELECT user_id, email FROM invitation_subscribers ORDER BY email"
    ).all()
    rsvps: dict[tuple[int, str], str] = {}
    if wanted and subscribers:
        for row in await db.query(
            "SELECT event_id, user_id, status FROM rsvps WHERE event_id = ANY($1)", list(wanted)
        ).all():
            rsvps[(row["event_id"], row["user_id"])] = row["status"]

    # Deleted events, and events no longer wanted: cancelled, with Google's
    # email to the guests, but for those that are over, which stay.
    stale = [r for i, r in sent.items() if i not in wanted]
    if stale:
        over = {
            row["id"]
            for row in await db.query(
                f"SELECT id FROM events WHERE id = ANY($1)"
                f" AND COALESCE(ends_at, starts_at + {DEFAULT_DURATION_SQL}) < now()",
                [r["event_id"] for r in stale],
            ).all()
        }
        for row in stale:
            if row["event_id"] in over:
                continue
            path = f"/calendars/{calendar}/events/{quote(row['google_event_id'], safe='')}"
            await google.call("DELETE", path, params={"sendUpdates": "all"}, missing_ok=True)
            await db.exec("DELETE FROM invitation_events WHERE event_id = $1", row["event_id"])
            await db.exec("DELETE FROM invitation_answers WHERE event_id = $1", row["event_id"])

    for event_id, event in wanted.items():
        guests = [
            {"email": s["email"], "responseStatus": ANSWER_OF[rsvps.get((event_id, s["user_id"]))]}
            for s in subscribers
        ]
        body = invitation_body(event, guests, org["app_origin"])
        content, answers = hashes(body)
        row = sent.get(event_id)
        if row is not None and (row["content_hash"], row["answers_hash"]) == (content, answers):
            continue
        # Guests are told of a new event, or of a change to it or to who's
        # invited; not of their own RSVP, made in the app, coming through.
        notify_guests = row is None or row["content_hash"] != content
        params = {"sendUpdates": "all" if notify_guests else "none"}
        google_id = None
        if row is not None:
            path = f"/calendars/{calendar}/events/{quote(row['google_event_id'], safe='')}"
            updated = await google.call("PUT", path, body=body, params=params, missing_ok=True)
            google_id = None if updated is None else updated["id"]
        if google_id is None:
            params["sendUpdates"] = "all"
            created = await google.call("POST", f"/calendars/{calendar}/events", body=body, params=params)
            assert created is not None
            google_id = created["id"]
        # Recorded as soon as it's sent, as a member's calendar sync does.
        await db.exec(
            """
            INSERT INTO invitation_events (event_id, google_event_id, content_hash, answers_hash)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (event_id) DO UPDATE
                SET google_event_id = EXCLUDED.google_event_id,
                    content_hash = EXCLUDED.content_hash,
                    answers_hash = EXCLUDED.answers_hash, synced_at = now()
            """,
            event_id,
            google_id,
            content,
            answers,
        )
        # What Google now has as each guest's answer: one it has otherwise
        # later is theirs.
        await db.exec("DELETE FROM invitation_answers WHERE event_id = $1", event_id)
        for s, guest in zip(subscribers, guests, strict=True):
            await db.exec(
                "INSERT INTO invitation_answers (event_id, user_id, answer) VALUES ($1, $2, $3)",
                event_id,
                s["user_id"],
                guest["responseStatus"],
            )


async def watch(google: Google, org: dict[str, Any]) -> None:
    """Have Google tell of the calendar's changes, renewing the channel before
    it expires. Only an HTTPS address is called, so none is made locally."""
    expires = org["channel_expires_at"]
    if expires is not None and expires > datetime.now(UTC) + CHANNEL_RENEW:
        return
    address = f"{gateways.url('api')}/api/google/notifications"
    if not address.startswith("https://"):
        return
    channel_id, token = str(uuid.uuid4()), pysecrets.token_urlsafe(32)
    created = await google.call(
        "POST",
        f"/calendars/{quote(org['calendar_id'], safe='')}/events/watch",
        body={
            "id": channel_id,
            "type": "web_hook",
            "address": address,
            "token": token,
            "params": {"ttl": str(int(CHANNEL_TTL.total_seconds()))},
        },
    )
    assert created is not None
    expiration = datetime.fromtimestamp(int(created.get("expiration", 0)) / 1000, UTC)
    await db.exec(
        """
        UPDATE google_organizer
        SET channel_id = $1, channel_resource_id = $2, channel_token = $3, channel_expires_at = $4
        """,
        channel_id,
        created.get("resourceId", ""),
        token,
        expiration,
    )
    # The old one, if any, would go on telling until it expires.
    if org["channel_id"]:
        await stop_channel(google, org)


async def stop_channel(google: Google, org: dict[str, Any]) -> None:
    try:
        await google.call(
            "POST",
            "/channels/stop",
            body={"id": org["channel_id"], "resourceId": org["channel_resource_id"]},
            missing_ok=True,
        )
    except GoogleError:
        logger.warning("stopping a push channel failed", exc_info=True)


async def sync_invitations(event_ids: list[int] | None = None) -> None:
    """Read the members' answers, then bring the invitations up to date: for
    every event, or the ones given. Raises GoogleError, after recording it,
    if Google fails."""
    if not configured():
        return
    async with db.begin() as tx:
        await lock_invitations(tx)
        org = await db.query("SELECT * FROM google_organizer").first()
        if org is None or org["status"] != "ok":
            return
        org = dict(org)
        google = organizer_google(org)
        try:
            refused = await read_answers(google, org)
            if event_ids is not None:
                event_ids = sorted(set(event_ids) | refused)
            await send_invitations(google, org, event_ids)
            if event_ids is None:
                await watch(google, org)
        except ReauthNeeded as err:
            await mark_organizer("reauth", str(err))
            logger.warning("the house's google account needs reconnecting", extra={"reason": str(err)})
            return
        except GoogleError as err:
            await mark_organizer("ok", str(err))
            raise
        await db.exec(
            "UPDATE google_organizer SET last_error = '', last_synced_at = now(), updated_at = now()"
        )


# --- keeping up ----------------------------------------------------------------


async def on_calendar_change(message: pubsub.Message[CalendarChange]) -> None:
    await follow_change(message.data)


async def follow_change(change: CalendarChange) -> None:
    """An event changed, or an RSVP to it: its invitation follows."""
    if change.event_id is not None:
        await sync_invitations([change.event_id])


async def on_sync(message: pubsub.Message[InvitationSync]) -> None:
    await sync_invitations()


follow_changes = pubsub.Subscription[CalendarChange](
    calendar_changes, "invitations", handler=on_calendar_change
)
LOCAL_HANDLERS.append(follow_change)
follow_syncs = pubsub.Subscription[InvitationSync](
    invitation_syncs, "invitations", handler=on_sync
)

invitations_job = Job(
    "google-invitations",
    path="/internal/google-invitations/sync",
    title="Read members' invitation answers, and send invitations",
    every="10m",
)


@internal.post("/google-invitations/sync", status_code=204)
async def cron_sync() -> Response:
    try:
        await sync_invitations()
    except GoogleError:
        logger.warning("syncing the invitations failed", exc_info=True)
    return Response(status_code=204)


@router.post("/google/notifications")
async def notification(request: Request) -> Response:
    """Google, telling of a change in the house's calendar. Answered at once;
    the sync that reads it follows."""
    channel = request.headers.get("x-goog-channel-id", "")
    token = request.headers.get("x-goog-channel-token", "")
    org = await db.query("SELECT channel_id, channel_token FROM google_organizer").first()
    if (
        org is None
        or not org["channel_id"]
        or channel != org["channel_id"]
        or not hmac.compare_digest(token, org["channel_token"] or "")
    ):
        raise HTTPException(status_code=404, detail="no such channel")
    # "sync" is the channel saying it's there, not a change.
    if request.headers.get("x-goog-resource-state") != "sync":
        await request_sync("google told of a change")
    return Response(status_code=200)


# --- the member's invitations --------------------------------------------------


class InvitationStatus(Model):
    # Whether the house's account is connected, to send invitations from.
    available: bool
    enabled: bool
    # Where theirs go: their account's address.
    email: str
    organizer_email: str = ""


class InvitationsIn(Model):
    enabled: bool
    # Where to send them: any address the member gives, their account's if
    # they give none. Kept here, not on their account, and not verified: the
    # house's members are its own.
    email: str | None = Field(default=None, max_length=254)

    @field_validator("email")
    @classmethod
    def _email(cls, email: str | None) -> str | None:
        if email is None or not email.strip():
            return None
        email = email.strip().lower()
        if not EMAIL.match(email):
            raise ValueError("give a valid email address")
        return email


async def invitation_status(user_id: str, email: str) -> InvitationStatus:
    """The member's invitations. The address is the one they get them at,
    else their account's, as the settings page fills its field in with."""
    org = await db.query("SELECT google_email, status FROM google_organizer").first()
    mine = await db.query(
        "SELECT email FROM invitation_subscribers WHERE user_id = $1", user_id
    ).first()
    return InvitationStatus(
        available=configured() and org is not None and org["status"] == "ok",
        enabled=mine is not None,
        email=mine["email"] if mine is not None else email.lower(),
        organizer_email=org["google_email"] if org is not None else "",
    )


@router.get("/invitations")
async def my_invitations(user: Member) -> InvitationStatus:
    return await invitation_status(user.id, user.email)


@router.put("/invitations")
async def set_invitations(body: InvitationsIn, user: Member) -> InvitationStatus:
    """Every event as an invitation, at the address given (else the account's),
    or none: sent, moved or cancelled by the sync that follows."""
    if body.enabled:
        status = await invitation_status(user.id, user.email)
        if not status.available:
            raise HTTPException(status_code=409, detail="invitations aren't set up yet")
        address = body.email or user.email.strip().lower()
        if not address or not EMAIL.match(address):
            raise HTTPException(status_code=422, detail="email: give the address to send invitations to")
        taken = await db.query(
            "SELECT user_id FROM invitation_subscribers WHERE email = $1 AND user_id <> $2",
            address,
            user.id,
        ).first()
        if taken is not None:
            raise HTTPException(status_code=409, detail="another member gets invitations at that address")
        await db.exec(
            """
            INSERT INTO invitation_subscribers (user_id, email) VALUES ($1, $2)
            ON CONFLICT (user_id) DO UPDATE SET email = EXCLUDED.email
            """,
            user.id,
            address,
        )
    else:
        await db.exec("DELETE FROM invitation_subscribers WHERE user_id = $1", user.id)
        await db.exec("DELETE FROM invitation_answers WHERE user_id = $1", user.id)
    await request_sync("a member's invitations changed")
    return await invitation_status(user.id, user.email)


# --- the house's account, for admins -------------------------------------------


class OrganizerStatus(Model):
    # Whether the app has a Google OAuth client to connect with.
    available: bool
    connected: bool
    google_email: str = ""
    needs_reconnect: bool = False
    last_error: str = ""
    last_synced_at: datetime | None = None
    # Whether Google tells of answers as they're given (only over HTTPS),
    # rather than the cron job finding them within ten minutes.
    push: bool = False
    subscribers: int = 0
    events: int = 0


async def organizer_status() -> OrganizerStatus:
    available = configured()
    org = await db.query("SELECT * FROM google_organizer").first()
    if org is None:
        return OrganizerStatus(available=available, connected=False)
    counts = await db.query(
        """
        SELECT (SELECT count(*) FROM invitation_subscribers)::int AS subscribers,
               (SELECT count(*) FROM invitation_events)::int AS events
        """
    ).one()
    return OrganizerStatus(
        available=available,
        connected=True,
        google_email=org["google_email"],
        needs_reconnect=org["status"] == "reauth",
        last_error=org["last_error"],
        last_synced_at=org["last_synced_at"],
        push=org["channel_expires_at"] is not None
        and org["channel_expires_at"] > datetime.now(UTC),
        subscribers=counts["subscribers"],
        events=counts["events"],
    )


@router.get("/admin/google-organizer")
async def get_organizer(_: Admin) -> OrganizerStatus:
    return await organizer_status()


@router.post("/admin/google-organizer/connect")
async def connect_organizer(body: ConnectIn, user: Admin) -> ConnectOut:
    return await sign_in_url(user, body.origin, "organizer")


@router.post("/admin/google-organizer/sync")
async def sync_organizer(_: Admin) -> OrganizerStatus:
    require_setup()
    try:
        await sync_invitations()
    except GoogleError:
        pass  # recorded as the status's lastError
    return await organizer_status()


@router.delete("/admin/google-organizer", status_code=204)
async def disconnect_organizer(user: Admin) -> Response:
    """Cancel the invitations not over, as far as Google lets the app, stop
    the push channel, revoke the app's access, and forget the account. The
    members' wish for invitations is kept, for when one is connected again."""
    async with db.begin() as tx:
        await lock_invitations(tx)
        org = await db.query("SELECT * FROM google_organizer").first()
        if org is None:
            return Response(status_code=204)
        if org["status"] == "ok" and configured():
            google = organizer_google(dict(org))
            calendar = quote(org["calendar_id"], safe="")
            rows = await db.query(
                f"""
                SELECT i.google_event_id FROM invitation_events i
                JOIN events e ON e.id = i.event_id
                WHERE COALESCE(e.ends_at, e.starts_at + {DEFAULT_DURATION_SQL}) >= now()
                """
            ).all()
            try:
                for row in rows:
                    path = f"/calendars/{calendar}/events/{quote(row['google_event_id'], safe='')}"
                    await google.call("DELETE", path, params={"sendUpdates": "all"}, missing_ok=True)
                if org["channel_id"]:
                    await stop_channel(google, dict(org))
                await revoke(unseal(org["refresh_token"]))
            except (GoogleError, ReauthNeeded):
                logger.warning("invitations were left in the house's calendar", exc_info=True)
        await db.exec("DELETE FROM invitation_events")
        await db.exec("DELETE FROM invitation_answers")
        await db.exec("DELETE FROM google_organizer")
    logger.info("disconnected the house's google account", extra={"by": user.id})
    return Response(status_code=204)
