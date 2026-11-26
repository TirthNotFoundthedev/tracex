"""Settings, read from environment variables only. Nothing here has a default for a secret."""

import base64
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


DEV_SECRET_PREFIX = "dev-only"
ALLOW_DEV_SECRETS = "TRACEX_ALLOW_DEV_SECRETS"


def dev_secret_names(source: Mapping[str, str], keys: Mapping[str, bytes]) -> list[str]:
    """Names of the settings that still carry a published `dev-only` placeholder value."""
    weak = [name for name, value in keys.items() if value.startswith(DEV_SECRET_PREFIX.encode())]
    if source.get("TRACEX_API_DB_PASSWORD", "").startswith(DEV_SECRET_PREFIX):
        weak.append("TRACEX_API_DB_PASSWORD")
    if (urlsplit(source.get("DATABASE_URL", "")).password or "").startswith(DEV_SECRET_PREFIX):
        weak.append("DATABASE_URL")
    return weak


class ConfigError(RuntimeError):
    """A required setting is missing or malformed. The API refuses to start."""


@dataclass(frozen=True)
class Settings:
    database_url: str
    database_admin_url: str | None
    jwt_key: bytes
    cursor_key: bytes
    row_ref_key: bytes
    hmac_key: bytes
    audit_anchor_path: Path
    neo4j_uri: str | None
    neo4j_user: str
    neo4j_password: str
    access_token_minutes: int = 15
    session_hours: int = 8
    max_upload_bytes: int = 2_000_000

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = os.environ if env is None else env

        def need(name: str) -> str:
            value = source.get(name, "")
            if not value:
                raise ConfigError(f"environment variable {name} is required")
            return value

        def key(name: str) -> bytes:
            raw = need(name)
            try:
                decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
            except ValueError as exc:
                raise ConfigError(f"{name} must be base64url") from exc
            if len(decoded) < 32:
                raise ConfigError(f"{name} must decode to at least 32 bytes")
            return decoded

        keys = {
            name: key(name)
            for name in (
                "TRACEX_JWT_KEY",
                "TRACEX_CURSOR_KEY",
                "TRACEX_ROW_REF_KEY",
                "TRACEX_HMAC_KEY",
            )
        }
        if len(set(keys.values())) != len(keys):
            raise ConfigError("the four signing keys must be distinct secrets")
        if source.get(ALLOW_DEV_SECRETS, "") != "1":
            weak = dev_secret_names(source, keys)
            if weak:
                raise ConfigError(
                    f"{', '.join(weak)} hold public dev-only values; set real secrets, or set "
                    f"{ALLOW_DEV_SECRETS}=1 for a local development setup only"
                )
        return cls(
            database_url=need("DATABASE_URL"),
            database_admin_url=source.get("DATABASE_ADMIN_URL") or None,
            jwt_key=keys["TRACEX_JWT_KEY"],
            cursor_key=keys["TRACEX_CURSOR_KEY"],
            row_ref_key=keys["TRACEX_ROW_REF_KEY"],
            hmac_key=keys["TRACEX_HMAC_KEY"],
            audit_anchor_path=Path(need("AUDIT_ANCHOR_PATH")),
            neo4j_uri=source.get("NEO4J_URI") or None,
            neo4j_user=source.get("NEO4J_USER", "neo4j"),
            neo4j_password=source.get("NEO4J_PASSWORD", ""),
        )
