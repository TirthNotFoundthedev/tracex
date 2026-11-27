"""Unit tests for the pieces of the demo seed that need no database."""

from collections.abc import Mapping
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from typing import Any

import pytest

from tracex_api.seed_demo import (
    EXIT_REFUSED,
    SeedError,
    UrllibHttp,
    file_rank,
    login,
    main,
    multipart,
    read_cases,
    refuse_if_production,
)

ALLOWED = {"TRACEX_ENV": "development", "TRACEX_ALLOW_DEV_SECRETS": "1"}


@pytest.mark.parametrize(
    "value",
    ["production", "prd", "pre", "qa", "main", "gov", "state1", "stag", "Development", " test", ""],
)
def test_refuses_every_environment_not_on_the_allow_list(value: str) -> None:
    with pytest.raises(SeedError, match="TRACEX_ENV"):
        refuse_if_production({**ALLOWED, "TRACEX_ENV": value})


@pytest.mark.parametrize("value", ["development", "local", "test", "demo"])
def test_allows_only_the_four_listed_environments(value: str) -> None:
    refuse_if_production({**ALLOWED, "TRACEX_ENV": value})


def test_refuses_when_env_is_unset() -> None:
    with pytest.raises(SeedError, match="TRACEX_ENV"):
        refuse_if_production({"TRACEX_ALLOW_DEV_SECRETS": "1"})


@pytest.mark.parametrize("flag", [None, "", "0", "true", "yes", " 1"])
def test_refuses_without_the_dev_secrets_flag(flag: str | None) -> None:
    env = {"TRACEX_ENV": "development"}
    if flag is not None:
        env["TRACEX_ALLOW_DEV_SECRETS"] = flag
    with pytest.raises(SeedError, match="TRACEX_ALLOW_DEV_SECRETS"):
        refuse_if_production(env)


def test_main_with_no_environment_exits_2() -> None:
    assert main(["--api-url", "http://localhost:1"], env={}) == EXIT_REFUSED


@pytest.mark.parametrize("env_value", ["prd", "qa", ""])
def test_main_exits_2_for_refused_environments(env_value: str) -> None:
    env = {**ALLOWED, "TRACEX_ENV": env_value}
    assert main(["--api-url", "http://localhost:1"], env=env) == EXIT_REFUSED


def test_main_exits_2_without_the_dev_secrets_flag() -> None:
    assert main(["--api-url", "http://localhost:1"], env={"TRACEX_ENV": "development"}) == (
        EXIT_REFUSED
    )


@pytest.mark.parametrize(
    "url", ["file:///etc/passwd", "ftp://host/x", "gopher://host", "//host/x", "host:8000", ""]
)
def test_only_http_and_https_urls_are_accepted(url: str) -> None:
    with pytest.raises(SeedError, match="http"):
        UrllibHttp(url)


@pytest.mark.parametrize("url", ["http://api:8000", "https://api.example"])
def test_http_and_https_urls_are_accepted(url: str) -> None:
    UrllibHttp(url)


def test_a_redirect_is_not_followed_and_never_gets_the_token() -> None:
    seen: list[str | None] = []

    class Target(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            seen.append(self.headers.get("Authorization"))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args: object) -> None:
            return

    class Redirector(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{target.server_port}/stolen")
            self.end_headers()

        def log_message(self, *args: object) -> None:
            return

    target = HTTPServer(("127.0.0.1", 0), Target)
    redirector = HTTPServer(("127.0.0.1", 0), Redirector)
    threads = [Thread(target=s.serve_forever, daemon=True) for s in (target, redirector)]
    for thread in threads:
        thread.start()
    try:
        http = UrllibHttp(f"http://127.0.0.1:{redirector.server_port}")
        with pytest.raises(SeedError, match="redirect"):
            http.request("GET", "/x", token="secret-token")  # noqa: S106
    finally:
        target.shutdown()
        redirector.shutdown()
    assert seen == []


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
