"""Events' slugs: their date in Stockholm and their title."""

from datetime import UTC, datetime

import pytest

from slugs import base_slug, slugify


@pytest.mark.parametrize(
    ("title", "slug"),
    [
        ("The House Dinner: Thanksgiving", "the-house-dinner-thanksgiving"),
        ("Stitch & Bitch", "stitch-bitch"),
        ("Night Owl Nerd-out", "night-owl-nerd-out"),
        ("Midsommar på gården", "midsommar-pa-garden"),
        ("Smörgåsbord för älgar", "smorgasbord-for-algar"),
        ("Café Ærø", "cafe-aro"),
        ("  --Second-Rate Cinema--  ", "second-rate-cinema"),
        ("🧸 MINI BEASTS 💛", "mini-beasts"),
        ("!!!", "event"),
    ],
)
def test_slugifies_titles(title: str, slug: str):
    assert slugify(title) == slug


def test_cuts_long_titles_at_a_word_boundary_dash():
    slug = slugify("a" * 59 + " bcd")
    assert len(slug) <= 60
    assert not slug.endswith("-")


def test_dates_are_the_houses():
    # 23:30 UTC on the 30th is already the 31st in Stockholm.
    assert base_slug("Late", datetime(2026, 10, 30, 23, 30, tzinfo=UTC)) == "2026-10-31-late"
    assert base_slug("Early", datetime(2026, 11, 26, 17, 0, tzinfo=UTC)) == "2026-11-26-early"
