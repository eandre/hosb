-- Every event has a slug: its date in Stockholm and its title, as
-- 2026-11-26-the-house-dinner-thanksgiving, with -2, -3, ... for the second
-- and third of the same name on one day. Its page is /events/<slug>. events.py
-- makes the slugs of new and changed events the same way (see slugify there).
ALTER TABLE events ADD COLUMN slug TEXT;

WITH base AS (
    SELECT id,
           to_char(starts_at AT TIME ZONE 'Europe/Stockholm', 'YYYY-MM-DD') || '-' ||
           COALESCE(
               NULLIF(trim(BOTH '-' FROM left(trim(BOTH '-' FROM regexp_replace(
                   translate(lower(title), 'åäöáàâãéèêëíìîïóòôõúùûüýÿçñæø',
                                           'aaoaaaaeeeeiiiiooooouuuuyycnao'),
                   '[^a-z0-9]+', '-', 'g')), 60)), ''),
               'event') AS base
    FROM events
),
numbered AS (
    SELECT id, base, row_number() OVER (PARTITION BY base ORDER BY id) AS n FROM base
)
UPDATE events e
SET slug = CASE WHEN numbered.n = 1 THEN numbered.base ELSE numbered.base || '-' || numbered.n END
FROM numbered
WHERE numbered.id = e.id;

ALTER TABLE events ALTER COLUMN slug SET NOT NULL;
ALTER TABLE events ADD CONSTRAINT events_slug_key UNIQUE (slug);

-- Every slug an event has had, so that a page's address keeps working when the
-- event's title or date, and with them its slug, changes. A slug is never
-- given to another event.
CREATE TABLE event_slugs (
    slug     TEXT PRIMARY KEY,
    event_id BIGINT NOT NULL REFERENCES events (id) ON DELETE CASCADE
);
INSERT INTO event_slugs (slug, event_id) SELECT slug, id FROM events;

-- How many guests a member's shareable link for the event may sign up: NULL
-- for no limit. An admin's links each have a cap of their own.
ALTER TABLE events ADD COLUMN share_signup_cap INTEGER CHECK (share_signup_cap > 0);

-- Shareable links to one event, /s/<slug>-<token>: whoever has one sees that event,
-- and nothing else, and may sign up for it as a guest.
CREATE TABLE share_links (
    id         BIGSERIAL PRIMARY KEY,
    token      TEXT NOT NULL UNIQUE,
    event_id   BIGINT NOT NULL REFERENCES events (id) ON DELETE CASCADE,
    created_by TEXT NOT NULL REFERENCES members (id),
    -- 'member': a member's one link to the event, whose cap is the event's.
    -- 'admin': one of an admin's named links, with a cap of its own.
    kind       TEXT NOT NULL CHECK (kind IN ('member', 'admin')),
    name       TEXT NOT NULL DEFAULT '',
    signup_cap INTEGER CHECK (signup_cap > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX share_links_one_per_member ON share_links (event_id, created_by)
    WHERE kind = 'member';
CREATE INDEX share_links_event_idx ON share_links (event_id);

-- Who has opened a link: one row per visitor (an id their browser keeps), with
-- how often they did.
CREATE TABLE share_link_views (
    link_id         BIGINT NOT NULL REFERENCES share_links (id) ON DELETE CASCADE,
    visitor_id      TEXT NOT NULL,
    views           INTEGER NOT NULL DEFAULT 1,
    first_viewed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_viewed_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (link_id, visitor_id)
);

-- Guests who signed up for an event through a link. They count towards the
-- event's places, as members going and their guests do.
CREATE TABLE guest_signups (
    id         BIGSERIAL PRIMARY KEY,
    event_id   BIGINT NOT NULL REFERENCES events (id) ON DELETE CASCADE,
    link_id    BIGINT REFERENCES share_links (id) ON DELETE SET NULL,
    name       TEXT NOT NULL,
    -- Lowercased: one sign-up per address and event.
    email      TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (event_id, email)
);
CREATE INDEX guest_signups_link_idx ON guest_signups (link_id);
