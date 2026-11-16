-- Members are Clerk users. A row is kept up to date from their session token
-- so that attendee lists can show names without calling Clerk.
CREATE TABLE members (
    id         TEXT PRIMARY KEY, -- Clerk user id (the token's sub)
    name       TEXT NOT NULL DEFAULT '',
    email      TEXT NOT NULL DEFAULT '',
    image_url  TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE events (
    id          BIGSERIAL PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    location    TEXT NOT NULL DEFAULT '',
    starts_at   TIMESTAMPTZ NOT NULL,
    ends_at     TIMESTAMPTZ,
    -- Most people (members and their guests) who can attend; NULL for no limit.
    capacity    INTEGER CHECK (capacity > 0),
    created_by  TEXT NOT NULL REFERENCES members (id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (ends_at IS NULL OR ends_at > starts_at)
);

CREATE INDEX events_starts_at_idx ON events (starts_at);

CREATE TABLE rsvps (
    event_id   BIGINT NOT NULL REFERENCES events (id) ON DELETE CASCADE,
    user_id    TEXT NOT NULL REFERENCES members (id),
    status     TEXT NOT NULL CHECK (status IN ('going', 'maybe', 'not_going')),
    -- Guests the member brings along (guest passes).
    guests     INTEGER NOT NULL DEFAULT 0 CHECK (guests BETWEEN 0 AND 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (event_id, user_id)
);

CREATE INDEX rsvps_user_idx ON rsvps (user_id);
