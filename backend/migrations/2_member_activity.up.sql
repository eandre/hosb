-- Whether the member was an admin, and when they were last seen, as of their
-- latest session token: for the admin page. Admin rights themselves are
-- checked on each request, from the token.
ALTER TABLE members
    ADD COLUMN admin        BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now();

CREATE INDEX members_last_seen_idx ON members (last_seen_at);
