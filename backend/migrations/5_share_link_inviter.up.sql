-- Whose invitation an admin's link is, as its guests read it ("Lisa invited
-- you to..."): someone the admin made it for. NULL for the admin's own, which
-- guests see as from the admin's first name.
ALTER TABLE share_links ADD COLUMN invited_by TEXT;
