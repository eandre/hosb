# House of Soft Beasts · Members' calendar

A calendar of the events at the [House of Soft Beasts](https://www.houseofsoftbeasts.se/),
where members sign in, see what's coming up, and say whether they'll be there.
Admins create, change and delete events.

It is an [Encore](https://encore.dev) v2 app:

| Directory  | What it is |
|------------|------------|
| `backend/` | The `community` service: Python, FastAPI. The JSON API under `/api`, which the gateway doesn't route to: `web` passes it on. Postgres database `community`. |
| `frontend/`| The `web` service: Next.js, React, Tailwind CSS and shadcn/ui, mobile first. It hosts the frontend, and passes `/api` on its own origin to `community`. |
| `gateway/` | The `api` gateway, the app's one public address. It routes every path to `web`. |
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

## Develop

```sh
cd frontend && bun install
encore run   # the app, and its API at /api, at http://api.localhost:4000
```

`encore run` runs `web` as Next.js's dev server, with hot reload, through
`frontend/server.mjs`: it serves the app where Encore assigns the service, and
passes `/api` requests on to `community` with Encore's service client, so the
browser talks to one origin and each API call continues the page request's
trace.

Deployed, Encore builds `web` with its package's `build` script: `next build`,
then `scripts/release.mjs` packages Next.js's standalone output (only the files
its server loads), its static files, `server.mjs` and the packages
`server.mjs` loads itself (Encore's SDK) into `$ENCORE_OUTPUT_DIR`, which is all
the image holds, about 50 MB. The image starts `node server.mjs`, which serves
the build in production mode.

`frontend/` likewise uses the TypeScript SDK from the Encore checkout
(`@encore.dev/sdk` as a `file:` dependency).

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
| `POST /api/events/{id}/share-links` | member | the member's one shareable link to the event; an admin's new one, `{"name": "...", "signupCap": 10}` |
| `GET /api/events/{id}/share-links` | admin | the event's links, with views and sign-ups |
| `GET /api/admin/share-links` | admin | every link, with views and sign-ups |
| `GET /api/share/{token}` | anyone | the link's event, as a guest sees it |
| `POST /api/share/{token}/views` | anyone | a visit, `{"visitorId": "..."}` |
| `POST /api/share/{token}/signups` | anyone | sign up as a guest, `{"name": "...", "email": "..."}` |

An event can have a number of places, which members going, their guests, and
guests signed up through shareable links fill; an RSVP or sign-up that would
overfill it is refused (409).

Each event has a slug, its date in Stockholm and its title
(`2026-11-26-the-house-dinner-thanksgiving`), and its page is
`/events/<slug>`. A shareable link, `/s/<token>`, shows its one event to anyone
who has it, without signing in, and lets them sign up as a guest with their
name and email address. A member has one link per event; its sign-ups are
capped by the event's "guests per member link". An admin makes named links,
each with a cap of its own, and sees each one's views (by visitor) and
sign-ups. Interactive docs are at
`/api/docs`.

## Test

```sh
encore test
```

The system tests can't sign in through Clerk, so they sign Clerk-shaped
session tokens with `systest/clerk_test_key.pem`, a key made for the tests
only, whose public half `secrets.test.toml` gives the backend as
`ClerkJWTKey` under test.
