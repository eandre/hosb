-- Each event's own guest rules, as its admin sets them: how many guests a
-- member may bring, and whether they must give each one's full name.
ALTER TABLE events
    ADD COLUMN max_guests INTEGER NOT NULL DEFAULT 4 CHECK (max_guests BETWEEN 0 AND 20),
    ADD COLUMN guest_names_required BOOLEAN NOT NULL DEFAULT TRUE;

-- The limit is the event's now, which save_rsvp keeps to; this is only the
-- most any event allows. An RSVP made under a higher limit stays as it was.
ALTER TABLE rsvps DROP CONSTRAINT rsvps_guests_check;
ALTER TABLE rsvps
    ADD CONSTRAINT rsvps_guests_check CHECK (guests BETWEEN 0 AND 20),
    -- The names of the guests a member brings, as they gave them.
    ADD COLUMN guest_names TEXT[] NOT NULL DEFAULT '{}';
