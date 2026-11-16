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


settings = Config[Settings]("settings")
