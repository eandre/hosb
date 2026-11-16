"""Verifying Clerk session tokens.

Under test, the ClerkJWTKey secret is the public half of the system tests' key
(secrets.test.toml), and settings.test.config.toml allows tokens issued for
http://localhost:4000 only.
"""

import time
from pathlib import Path

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException

from auth import verify

TEST_KEY = (Path(__file__).parents[2] / "systest" / "clerk_test_key.pem").read_text()
ORIGIN = "http://localhost:4000"


def token(key: str = TEST_KEY, lifetime: int = 60, **claims) -> str:
    now = int(time.time())
    return jwt.encode(
        {"sub": "user_ada", "azp": ORIGIN, "iat": now, "nbf": now - 5, "exp": now + lifetime}
        | claims,
        key,
        algorithm="RS256",
    )


def rejected(t: str) -> str:
    with pytest.raises(HTTPException) as err:
        verify(t)
    assert err.value.status_code == 401
    return err.value.detail


def test_reads_the_member_from_the_claims():
    user = verify(
        token(
            name=" Ada Lovelace ",
            email="ada@example.test",
            image="https://img.example.test/ada.png",
            metadata={"admin": True},
        )
    )
    assert user.id == "user_ada"
    assert user.name == "Ada Lovelace"
    assert user.email == "ada@example.test"
    assert user.image_url == "https://img.example.test/ada.png"
    assert user.admin is True


def test_only_admin_true_makes_an_admin():
    assert verify(token(metadata={})).admin is False
    assert verify(token(metadata={"admin": "true"})).admin is False
    assert verify(token(metadata=["admin"])).admin is False
    # A token that wasn't customized has no metadata, and no names.
    plain = verify(token())
    assert (plain.admin, plain.name, plain.email) == (False, "", "")


def test_rejects_bad_tokens():
    other = (
        rsa.generate_private_key(public_exponent=65537, key_size=2048)
        .private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        .decode()
    )
    assert "Signature verification failed" in rejected(token(key=other))
    assert "expired" in rejected(token(lifetime=-60))
    assert "another origin" in rejected(token(azp="https://evil.example"))
    assert rejected("not-a-token")

    # A token must say who it is for, and when it was issued.
    now = int(time.time())
    no_sub = jwt.encode({"azp": ORIGIN, "iat": now, "exp": now + 60}, TEST_KEY, algorithm="RS256")
    assert "sub" in rejected(no_sub)


def test_rejects_other_algorithms():
    # An HMAC token signed with the public key, the classic confusion attack.
    public = jwt.decode(token(), options={"verify_signature": False})
    forged = jwt.encode(public, "a-shared-secret-of-thirty-two-bytes", algorithm="HS256")
    assert rejected(forged)
