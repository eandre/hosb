"""The calendar-changes topic: what changed that members' synced calendars
may need to follow (see google_calendar.py and google_invitations.py).

A change is followed twice over. Right away, in this process: the handlers
in LOCAL_HANDLERS run in the background as soon as the change is published,
so a member's calendar has an RSVP within seconds. And when the topic
delivers it, to the same handlers through its subscriptions, which catch up
on what the first run missed (the process stopping, Google failing). The
second run finds the calendar up to date, and sends nothing: syncs take a
lock and send only what changed.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any

from encore import pubsub
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class CalendarChange(BaseModel):
    """What to bring up to date: one member's calendar (user_id), one event in
    every member's (event_id), or one event in one member's (both)."""

    user_id: str | None = None
    event_id: int | None = None


calendar_changes = pubsub.Topic[CalendarChange]("calendar-changes")

# What follows a change in this process as soon as it is made: each module
# that keeps calendars adds its handler here as it is imported.
LOCAL_HANDLERS: list[Callable[[CalendarChange], Awaitable[None]]] = []

# The background work running now: held so that it isn't collected before
# it finishes.
_running: set[asyncio.Task[None]] = set()


def run_soon(what: str, work: Coroutine[Any, Any, None]) -> None:
    """Run work in the background, logging rather than raising its failure:
    the topic's delivery, or a cron job, does it again."""

    async def run() -> None:
        try:
            await work
        except Exception:
            logger.warning("background work failed", exc_info=True, extra={"what": what})

    task = asyncio.create_task(run())
    _running.add(task)
    task.add_done_callback(_running.discard)


async def _publish(change: CalendarChange) -> None:
    await calendar_changes.publish(change)


async def notify(*, user_id: str | None = None, event_id: int | None = None) -> None:
    """Publish a change, and start following it here. A failure is logged, not
    raised: the change itself has been made, and a member's "Sync now" or the
    cron jobs catch their calendar up."""
    change = CalendarChange(user_id=user_id, event_id=event_id)
    try:
        await _publish(change)
    except Exception:
        logger.exception("publishing a calendar change", extra={"user": user_id, "event": event_id})
    for handler in LOCAL_HANDLERS:
        run_soon(handler.__qualname__, handler(change))
