"""Google Calendar sync: a member connects their Google account, picks one of
its calendars, and the house's events are kept in it: the ones they are going
to or might go to ("rsvp"), or all of them ("all").

GET    /api/google               the member's connection, and whether sync is set up
POST   /api/google/connect       start connecting {"origin": "https://..."}: where to
                                 send the member to sign in to Google
GET    /api/google/callback      where Google sends them back; no session token (it's
                                 a page load): the state says whose it is
GET    /api/google/calendars     the calendars the member can add events to
PUT    /api/google/settings      {"mode": "rsvp"|"all", "calendarId": "..."} or
                                 {"mode": ..., "newCalendar": true}; syncs at once
POST   /api/google/sync          sync the member's calendar now
DELETE /api/google               disconnect: the events are taken out of their
                                 calendar, and Google's access revoked

How events reach a calendar:
- A change to an event, or to a member's RSVP, is published to the
  calendar-changes topic (calendar_changes.py), and this module's
  subscription syncs the calendars it touches.
- Saving the settings, and "Sync now", sync the member's calendar at once.
- Every hour a cron job syncs every calendar, catching up on what failed,
  at /internal/google-calendar/sync: outside /api, so the gateway doesn't
  expose it.

A sync compares what the calendar should hold with what was sent to it
(google_synced_events), and adds, changes and removes the difference only.
Events that are over are left as they are: a calendar keeps its history.

Setting it up, per environment:
- A Google Cloud project with the Google Calendar API enabled, its OAuth
  consent screen published (in testing, Google drops a connection after a
  week), and an OAuth client of type "Web application" whose authorized
  redirect URI is the api gateway's /api/google/callback, where the
  environment serves its API.
- The client's id in the google_client_id config value, and its secret in the
  GoogleClientSecret secret.
- The GoogleTokenKey secret, which encrypts members' Google tokens.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets as pysecrets
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from urllib.parse import quote, urlencode, urlsplit

import httpx
import jwt
from cryptography.fernet import Fernet, InvalidToken
from encore import gateways, pubsub
from encore.cron import Job
from encore.secrets import Secret
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import RedirectResponse
from pydantic import Field, model_validator

from calendar_changes import CalendarChange, calendar_changes, notify
from db import db
from events import DEFAULT_DURATION, DEFAULT_DURATION_SQL, Member, Model
from settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")
# Routes for Encore to call, not exposed by the gateway (encore.service.json).
internal = APIRouter(prefix="/internal")

client_secret = Secret[str](
    "GoogleClientSecret",
    description="The secret of the Google OAuth client whose id is the google_client_id config value: Google Cloud console, APIs & Services, Credentials. To rotate it, add a secret to the client there, set it here, deploy, then disable the old one.",
)
token_key = Secret[str](
    "GoogleTokenKey",
    description="Encrypts members' Google tokens in the database: any long random string, such as the output of `openssl rand -base64 32`. Changing it disconnects every member, who then reconnect from the settings page.",
)

# What the app asks Google for: who the member is, the list of their
# calendars, their calendars' events, and calendars it makes itself.
SCOPES = [
    "openid",
    "email",
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.app.created",
]
# Without these there's nothing to sync to: Google lets a member leave any out.
REQUIRED_SCOPES = {
    "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
    "https://www.googleapis.com/auth/calendar.events",
}

TIME_ZONE = "Europe/Stockholm"
ADDRESS = "House of Soft Beasts, Patentgatan 2, Stockholm"
NEW_CALENDAR_NAME = "House of Soft Beasts"
# How long a sign-in to Google may take, from Connect to coming back.
STATE_LIFETIME = timedelta(minutes=15)

Mode = Literal["rsvp", "all"]


# --- errors ------------------------------------------------------------------


class GoogleError(Exception):
    """Google failed or refused a request: a sync tries again later."""


class ReauthNeeded(Exception):
    """Google no longer accepts the member's connection: they must reconnect."""


def _error_message(response: httpx.Response) -> str:
    """Google's own account of a failed request."""
    try:
        body = response.json()
    except ValueError:
        return f"Google answered {response.status_code}"
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        return f"Google answered {response.status_code}: {error.get('message', '')}".rstrip(": ")
    if isinstance(error, str):
        return f"Google answered {response.status_code}: {body.get('error_description', error)}"
    return f"Google answered {response.status_code}"


# --- tokens ------------------------------------------------------------------


def _fernet() -> Fernet:
    digest = hashlib.sha256(token_key.value.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def seal(token: str) -> str:
    """A token encrypted for the database."""
    return _fernet().encrypt(token.encode()).decode()


def unseal(sealed: str) -> str:
    """A token from the database. Raises ReauthNeeded if GoogleTokenKey has
    changed since it was sealed."""
    try:
        return _fernet().decrypt(sealed.encode()).decode()
    except InvalidToken:
        raise ReauthNeeded("the connection can't be read since the app's key changed") from None


_http: httpx.AsyncClient | None = None


def http() -> httpx.AsyncClient:
    global _http
    if _http is None:
        _http = httpx.AsyncClient(timeout=httpx.Timeout(20.0))
    return _http


def configured() -> bool:
    """Whether the environment has an OAuth client to connect with, and its
    secrets."""
    if not settings.value.google_client_id:
        return False
    try:
        return bool(client_secret.value and token_key.value)
    except KeyError:  # a secret without a value
        return False


def require_setup() -> None:
    """Raises 503 unless the sync is set up (see the module's doc)."""
    if not configured():
        raise HTTPException(status_code=503, detail="Google Calendar sync isn't set up")


async def token_request(data: dict[str, str]) -> dict[str, Any]:
    """A request to Google's token endpoint, as the app's OAuth client."""
    s = settings.value
    try:
        response = await http().post(
            s.google_token_url,
            data={**data, "client_id": s.google_client_id, "client_secret": client_secret.value},
        )
    except httpx.HTTPError as err:
        raise GoogleError(f"Google couldn't be reached: {err}") from err
    if response.status_code == 400 and _json(response).get("error") == "invalid_grant":
        raise ReauthNeeded("Google no longer accepts the connection")
    if response.status_code >= 400:
        raise GoogleError(_error_message(response))
    return _json(response)


def _json(response: httpx.Response) -> dict[str, Any]:
    try:
        body = response.json()
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


async def revoke(token: str) -> None:
    """Revoke Google's grant of the token, if it can be: disconnecting goes
    on regardless."""
    try:
        await http().post(settings.value.google_revoke_url, data={"token": token})
    except httpx.HTTPError:
        logger.warning("revoking a Google token failed", exc_info=True)


def id_token_email(id_token: str | None) -> str:
    """The Google account's address, from the ID token the token endpoint gave.
    It came straight from Google over TLS, so its signature needn't be checked
    (OpenID Connect Core, 3.1.3.7)."""
    if not id_token:
        return ""
    try:
        claims = jwt.decode(id_token, options={"verify_signature": False})
    except jwt.PyJWTError:
        return ""
    email = claims.get("email")
    return email if isinstance(email, str) else ""


# --- Google, as the member ---------------------------------------------------


class Google:
    """The Calendar API, as a member whose connection (a google_connections
    row) this is. Refreshes its access token when it must."""

    def __init__(self, connection: dict[str, Any]) -> None:
        self.connection = dict(connection)
        self.user_id: str = connection["user_id"]

    async def access_token(self, *, fresh: bool = False) -> str:
        c = self.connection
        soon = datetime.now(UTC) + timedelta(minutes=1)
        if not fresh and c["access_token"] and c["access_expires_at"] and c["access_expires_at"] > soon:
            return unseal(c["access_token"])
        tokens = await token_request(
            {"grant_type": "refresh_token", "refresh_token": unseal(c["refresh_token"])}
        )
        token = tokens["access_token"]
        c["access_token"] = seal(token)
        c["access_expires_at"] = datetime.now(UTC) + timedelta(
            seconds=int(tokens.get("expires_in", 3600))
        )
        await db.exec(
            """
            UPDATE google_connections SET access_token = $2, access_expires_at = $3
            WHERE user_id = $1
            """,
            self.user_id,
            c["access_token"],
            c["access_expires_at"],
        )
        return token

    async def call(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        missing_ok: bool = False,
    ) -> dict[str, Any] | None:
        """A Calendar API request. None if missing_ok and Google has no such
        thing (any more)."""
        url = settings.value.google_api_url + path
        response: httpx.Response | None = None
        for fresh in (False, True):
            headers = {"Authorization": f"Bearer {await self.access_token(fresh=fresh)}"}
            try:
                response = await http().request(
                    method, url, json=body, params=params, headers=headers
                )
            except httpx.HTTPError as err:
                raise GoogleError(f"Google couldn't be reached: {err}") from err
            # An access token Google stopped accepting early: once more, with a new one.
            if response.status_code != 401:
                break
        assert response is not None
        if response.status_code == 401:
            raise ReauthNeeded("Google refused the connection's access")
        if missing_ok and response.status_code in (404, 410):
            return None
        if response.status_code >= 400:
            raise GoogleError(_error_message(response))
        return _json(response)

    async def calendars(self) -> list[dict[str, Any]]:
        """The member's calendars they can add events to."""
        found: list[dict[str, Any]] = []
        params = {"minAccessRole": "writer", "maxResults": "250"}
        while True:
            page = await self.call("GET", "/users/me/calendarList", params=params) or {}
            found.extend(page.get("items", []))
            if not page.get("nextPageToken"):
                return found
            params = {**params, "pageToken": page["nextPageToken"]}

    async def create_calendar(self, name: str) -> dict[str, Any]:
        created = await self.call("POST", "/calendars", body={"summary": name, "timeZone": TIME_ZONE})
        assert created is not None
        return created

    async def insert_event(self, calendar_id: str, event: dict[str, Any]) -> str:
        created = await self.call("POST", f"/calendars/{quote(calendar_id, safe='')}/events", body=event)
        assert created is not None
        return created["id"]

    async def update_event(self, calendar_id: str, event_id: str, event: dict[str, Any]) -> bool:
        """False if the event is gone from the calendar."""
        path = f"/calendars/{quote(calendar_id, safe='')}/events/{quote(event_id, safe='')}"
        return await self.call("PUT", path, body=event, missing_ok=True) is not None

    async def delete_event(self, calendar_id: str, event_id: str) -> None:
        path = f"/calendars/{quote(calendar_id, safe='')}/events/{quote(event_id, safe='')}"
        await self.call("DELETE", path, missing_ok=True)


def calendar_name(calendar: dict[str, Any]) -> str:
    return calendar.get("summaryOverride") or calendar.get("summary") or calendar["id"]


# --- what a calendar holds ---------------------------------------------------


def event_body(event: dict[str, Any], app_origin: str) -> dict[str, Any]:
    """A house event as a Google Calendar event: the event's row, with the
    member's RSVP status as my_status."""
    link = f"{app_origin}/events/{event['slug']}"
    ends = event["ends_at"] or event["starts_at"] + DEFAULT_DURATION
    description = event["description"].strip()
    return {
        "summary": event["title"],
        "description": f"{description}\n\n{link}" if description else link,
        "location": f"{event['location']}, {ADDRESS}" if event["location"] else ADDRESS,
        "start": {"dateTime": event["starts_at"].isoformat(), "timeZone": TIME_ZONE},
        "end": {"dateTime": ends.isoformat(), "timeZone": TIME_ZONE},
        # Busy for what they're going to, free for the rest.
        "transparency": "opaque" if event["my_status"] == "going" else "transparent",
        # Brings back an event the member deleted in Google, when it changes.
        "status": "confirmed",
        "source": {"title": "House of Soft Beasts", "url": link},
        "extendedProperties": {"private": {"hosbEventId": str(event["id"])}},
    }


def content_hash(body: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()


# The events the member's calendar should hold ($1 the member, $2 the mode):
# the ones not over, and in "rsvp" mode only those they're going or might go
# to. {only} narrows it to some ($3).
WANTED_QUERY = f"""
SELECT e.id, e.slug, e.title, e.description, e.location, e.starts_at, e.ends_at,
       r.status AS my_status
FROM events e
LEFT JOIN rsvps r ON r.event_id = e.id AND r.user_id = $1
WHERE COALESCE(e.ends_at, e.starts_at + {DEFAULT_DURATION_SQL}) >= now()
  AND ($2 = 'all' OR r.status IN ('going', 'maybe'))
  {{only}}
"""

OVER_QUERY = f"""
SELECT id FROM events
WHERE id = ANY($1) AND COALESCE(ends_at, starts_at + {DEFAULT_DURATION_SQL}) < now()
"""


async def reconcile(google: Google, event_ids: list[int] | None) -> None:
    """Make the member's calendar hold what it should: of every event, or of
    the ones given."""
    c = google.connection
    user_id, calendar_id = c["user_id"], c["calendar_id"]
    narrow = [] if event_ids is None else [event_ids]
    wanted = {
        row["id"]: row
        for row in await db.query(
            WANTED_QUERY.format(only="" if event_ids is None else "AND e.id = ANY($3)"),
            user_id,
            c["mode"],
            *narrow,
        ).all()
    }
    synced = {
        row["event_id"]: row
        for row in await db.query(
            "SELECT event_id, calendar_id, google_event_id, content_hash"
            " FROM google_synced_events WHERE user_id = $1"
            + ("" if event_ids is None else " AND event_id = ANY($2)"),
            user_id,
            *narrow,
        ).all()
    }

    # What it shouldn't hold any more, or holds in a calendar the member has
    # moved away from: out, but for events that are over, in the calendar.
    stale = [r for i, r in synced.items() if i not in wanted or r["calendar_id"] != calendar_id]
    over: set[int] = set()
    if stale:
        rows = await db.query(OVER_QUERY, [r["event_id"] for r in stale]).all()
        over = {row["id"] for row in rows}
    for row in stale:
        if row["calendar_id"] == calendar_id and row["event_id"] in over:
            continue
        await google.delete_event(row["calendar_id"], row["google_event_id"])
        await db.exec(
            "DELETE FROM google_synced_events WHERE user_id = $1 AND event_id = $2",
            user_id,
            row["event_id"],
        )
        del synced[row["event_id"]]

    # What it should hold: added, or changed if it changed.
    for event_id, event in wanted.items():
        body = event_body(event, c["app_origin"])
        digest = content_hash(body)
        row = synced.get(event_id)
        if row is not None and row["content_hash"] == digest:
            continue
        google_id = row["google_event_id"] if row is not None else None
        if google_id is None or not await google.update_event(calendar_id, google_id, body):
            google_id = await google.insert_event(calendar_id, body)
        # Recorded as soon as it's sent: a sync that fails later on won't
        # send it again as a second event.
        await db.exec(
            """
            INSERT INTO google_synced_events
                (user_id, event_id, calendar_id, google_event_id, content_hash)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (user_id, event_id) DO UPDATE
                SET calendar_id = EXCLUDED.calendar_id,
                    google_event_id = EXCLUDED.google_event_id,
                    content_hash = EXCLUDED.content_hash, synced_at = now()
            """,
            user_id,
            event_id,
            calendar_id,
            google_id,
            digest,
        )


async def lock_member(tx: Any, user_id: str) -> None:
    """Hold the member's calendar until the transaction ends: two syncs at
    once could both add an event."""
    await tx.exec("SELECT pg_advisory_xact_lock(hashtext($1))", f"google-calendar:{user_id}")


async def mark_reauth(user_id: str, reason: str) -> None:
    await db.exec(
        """
        UPDATE google_connections
        SET status = 'reauth', last_error = $2, access_token = NULL, updated_at = now()
        WHERE user_id = $1
        """,
        user_id,
        reason,
    )
    logger.info("google connection needs reconnecting", extra={"user": user_id, "reason": reason})


async def sync_member(user_id: str, event_ids: list[int] | None = None) -> None:
    """Bring the member's calendar up to date, for every event or the ones
    given. Raises GoogleError, after recording it, if Google fails."""
    if not configured():
        return
    async with db.begin() as tx:
        await lock_member(tx, user_id)
        connection = await db.query(
            "SELECT * FROM google_connections WHERE user_id = $1", user_id
        ).first()
        if connection is None or connection["status"] != "ok" or connection["calendar_id"] is None:
            return
        try:
            await reconcile(Google(connection), event_ids)
        except ReauthNeeded as err:
            await mark_reauth(user_id, str(err))
            return
        except GoogleError as err:
            await db.exec(
                "UPDATE google_connections SET last_error = $2 WHERE user_id = $1",
                user_id,
                str(err),
            )
            raise
        await db.exec(
            "UPDATE google_connections SET last_error = '', last_synced_at = now()"
            " WHERE user_id = $1",
            user_id,
        )


# --- keeping up with changes -------------------------------------------------

# The members whose calendars an event's change may touch ($1): every one in
# "all" mode, those who RSVP'd to it, and those whose calendar has it.
TOUCHED_QUERY = """
SELECT c.user_id FROM google_connections c
WHERE c.status = 'ok' AND c.calendar_id IS NOT NULL
  AND (c.mode = 'all'
       OR EXISTS (SELECT 1 FROM rsvps r WHERE r.user_id = c.user_id AND r.event_id = $1)
       OR EXISTS (SELECT 1 FROM google_synced_events s
                  WHERE s.user_id = c.user_id AND s.event_id = $1))
"""


async def on_change(message: pubsub.Message[CalendarChange]) -> None:
    change = message.data
    if change.user_id is not None:
        await sync_member(change.user_id, None if change.event_id is None else [change.event_id])
        return
    if change.event_id is None:
        return
    rows = await db.query(TOUCHED_QUERY, change.event_id).all()
    failed = 0
    for row in rows:
        try:
            await sync_member(row["user_id"], [change.event_id])
        except GoogleError:
            logger.warning(
                "syncing an event to a calendar failed",
                exc_info=True,
                extra={"user": row["user_id"], "event_id": change.event_id},
            )
            failed += 1
    if failed:
        # Delivered again: the calendars that took the change aren't sent it twice.
        raise GoogleError(f"event {change.event_id}: {failed} calendar(s) failed to sync")


sync_changes = pubsub.Subscription[CalendarChange](
    calendar_changes, "google-calendar-sync", handler=on_change
)

sync_everyone_job = Job(
    "google-calendar-sync",
    path="/internal/google-calendar/sync",
    title="Sync members' Google calendars",
    every="1h",
)


@internal.post("/google-calendar/sync", status_code=204)
async def sync_everyone() -> Response:
    """Every calendar brought up to date, for what its changes missed. Called
    by the cron job."""
    rows = await db.query(
        "SELECT user_id FROM google_connections WHERE status = 'ok' AND calendar_id IS NOT NULL"
    ).all()
    for row in rows:
        try:
            await sync_member(row["user_id"])
        except GoogleError:
            logger.warning("syncing a calendar failed", exc_info=True, extra={"user": row["user_id"]})
    return Response(status_code=204)


# --- the member's connection -------------------------------------------------


class GoogleStatus(Model):
    # Whether the app has a Google OAuth client to connect with.
    enabled: bool
    connected: bool
    google_email: str = ""
    # The calendar the events go to: None until the member picks one.
    calendar_id: str | None = None
    calendar_name: str = ""
    mode: Mode = "rsvp"
    # Google stopped accepting the connection: the member must connect again.
    needs_reconnect: bool = False
    # What went wrong the last time, if it did.
    last_error: str = ""
    last_synced_at: datetime | None = None
    synced_events: int = 0


async def load_status(user_id: str) -> GoogleStatus:
    enabled = configured()
    row = await db.query(
        """
        SELECT c.*,
               (SELECT count(*) FROM google_synced_events s
                WHERE s.user_id = c.user_id)::int AS synced_events
        FROM google_connections c WHERE c.user_id = $1
        """,
        user_id,
    ).first()
    if row is None:
        return GoogleStatus(enabled=enabled, connected=False)
    return GoogleStatus(
        enabled=enabled,
        connected=True,
        google_email=row["google_email"],
        calendar_id=row["calendar_id"],
        calendar_name=row["calendar_name"],
        mode=row["mode"],
        needs_reconnect=row["status"] == "reauth",
        last_error=row["last_error"],
        last_synced_at=row["last_synced_at"],
        synced_events=row["synced_events"],
    )


async def connected(user_id: str) -> Google:
    """The member's Google, if they're connected and it still accepts them."""
    require_setup()
    row = await db.query("SELECT * FROM google_connections WHERE user_id = $1", user_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Google Calendar isn't connected")
    if row["status"] == "reauth":
        raise HTTPException(status_code=409, detail="reconnect Google Calendar: Google no longer accepts the connection")
    return Google(row)


def check_origin(origin: str) -> str:
    """The frontend's origin as the member's browser has it, which they are
    sent back to from Google, and the events link to: one the app is served
    from, where the environment says."""
    parts = urlsplit(origin.strip())
    if parts.scheme not in ("http", "https") or not parts.netloc or parts.path not in ("", "/"):
        raise HTTPException(status_code=422, detail="origin: give the app's origin, as https://host")
    origin = f"{parts.scheme}://{parts.netloc}"
    allowed = settings.value.authorized_parties
    if allowed and origin not in allowed:
        raise HTTPException(status_code=422, detail=f"origin: the app isn't served from {origin}")
    return origin


def redirect_uri() -> str:
    """Where Google sends the member back to: the callback, on the gateway
    the API is exposed on. Registered with the OAuth client."""
    return f"{gateways.url('api')}/api/google/callback"


@router.get("/google")
async def google_status(user: Member) -> GoogleStatus:
    return await load_status(user.id)


class ConnectIn(Model):
    origin: str = Field(max_length=200)


class ConnectOut(Model):
    # Google's sign-in page, to send the member to.
    url: str


@router.post("/google/connect")
async def connect(body: ConnectIn, user: Member) -> ConnectOut:
    require_setup()
    origin = check_origin(body.origin)
    state = pysecrets.token_urlsafe(32)
    await db.exec(
        "DELETE FROM google_oauth_states WHERE created_at < now() - interval '1 day'"
    )
    await db.exec(
        "INSERT INTO google_oauth_states (state, user_id, return_origin) VALUES ($1, $2, $3)",
        state,
        user.id,
        origin,
    )
    params = {
        "client_id": settings.value.google_client_id,
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "scope": " ".join(SCOPES),
        # A refresh token, to sync while the member is away; asked for again
        # each time, as Google gives one only on consent.
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    if user.email:
        params["login_hint"] = user.email
    return ConnectOut(url=f"{settings.value.google_auth_url}?{urlencode(params)}")


@router.get("/google/callback")
async def callback(
    state: str = "", code: str = "", error: str = "", scope: str = ""
) -> RedirectResponse:
    """Google sends the member back here, with a code to exchange for their
    tokens, and back they go to the settings page, which reads ?google= for
    how it went: connected, denied, scopes (calendar access left out) or
    failed."""
    row = await db.query(
        "DELETE FROM google_oauth_states WHERE state = $1 RETURNING user_id, return_origin, created_at",
        state,
    ).first()
    if row is None or row["created_at"] < datetime.now(UTC) - STATE_LIFETIME:
        raise HTTPException(
            status_code=400,
            detail="This sign-in to Google has expired or was already used: connect again from the settings page.",
        )
    origin, user_id = row["return_origin"], row["user_id"]

    def back(result: str) -> RedirectResponse:
        return RedirectResponse(f"{origin}/settings?google={result}", status_code=303)

    if error or not code:
        return back("denied" if error == "access_denied" else "failed")
    require_setup()
    try:
        tokens = await token_request(
            {"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri()}
        )
    except (GoogleError, ReauthNeeded):
        logger.warning("exchanging a Google code failed", exc_info=True, extra={"user": user_id})
        return back("failed")
    refresh_token = tokens.get("refresh_token")
    if not REQUIRED_SCOPES <= set(str(tokens.get("scope", scope)).split()):
        await revoke(refresh_token or tokens.get("access_token", ""))
        return back("scopes")
    if not refresh_token or not tokens.get("access_token"):
        return back("failed")

    email = id_token_email(tokens.get("id_token"))
    expires = datetime.now(UTC) + timedelta(seconds=int(tokens.get("expires_in", 3600)))
    async with db.begin() as tx:
        await lock_member(tx, user_id)
        # Another Google account: what was synced is in the old one, out of reach.
        await tx.exec(
            """
            DELETE FROM google_synced_events s USING google_connections c
            WHERE s.user_id = c.user_id AND c.user_id = $1 AND c.google_email <> $2
            """,
            user_id,
            email,
        )
        saved = await tx.query(
            """
            INSERT INTO google_connections
                (user_id, google_email, refresh_token, access_token, access_expires_at, app_origin)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (user_id) DO UPDATE
                SET refresh_token = EXCLUDED.refresh_token,
                    access_token = EXCLUDED.access_token,
                    access_expires_at = EXCLUDED.access_expires_at,
                    app_origin = EXCLUDED.app_origin,
                    status = 'ok', last_error = '', updated_at = now(),
                    calendar_id = CASE WHEN google_connections.google_email = EXCLUDED.google_email
                                       THEN google_connections.calendar_id END,
                    calendar_name = CASE WHEN google_connections.google_email = EXCLUDED.google_email
                                         THEN google_connections.calendar_name ELSE '' END,
                    google_email = EXCLUDED.google_email
            RETURNING calendar_id
            """,
            user_id,
            email,
            seal(refresh_token),
            seal(tokens["access_token"]),
            expires,
            origin,
        ).one()
    logger.info("connected google calendar", extra={"user": user_id})
    if saved["calendar_id"] is not None:
        # Reconnected to the same calendar: catch up on what was missed.
        await notify(user_id=user_id)
    return back("connected")


class CalendarOption(Model):
    id: str
    name: str
    primary: bool


class CalendarList(Model):
    calendars: list[CalendarOption]


@router.get("/google/calendars")
async def list_calendars(user: Member) -> CalendarList:
    google = await connected(user.id)
    try:
        calendars = await google.calendars()
    except ReauthNeeded as err:
        await mark_reauth(user.id, str(err))
        raise HTTPException(status_code=409, detail="reconnect Google Calendar: " + str(err)) from None
    except GoogleError as err:
        raise HTTPException(status_code=502, detail=str(err)) from None
    options = [
        CalendarOption(id=c["id"], name=calendar_name(c), primary=bool(c.get("primary")))
        for c in calendars
    ]
    # The member's own calendar first, then by name.
    options.sort(key=lambda c: (not c.primary, c.name.lower()))
    return CalendarList(calendars=options)


class SettingsIn(Model):
    mode: Mode
    # One of the member's calendars they can add events to, or a new one.
    calendar_id: str | None = Field(default=None, min_length=1, max_length=1024)
    new_calendar: bool = False

    @model_validator(mode="after")
    def _one_calendar(self) -> SettingsIn:
        if (self.calendar_id is None) == (not self.new_calendar):
            raise ValueError("give a calendarId, or newCalendar: true")
        return self


@router.put("/google/settings")
async def save_settings(body: SettingsIn, user: Member) -> GoogleStatus:
    """Where the events go, and which: then a sync, which moves them there
    from the calendar they were in. A failed sync is in the status's lastError."""
    google = await connected(user.id)
    try:
        if body.new_calendar:
            calendar = await google.create_calendar(NEW_CALENDAR_NAME)
        else:
            calendar = next((c for c in await google.calendars() if c["id"] == body.calendar_id), None)
            if calendar is None:
                raise HTTPException(
                    status_code=422, detail="calendarId: not a calendar you can add events to"
                )
    except ReauthNeeded as err:
        await mark_reauth(user.id, str(err))
        raise HTTPException(status_code=409, detail="reconnect Google Calendar: " + str(err)) from None
    except GoogleError as err:
        raise HTTPException(status_code=502, detail=str(err)) from None

    await db.exec(
        """
        UPDATE google_connections
        SET calendar_id = $2, calendar_name = $3, mode = $4, updated_at = now()
        WHERE user_id = $1
        """,
        user.id,
        calendar["id"],
        calendar_name(calendar),
        body.mode,
    )
    try:
        await sync_member(user.id)
    except GoogleError:
        pass  # recorded as the status's lastError; the hourly sync tries again
    return await load_status(user.id)


@router.post("/google/sync")
async def sync_now(user: Member) -> GoogleStatus:
    await connected(user.id)
    try:
        await sync_member(user.id)
    except GoogleError:
        pass  # recorded as the status's lastError
    return await load_status(user.id)


@router.delete("/google", status_code=204)
async def disconnect(user: Member) -> Response:
    """Take the events out of the member's calendar, as far as Google lets
    the app, revoke its access, and forget the connection."""
    async with db.begin() as tx:
        await lock_member(tx, user.id)
        row = await db.query("SELECT * FROM google_connections WHERE user_id = $1", user.id).first()
        if row is None:
            return Response(status_code=204)
        if row["status"] == "ok" and configured():
            google = Google(row)
            synced = await db.query(
                "SELECT calendar_id, google_event_id FROM google_synced_events WHERE user_id = $1",
                user.id,
            ).all()
            try:
                for s in synced:
                    await google.delete_event(s["calendar_id"], s["google_event_id"])
                await revoke(unseal(row["refresh_token"]))
            except (GoogleError, ReauthNeeded):
                logger.warning(
                    "events were left in a disconnected calendar", exc_info=True, extra={"user": user.id}
                )
        await db.exec("DELETE FROM google_connections WHERE user_id = $1", user.id)
    logger.info("disconnected google calendar", extra={"user": user.id})
    return Response(status_code=204)
