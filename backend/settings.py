"""The service's config: settings.config.toml, with an overlay per environment."""

from dataclasses import dataclass, field

from encore.config import Config


@dataclass
class Settings:
    # The Clerk publishable key the frontend signs in with. Public.
    clerk_publishable_key: str = ""
    # Origins a session token may have been issued for (its azp claim).
    # Empty accepts any.
    authorized_parties: list[str] = field(default_factory=list)
    # Google Calendar sync: the OAuth client's id, from the Google Cloud
    # console (APIs & Services → Credentials), whose secret is the
    # GoogleClientSecret secret. Empty turns the sync off. See
    # google_calendar.py for the rest of its setup.
    google_client_id: str = ""
    # Google's endpoints: changed only for tests.
    google_auth_url: str = "https://accounts.google.com/o/oauth2/v2/auth"
    google_token_url: str = "https://oauth2.googleapis.com/token"
    google_revoke_url: str = "https://oauth2.googleapis.com/revoke"
    google_api_url: str = "https://www.googleapis.com/calendar/v3"


settings = Config[Settings]("settings")
