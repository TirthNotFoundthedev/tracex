"""Passwords, tokens, cursors and keyed hashes. Four distinct keys, each used for one purpose."""

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import uuid
from datetime import datetime
from typing import Any

import jwt
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ALGORITHM = "HS256"
_SCRYPT = {"n": 2**14, "r": 8, "p": 1}
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT, maxmem=2**26)
    return f"scrypt${b64(salt)}${b64(digest)}"


# A hash of an unguessable value, checked when the username is unknown so both paths cost the same.
DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def verify_password(password: str, stored: str | None) -> bool:
    candidate = stored or DUMMY_HASH
    try:
        scheme, salt, digest = candidate.split("$")
        derived = hashlib.scrypt(password.encode(), salt=unb64(salt), **_SCRYPT, maxmem=2**26)
    except ValueError:
        return False
    return scheme == "scrypt" and stored is not None and hmac.compare_digest(derived, unb64(digest))


def keyed_hash(key: bytes, value: str) -> str:
    """The `hmac:<16 hex>` form of a raw string that must not be stored (audit spec section 6)."""
    return "hmac:" + hmac.new(key, value.encode(), hashlib.sha256).hexdigest()[:16]


def well_formed_uuid(value: str) -> bool:
    return bool(_UUID.match(value))


class TokenError(Exception):
    """A token that cannot be used; `failure` is the audit label."""

    def __init__(self, failure: str, claimed_sub: str | None = None) -> None:
        super().__init__(failure)
        self.failure = failure
        self.claimed_sub = claimed_sub


def issue_access_token(
    key: bytes, user_id: str, sid: str, version: int, now: datetime, minutes: int
) -> str:
    claims = {
        "sub": user_id,
        "sid": sid,
        "iat": int(now.timestamp()),
        "exp": int(now.timestamp()) + minutes * 60,
        "jti": str(uuid.uuid4()),
        "ver": version,
        "typ": "access",
    }
    return jwt.encode(claims, key, algorithm=ALGORITHM)


def issue_refresh_token(key: bytes, sid: str, jti: str, now: datetime, hours: int) -> str:
    claims = {
        "sid": sid,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(now.timestamp()) + hours * 3600,
        "typ": "refresh",
    }
    return jwt.encode(claims, key, algorithm=ALGORITHM)


def decode_token(key: bytes, token: str, kind: str, now: datetime) -> dict[str, Any]:
    """Verify signature and algorithm (pinned) and the expiry against the injected clock."""
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise TokenError("MALFORMED") from exc
    if header.get("alg") != ALGORITHM:
        raise TokenError("ALGORITHM")
    try:
        claims: dict[str, Any] = jwt.decode(
            token, key, algorithms=[ALGORITHM], options={"verify_exp": False, "verify_iat": False}
        )
    except jwt.InvalidSignatureError as exc:
        raise TokenError("BAD_SIGNATURE") from exc
    except jwt.PyJWTError as exc:
        raise TokenError("MALFORMED") from exc
    sub = claims.get("sub")
    claimed = sub if isinstance(sub, str) else None
    if claims.get("typ") != kind:
        raise TokenError("WRONG_TYPE", claimed)
    exp = claims.get("exp")
    if not isinstance(exp, int) or exp <= int(now.timestamp()):
        raise TokenError("EXPIRED", claimed)
    return claims


class CursorError(Exception):
    """A cursor that is malformed, foreign, for other filters, altered or expired (422)."""


def seal_cursor(key: bytes, payload: dict[str, Any], now: datetime, minutes: int = 15) -> str:
    body = json.dumps({**payload, "exp": int(now.timestamp()) + minutes * 60}, sort_keys=True)
    nonce = os.urandom(12)
    sealed = AESGCM(key[:32]).encrypt(nonce, body.encode(), None)
    return b64(nonce + sealed)


def open_cursor(key: bytes, cursor: str, now: datetime) -> dict[str, Any]:
    try:
        raw = unb64(cursor)
        body = AESGCM(key[:32]).decrypt(raw[:12], raw[12:], None)
        payload: dict[str, Any] = json.loads(body)
    except (ValueError, InvalidTag) as exc:
        raise CursorError("malformed") from exc
    if not isinstance(payload.get("exp"), int) or payload["exp"] <= int(now.timestamp()):
        raise CursorError("expired")
    return payload


def row_ref(key: bytes, row_id: str, reader_id: str) -> str:
    mac = hmac.new(key, f"{row_id}|{reader_id}".encode(), hashlib.sha256).digest()
    return b64(mac[:24])
