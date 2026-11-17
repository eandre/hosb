"""Events' slugs: their date in Stockholm and their title, as
2026-11-26-the-house-dinner-thanksgiving.

The migration that gave the existing events theirs makes them the same way
(migrations/4_slugs_and_share_links.up.sql).
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from encore.storage.postgres import Transaction

HOUSE_TIME = ZoneInfo("Europe/Stockholm")
MAX_TITLE_LENGTH = 60

# Letters NFKD doesn't decompose into an ASCII one.
_SPECIAL = str.maketrans({"æ": "a", "ø": "o", "Æ": "a", "Ø": "o", "ß": "ss"})


def slugify(title: str) -> str:
    """The title as lowercase ASCII words joined by dashes: "Stitch & Bitch"
    → "stitch-bitch". "event" for a title with no letters or digits."""
    text = unicodedata.normalize("NFKD", title.translate(_SPECIAL))
    text = text.encode("ascii", "ignore").decode().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:MAX_TITLE_LENGTH].strip("-") or "event"


def base_slug(title: str, starts_at: datetime) -> str:
    """The slug an event starting at starts_at has, before it is told apart
    from another's of the same name and day."""
    return f"{starts_at.astimezone(HOUSE_TIME):%Y-%m-%d}-{slugify(title)}"


async def assign_slug(tx: Transaction, event_id: int, title: str, starts_at: datetime) -> str:
    """Gives the event its slug, the first of base, base-2, base-3, ... that no
    other event has ever had, and records it among the event's slugs, whose
    pages lead to the event. Returns the slug."""
    base = base_slug(title, starts_at)
    rows = await tx.query(
        "SELECT slug, event_id FROM event_slugs WHERE slug = $1 OR slug LIKE $1 || '-%'",
        base,
    ).all()
    owners = {r["slug"]: r["event_id"] for r in rows}
    n = 1
    while True:
        slug = base if n == 1 else f"{base}-{n}"
        if owners.get(slug, event_id) == event_id:
            break
        n += 1
    await tx.exec(
        "INSERT INTO event_slugs (slug, event_id) VALUES ($1, $2) ON CONFLICT (slug) DO NOTHING",
        slug,
        event_id,
    )
    await tx.exec("UPDATE events SET slug = $2 WHERE id = $1", event_id, slug)
    return slug
