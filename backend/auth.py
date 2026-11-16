"""Authentication with Clerk session tokens.

The frontend signs members in with Clerk and sends each API request a session
token: ``Authorization: Bearer <token>``. The token is an RS256 JWT signed by
the Clerk instance, which this service verifies without calling Clerk, with
the instance's public key (the ``ClerkJWTKey`` secret).

What the service needs to know about a member beyond their id is added to the
token by customizing the session token in the Clerk dashboard (Sessions →
Customize session token):

    {
      "name": "{{user.full_name}}",
      "email": "{{user.primary_email_address}}",
      "image": "{{user.image_url}}",
      "metadata": "{{user.public_metadata}}"
    }

A member is an admin when their public metadata has ``"admin": true``.
"""

from __future__ import annotations

import functools
import logging
from dataclasses import dataclass
from typing import Annotated, Any

import jwt
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from encore.secrets import Secret
from fastapi import Depends, HTTPException, Request

from settings import settings

logger = logging.getLogger(__name__)

clerk_jwt_key = Secret[str](
    "ClerkJWTKey",
    description=(
        "The PEM public key of the Clerk instance, which signs session tokens. "
        "Copy it from the Clerk dashboard: API keys → JWKS Public Key (PEM). "
        "It changes only if the instance's signing key is rotated in Clerk; "
        "set the new key here when it is."
    ),
)

# Clock skew tolerated between Clerk and this service, in seconds.
LEEWAY = 5


@dataclass(frozen=True)
class User:
    id: str
    name: str
    email: str
    image_url: str
    admin: bool


@functools.cache
def _public_key(pem: str) -> Any:
    # Keys pasted from a dashboard sometimes arrive with escaped newlines.
    return load_pem_public_key(pem.replace("\\n", "\n").strip().encode())


def _key() -> Any:
    try:
        pem = clerk_jwt_key.value
    except KeyError:
        logger.error("the ClerkJWTKey secret is not set: no request can be authenticated")
        raise HTTPException(status_code=503, detail="authentication is not configured")
    try:
        return _public_key(pem)
    except ValueError:
        logger.exception("the ClerkJWTKey secret is not a PEM public key")
        raise HTTPException(status_code=503, detail="authentication is not configured")


def _bearer(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=401,
            detail="sign in to continue",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token.strip()


def verify(token: str) -> User:
    """The member a session token is for, if it is valid.

    Raises:
        HTTPException: 401 if it is not, 503 if no key is configured.
    """
    try:
        claims = jwt.decode(
            token,
            _key(),
            algorithms=["RS256"],
            leeway=LEEWAY,
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError as err:
        raise HTTPException(
            status_code=401,
            detail=f"invalid session token: {err}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    allowed = settings.value.authorized_parties
    if allowed and claims.get("azp") not in allowed:
        raise HTTPException(
            status_code=401,
            detail="invalid session token: issued for another origin",
            headers={"WWW-Authenticate": "Bearer"},
        )

    metadata = claims.get("metadata")
    admin = isinstance(metadata, dict) and metadata.get("admin") is True
    if "metadata" not in claims:
        # Without it no one is an admin, and members have no names: the
        # session token hasn't been customized (see the module's doc).
        logger.warning(
            "session token lacks the custom claims: customize the session token in Clerk",
            extra={"claims": sorted(claims), "issuer": claims.get("iss", "")},
        )

    def text(key: str) -> str:
        value = claims.get(key)
        return value.strip() if isinstance(value, str) else ""

    return User(
        id=str(claims["sub"]),
        name=text("name"),
        email=text("email"),
        image_url=text("image"),
        admin=admin,
    )


async def current_user(request: Request) -> User:
    """FastAPI dependency: the signed-in member, or 401."""
    return verify(_bearer(request))


async def current_admin(user: Annotated[User, Depends(current_user)]) -> User:
    """FastAPI dependency: the signed-in member, who must be an admin, or 403."""
    if not user.admin:
        raise HTTPException(status_code=403, detail="only admins can do that")
    return user
