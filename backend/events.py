"""The calendar API: events, and members' RSVPs to them.

Every route needs a signed-in member; creating, changing and deleting events
needs an admin.

GET    /api/me                      the signed-in member
GET    /api/events                  upcoming events (?scope=past, or ?from=&to=)
POST   /api/events                  create an event (admin)
GET    /api/events/{ref}            an event and who is coming, by its slug (or one it
                                    had) or its id
PUT    /api/events/{id}             change an event (admin)
DELETE /api/events/{id}             delete an event (admin)
PUT    /api/events/{id}/rsvp        RSVP {"status": "going"|"maybe"|"not_going", "guests": 0-4}
DELETE /api/events/{id}/rsvp        withdraw one's RSVP

The admin page's own routes are in admin.py, and shareable links' in share.py.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from auth import User, current_admin, current_user
from db import db
from slugs import assign_slug

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# An event without an end time counts as ongoing for this long after it starts.
DEFAULT_DURATION = timedelta(hours=3)
DEFAULT_DURATION_SQL = "interval '3 hours'"
MAX_GUESTS = 4

RSVPStatus = Literal["going", "maybe", "not_going"]


class Model(BaseModel):
    """JSON in camelCase, as the frontend writes it."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Me(Model):
    id: str
    name: str
    email: str
    image_url: str
    admin: bool


class EventIn(Model):
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    location: str = Field(default="", max_length=200)
    starts_at: AwareDatetime
    ends_at: AwareDatetime | None = None
    capacity: int | None = Field(default=None, ge=1, le=10000)
    # How many guests a member's shareable link may sign up; None for no limit.
    share_signup_cap: int | None = Field(default=None, ge=1, le=10000)

    @model_validator(mode="after")
    def _check(self) -> EventIn:
        self.title = self.title.strip()
        self.description = self.description.strip()
        self.location = self.location.strip()
        if not self.title:
            raise ValueError("title must not be blank")
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            raise ValueError("endsAt must be after startsAt")
        return self


class MyRSVP(Model):
    status: RSVPStatus
    guests: int


class Event(Model):
    id: int
    slug: str
    title: str
    description: str
    location: str
    starts_at: datetime
    ends_at: datetime | None
    capacity: int | None
    share_signup_cap: int | None
    # None for an event imported from the old calendar.
    created_by: str | None
    created_at: datetime
    updated_at: datetime
    # People coming: members going, their guests, and guests who signed up
    # through a shareable link (guest_count of them).
    going_count: int
    guest_count: int
    maybe_count: int
    my_rsvp: MyRSVP | None


class Attendee(Model):
    user_id: str
    name: str
    image_url: str
    status: RSVPStatus
    guests: int
    updated_at: datetime


class GuestSignup(Model):
    """A guest who signed up through a shareable link, as members see them."""

    name: str
    # Whose invitation they came by: the link's creator, or whom an admin
    # made it for.
    invited_by: str
    created_at: datetime


class EventDetail(Event):
    attendees: list[Attendee]
    guest_signups: list[GuestSignup]


class EventList(Model):
    events: list[Event]


class RSVPIn(Model):
    status: RSVPStatus
    guests: int = Field(default=0, ge=0, le=MAX_GUESTS)


async def upsert_member(user: User) -> None:
    """Record the member, or what changed about them, from their token.

    When they were last seen is kept to the hour, so that an unchanged member
    isn't written on every request.
    """
    await db.exec(
        """
        INSERT INTO members (id, name, email, image_url, admin)
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (id) DO UPDATE
            SET name = EXCLUDED.name, email = EXCLUDED.email,
                image_url = EXCLUDED.image_url, admin = EXCLUDED.admin,
                updated_at = CASE
                    WHEN (members.name, members.email, members.image_url, members.admin)
                        IS DISTINCT FROM
                        (EXCLUDED.name, EXCLUDED.email, EXCLUDED.image_url, EXCLUDED.admin)
                    THEN now() ELSE members.updated_at END,
                last_seen_at = now()
            WHERE (members.name, members.email, members.image_url, members.admin)
                    IS DISTINCT FROM
                    (EXCLUDED.name, EXCLUDED.email, EXCLUDED.image_url, EXCLUDED.admin)
                OR members.last_seen_at < now() - interval '1 hour'
        """,
        user.id,
        user.name,
        user.email,
        user.image_url,
        user.admin,
    )


async def member(user: Annotated[User, Depends(current_user)]) -> User:
    """FastAPI dependency: the signed-in member, recorded in the database."""
    await upsert_member(user)
    return user


async def admin(user: Annotated[User, Depends(current_admin)]) -> User:
    await upsert_member(user)
    return user


# The signed-in member: any, recorded in the database, or an admin.
AnyMember = Annotated[User, Depends(current_user)]
Member = Annotated[User, Depends(member)]
Admin = Annotated[User, Depends(admin)]


# The events with their RSVP counts and the member's ($1) own RSVP. A WHERE
# clause goes in {where}, made only of fixed fragments with parameters.
EVENTS_QUERY = """
SELECT e.id, e.slug, e.title, e.description, e.location, e.starts_at, e.ends_at,
       e.capacity, e.share_signup_cap, e.created_by, e.created_at, e.updated_at,
       (COALESCE(SUM(1 + r.guests) FILTER (WHERE r.status = 'going'), 0)
        + (SELECT count(*) FROM guest_signups g WHERE g.event_id = e.id))::int AS going_count,
       (SELECT count(*) FROM guest_signups g WHERE g.event_id = e.id)::int AS guest_count,
       COUNT(r.user_id) FILTER (WHERE r.status = 'maybe')::int AS maybe_count,
       mine.status AS my_status, mine.guests AS my_guests
FROM events e
LEFT JOIN rsvps r ON r.event_id = e.id
LEFT JOIN rsvps mine ON mine.event_id = e.id AND mine.user_id = $1
{where}
GROUP BY e.id, mine.status, mine.guests
{order}
"""


def to_event(row: dict[str, Any]) -> Event:
    mine = None
    if row["my_status"] is not None:
        mine = MyRSVP(status=row["my_status"], guests=row["my_guests"])
    return Event(
        id=row["id"],
        slug=row["slug"],
        title=row["title"],
        description=row["description"],
        location=row["location"],
        starts_at=row["starts_at"],
        ends_at=row["ends_at"],
        capacity=row["capacity"],
        share_signup_cap=row["share_signup_cap"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        going_count=row["going_count"],
        guest_count=row["guest_count"],
        maybe_count=row["maybe_count"],
        my_rsvp=mine,
    )


async def load_event(event_id: int, user_id: str) -> EventDetail:
    row = await db.query(
        EVENTS_QUERY.format(where="WHERE e.id = $2", order=""), user_id, event_id
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="no such event")
    attendees = await db.query(
        """
        SELECT r.user_id, m.name, m.image_url, r.status, r.guests, r.updated_at
        FROM rsvps r JOIN members m ON m.id = r.user_id
        WHERE r.event_id = $1
        ORDER BY CASE r.status WHEN 'going' THEN 0 WHEN 'maybe' THEN 1 ELSE 2 END,
                 r.created_at
        """,
        event_id,
    ).all()
    guests = await db.query(
        """
        SELECT g.name, COALESCE(l.invited_by, m.name, '') AS invited_by, g.created_at
        FROM guest_signups g
        LEFT JOIN share_links l ON l.id = g.link_id
        LEFT JOIN members m ON m.id = l.created_by
        WHERE g.event_id = $1
        ORDER BY g.created_at
        """,
        event_id,
    ).all()
    return EventDetail(
        **to_event(row).model_dump(),
        attendees=[Attendee(**a) for a in attendees],
        guest_signups=[GuestSignup(**g) for g in guests],
    )


async def resolve_event(ref: str) -> int:
    """The id of the event ref names: a slug it has or had, or its id."""
    if ref.isdigit():
        return int(ref)
    row = await db.query("SELECT event_id FROM event_slugs WHERE slug = $1", ref).first()
    if row is None:
        raise HTTPException(status_code=404, detail="no such event")
    return row["event_id"]


@router.get("/me")
async def me(user: Member) -> Me:
    return Me(**user.__dict__)


@router.get("/events")
async def list_events(
    user: AnyMember,
    scope: Literal["upcoming", "past"] = "upcoming",
    start: Annotated[AwareDatetime | None, Query(alias="from")] = None,
    end: Annotated[AwareDatetime | None, Query(alias="to")] = None,
) -> EventList:
    """Upcoming events (those not yet over), soonest first; past ones, latest
    first; or, given from and/or to, those starting in [from, to)."""
    params: list[Any] = [user.id]
    if start is not None or end is not None:
        clauses = []
        if start is not None:
            params.append(start)
            clauses.append(f"e.starts_at >= ${len(params)}")
        if end is not None:
            params.append(end)
            clauses.append(f"e.starts_at < ${len(params)}")
        where = "WHERE " + " AND ".join(clauses)
        order = "ORDER BY e.starts_at LIMIT 500"
    else:
        ends = f"COALESCE(e.ends_at, e.starts_at + {DEFAULT_DURATION_SQL})"
        if scope == "upcoming":
            where, order = f"WHERE {ends} >= now()", "ORDER BY e.starts_at LIMIT 200"
        else:
            where, order = f"WHERE {ends} < now()", "ORDER BY e.starts_at DESC LIMIT 100"
    rows = await db.read().query(EVENTS_QUERY.format(where=where, order=order), *params).all()
    return EventList(events=[to_event(r) for r in rows])


@router.post("/events", status_code=201)
async def create_event(event: EventIn, user: Admin) -> EventDetail:
    async with db.begin() as tx:
        # A placeholder slug, until the event has the id its slug is checked by.
        row = await tx.query(
            """
            INSERT INTO events (title, description, location, starts_at, ends_at, capacity,
                                share_signup_cap, created_by, slug)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'new-' || gen_random_uuid())
            RETURNING id
            """,
            event.title,
            event.description,
            event.location,
            event.starts_at,
            event.ends_at,
            event.capacity,
            event.share_signup_cap,
            user.id,
        ).one()
        await assign_slug(tx, row["id"], event.title, event.starts_at)
    logger.info("created event", extra={"event_id": row["id"], "by": user.id})
    return await load_event(row["id"], user.id)


@router.get("/events/{ref}")
async def get_event(ref: str, user: AnyMember) -> EventDetail:
    return await load_event(await resolve_event(ref), user.id)


@router.put("/events/{event_id}")
async def update_event(event_id: int, event: EventIn, user: Admin) -> EventDetail:
    async with db.begin() as tx:
        result = await tx.exec(
            """
            UPDATE events
            SET title = $2, description = $3, location = $4, starts_at = $5,
                ends_at = $6, capacity = $7, share_signup_cap = $8, updated_at = now()
            WHERE id = $1
            """,
            event_id,
            event.title,
            event.description,
            event.location,
            event.starts_at,
            event.ends_at,
            event.capacity,
            event.share_signup_cap,
        )
        if result.rows_affected == 0:
            raise HTTPException(status_code=404, detail="no such event")
        # A new title or date makes a new slug; the old one still leads here.
        await assign_slug(tx, event_id, event.title, event.starts_at)
    logger.info("updated event", extra={"event_id": event_id, "by": user.id})
    return await load_event(event_id, user.id)


@router.delete("/events/{event_id}", status_code=204)
async def delete_event(event_id: int, user: Admin) -> Response:
    result = await db.exec("DELETE FROM events WHERE id = $1", event_id)
    if result.rows_affected == 0:
        raise HTTPException(status_code=404, detail="no such event")
    logger.info("deleted event", extra={"event_id": event_id, "by": user.id})
    return Response(status_code=204)


@router.put("/events/{event_id}/rsvp")
async def rsvp(event_id: int, body: RSVPIn, user: Member) -> EventDetail:
    guests = body.guests if body.status == "going" else 0
    async with db.begin() as tx:
        # Lock the event so that concurrent RSVPs can't overfill it.
        event = await tx.query(
            "SELECT capacity, starts_at, ends_at FROM events WHERE id = $1 FOR UPDATE",
            event_id,
        ).first()
        if event is None:
            raise HTTPException(status_code=404, detail="no such event")
        ends = event["ends_at"] or event["starts_at"] + DEFAULT_DURATION
        if ends < datetime.now(UTC):
            raise HTTPException(status_code=409, detail="the event is over")
        if body.status == "going" and event["capacity"] is not None:
            taken = await tx.query(
                """
                SELECT (
                    (SELECT COALESCE(SUM(1 + guests), 0) FROM rsvps
                     WHERE event_id = $1 AND status = 'going' AND user_id <> $2)
                    + (SELECT count(*) FROM guest_signups WHERE event_id = $1)
                )::int AS n
                """,
                event_id,
                user.id,
            ).one()
            if taken["n"] + 1 + guests > event["capacity"]:
                left = max(event["capacity"] - taken["n"], 0)
                raise HTTPException(
                    status_code=409,
                    detail=f"the event is full: {left} place(s) left",
                )
        await tx.exec(
            """
            INSERT INTO rsvps (event_id, user_id, status, guests)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (event_id, user_id) DO UPDATE
                SET status = EXCLUDED.status, guests = EXCLUDED.guests, updated_at = now()
            """,
            event_id,
            user.id,
            body.status,
            guests,
        )
    return await load_event(event_id, user.id)


@router.delete("/events/{event_id}/rsvp")
async def withdraw_rsvp(event_id: int, user: AnyMember) -> EventDetail:
    await db.exec("DELETE FROM rsvps WHERE event_id = $1 AND user_id = $2", event_id, user.id)
    return await load_event(event_id, user.id)
