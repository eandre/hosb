-- Calendar invitations: the house's own Google account organizes every event
-- in its calendar, with the members who asked for invitations as attendees.
-- Their answers there (yes, maybe, no) are their RSVPs.

-- Whose sign-in to Google this is: a member connecting their own calendar,
-- or an admin connecting the house's account, which sends the invitations.
ALTER TABLE google_oauth_states
    ADD COLUMN purpose TEXT NOT NULL DEFAULT 'member' CHECK (purpose IN ('member', 'organizer'));

-- The house's Google account: one row, or none until an admin connects it.
CREATE TABLE google_organizer (
    id                  BOOLEAN PRIMARY KEY DEFAULT TRUE CHECK (id),
    google_email        TEXT NOT NULL DEFAULT '',
    -- Encrypted with the GoogleTokenKey secret.
    refresh_token       TEXT NOT NULL,
    access_token        TEXT,
    access_expires_at   TIMESTAMPTZ,
    -- The account's calendar the events are organized in.
    calendar_id         TEXT NOT NULL DEFAULT 'primary',
    -- The app's address as the admin used it, for links back to events.
    app_origin          TEXT NOT NULL,
    status              TEXT NOT NULL DEFAULT 'ok' CHECK (status IN ('ok', 'reauth')),
    last_error          TEXT NOT NULL DEFAULT '',
    last_synced_at      TIMESTAMPTZ,
    -- Where the last read of the calendar's changes left off (Google's sync
    -- token): the next reads only what changed since.
    sync_token          TEXT,
    -- The push channel Google tells of the calendar's changes on, if any.
    channel_id          TEXT,
    channel_resource_id TEXT,
    channel_token       TEXT,
    channel_expires_at  TIMESTAMPTZ,
    connected_by        TEXT REFERENCES members (id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The members who get every event as an invitation, at this address.
CREATE TABLE invitation_subscribers (
    user_id    TEXT PRIMARY KEY REFERENCES members (id) ON DELETE CASCADE,
    -- Lowercased: how their answers are matched to them.
    email      TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- The house's events in the organizer's calendar. Not tied to events by a
-- foreign key: a deleted event's row says which invitation to cancel.
CREATE TABLE invitation_events (
    event_id        BIGINT PRIMARY KEY,
    google_event_id TEXT NOT NULL,
    -- What was sent: the event and who's invited, and their answers apart,
    -- since a change to the first notifies the attendees and to the
    -- second doesn't.
    content_hash    TEXT NOT NULL,
    answers_hash    TEXT NOT NULL,
    synced_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Each attendee's answer as Google last had it: one that differs when the
-- calendar is next read is the member's own, made in their calendar.
CREATE TABLE invitation_answers (
    event_id BIGINT NOT NULL,
    user_id  TEXT NOT NULL REFERENCES members (id) ON DELETE CASCADE,
    -- Google's responseStatus: needsAction, accepted, tentative or declined.
    answer   TEXT NOT NULL,
    PRIMARY KEY (event_id, user_id)
);
