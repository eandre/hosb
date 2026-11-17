"""Shareable links to an event, and the guests who sign up through them.

A link, /s/<slug>-<token>, shows its one event to whoever has it, signed in or not,
and lets them sign up for it as a guest with their name and email address.
It shows them nothing else: every other route needs a signed-in member.

A member has one link to each event: asking for one again gives the same
link. Its sign-ups are capped by the event's share_signup_cap. An admin makes
as many links as they like, each with a name and a cap of its own, and
optionally in someone else's name: whose invitation it is to its guests.

POST /api/events/{id}/share-links     a member's link; an admin's new link
                                      {"name": "...", "signupCap": 10 | null,
                                       "invitedBy": "..." | null}
GET  /api/events/{id}/share-links     the event's links, with their numbers (admin)
GET  /api/admin/share-links           every link, with their numbers (admin)

GET  /api/share/{ref}                 the link's event, as a guest sees it
POST /api/share/{ref}/views           a visit {"visitorId": "..."}
POST /api/share/{ref}/signups         sign up {"name": "...", "email": "..."}

A link's token is random and unguessable, and follows the event's slug, its
date and title, which is there for people to read. A ref is the link's path
after /s/, or its token alone: only the token is looked up, so a link still
leads to its event after the event's slug has changed.
"""

from __future__ import annotations

import logging
import re
import secrets
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Response
from pydantic import Field, field_validator

from db import db
from events import DEFAULT_DURATION, DEFAULT_DURATION_SQL, Admin, Member, Model

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# A token's letters: lowercase, with no digits or letters that look like
# another, and no dash, so that in a link it is what follows the last one.
TOKEN_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"
TOKEN_LENGTH = 16  # about 79 bits

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VISITOR_ID = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


class ShareLinkIn(Model):
    """An admin's new link. A member's needs nothing: it is always the same."""

    name: str = Field(default="", max_length=100)
    signup_cap: int | None = Field(default=None, ge=1, le=10000)
    # Whose invitation it is, as its guests read it: someone the admin makes
    # it for. None or blank for the admin's own.
    invited_by: str | None = Field(default=None, max_length=100)

    @field_validator("invited_by")
    @classmethod
    def _invited_by(cls, invited_by: str | None) -> str | None:
        if invited_by is None:
            return None
        return " ".join(invited_by.split()) or None


class ShareLink(Model):
    id: int
    token: str
    # Where the link leads, on the app's own origin.
    path: str
    kind: Literal["member", "admin"]
    name: str
    event_id: int
    event_slug: str
    event_title: str
    event_starts_at: datetime
    created_by: str
    created_by_name: str
    # Whose invitation an admin's link is to its guests, if not its creator's.
    invited_by: str | None
    created_at: datetime
    # How many guests may sign up through it: None for no limit.
    signup_cap: int | None
    # People who opened it, and how often they did in all.
    views: int
    total_views: int
    signups: int


class ShareLinkList(Model):
    links: list[ShareLink]


LINKS_QUERY = """
SELECT l.id, l.token, l.kind, l.name, l.invited_by, l.created_at, l.created_by,
       m.name AS created_by_name,
       e.id AS event_id, e.slug AS event_slug, e.title AS event_title,
       e.starts_at AS event_starts_at,
       CASE WHEN l.kind = 'member' THEN e.share_signup_cap ELSE l.signup_cap END AS signup_cap,
       (SELECT count(*) FROM share_link_views v WHERE v.link_id = l.id)::int AS views,
       (SELECT COALESCE(sum(v.views), 0) FROM share_link_views v
        WHERE v.link_id = l.id)::int AS total_views,
       (SELECT count(*) FROM guest_signups g WHERE g.link_id = l.id)::int AS signups
FROM share_links l
JOIN events e ON e.id = l.event_id
JOIN members m ON m.id = l.created_by
{where}
ORDER BY {order}
"""


def new_token() -> str:
    return "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(TOKEN_LENGTH))


def token_of(ref: str) -> str:
    """The token of a link's path after /s/ (<slug>-<token>), or a token."""
    return ref.rsplit("-", 1)[-1]


def link_path(token: str, slug: str) -> str:
    return f"/s/{slug}-{token}"


def to_link(row: dict[str, Any]) -> ShareLink:
    return ShareLink(path=link_path(row["token"], row["event_slug"]), **row)


async def load_link(link_id: int) -> ShareLink:
    row = await db.query(LINKS_QUERY.format(where="WHERE l.id = $1", order="l.id"), link_id).one()
    return to_link(row)


@router.post("/events/{event_id}/share-links")
async def create_link(
    event_id: int, user: Member, response: Response, body: ShareLinkIn | None = None
) -> ShareLink:
    """An admin's new link, named and capped as asked. A member's one link to
    the event: made the first time, and the same one after."""
    event = await db.query("SELECT id FROM events WHERE id = $1", event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="no such event")

    if user.admin:
        body = body or ShareLinkIn()
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="an admin's link needs a name")
        row = await db.query(
            """
            INSERT INTO share_links
                (token, event_id, created_by, kind, name, signup_cap, invited_by)
            VALUES ($1, $2, $3, 'admin', $4, $5, $6)
            RETURNING id
            """,
            new_token(),
            event_id,
            user.id,
            name,
            body.signup_cap,
            body.invited_by,
        ).one()
        response.status_code = 201
        logger.info("created share link", extra={"link_id": row["id"], "by": user.id})
        return await load_link(row["id"])

    created = await db.query(
        """
        INSERT INTO share_links (token, event_id, created_by, kind)
        VALUES ($1, $2, $3, 'member')
        ON CONFLICT (event_id, created_by) WHERE kind = 'member' DO NOTHING
        RETURNING id
        """,
        new_token(),
        event_id,
        user.id,
    ).first()
    if created is not None:
        response.status_code = 201
        return await load_link(created["id"])
    row = await db.query(
        "SELECT id FROM share_links WHERE event_id = $1 AND created_by = $2 AND kind = 'member'",
        event_id,
        user.id,
    ).one()
    return await load_link(row["id"])


@router.get("/events/{event_id}/share-links")
async def event_links(event_id: int, _: Admin) -> ShareLinkList:
    rows = (
        await db.read()
        .query(LINKS_QUERY.format(where="WHERE l.event_id = $1", order="l.created_at"), event_id)
        .all()
    )
    return ShareLinkList(links=[to_link(r) for r in rows])


@router.get("/admin/share-links")
async def all_links(_: Admin) -> ShareLinkList:
    rows = (
        await db.read()
        .query(LINKS_QUERY.format(where="", order="e.starts_at DESC, l.created_at"))
        .all()
    )
    return ShareLinkList(links=[to_link(r) for r in rows])


# --- what a guest sees, signed in or not -------------------------------------


class SharedEvent(Model):
    slug: str
    title: str
    description: str
    location: str
    starts_at: datetime
    ends_at: datetime | None
    # Places left for anyone, members and guests; None for no limit.
    places_left: int | None
    is_over: bool


class Shared(Model):
    event: SharedEvent
    # The link's path, with the event's slug as it is now.
    path: str
    # Whose invitation it is: the first name of the member who shared it, or
    # whom an admin made it for.
    invited_by: str
    # Whether a guest can sign up through the link now, and if not, why not.
    signups_open: bool
    closed_reason: str | None


class SignupIn(Model):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(min_length=3, max_length=254)

    @field_validator("name")
    @classmethod
    def _name(cls, name: str) -> str:
        name = " ".join(name.split())
        if len(name) < 2:
            raise ValueError("give your full name")
        return name

    @field_validator("email")
    @classmethod
    def _email(cls, email: str) -> str:
        email = email.strip().lower()
        if not EMAIL.match(email):
            raise ValueError("give a valid email address")
        return email


class Signup(Model):
    status: Literal["signed_up", "already_signed_up"]
    name: str


class ViewIn(Model):
    visitor_id: str

    @field_validator("visitor_id")
    @classmethod
    def _visitor(cls, visitor_id: str) -> str:
        if not VISITOR_ID.match(visitor_id):
            raise ValueError("a visitor id is 8 to 64 letters, digits, - or _")
        return visitor_id


# The link's event with what a guest sign-up depends on, the link's by $1.
SHARED_QUERY = f"""
SELECT l.id AS link_id, l.kind, l.signup_cap AS link_cap,
       COALESCE(l.invited_by, split_part(m.name, ' ', 1)) AS invited_by,
       e.id AS event_id, e.slug, e.title, e.description, e.location, e.starts_at, e.ends_at,
       e.capacity, e.share_signup_cap,
       COALESCE(e.ends_at, e.starts_at + {DEFAULT_DURATION_SQL}) < now() AS is_over,
       ((SELECT COALESCE(sum(1 + r.guests), 0) FROM rsvps r
         WHERE r.event_id = e.id AND r.status = 'going')
        + (SELECT count(*) FROM guest_signups g WHERE g.event_id = e.id))::int AS taken,
       (SELECT count(*) FROM guest_signups g WHERE g.link_id = l.id)::int AS link_signups
FROM share_links l
JOIN events e ON e.id = l.event_id
JOIN members m ON m.id = l.created_by
WHERE l.token = $1
"""


def closed_reason(row: dict[str, Any]) -> str | None:
    """Why no guest can sign up through the link now, if none can."""
    if row["is_over"]:
        return "The event is over."
    if row["capacity"] is not None and row["taken"] >= row["capacity"]:
        return "The event is full."
    cap = row["share_signup_cap"] if row["kind"] == "member" else row["link_cap"]
    if cap is not None and row["link_signups"] >= cap:
        return "This link has no sign-ups left."
    return None


async def shared(ref: str) -> dict[str, Any]:
    row = await db.query(SHARED_QUERY, token_of(ref)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="no such link")
    return row


@router.get("/share/{ref}")
async def get_shared(ref: str) -> Shared:
    row = await shared(ref)
    reason = closed_reason(row)
    places_left = None if row["capacity"] is None else max(row["capacity"] - row["taken"], 0)
    return Shared(
        event=SharedEvent(places_left=places_left, **row),
        path=link_path(token_of(ref), row["slug"]),
        invited_by=row["invited_by"],
        signups_open=reason is None,
        closed_reason=reason,
    )


@router.post("/share/{ref}/views", status_code=204)
async def record_view(ref: str, body: ViewIn) -> Response:
    row = await shared(ref)
    await db.exec(
        """
        INSERT INTO share_link_views (link_id, visitor_id) VALUES ($1, $2)
        ON CONFLICT (link_id, visitor_id) DO UPDATE
            SET views = share_link_views.views + 1, last_viewed_at = now()
        """,
        row["link_id"],
        body.visitor_id,
    )
    return Response(status_code=204)


@router.post("/share/{ref}/signups")
async def sign_up(ref: str, body: SignupIn, response: Response) -> Signup:
    token = token_of(ref)
    async with db.begin() as tx:
        link = await tx.query("SELECT event_id FROM share_links WHERE token = $1", token).first()
        if link is None:
            raise HTTPException(status_code=404, detail="no such link")
        # Lock the event, so that concurrent sign-ups and RSVPs can't overfill
        # it, nor the link.
        await tx.query("SELECT 1 FROM events WHERE id = $1 FOR UPDATE", link["event_id"]).one()

        existing = await tx.query(
            "SELECT name FROM guest_signups WHERE event_id = $1 AND email = $2",
            link["event_id"],
            body.email,
        ).first()
        if existing is not None:
            return Signup(status="already_signed_up", name=existing["name"])

        row = await tx.query(SHARED_QUERY, token).one()
        reason = closed_reason(row)
        if reason is not None:
            raise HTTPException(status_code=409, detail=reason)
        ends = row["ends_at"] or row["starts_at"] + DEFAULT_DURATION
        if ends < datetime.now(UTC):
            raise HTTPException(status_code=409, detail="The event is over.")

        await tx.exec(
            "INSERT INTO guest_signups (event_id, link_id, name, email) VALUES ($1, $2, $3, $4)",
            row["event_id"],
            row["link_id"],
            body.name,
            body.email,
        )
    logger.info("guest signed up", extra={"link_id": row["link_id"], "event_id": row["event_id"]})
    response.status_code = 201
    return Signup(status="signed_up", name=body.name)
