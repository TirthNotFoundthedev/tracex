"""Item 12 (PR #30 re-review): a missing anchor is BROKEN, the verify result is cached, and a
broken chain makes every route except /health, /ready and POST /audit/verify answer 503."""

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import Api
from tracex_api import audit
from tracex_api.main import create_app


def busy(api: Api) -> None:
    for name in ("asha", "meena", "hari"):
        api.login(name)


def break_anchor(api: Api, how: str) -> None:
    path = api.settings.audit_anchor_path
    if how == "missing":
        path.unlink(missing_ok=True)
    elif how == "empty":
        path.write_text("", encoding="utf-8")
    else:
        path.write_text("not json\n{}\n", encoding="utf-8")


def restore_anchor(api: Api) -> None:
    with api.owner() as conn:
        audit.write_anchor(conn, api.settings.audit_anchor_path)


@pytest.mark.parametrize("how", ["missing", "empty", "no_well_formed_line"])
def test_a_missing_anchor_is_broken_once_the_log_has_more_than_one_row(api: Api, how: str) -> None:
    busy(api)
    break_anchor(api, how)
    with api.owner() as conn:
        assert audit.verify(conn, api.settings.audit_anchor_path) == (False, 1)
        assert audit.verify(conn, api.settings.audit_anchor_path, tail=2) == (False, 1)


def test_a_fresh_log_with_one_row_and_no_anchor_is_ok(api: Api, tmp_path: Path) -> None:
    with api.owner() as conn:
        assert audit.verify(conn, tmp_path / "none.log") == (True, None)


def test_a_present_anchor_still_verifies(api: Api) -> None:
    busy(api)
    restore_anchor(api)
    with api.owner() as conn:
        assert audit.verify(conn, api.settings.audit_anchor_path) == (True, None)


def test_a_broken_chain_answers_503_everywhere_but_the_three_exempt_routes(api: Api) -> None:
    busy(api)
    asha, meena = api.h("asha"), api.h("meena")
    assert api.client.get("/cases", headers=asha).status_code == 200
    break_anchor(api, "missing")
    broken = api.client.post("/audit/verify", headers=meena)
    assert broken.status_code == 200 and broken.json()["result"] == "BROKEN"
    for method, path in (
        ("GET", "/cases"),
        ("GET", "/me"),
        ("GET", "/links"),
        ("GET", "/review-queue"),
        ("POST", "/auth/login"),
    ):
        response = api.client.request(method, path, headers=asha)
        assert response.status_code == 503, (method, path)
        assert response.json()["code"] == "NOT_READY"
    assert api.client.get("/health").status_code == 200
    assert api.client.get("/ready").status_code == 503
    assert api.client.post("/audit/verify", headers=meena).status_code == 200
    restore_anchor(api)
    healed = api.client.post("/audit/verify", headers=meena)
    assert healed.json()["result"] == "OK"
    assert api.client.get("/cases", headers=asha).status_code == 200
    assert api.client.get("/ready").status_code == 200


def test_ready_runs_at_most_one_verify_a_minute(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    busy(api)
    restore_anchor(api)
    calls: list[int] = []
    real = audit.verify

    def counting(*args: object, **kwargs: object) -> tuple[bool, int | None]:
        calls.append(1)
        return real(*args, **kwargs)  # type: ignore[arg-type]

    clock = [1000.0]
    monkeypatch.setattr("tracex_api.main.audit.verify", counting)
    monkeypatch.setattr("tracex_api.main.monotonic", lambda: clock[0])
    for _ in range(50):
        assert api.client.get("/ready").status_code == 200
    assert len(calls) == 1
    clock[0] += 59
    api.client.get("/ready")
    assert len(calls) == 1
    clock[0] += 2
    api.client.get("/ready")
    assert len(calls) == 2


def test_startup_writes_the_first_anchor_for_a_fresh_log(api: Api) -> None:
    path = api.settings.audit_anchor_path
    path.unlink(missing_ok=True)
    app = create_app(api.settings, api.engine, api.clock)
    with TestClient(app):
        assert audit.read_anchor(path) is not None
        assert app.state.tracex.chain_ok is True


def test_startup_on_a_log_with_rows_and_no_anchor_is_broken_and_gated(api: Api) -> None:
    busy(api)
    asha = api.h("asha")
    break_anchor(api, "missing")
    app = create_app(api.settings, api.engine, api.clock)
    with TestClient(app) as client:
        time.sleep(0.5)
        assert app.state.tracex.chain_ok is False
        assert client.get("/ready").status_code == 503
        assert client.get("/cases", headers=asha).status_code == 503
        assert client.get("/health").status_code == 200
        assert any("audit" in a for a in app.state.tracex.alerts)
