"""N2: the API refuses to start on the published dev-only secrets (PR #30 re-review)."""

import base64
import secrets
from collections.abc import Mapping
from pathlib import Path

import pytest

from tracex_api.config import ConfigError, Settings

KEY_NAMES = ("TRACEX_JWT_KEY", "TRACEX_CURSOR_KEY", "TRACEX_ROW_REF_KEY", "TRACEX_HMAC_KEY")


def real_key() -> str:
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


def dev_key(name: str) -> str:
    return base64.urlsafe_b64encode(f"dev-only-{name}".ljust(32, "0").encode()).decode()


def env(**over: str) -> Mapping[str, str]:
    base = {name: real_key() for name in KEY_NAMES}
    base["DATABASE_URL"] = "postgresql://tracex_api:" + secrets.token_hex(8) + "@db:5432/tracex"
    base["AUDIT_ANCHOR_PATH"] = "/tmp/anchor.log"  # noqa: S108 - never opened here
    return {**base, **over}


def test_real_secrets_start() -> None:
    assert Settings.from_env(env()).database_url


@pytest.mark.parametrize(
    ("over", "named"),
    [
        ({"TRACEX_JWT_KEY": dev_key("jwt")}, "TRACEX_JWT_KEY"),
        ({"TRACEX_HMAC_KEY": dev_key("hmac")}, "TRACEX_HMAC_KEY"),
        ({"TRACEX_CURSOR_KEY": dev_key("cursor")}, "TRACEX_CURSOR_KEY"),
        ({"TRACEX_ROW_REF_KEY": dev_key("rowref")}, "TRACEX_ROW_REF_KEY"),
        ({"TRACEX_API_DB_PASSWORD": "dev-only-api-db-password"}, "TRACEX_API_DB_PASSWORD"),
        (
            {"DATABASE_URL": "postgresql://tracex_api:dev-only-api-db-password@db/tracex"},
            "DATABASE_URL",
        ),
    ],
)
def test_dev_only_secret_is_refused_and_named(over: dict[str, str], named: str) -> None:
    with pytest.raises(ConfigError, match=named):
        Settings.from_env(env(**over))


def test_the_flag_allows_dev_secrets_only_when_exactly_one() -> None:
    weak = {"TRACEX_JWT_KEY": dev_key("jwt"), "TRACEX_API_DB_PASSWORD": "dev-only-x"}
    assert Settings.from_env(env(**weak, TRACEX_ALLOW_DEV_SECRETS="1"))
    for value in ("", "0", "true", "yes"):
        with pytest.raises(ConfigError):
            Settings.from_env(env(**weak, TRACEX_ALLOW_DEV_SECRETS=value))


def test_the_published_env_example_keys_are_refused_without_the_flag() -> None:
    text = (Path(__file__).resolve().parents[3] / ".env.example").read_text(encoding="utf-8")
    values = dict(
        line.strip().split("=", 1) for line in text.splitlines() if "=" in line and line[0] != "#"
    )
    published = {k: values[k] for k in KEY_NAMES} | {
        "DATABASE_URL": "postgresql://x@db/x",
        "AUDIT_ANCHOR_PATH": "/tmp/a",  # noqa: S108
    }
    with pytest.raises(ConfigError, match="dev-only"):
        Settings.from_env(published)
    assert Settings.from_env({**published, "TRACEX_ALLOW_DEV_SECRETS": "1"})
    assert values["TRACEX_ALLOW_DEV_SECRETS"] == "1"
