"""The calendar-changes topic: what changed that members' synced calendars
may need to follow (see google_calendar.py)."""

import logging

from encore import pubsub
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CalendarChange(BaseModel):
    """What to bring up to date: one member's calendar (user_id), one event in
    every member's (event_id), or one event in one member's (both)."""

    user_id: str | None = None
    event_id: int | None = None


calendar_changes = pubsub.Topic[CalendarChange]("calendar-changes")


async def notify(*, user_id: str | None = None, event_id: int | None = None) -> None:
    """Publish a change. A failure is logged, not raised: the change itself has
    been made, and a member's "Sync now" catches their calendar up."""
    try:
        await calendar_changes.publish(CalendarChange(user_id=user_id, event_id=event_id))
    except Exception:
        logger.exception("publishing a calendar change", extra={"user": user_id, "event": event_id})
