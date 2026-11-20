"""What a link to an event shows where it's shared (WhatsApp, Slack, iMessage):
the event's name and when it is. The web service puts it in the page as it
serves it (frontend/preview.go): those apps read a page's HTML and run none of
its scripts, so the app itself can't tell them.

GET /internal/previews/events/{ref}   an event page's: by a slug it has or had, or its id
GET /internal/previews/share/{ref}    a shareable link's: its event, and who invites

Under /internal, which the gateway doesn't route: only the web service asks.
What they return is shown to anyone with a link, signed in or not, so it is the
event's name, time and place, and no more: not who is coming, nor its
description.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException

from db import db
from events import Model, resolve_event
from share import shared

internal = APIRouter(prefix="/internal/previews")


class Preview(Model):
    title: str
    starts_at: datetime
    ends_at: datetime | None
    location: str
    # Who invites, on a shareable link's page.
    invited_by: str | None = None


@internal.get("/events/{ref}")
async def event_preview(ref: str) -> Preview:
    event_id = await resolve_event(ref)
    row = await db.query(
        "SELECT title, starts_at, ends_at, location FROM events WHERE id = $1", event_id
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="no such event")
    return Preview(**row)


@internal.get("/share/{ref}")
async def share_preview(ref: str) -> Preview:
    row = await shared(ref)
    return Preview(
        title=row["title"],
        starts_at=row["starts_at"],
        ends_at=row["ends_at"],
        location=row["location"],
        invited_by=row["invited_by"],
    )
