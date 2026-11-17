"""A fake Google, for the system tests: its OAuth token and revoke endpoints
and the part of the Calendar API the app uses, kept in memory.

The app finds it where settings.test.config.toml says, on PORT.
"""

from __future__ import annotations

import json
import secrets
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

import jwt

PORT = 47365
CLIENT_ID = "test-client.apps.googleusercontent.com"
CLIENT_SECRET = "test-client-secret"  # secrets.test.toml's GoogleClientSecret
ALL_SCOPES = " ".join(
    [
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/calendar.calendarlist.readonly",
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/calendar.app.created",
    ]
)


@dataclass
class Calendar:
    id: str
    owner: str
    summary: str
    access_role: str = "owner"
    primary: bool = False
    events: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass
class Grant:
    email: str
    scope: str
    redirect_uri: str


class FakeGoogle:
    """Google's state: accounts' calendars, and the codes and tokens given."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self.lock:
            self.calendars: dict[str, Calendar] = {}
            self.codes: dict[str, Grant] = {}
            self.refresh_tokens: dict[str, str] = {}  # token: email
            self.access_tokens: dict[str, str] = {}  # token: email
            self.revoked: list[str] = []

    # --- for the tests ---

    def account(self, email: str) -> None:
        """A Google account, with its own calendar and a friend's it may only read."""
        with self.lock:
            self.calendars[email] = Calendar(email, email, email, primary=True)
            shared = f"shared-{email}#holidays@group.calendar.google.com"
            self.calendars[shared] = Calendar(shared, email, "Holidays", access_role="reader")

    def consent(self, email: str, redirect_uri: str, scope: str = ALL_SCOPES) -> str:
        """The code Google sends the member back with, once they've agreed."""
        code = "code-" + secrets.token_hex(8)
        with self.lock:
            self.codes[code] = Grant(email, scope, redirect_uri)
        return code

    def events(self, calendar_id: str) -> list[dict[str, Any]]:
        with self.lock:
            calendar = self.calendars.get(calendar_id)
            return [] if calendar is None else [dict(e) for e in calendar.events.values()]

    def calendars_of(self, email: str) -> list[Calendar]:
        with self.lock:
            return [c for c in self.calendars.values() if c.owner == email]

    def revoke_all(self, email: str) -> None:
        """The member removes the app's access in their Google account."""
        with self.lock:
            for tokens in (self.refresh_tokens, self.access_tokens):
                for token in [t for t, e in tokens.items() if e == email]:
                    del tokens[token]

    # --- what Google answers ---

    def token(self, form: dict[str, str]) -> tuple[int, dict[str, Any]]:
        if form.get("client_id") != CLIENT_ID or form.get("client_secret") != CLIENT_SECRET:
            return 401, {"error": "invalid_client"}
        with self.lock:
            if form.get("grant_type") == "authorization_code":
                grant = self.codes.pop(form.get("code", ""), None)
                if grant is None or grant.redirect_uri != form.get("redirect_uri"):
                    return 400, {"error": "invalid_grant"}
                refresh = "refresh-" + secrets.token_hex(8)
                self.refresh_tokens[refresh] = grant.email
                return 200, {
                    **self._access(grant.email),
                    "refresh_token": refresh,
                    "scope": grant.scope,
                    "id_token": jwt.encode({"email": grant.email}, "a-fake-google-signing-key-of-32-bytes", algorithm="HS256"),
                }
            if form.get("grant_type") == "refresh_token":
                email = self.refresh_tokens.get(form.get("refresh_token", ""))
                if email is None:
                    return 400, {"error": "invalid_grant", "error_description": "Token has been expired or revoked."}
                return 200, self._access(email)
        return 400, {"error": "unsupported_grant_type"}

    def _access(self, email: str) -> dict[str, Any]:
        token = "access-" + secrets.token_hex(8)
        self.access_tokens[token] = email
        return {"access_token": token, "expires_in": 3599, "token_type": "Bearer"}

    def revoke(self, form: dict[str, str]) -> tuple[int, dict[str, Any]]:
        token = form.get("token", "")
        with self.lock:
            self.revoked.append(token)
            email = self.refresh_tokens.pop(token, None) or self.access_tokens.pop(token, None)
        if email is not None:
            self.revoke_all(email)
        return 200, {}

    def api(self, method: str, parts: list[str], query: dict[str, str], body: Any, email: str) -> tuple[int, Any]:
        with self.lock:
            match method, parts:
                case "GET", ["users", "me", "calendarList"]:
                    writable = query.get("minAccessRole") == "writer"
                    items = [
                        {"id": c.id, "summary": c.summary, "accessRole": c.access_role, "primary": c.primary}
                        for c in self.calendars.values()
                        if c.owner == email and (not writable or c.access_role in ("owner", "writer"))
                    ]
                    return 200, {"items": items}
                case "POST", ["calendars"]:
                    calendar_id = f"c_{secrets.token_hex(6)}@group.calendar.google.com"
                    self.calendars[calendar_id] = Calendar(calendar_id, email, body["summary"])
                    return 200, {"id": calendar_id, "summary": body["summary"]}
            calendar = self.calendars.get(parts[1]) if len(parts) > 1 and parts[0] == "calendars" else None
            if calendar is None or calendar.owner != email:
                return 404, {"error": {"code": 404, "message": "Not Found"}}
            if calendar.access_role not in ("owner", "writer"):
                return 403, {"error": {"code": 403, "message": "Forbidden"}}
            match method, parts[2:]:
                case "POST", ["events"]:
                    event_id = secrets.token_hex(10)
                    calendar.events[event_id] = {**body, "id": event_id}
                    return 200, calendar.events[event_id]
                case "PUT", ["events", event_id] if event_id in calendar.events:
                    calendar.events[event_id] = {**body, "id": event_id}
                    return 200, calendar.events[event_id]
                case "DELETE", ["events", event_id] if event_id in calendar.events:
                    del calendar.events[event_id]
                    return 204, None
                case ("PUT" | "DELETE"), ["events", _]:
                    return 410, {"error": {"code": 410, "message": "Resource has been deleted"}}
        return 404, {"error": {"code": 404, "message": "Not Found"}}


class Handler(BaseHTTPRequestHandler):
    google: FakeGoogle

    def log_message(self, format: str, *args: Any) -> None:
        pass

    def _answer(self, status: int, body: Any) -> None:
        data = b"" if body is None else json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> bytes:
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))

    def _handle(self) -> None:
        url = urlsplit(self.path)
        parts = [unquote(p) for p in url.path.split("/") if p]
        query = {k: v[0] for k, v in parse_qs(url.query).items()}
        raw = self._body()
        if parts in (["token"], ["revoke"]):
            form = {k: v[0] for k, v in parse_qs(raw.decode()).items()}
            status, body = (self.google.token if parts == ["token"] else self.google.revoke)(form)
            return self._answer(status, body)
        if parts[:2] != ["calendar", "v3"]:
            return self._answer(404, {"error": "not found"})
        token = self.headers.get("Authorization", "").removeprefix("Bearer ")
        with self.google.lock:
            email = self.google.access_tokens.get(token)
        if email is None:
            return self._answer(401, {"error": {"code": 401, "message": "Invalid Credentials"}})
        status, body = self.google.api(
            self.command, parts[2:], query, json.loads(raw) if raw else None, email
        )
        self._answer(status, body)

    do_GET = do_POST = do_PUT = do_DELETE = _handle


def serve(google: FakeGoogle) -> ThreadingHTTPServer:
    handler = type("FakeGoogleHandler", (Handler,), {"google": google})
    server = ThreadingHTTPServer(("127.0.0.1", PORT), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server
