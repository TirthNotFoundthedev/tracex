"""Unit tests for the pieces of the demo seed that need no database."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from tracex_api.seed_demo import (
    SeedError,
    file_rank,
    login,
    multipart,
    read_cases,
    refuse_if_production,
)


@pytest.mark.parametrize("value", ["production", "PROD", "eu-live", "staging", "uat1", "release"])
def test_refuses_production_like_values(value: str) -> None:
    with pytest.raises(SeedError, match="production"):
        refuse_if_production({"TRACEX_ENV": value})


@pytest.mark.parametrize("value", ["development", "local", "test", "demo", " Dev "])
def test_allows_development_values(value: str) -> None:
    refuse_if_production({"TRACEX_ENV": value})


def test_refuses_when_env_is_unset() -> None:
    with pytest.raises(SeedError, match="TRACEX_ENV"):
        refuse_if_production({})


def test_file_order_follows_the_data_kit_load_order() -> None:
    names = ["bank.csv", "notes-02.txt", "fir.txt", "cdr.csv", "notes.txt", "sdr.csv"]
    assert sorted(names, key=file_rank) == [
        "fir.txt",
        "notes.txt",
        "notes-02.txt",
        "sdr.csv",
        "cdr.csv",
        "bank.csv",
    ]


def test_multipart_carries_fields_and_files() -> None:
    body, content_type = multipart({"case_number": "C-101"}, [("fir.txt", b"line one")])
    boundary = content_type.split("boundary=")[1]
    assert body.startswith(f"--{boundary}".encode())
    assert b'name="case_number"\r\n\r\nC-101' in body
    assert b'name="files"; filename="fir.txt"' in body
    assert b"line one" in body
    assert body.endswith(f"--{boundary}--\r\n".encode())


def test_read_cases_puts_late_files_after_baseline(tmp_path: Path) -> None:
    for batch, case, name in (
        ("b01", "C-101", "notes.txt"),
        ("b01", "C-101", "fir.txt"),
        ("b02", "C-101", "notes-02.txt"),
        ("b02", "C-202", "fir.txt"),
        ("b01", "C-1100", "fir.txt"),
    ):
        folder = tmp_path / "batches" / batch / "cases" / case
        folder.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(name.encode())
    cases = read_cases(tmp_path)
    assert [c.case_number for c in cases] == ["C-101", "C-1100", "C-202"]
    assert [n for n, _ in cases[0].files] == ["fir.txt", "notes.txt", "notes-02.txt"]
    assert [c.digit for c in cases] == ["1", "1", "2"]


class FakeHttp:
    def __init__(self, status: int) -> None:
        self.status = status
        self.calls: list[tuple[str, str, Any]] = []

    def request(
        self,
        method: str,
        path: str,
        *,
        token: str | None = None,
        body: Any = None,
        form: Mapping[str, str] | None = None,
        files: list[tuple[str, bytes]] | None = None,
    ) -> tuple[int, Any]:
        self.calls.append((method, path, body))
        return self.status, {"access_token": "t"}


def test_login_needs_a_password_from_the_environment() -> None:
    with pytest.raises(SeedError, match="TRACEX_SEED_PASSWORD_HARI"):
        login(FakeHttp(200), "hari", {})


def test_login_failure_is_reported_without_the_password() -> None:
    with pytest.raises(SeedError) as info:
        login(FakeHttp(401), "hari", {"TRACEX_SEED_PASSWORD_HARI": "s3cret"})
    assert "s3cret" not in str(info.value)


def test_login_returns_a_session() -> None:
    fake = FakeHttp(200)
    session = login(fake, "hari", {"TRACEX_SEED_PASSWORD_HARI": "pw"})
    assert session.token == "t"  # noqa: S105 - fake token
    assert fake.calls == [("POST", "/auth/login", {"username": "hari", "password": "pw"})]
