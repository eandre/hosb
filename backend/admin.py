"""The admin API: an overview of the house, its members, and door lists.

Every route needs an admin.

GET /api/admin/stats                         members, activity, upcoming events and RSVPs
GET /api/admin/members                       everyone who has signed in
GET /api/admin/events/{id}/attendees.csv     who answered an event, with emails
"""

from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import APIRouter, HTTPException, Response

from db import db
from events import DEFAULT_DURATION_SQL, Admin, Model

router = APIRouter(prefix="/api/admin")

# Whether an event, e, is not yet over.
NOT_OVER = f"COALESCE(e.ends_at, e.starts_at + {DEFAULT_DURATION_SQL}) >= now()"


class Stats(Model):
    members: int
    # Members seen in the last 30 days.
    active_members: int
    upcoming_events: int
    # People going to upcoming events: members and their guests.
    upcoming_going: int


class MemberRow(Model):
    id: str
    name: str
    email: str
    image_url: str
    # As of their latest sign-in: admins are made in Clerk.
    admin: bool
    joined_at: datetime
    last_seen_at: datetime
    # Upcoming events they're going to, and past ones they went to.
    upcoming_going: int
    past_going: int


class MemberList(Model):
    members: list[MemberRow]


@router.get("/stats")
async def stats(_: Admin) -> Stats:
    row = (
        await db.read()
        .query(
            f"""
        SELECT
            (SELECT count(*) FROM members)::int AS members,
            (SELECT count(*) FROM members
                WHERE last_seen_at >= now() - interval '30 days')::int AS active_members,
            (SELECT count(*) FROM events e WHERE {NOT_OVER})::int AS upcoming_events,
            ((SELECT COALESCE(SUM(1 + r.guests), 0) FROM rsvps r
                JOIN events e ON e.id = r.event_id
                WHERE r.status = 'going' AND {NOT_OVER})
             + (SELECT count(*) FROM guest_signups g
                JOIN events e ON e.id = g.event_id
                WHERE {NOT_OVER}))::int AS upcoming_going
        """
        )
        .one()
    )
    return Stats(**row)


@router.get("/members")
async def members(_: Admin) -> MemberList:
    rows = (
        await db.read()
        .query(
            f"""
        SELECT m.id, m.name, m.email, m.image_url, m.admin,
               m.created_at AS joined_at, m.last_seen_at,
               COUNT(r.event_id) FILTER (WHERE r.status = 'going' AND {NOT_OVER})::int
                   AS upcoming_going,
               COUNT(r.event_id) FILTER (WHERE r.status = 'going' AND NOT {NOT_OVER})::int
                   AS past_going
        FROM members m
        LEFT JOIN rsvps r ON r.user_id = m.id
        LEFT JOIN events e ON e.id = r.event_id
        GROUP BY m.id
        ORDER BY m.last_seen_at DESC, m.name
        """
        )
        .all()
    )
    return MemberList(members=[MemberRow(**r) for r in rows])


STATUS_LABELS = {"going": "Going", "maybe": "Maybe", "not_going": "Can't go"}


def cell(value: str) -> str:
    """A value a spreadsheet won't run as a formula."""
    return "'" + value if value[:1] in ("=", "+", "-", "@", "\t", "\r") else value


@router.get("/events/{event_id}/attendees.csv")
async def attendees_csv(event_id: int, _: Admin) -> Response:
    event = await db.read().query("SELECT slug FROM events WHERE id = $1", event_id).first()
    if event is None:
        raise HTTPException(status_code=404, detail="no such event")
    rows = (
        await db.read()
        .query(
            """
        SELECT m.name, m.email, r.status, r.guests, r.updated_at
        FROM rsvps r JOIN members m ON m.id = r.user_id
        WHERE r.event_id = $1
        ORDER BY CASE r.status WHEN 'going' THEN 0 WHEN 'maybe' THEN 1 ELSE 2 END, m.name
        """,
            event_id,
        )
        .all()
    )
    guests = (
        await db.read()
        .query(
            """
        SELECT name, email, created_at FROM guest_signups
        WHERE event_id = $1
        ORDER BY name
        """,
            event_id,
        )
        .all()
    )

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Name", "Email", "Answer", "Guests", "Answered at"])
    for r in rows:
        writer.writerow(
            [
                cell(r["name"]),
                cell(r["email"]),
                STATUS_LABELS[r["status"]],
                r["guests"],
                r["updated_at"].isoformat(timespec="minutes"),
            ]
        )
    # Guests who signed up through a shareable link.
    for g in guests:
        writer.writerow(
            [
                cell(g["name"]),
                cell(g["email"]),
                "Guest sign-up",
                0,
                g["created_at"].isoformat(timespec="minutes"),
            ]
        )

    filename = f"{event['slug']}.csv"
    return Response(
        content=out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
