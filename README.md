# House of Soft Beasts · Members' calendar

A calendar of the events at the [House of Soft Beasts](https://www.houseofsoftbeasts.se/),
where members sign in, see what's coming up, and say whether they'll be there.
Admins create, change and delete events.

It is an [Encore](https://encore.dev) v2 app:

| Directory  | What it is |
|------------|------------|
| `backend/` | The `community` service: Python, FastAPI. The JSON API under `/api`, which the `api` gateway exposes. Postgres database `community`. |
| `frontend/`| The `web` service: a Go program serving the frontend, a Vite app (React, Tailwind CSS and shadcn/ui, mobile first) embedded in it. Served from an origin of its own, it calls the API on the `api` gateway. |
| `gateway/` | The `api` gateway, where the API is reached. Its CORS policy lets the `web` frontend call it. |
| `systest/` | System tests (`e2e`): pytest against the whole running app's API. |

## Authentication

Members sign in with [Clerk](https://clerk.com). The frontend sends each API
request the member's Clerk session token, which the backend verifies itself
(networkless) with the Clerk instance's public key. An admin is a Clerk user
whose **public metadata** has `"admin": true`.

To set up a Clerk instance for it:

1. **Customize the session token** (Clerk dashboard → Sessions → Customize
   session token), so it says who the member is and whether they are an admin:

   ```json
   {
     "name": "{{user.full_name}}",
     "email": "{{user.primary_email_address}}",
     "image": "{{user.image_url}}",
     "metadata": "{{user.public_metadata}}"
   }
   ```

2. **Give the backend the instance's public key** (API keys → **JWKS Public Key**, the
   PEM that starts `-----BEGIN PUBLIC KEY-----`) as the `ClerkJWTKey` secret:

   ```sh
   encore secret set community.ClerkJWTKey < clerk-public-key.pem
   ```

3. **Give the frontend the publishable key**: `clerk_publishable_key` in
   `backend/settings.config.toml` (or an environment's overlay, such as
   `settings.production.config.toml`). The frontend reads it from
   `GET /api/config`, so one build serves every environment.

4. Optionally, list the frontend's origins in `authorized_parties` in the same
   file: tokens issued for any other origin are then refused.

5. **Make someone an admin**: on their user in the Clerk dashboard, set public
   metadata `{"admin": true}`. It takes effect when their session token is
   next refreshed (within a minute).

Anyone who can sign in to the Clerk instance is a member, so restrict sign-ups
in Clerk (Restrictions → allowlist, or invitations only).

## Google Calendar

On the settings page (`/settings`), a member can connect their Google account
and have the house's events kept in one of its calendars, or in a new one the
app makes: the events they're going to or might go to, or all of them. Changes
to events and RSVPs reach their calendar within seconds, through the
`calendar-changes` Pub/Sub topic, and an hourly cron job catches up on any
that failed. Disconnecting takes the events out again. How it works is in
`backend/google_calendar.py`.

To set it up for an environment:

1. In a [Google Cloud project](https://console.cloud.google.com), **enable the
   Google Calendar API**, and set up the **OAuth consent screen** with the
   scopes `openid`, `email`, `calendar.calendarlist.readonly`,
   `calendar.events` and `calendar.app.created`. Publish the app: while it is
   in testing, only listed test users can connect, and Google drops their
   connection after a week.

2. **Create an OAuth client** (Credentials → Create credentials → OAuth client
   ID, type "Web application"), with an authorized redirect URI of
   the `api` gateway's `/api/google/callback` in each environment, such as
   `http://api.localhost:4000/api/google/callback` locally: the callback is
   part of the API.

3. **Give the app the client**: its id as `google_client_id` in
   `backend/settings.config.toml` (or an environment's overlay), and its secret
   as the `GoogleClientSecret` secret:

   ```sh
   encore secret set community.GoogleClientSecret
   ```

4. **Set the `GoogleTokenKey` secret**, which encrypts members' Google tokens in
   the database: any long random string. Changing it later disconnects
   everyone.

   ```sh
   openssl rand -base64 32 | encore secret set community.GoogleTokenKey
   ```

Until `google_client_id` is set, the settings page says the sync isn't set up.

### Calendar invitations

A member can instead ask for every event as an invitation (settings page,
"Calendar invitations"), sent to their account's address: they answer it yes,
maybe or no in their calendar, whichever it is, and that's their RSVP here; an
RSVP made here is their answer there. Google shows an event's yes/maybe/no
only to guests of someone else's event, so the invitations come from a Google
account of the house's own, such as `calendar@hosb.se`: each event is one
event in its calendar, with the members who asked as guests (who can't see
each other). Answers reach the app as Google tells it of them, or within ten
minutes, when a cron job reads them; a yes to an event that's full is set
back. How it works is in `backend/google_invitations.py`.

To set it up, with the OAuth client above: an admin opens the admin page's
Invitations tab and connects the house's account. Its consent screen needs the
same scopes. Google tells the app of answers only at an HTTPS address, the
`api` gateway's `/api/google/notifications`, so locally the cron job (`encore
cron trigger google-invitations`) and "Sync now" read them.

## Develop

```sh
cd frontend && bun install
encore run   # the app at http://web.localhost:4000, its API at http://api.localhost:4000
```

`web` is a Go service hosting a frontend (the `frontend` section of
`frontend/encore.service.json`). Its build's `prebuild` step runs
`bun run build`, which typechecks the Vite app in `frontend/src` and builds it
into `frontend/dist/app`; then Encore's Go build compiles `main.go`, which
embeds it (`//go:embed`). The program serves the app's files, and its page for
every other path, the app's own routes, with the `api` gateway's URL in it
(`window.hosb.apiURL`, from `gateways.URL("api")`), which the app calls the API
at.

The frontend is served from an origin of its own, apart from the gateway's: a
gateway can't route `/api` to `community` and every other path to `web`
(ENC0029). Locally they are `web.localhost` and `api.localhost` on the app
port; deployed, each has the environment's address, and a custom domain such as
`www.hosb.se` belongs to the `web` frontend. The page calls the API across
origins, with the member's session token, which the gateway's CORS policy allows
the `web` frontend (`allow_frontends`).

There is no hot reload: a change to the app is built when `web` is next
restarted, as Encore restarts a service whose source changed. `bun run dev`
serves the app alone with Vite's dev server, without the API.

Encore gives the Go program its SDK, `sdk.encore.dev`, through a Go workspace
of its own, so `frontend/` builds under Encore (`encore run`, `encore test`,
`encore build`) and not with a plain `go build`.

The backend's Python environment is managed with uv (`backend/pyproject.toml`).
This app was made with a development build of Encore, whose Python SDK is not
published, so `backend/` and `systest/` use the SDK from a checkout of Encore
beside this repository (`[tool.uv.sources]`). With a released Encore, remove
that and depend on `encore-dev` from PyPI.

## API

| Route | Who | |
|---|---|---|
| `GET /api/health` | anyone | liveness |
| `GET /api/config` | anyone | the Clerk publishable key |
| `GET /api/me` | member | the member, and whether they are an admin |
| `GET /api/events` | member | upcoming events; `?scope=past`, or `?from=&to=` (ISO 8601) for a range |
| `GET /api/events/{ref}` | member | an event, with who's coming, by its slug (or one it had) or id |
| `POST /api/events` | admin | create an event |
| `PUT /api/events/{id}` | admin | change an event |
| `DELETE /api/events/{id}` | admin | delete an event and its RSVPs |
| `PUT /api/events/{id}/rsvp` | member | `{"status": "going" \| "maybe" \| "not_going", "guests": 0-4}` |
| `DELETE /api/events/{id}/rsvp` | member | withdraw one's RSVP |
| `POST /api/events/{id}/share-links` | member | the member's one shareable link to the event; an admin's new one, `{"name": "...", "signupCap": 10, "invitedBy": "Lisa"}` |
| `GET /api/events/{id}/share-links` | admin | the event's links, with views and sign-ups |
| `GET /api/admin/share-links` | admin | every link, with views and sign-ups |
| `GET /api/share/{token}` | anyone | the link's event, as a guest sees it |
| `POST /api/share/{token}/views` | anyone | a visit, `{"visitorId": "..."}` |
| `POST /api/share/{token}/signups` | anyone | sign up as a guest, `{"name": "...", "email": "..."}` |
| `GET /api/google` | member | the member's Google Calendar connection |
| `POST /api/google/connect` | member | start connecting, `{"origin": "https://..."}`: Google's sign-in URL |
| `GET /api/google/callback` | anyone | where Google sends the member back; its state says whose it is |
| `GET /api/google/calendars` | member | the calendars the member can add events to |
| `PUT /api/google/settings` | member | `{"mode": "rsvp" \| "all", "calendarId": "..."}` or `{"mode": ..., "newCalendar": true}`, then a sync |
| `POST /api/google/sync` | member | sync the member's calendar now |
| `DELETE /api/google` | member | disconnect, taking the events out of the calendar |
| `GET /api/invitations` | member | whether the member gets invitations, and where |
| `PUT /api/invitations` | member | `{"enabled": true}` for every event as an invitation, or `false` |
| `GET /api/admin/google-organizer` | admin | the house's Google account, which sends the invitations |
| `POST /api/admin/google-organizer/connect` | admin | start connecting it, `{"origin": "https://..."}` |
| `POST /api/admin/google-organizer/sync` | admin | read the answers and send the invitations now |
| `DELETE /api/admin/google-organizer` | admin | disconnect it, cancelling the invitations |
| `POST /api/google/notifications` | Google | a change in the house's calendar, on its push channel |

An event can have a number of places, which members going, their guests, and
guests signed up through shareable links fill; an RSVP or sign-up that would
overfill it is refused (409).

Each event has a slug, its date in Stockholm and its title
(`2026-11-26-the-house-dinner-thanksgiving`), and its page is
`/events/<slug>`. A shareable link, `/s/<slug>-<token>`, shows its one event to anyone
who has it, without signing in, and lets them sign up as a guest with their
name and email address. A member has one link per event; its sign-ups are
capped by the event's "guests per member link". An admin makes named links,
each with a cap of its own, and sees each one's views (by visitor) and
sign-ups. Guests read who invited them: the first name of whoever made the
link, or, for an admin's link made for someone else, the name the admin gave
as "Invited by". Interactive docs are at
`/api/docs`.

## Test

```sh
encore test
```

The system tests can't sign in through Clerk, so they sign Clerk-shaped
session tokens with `systest/clerk_test_key.pem`, a key made for the tests
only, whose public half `secrets.test.toml` gives the backend as
`ClerkJWTKey` under test.

Nor can they reach Google: `systest/fake_google.py` stands in for its OAuth
and Calendar APIs, on the port `backend/settings.test.config.toml` points the
backend at, with the test-only `GoogleClientSecret` and `GoogleTokenKey` from
`secrets.test.toml`.
