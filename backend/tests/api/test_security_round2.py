"""Dutta's security review of PR #45 (blockers 1 to 4): each test reproduces his probe.

B1: the gate fails closed (junk anchor line, a verify that raises, a verify that never ran).
B2: the shutdown anchor and the anchor loop only bless a log that a fresh verify passed, and they
    anchor the row the verify checked.
B3: the retry loop never interrupts a live run, never withdraws beside a partly refilled store and
    never resumes on its own after a lost store.
B4: `migrate` and `seed` refuse the public dev-only passwords without the flag.
"""

import json
import time
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.api.conftest import Api, World
from tests.api.test_audit_anchor_gate import busy
from tests.api.test_engine_store_lost import link_states
from tracex_api import audit, migrate, seed
from tracex_api.config import ConfigError, refuse_dev_secrets_in_tools
from tracex_api.engine_bridge import EngineGateway
from tracex_api.main import GATE_EXEMPT, check_chain, create_app, reconcile_once
from tracex_api.verify_audit import main as nightly_main

JUNK_LINES = ["1", "[]", '"x"', "null", "true", "{}", '{"seq": "3", "row_hash": 1}']


def anchor_lines(api: Api) -> list[dict[str, Any]]:
    path = api.settings.audit_anchor_path
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def boom(*_: Any, **__: Any) -> Any:
    raise RuntimeError("verify cannot run")


def add_audit_row(api: Api) -> int:
    with api.owner() as conn:
        seq = audit.append(
            conn,
            audit.AuditEvent(
                "AUDIT_VERIFY_RUN",
                audit.SYSTEM,
                target_type="AUDIT",
                target_id="late",
                detail={"result": "OK"},
            ),
        )
        conn.commit()
    return seq


def head_seq(api: Api) -> int:
    with api.owner() as conn:
        row = conn.execute("SELECT max(seq) AS m FROM audit_log").fetchone()
    assert row is not None
    return int(row["m"])


def insert_running_run(api: Api) -> str:
    run_id = str(uuid.uuid4())
    with api.owner() as conn:
        conn.execute(
            "INSERT INTO match_runs (id, started_at, ruleset_version, thresholds_version, status) "
            "VALUES (%s, now(), 'test', 1, 'RUNNING')",
            (uuid.UUID(run_id),),
        )
        conn.commit()
    return run_id


def run_status(api: Api, run_id: str) -> tuple[str, str | None]:
    with api.owner() as conn:
        row = conn.execute(
            "SELECT status, error_code FROM match_runs WHERE id = %s", (uuid.UUID(run_id),)
        ).fetchone()
    assert row is not None
    return str(row["status"]), row["error_code"]


# ---------------------------------------------------------------------------------------- B1


@pytest.mark.parametrize("line", JUNK_LINES)
def test_b1c_read_anchor_skips_a_line_that_is_not_an_anchor_object(
    tmp_path: Path, line: str
) -> None:
    path = tmp_path / "anchor.log"
    good = json.dumps({"seq": 2, "row_hash": "ab", "at": "x"})
    path.write_text(f"{good}\n{line}\n", encoding="utf-8")
    assert audit.read_anchor(path) == json.loads(good)
    path.write_text(f"{line}\n", encoding="utf-8")
    assert audit.read_anchor(path) is None


def test_b1_a_junk_only_anchor_gates_everything_while_running_and_after_a_restart(api: Api) -> None:
    busy(api)
    asha, meena = api.h("asha"), api.h("meena")
    api.settings.audit_anchor_path.write_text("1\n", encoding="utf-8")
    broken = api.client.post("/audit/verify", headers=meena)
    assert broken.status_code == 200 and broken.json()["result"] == "BROKEN"
    assert api.client.get("/cases", headers=asha).status_code == 503
    restarted = create_app(api.settings, api.engine, api.clock)
    with TestClient(restarted, raise_server_exceptions=False) as client:
        assert restarted.state.tracex.chain_ok is False
        assert client.get("/cases", headers=asha).status_code == 503
        login = client.post("/auth/login", json={"username": "asha", "password": "x"})
        assert login.status_code == 503 and login.json()["code"] == "NOT_READY"


def test_b1_a_verify_that_raises_gates_while_running_and_after_a_restart(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    busy(api)
    asha, meena = api.h("asha"), api.h("meena")
    assert api.client.get("/cases", headers=asha).status_code == 200
    monkeypatch.setattr(audit, "verify_checked", boom)
    state = api.client.app.state.tracex  # type: ignore[attr-defined]
    assert check_chain(state) is False and check_chain(state) is False
    assert state.chain_ok is False
    assert len([a for a in state.alerts if "BROKEN" in a]) == 1  # alerted once
    assert api.client.get("/cases", headers=asha).status_code == 503
    # POST /audit/verify, with the verify still raising, answers BROKEN and records it
    state.chain_ok = True
    answer = api.client.post("/audit/verify", headers=meena)
    assert answer.status_code == 200 and answer.json()["result"] == "BROKEN"
    assert state.chain_ok is False
    restarted = create_app(api.settings, api.engine, api.clock)
    with TestClient(restarted, raise_server_exceptions=False) as client:
        assert restarted.state.tracex.chain_ok is False
        assert client.get("/cases", headers=asha).status_code == 503
        assert client.get("/ready").status_code == 503


def test_b1_a_raising_ready_check_is_recorded_as_not_ok(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = api.client.app.state.tracex  # type: ignore[attr-defined]
    asha = api.h("asha")
    state.chain_checked_at = -1000.0
    monkeypatch.setattr(audit, "verify_checked", boom)
    assert api.client.get("/ready").status_code == 503
    assert state.chain_ok is False
    assert api.client.get("/cases", headers=asha).status_code == 503


def test_b1a_a_verify_that_never_ran_leaves_the_gate_shut(api: Api) -> None:
    app = create_app(api.settings, api.engine, api.clock)  # no lifespan: chain_ok stays None
    app.state.tracex.reconciled.set()
    client = TestClient(app, raise_server_exceptions=False)
    assert app.state.tracex.chain_ok is None
    for method, path in (("GET", "/cases"), ("GET", "/me"), ("POST", "/auth/login")):
        response = client.request(method, path)
        assert response.status_code == 503, path
        assert response.json()["code"] == "NOT_READY"
    assert client.get("/health").status_code == 200
    assert ("POST", "/audit/verify") in GATE_EXEMPT


# ---------------------------------------------------------------------------------------- B2


@pytest.mark.parametrize("tamper", ["delete_anchor", "truncate_tail"])
def test_b2_a_shutdown_does_not_bless_a_log_that_no_longer_verifies(api: Api, tamper: str) -> None:
    busy(api)
    app = create_app(api.settings, api.engine, api.clock)
    with TestClient(app, raise_server_exceptions=False):
        assert app.state.tracex.chain_ok is True  # cached True, as in Dutta's probe
        if tamper == "delete_anchor":
            api.settings.audit_anchor_path.unlink()
        else:
            with api.owner() as conn:
                audit.write_anchor(conn, api.settings.audit_anchor_path)  # the loop's anchor
            with api.superuser() as conn:
                conn.execute("ALTER TABLE audit_log DISABLE TRIGGER ALL")
                conn.execute("DELETE FROM audit_log WHERE seq = (SELECT max(seq) FROM audit_log)")
        before = anchor_lines(api)
    assert anchor_lines(api) == before  # the shutdown wrote nothing
    restarted = create_app(api.settings, api.engine, api.clock)
    with TestClient(restarted, raise_server_exceptions=False) as client:
        assert restarted.state.tracex.chain_ok is False
        assert client.get("/cases", headers=api.h("asha")).status_code == 503


def test_b2_a_shutdown_whose_verify_raises_writes_no_anchor(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    busy(api)
    app = create_app(api.settings, api.engine, api.clock)
    with TestClient(app, raise_server_exceptions=False):
        before = anchor_lines(api)
        monkeypatch.setattr(audit, "verify_checked", boom)
    assert anchor_lines(api) == before


def test_b2_a_clean_shutdown_anchors_the_head_it_checked(api: Api) -> None:
    busy(api)
    app = create_app(api.settings, api.engine, api.clock)
    with TestClient(app, raise_server_exceptions=False):
        pass
    assert anchor_lines(api)[-1]["seq"] == head_seq(api)


def test_b2_the_loop_anchors_the_row_it_checked_not_a_later_head(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    busy(api)
    real = audit.verify_checked
    checked: list[int] = []

    def verify_then_a_row_arrives(*args: Any, **kwargs: Any) -> audit.VerifyResult:
        result = real(*args, **kwargs)
        checked.append(result.head_seq)
        add_audit_row(api)
        return result

    monkeypatch.setattr(audit, "verify_checked", verify_then_a_row_arrives)
    state = api.client.app.state.tracex  # type: ignore[attr-defined]
    assert check_chain(state, anchor=True) is True
    anchored = anchor_lines(api)[-1]["seq"]
    assert anchored == checked[0] and anchored < head_seq(api)


def test_b2_post_verify_anchors_the_row_it_checked(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    busy(api)
    real = audit.verify_checked
    checked: list[int] = []

    def verify_then_a_row_arrives(*args: Any, **kwargs: Any) -> audit.VerifyResult:
        result = real(*args, **kwargs)
        checked.append(result.head_seq)
        add_audit_row(api)
        return result

    monkeypatch.setattr(audit, "verify_checked", verify_then_a_row_arrives)
    answer = api.client.post("/audit/verify", headers=api.h("meena"))
    assert answer.json()["result"] == "OK"
    assert anchor_lines(api)[-1]["seq"] == checked[0]


def test_b2_the_nightly_job_anchors_the_row_it_checked(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    busy(api)
    real = audit.verify_checked
    checked: list[int] = []

    def verify_then_a_row_arrives(*args: Any, **kwargs: Any) -> audit.VerifyResult:
        result = real(*args, **kwargs)
        checked.append(result.head_seq)
        add_audit_row(api)
        return result

    monkeypatch.setattr(audit, "verify_checked", verify_then_a_row_arrives)
    code = nightly_main(
        [
            "--database-url",
            api.migrator_url,
            "--anchor-path",
            str(api.settings.audit_anchor_path),
        ]
    )
    assert code == 0
    assert anchor_lines(api)[-1]["seq"] == checked[0]


def test_note5_rows_since_the_last_anchor_are_walked_even_beyond_the_window(api: Api) -> None:
    busy(api)
    top = head_seq(api)
    with api.superuser() as conn:
        conn.execute("ALTER TABLE audit_log DISABLE TRIGGER ALL")
        conn.execute("UPDATE audit_log SET outcome = 'DENIED' WHERE seq = 2")
    with api.owner() as conn:
        assert top > 3
        assert audit.verify(conn, api.settings.audit_anchor_path, tail=2) == (False, 2)


def test_note6_an_empty_log_is_broken(api: Api) -> None:
    with api.superuser() as conn:
        conn.execute("ALTER TABLE audit_log DISABLE TRIGGER ALL")
        conn.execute("DELETE FROM audit_log")
    with api.owner() as conn:
        ok, _ = audit.verify(conn, api.settings.audit_anchor_path)
    assert ok is False


# ---------------------------------------------------------------------------------------- B3


def lost_store_app(api: Api, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, EngineGateway]:
    monkeypatch.setattr("tracex_api.main.RECONCILE_RETRY_SECONDS", 0.2)
    empty = EngineGateway.in_memory()
    return create_app(api.settings, empty, api.clock), empty


def test_b3_a_run_started_while_the_store_is_lost_is_not_interrupted(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = world.api
    app, _ = lost_store_app(api, monkeypatch)
    with TestClient(app, raise_server_exceptions=False):
        time.sleep(1)
        assert app.state.tracex.store_lost
        run = insert_running_run(api)  # the operator replays the batches
        time.sleep(1.5)  # many retry periods
        assert run_status(api, run) == ("RUNNING", None)
    interrupted = [r for r in api.audit_rows("MATCHING_RUN_COMPLETED") if r["target_id"] == run]
    assert interrupted == []


def test_b3_a_partly_refilled_store_withdraws_nothing(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = world.api
    before = link_states(api)
    app, empty = lost_store_app(api, monkeypatch)
    with TestClient(app, raise_server_exceptions=False) as client:
        time.sleep(1)
        assert app.state.tracex.store_lost
        empty.graphs = api.engine.graphs
        empty.links.put(api.engine.links.edges()[0])  # one edge reaches the store first
        time.sleep(1.5)
        assert client.get("/ready").status_code == 503
    assert link_states(api) == before


def test_b3_a_lost_store_does_not_recover_on_its_own(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = world.api
    before = link_states(api)
    app, empty = lost_store_app(api, monkeypatch)
    with TestClient(app, raise_server_exceptions=False) as client:
        time.sleep(1)
        empty.graphs = api.engine.graphs
        empty.links = api.engine.links  # the store is back, whole
        time.sleep(1.5)
        assert client.get("/ready").status_code == 503
        assert not app.state.tracex.reconciled.is_set()
        assert any("engine store" in a for a in app.state.tracex.alerts)
    assert link_states(api) == before
    restarted = create_app(api.settings, empty, api.clock)  # the operator restarts the API
    with TestClient(restarted, raise_server_exceptions=False) as client:
        deadline = time.monotonic() + 30
        while client.get("/ready").status_code != 200 and time.monotonic() < deadline:
            time.sleep(0.2)
        assert client.get("/ready").status_code == 200
    assert link_states(api) == before


def test_b3_the_stale_run_sweep_runs_on_the_first_sweep_only(world: World) -> None:
    api = world.api
    stale = insert_running_run(api)
    state = create_app(api.settings, api.engine, api.clock).state.tracex
    reconcile_once(state)
    assert run_status(api, stale) == ("FAILED", "INTERRUPTED")
    live = insert_running_run(api)
    reconcile_once(state)  # a retry
    assert run_status(api, live) == ("RUNNING", None)


def test_b3_no_withdrawal_while_a_run_is_running(world: World) -> None:
    api = world.api
    state = create_app(api.settings, api.engine, api.clock).state.tracex
    reconcile_once(state)
    assert state.reconciled.is_set()
    victim = world.links["L-3"]
    api.engine.links.remove(victim)
    state.reconciled.clear()
    run = insert_running_run(api)
    before = link_states(api)
    reconcile_once(state)
    assert link_states(api) == before and state.withdrawals_deferred
    assert not state.reconciled.is_set()
    with api.owner() as conn:
        conn.execute(
            "UPDATE match_runs SET status = 'SUCCEEDED', finished_at = now() WHERE id = %s",
            (uuid.UUID(run),),
        )
        conn.commit()
    reconcile_once(state)
    assert link_states(api)[victim] == "WITHDRAWN"
    assert state.reconciled.is_set() and not state.withdrawals_deferred


# ---------------------------------------------------------------------------------------- B4

WEAK = {
    "TRACEX_SEED_PASSWORD_HARI": "dev-only-seed-hari",
    "TRACEX_MIGRATOR_DB_PASSWORD": "dev-only-migrator-password",
    "TRACEX_API_DB_PASSWORD": "dev-only-api-db-password",
    "DATABASE_ADMIN_URL": "postgresql://postgres:dev-only-pg@db:5432/tracex",
}


def clean_env(monkeypatch: pytest.MonkeyPatch, **values: str) -> None:
    for name in (
        *WEAK,
        "TRACEX_ALLOW_DEV_SECRETS",
    ):
        monkeypatch.delenv(name, raising=False)
    for name, value in values.items():
        monkeypatch.setenv(name, value)


@pytest.mark.parametrize("name", list(WEAK))
def test_b4_each_dev_only_value_is_refused_and_named(name: str) -> None:
    safe = {
        "TRACEX_SEED_PASSWORD_HARI": "real-" + uuid.uuid4().hex,
        "TRACEX_MIGRATOR_DB_PASSWORD": "real-" + uuid.uuid4().hex,
        "TRACEX_API_DB_PASSWORD": "real-" + uuid.uuid4().hex,
        "DATABASE_ADMIN_URL": "postgresql://postgres:real@db:5432/tracex",
    }
    refuse_dev_secrets_in_tools(safe)
    with pytest.raises(ConfigError, match=name):
        refuse_dev_secrets_in_tools({**safe, name: WEAK[name]})
    refuse_dev_secrets_in_tools({**safe, name: WEAK[name], "TRACEX_ALLOW_DEV_SECRETS": "1"})
    with pytest.raises(ConfigError):
        refuse_dev_secrets_in_tools({**safe, name: WEAK[name], "TRACEX_ALLOW_DEV_SECRETS": "true"})


def test_b4_migrate_refuses_before_touching_the_database(monkeypatch: pytest.MonkeyPatch) -> None:
    clean_env(monkeypatch, **WEAK)
    monkeypatch.setattr(migrate, "bootstrap_roles", boom)
    with pytest.raises(SystemExit, match="refused"):
        migrate.main()


def test_b4_seed_refuses_before_touching_the_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    clean_env(monkeypatch, **WEAK)
    monkeypatch.setattr(seed, "connect", boom)
    seed_dir = Path(__file__).resolve().parents[3] / "data-kit" / "seed"
    with pytest.raises(SystemExit, match="refused"):
        seed.main(["--seed-dir", str(seed_dir)])


# ------------------------------------------------------------------------- the 503 contract

PLACEHOLDERS = ("case_id", "entity_id", "document_id", "link_id", "stub_id", "request_id")


def test_the_gate_body_matches_the_contract_on_every_gated_route(api: Api) -> None:
    from tests.api.contract import _spec, validate

    busy(api)
    state = api.client.app.state.tracex  # type: ignore[attr-defined]
    api.settings.audit_anchor_path.unlink()
    assert check_chain(state) is False
    checked = 0
    for path, item in _spec()["paths"].items():
        for method in ("get", "post"):
            if method not in item or (method.upper(), path) in GATE_EXEMPT:
                continue
            url = path
            for name in PLACEHOLDERS:
                url = url.replace("{" + name + "}", str(uuid.uuid4()))
            response = api.client.request(method.upper(), url)  # the gate answers before any token
            assert response.status_code == 503, (method, path)
            validate("SafetyPauseError", response.json())
            assert response.json() == {"code": "NOT_READY", "message_key": "error.not_ready"}
            checked += 1
    assert checked == 48
