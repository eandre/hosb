-- Google Calendar sync: each member may connect a Google account and have the
-- house's events kept in one of its calendars.

-- An OAuth sign-in to Google under way: the state sent to Google, whose
-- member it is for, and where to send them back.
CREATE TABLE google_oauth_states (
    state         TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL REFERENCES members (id) ON DELETE CASCADE,
    return_origin TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE google_connections (
    user_id           TEXT PRIMARY KEY REFERENCES members (id) ON DELETE CASCADE,
    google_email      TEXT NOT NULL DEFAULT '',
    -- Encrypted with the GoogleTokenKey secret.
    refresh_token     TEXT NOT NULL,
    access_token      TEXT,
    access_expires_at TIMESTAMPTZ,
    -- The calendar to sync to, once the member has picked one.
    calendar_id       TEXT,
    calendar_name     TEXT NOT NULL DEFAULT '',
    -- 'rsvp': the events they're going to or might go to; 'all': every event.
    mode              TEXT NOT NULL DEFAULT 'rsvp' CHECK (mode IN ('rsvp', 'all')),
    -- The app's address as the member uses it, for links back to events.
    app_origin        TEXT NOT NULL,
    -- 'reauth' when Google no longer accepts the refresh token.
    status            TEXT NOT NULL DEFAULT 'ok' CHECK (status IN ('ok', 'reauth')),
    last_error        TEXT NOT NULL DEFAULT '',
    last_synced_at    TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The events copied into a member's Google calendar. Not tied to events by a
-- foreign key: a deleted event's row says what to remove from Google.
CREATE TABLE google_synced_events (
    user_id         TEXT NOT NULL REFERENCES google_connections (user_id) ON DELETE CASCADE,
    event_id        BIGINT NOT NULL,
    calendar_id     TEXT NOT NULL,
    google_event_id TEXT NOT NULL,
    -- What was sent, to skip sending it again unchanged.
    content_hash    TEXT NOT NULL,
    synced_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, event_id)
);
