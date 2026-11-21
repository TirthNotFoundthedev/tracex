"""Startup reconcile and engine failures that must not block matching for good (PR #30, item 5)."""

import time
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import World
from tracex_api.db import one
from tracex_api.main import create_app


def engine_down(*_: Any, **__: Any) -> Any:
    raise ConnectionError("the graph database is not answering")


def wait_ready(client: TestClient, seconds: float = 30) -> int:
    deadline = time.monotonic() + seconds
    code = client.get("/ready").status_code
    while code != 200 and time.monotonic() < deadline:
        time.sleep(0.2)
        code = client.get("/ready").status_code
    return code


def confirm_while_engine_is_down(world: World, monkeypatch: pytest.MonkeyPatch) -> Callable[[], None]:
    api = world.api
    real = api.engine.matcher
    monkeypatch.setattr(api.engine, "matcher", engine_down)
    response = api.post("bharat", f"/links/{world.links['L-2']}/confirm", {})
    assert response.status_code == 200, response.text
    with api.owner() as conn:
        row = one(conn, "SELECT count(*) AS n FROM decision_outbox WHERE acked_at IS NULL")
    assert row is not None and row["n"] == 1
    return lambda: monkeypatch.setattr(api.engine, "matcher", real)


def test_one_failed_engine_call_does_not_block_matching_runs(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = world.api
    restore = confirm_while_engine_is_down(world, monkeypatch)
    restore()
    run = api.post("hari", "/matching/runs", {})
    assert run.status_code == 202, run.text
    with api.owner() as conn:
        row = one(conn, "SELECT count(*) AS n FROM decision_outbox WHERE acked_at IS NULL")
    assert row is not None and row["n"] == 0


def test_a_run_that_throws_in_the_engine_is_closed_as_failed(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = world.api
    real = api.engine.matcher
    monkeypatch.setattr(api.engine, "matcher", engine_down)
    failed = api.post("hari", "/matching/runs", {})
    assert failed.status_code == 500
    monkeypatch.setattr(api.engine, "matcher", real)
    with api.owner() as conn:
        row = one(conn, "SELECT status, error_code FROM match_runs ORDER BY started_at DESC")
    assert row == {"status": "FAILED", "error_code": "ENGINE_ERROR"}
    assert api.post("hari", "/matching/runs", {}).status_code == 202


def test_ready_waits_for_the_startup_reconcile_which_clears_what_a_crash_left(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = world.api
    restore = confirm_while_engine_is_down(world, monkeypatch)
    restore()
    stale = str(uuid.uuid4())
    with api.owner() as conn:
        conn.execute(
            "INSERT INTO match_runs (id, started_at, ruleset_version, thresholds_version, status) "
            "VALUES (%s, now(), 'engine-matching/1.1', 1, 'RUNNING')",
            (uuid.UUID(stale),),
        )
        conn.commit()
    assert api.post("hari", "/matching/runs", {}).status_code == 409
    restarted = create_app(api.settings, api.engine, api.clock)
    assert TestClient(restarted).get("/ready").status_code == 503
    with TestClient(restarted) as client:
        assert wait_ready(client) == 200
    with api.owner() as conn:
        run = one(conn, "SELECT status, error_code FROM match_runs WHERE id = %s", (stale,))
        pending = one(conn, "SELECT count(*) AS n FROM decision_outbox WHERE acked_at IS NULL")
    assert run == {"status": "FAILED", "error_code": "INTERRUPTED"}
    assert pending is not None and pending["n"] == 0
    assert api.post("hari", "/matching/runs", {}).status_code == 202
