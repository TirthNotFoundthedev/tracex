"""The audit log: append-only enforcement, the chain, the anchor and what is written (U1-U34)."""

import concurrent.futures
import hashlib
import json
import re
import uuid
from pathlib import Path

import psycopg
import pytest

from tests.api.conftest import Api, World
from tests.api.helpers import SEQ_KEYS, keys_of
from tracex_api import audit
from tracex_api.audit import Actor, AuditError, AuditEvent
from tracex_api.audit_events import EVENTS, registry_rows
from tracex_api.db import many, one
from tracex_api.main import chain_ready

PACKAGE = Path(__file__).resolve().parents[2] / "tracex_api"


def _denied(n: int = 0) -> AuditEvent:
    return AuditEvent(
        "ACCESS_DENIED",
        audit.ANONYMOUS,
        outcome="DENIED",
        reason_code="R2_NOT_VISIBLE",
        target_type="UNRESOLVED",
        target_id=f"hmac:{n:016x}",
        detail={"action": "GET /x", "http_status": 404},
    )


def test_u1_the_api_role_cannot_update_audit_rows(api: Api) -> None:
    with api.api_role() as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute("UPDATE audit_log SET outcome = 'DENIED'")


@pytest.mark.parametrize(
    "statement",
    ["UPDATE audit_log SET outcome = 'DENIED'", "DELETE FROM audit_log", "TRUNCATE audit_log"],
)
def test_u2_to_u4_triggers_block_even_a_superuser(api: Api, statement: str) -> None:
    with api.superuser() as conn:
        before = conn.execute("SELECT count(*) FROM audit_log").fetchone()
        with pytest.raises(psycopg.errors.RaiseException):
            conn.execute(statement)
        assert conn.execute("SELECT count(*) FROM audit_log").fetchone() == before


def test_u5_the_api_role_cannot_change_triggers_grants_or_owner(api: Api) -> None:
    statements = [
        "ALTER TABLE audit_log DISABLE TRIGGER ALL",
        "DROP TRIGGER audit_log_no_row_change ON audit_log",
        "ALTER TABLE audit_log OWNER TO tracex_api",
    ]
    for statement in statements:
        with api.api_role() as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute(statement)
    with api.api_role() as conn:
        # A GRANT by a role that does not own the table only warns and grants nothing.
        conn.execute("GRANT UPDATE ON audit_log TO PUBLIC")
        assert one(
            conn, "SELECT has_table_privilege('tracex_api', 'audit_log', 'UPDATE') AS p"
        ) == {"p": False}
    with api.superuser() as conn:
        role = conn.execute(
            "SELECT rolsuper, pg_has_role('tracex_api', 'tracex_migrator', 'member'), "
            "(SELECT tableowner = 'tracex_api' FROM pg_tables WHERE tablename = 'audit_log') "
            "FROM pg_roles WHERE rolname = 'tracex_api'"
        ).fetchone()
    assert role == (False, False, False)


def test_u6_no_code_path_updates_or_deletes_audit_rows() -> None:
    pattern = re.compile(r"(UPDATE|DELETE\s+FROM|TRUNCATE(\s+TABLE)?)\s+audit_log", re.IGNORECASE)
    hits = [p.name for p in PACKAGE.rglob("*.py") if pattern.search(p.read_text("utf-8"))]
    assert hits == []


def test_u7_append_keeps_seq_contiguous_and_chained(api: Api) -> None:
    with api.api_role() as conn:
        for n in range(3):
            audit.append(conn, _denied(n))
        conn.commit()
    rows = api.audit_rows()
    assert [r["seq"] for r in rows] == list(range(1, len(rows) + 1))
    for earlier, later in zip(rows, rows[1:], strict=False):
        assert bytes(later["prev_hash"]) == bytes(earlier["row_hash"])
    assert bytes(rows[0]["prev_hash"]) == bytes(32)


def test_u8_row_hash_matches_the_test_vector() -> None:
    columns = {
        "seq": 7,
        "event_id": uuid.UUID("11111111-1111-4111-8111-111111111111"),
        "occurred_at": __import__("datetime").datetime(
            2026, 11, 20, 10, 0, 0, 123456, tzinfo=__import__("datetime").UTC
        ),
        "event_type": "ACCESS_DENIED",
        "outcome": "DENIED",
        "actor_kind": "ANONYMOUS",
        "actor_user_id": None,
        "actor_role": None,
        "actor_district_id": None,
        "reason_code": "R2_NOT_VISIBLE",
        "refs": [],
        "target_type": "UNRESOLVED",
        "target_id": "hmac:0123456789abcdef",
        "resolved_target": None,
        "detail": {"http_status": 404, "action": "GET /x"},
        "session_id": None,
        "request_id": None,
        "client_ip": None,
        "row_nonce": bytes(range(16)),
        "prev_hash": bytes(range(32)),
    }
    expected_body = (
        '{"actor_district_id":null,"actor_kind":"ANONYMOUS","actor_role":null,'
        '"actor_user_id":null,"client_ip":null,"detail":{"action":"GET /x","http_status":404},'
        '"event_id":"11111111-1111-4111-8111-111111111111","event_type":"ACCESS_DENIED",'
        '"occurred_at":"2026-11-20T10:00:00.123456Z","outcome":"DENIED",'
        '"prev_hash":"' + bytes(range(32)).hex() + '","reason_code":"R2_NOT_VISIBLE","refs":[],'
        '"request_id":null,"resolved_target":null,"row_nonce":"' + bytes(range(16)).hex() + '",'
        '"seq":7,"session_id":null,"target_id":"hmac:0123456789abcdef","target_type":"UNRESOLVED"}'
    )
    assert audit.canonical(columns).decode() == expected_body
    expected = hashlib.sha256(bytes(range(32)) + expected_body.encode()).hexdigest()
    assert audit.row_hash(bytes(range(32)), columns).hex() == expected


def test_u9_fifty_concurrent_appends_keep_the_chain_whole(api: Api) -> None:
    def worker(n: int) -> None:
        with api.api_role() as conn:
            audit.append(conn, _denied(n))
            conn.commit()

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        list(pool.map(worker, range(50)))
    rows = api.audit_rows()
    assert [r["seq"] for r in rows] == list(range(1, len(rows) + 1))
    with api.api_role() as conn:
        assert audit.verify(conn, api.settings.audit_anchor_path) == (True, None)


def test_u10_verify_returns_only_the_result_and_is_logged(api: Api) -> None:
    response = api.post("meena", "/audit/verify")
    assert response.status_code == 200 and response.json() == {"result": "OK"}
    run = api.audit_rows("AUDIT_VERIFY_RUN")
    assert len(run) == 1 and run[0]["detail"]["result"] == "OK"
    assert api.post("charu", "/audit/verify").status_code == 403


def _tamper(api: Api, statements: list[str]) -> None:
    with api.superuser() as conn:
        conn.execute("ALTER TABLE audit_log DISABLE TRIGGER ALL")
        for statement in statements:
            conn.execute(statement)
        conn.execute("ALTER TABLE audit_log ENABLE TRIGGER ALL")


def _busy(api: Api) -> None:
    for user in ("asha", "bharat", "charu", "deepak", "hari", "meena"):
        api.login(user)
    assert api.post("meena", "/audit/verify").json() == {"result": "OK"}


def test_u11_an_edited_row_is_found_at_its_seq(api: Api) -> None:
    _busy(api)
    _tamper(api, ["UPDATE audit_log SET outcome = 'FAILED' WHERE seq = 5"])
    assert api.post("meena", "/audit/verify").json() == {"result": "BROKEN", "first_bad_seq": 5}


def test_u12_a_deleted_or_swapped_row_breaks_the_chain(api: Api) -> None:
    _busy(api)
    _tamper(api, ["DELETE FROM audit_log WHERE seq = 5"])
    assert api.post("meena", "/audit/verify").json()["result"] == "BROKEN"


def test_u12_swapped_rows_break_the_chain(api: Api) -> None:
    _busy(api)
    _tamper(
        api,
        [
            "UPDATE audit_log SET seq = 1000 WHERE seq = 5",
            "UPDATE audit_log SET seq = 5 WHERE seq = 6",
            "UPDATE audit_log SET seq = 6 WHERE seq = 1000",
        ],
    )
    assert api.post("meena", "/audit/verify").json()["result"] == "BROKEN"


def test_u13_a_chain_shorter_than_the_anchor_is_broken(api: Api) -> None:
    _busy(api)
    _tamper(api, ["DELETE FROM audit_log WHERE seq > (SELECT max(seq) - 3 FROM audit_log)"])
    assert api.post("meena", "/audit/verify").json()["result"] == "BROKEN"


def test_u14_rewriting_history_with_recomputed_hashes_is_caught_by_the_anchor(api: Api) -> None:
    _busy(api)
    with api.superuser() as conn:
        conn.execute("ALTER TABLE audit_log DISABLE TRIGGER ALL")
        conn.execute("UPDATE audit_log SET outcome = 'FAILED' WHERE seq = 5")
        head = conn.execute("SELECT row_hash FROM audit_log WHERE seq = 4").fetchone()
        assert head is not None
        prev = bytes(head[0])
    with api.owner() as conn:
        conn.execute("ALTER TABLE audit_log DISABLE TRIGGER ALL")
        for row in many(conn, "SELECT * FROM audit_log WHERE seq >= 5 ORDER BY seq"):
            columns = audit._row_columns(row)
            columns["prev_hash"] = prev
            prev = audit.row_hash(prev, columns)
            conn.execute(
                "UPDATE audit_log SET prev_hash = %s, row_hash = %s WHERE seq = %s",
                (columns["prev_hash"], prev, row["seq"]),
            )
        conn.execute("ALTER TABLE audit_log ENABLE TRIGGER ALL")
        conn.commit()
    result = api.post("meena", "/audit/verify").json()
    assert result["result"] == "BROKEN"


def test_u15_the_anchor_is_appended_never_rewritten(api: Api) -> None:
    api.post("meena", "/audit/verify")
    path = api.settings.audit_anchor_path
    first = path.read_text("utf-8").splitlines()
    api.post("meena", "/audit/verify")
    second = path.read_text("utf-8").splitlines()
    assert second[: len(first)] == first and len(second) > len(first)
    entry = json.loads(second[-1])
    assert set(entry) == {"seq", "row_hash", "at"}


def test_u16_a_broken_chain_in_the_tail_blocks_readiness(api: Api) -> None:
    _busy(api)
    assert api.client.get("/ready").status_code == 200
    _tamper(api, ["UPDATE audit_log SET outcome = 'FAILED' WHERE seq = 3"])
    state = api.client.app.state.tracex  # type: ignore[attr-defined]
    assert chain_ready(state) is False
    response = api.client.get("/ready")
    assert response.status_code == 503 and response.json()["code"] == "NOT_READY"


def test_u17_viewing_an_entity_is_audited_with_actor_and_refs(world: World) -> None:
    api = world.api
    api.get("bharat", f"/entities/{world.entities['E-4']}")
    [row] = [
        r for r in api.audit_rows("ENTITY_VIEWED") if str(r["target_id"]) == world.entities["E-4"]
    ]
    assert row["actor_role"] == "INVESTIGATOR" and row["detail"]["via_grant"] is False
    assert {r["case_id"] for r in row["refs"]} >= {world.cases["C-101"]}


def test_u18_stub_views_list_the_stub_ids_and_every_end_case(world: World) -> None:
    api = world.api
    stub = api.get("bharat", f"/entities/{world.entities['E-1']}").json()["stubs"][0]
    rows = [r for r in api.audit_rows("STUB_VIEWED") if stub["stub_id"] in r["detail"]["stub_ids"]]
    assert len(rows) == 1
    assert {r["case_id"] for r in rows[0]["refs"]} == {world.cases["C-101"], world.cases["C-201"]}


def test_u19_u20_denied_probes_of_a_hidden_and_a_random_id_look_alike(world: World) -> None:
    api = world.api
    hidden = api.get("bharat", f"/links/{world.links['L-1']}")
    random_id = str(uuid.uuid4())
    unknown = api.get("bharat", f"/links/{random_id}")
    assert (hidden.status_code, hidden.json(), dict(hidden.headers)) == (
        404,
        unknown.json(),
        {**unknown.headers, "content-length": hidden.headers["content-length"]},
    )
    rows = [r for r in api.audit_rows("ACCESS_DENIED") if r["target_type"] == "UNRESOLVED"]
    by_target = {r["target_id"]: r for r in rows}
    seen, absent = by_target[world.links["L-1"]], by_target[random_id]
    for row in (seen, absent):
        assert row["refs"] == [] and row["reason_code"] == "R2_NOT_VISIBLE"
        assert row["outcome"] == "DENIED"
    assert seen["resolved_target"] == world.links["L-1"] and absent["resolved_target"] is None


def test_u21_raw_strings_are_never_stored(world: World) -> None:
    api = world.api
    api.get("bharat", "/links/9100000001")
    api.client.post("/auth/login", json={"username": "nothing-here", "password": "abcdefgh"})
    api.client.post("/auth/login", json={"username": "asha", "password": "wrong-password"})
    denied = [r["target_id"] for r in api.audit_rows("ACCESS_DENIED")]
    assert any(t.startswith("hmac:") for t in denied) and "9100000001" not in denied
    failed = {r["detail"]["claimed_username"] for r in api.audit_rows("AUTH_LOGIN_FAILED")}
    assert "asha" in failed and "nothing-here" not in failed
    assert any(c.startswith("hmac:") for c in failed)


def test_u22_u23_a_forbidden_decision_leaves_a_denial_row(world: World) -> None:
    api = world.api
    before = len(api.audit_rows("ACCESS_DENIED"))
    assert api.post("asha", f"/links/{world.links['L-2']}/confirm", {}).status_code == 403
    rows = api.audit_rows("ACCESS_DENIED")
    assert len(rows) == before + 1 and rows[-1]["detail"]["http_status"] == 403
    assert rows[-1]["reason_code"] == "MATRIX_DENY"


def test_u24_failed_logins_are_throttled_and_never_store_a_password(api: Api) -> None:
    for attempt in range(5):
        response = api.client.post(
            "/auth/login", json={"username": "asha", "password": f"bad{attempt}"}
        )
        assert response.status_code == 401
    sixth = api.client.post("/auth/login", json={"username": "asha", "password": "bad-again"})
    assert sixth.status_code == 429
    nobody = [
        api.client.post("/auth/login", json={"username": "no-such", "password": "x"}).status_code
        for _ in range(6)
    ]
    assert nobody[-1] == 429
    rows = api.audit_rows("AUTH_LOGIN_FAILED")
    assert any(r["detail"]["throttled"] for r in rows)
    assert "bad0" not in json.dumps([r["detail"] for r in rows])


def test_u25_tampered_tokens_and_reused_refresh_tokens_are_audited(api: Api) -> None:
    api.login("asha")
    token = api.tokens["asha"]["access_token"]
    forged = api.client.get("/me", headers={"Authorization": f"Bearer {token[:-4]}AAAA"})
    assert forged.status_code == 401
    refreshed = api.client.post(
        "/auth/refresh", json={"refresh_token": api.tokens["asha"]["refresh_token"]}
    )
    assert refreshed.status_code == 200
    reused = api.client.post(
        "/auth/refresh", json={"refresh_token": api.tokens["asha"]["refresh_token"]}
    )
    assert reused.status_code == 401
    assert api.client.get("/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401
    assert len(api.audit_rows("AUTH_REFRESH_REUSED")) == 1
    assert len(api.audit_rows("AUTH_TOKEN_REJECTED")) >= 2


def test_u27_decision_reasons_stay_out_of_the_log(world: World) -> None:
    api = world.api
    api.post("bharat", f"/links/{world.links['L-2']}/confirm", {})
    api.post("charu", f"/links/{world.links['L-2']}/undo", {"reason": "secret reason text"})
    api.post("charu", f"/links/{world.links['L-2']}/reopen", {"reason": "other secret text"})
    rows = [r for r in api.audit_rows() if r["event_type"].startswith("LINK_")]
    assert {"LINK_CONFIRMED", "LINK_UNDONE", "LINK_REOPENED"} <= {r["event_type"] for r in rows}
    assert "secret" not in json.dumps([r["detail"] for r in rows])
    confirmed = [
        r
        for r in rows
        if r["event_type"] == "LINK_CONFIRMED" and r["detail"]["previous_state"] == "AUTO"
    ]
    assert confirmed


def test_u31_a_failed_append_fails_closed_without_data(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = world.api
    headers = api.h("bharat")

    def boom(*_: object, **__: object) -> int:
        raise AuditError("append failed")

    monkeypatch.setattr(audit, "append", boom)
    response = api.client.get(f"/entities/{world.entities['E-1']}", headers=headers)
    assert response.status_code == 500
    assert response.json() == {"code": "INTERNAL", "message_key": "error.internal"}


def test_u32_unknown_keys_and_uncovered_refs_are_rejected(world: World) -> None:
    api = world.api
    with api.api_role() as conn:
        with pytest.raises(AuditError):
            audit.append(conn, AuditEvent("CASE_LISTED", audit.SYSTEM, detail={"nope": 1}))
        with pytest.raises(AuditError):
            audit.append(
                conn,
                AuditEvent(
                    "CASE_LISTED", audit.SYSTEM, detail={"case_ids": [world.cases["C-101"]]}
                ),
            )
        conn.rollback()
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute("SELECT set_config('x.y', 'z', false)")
            conn.execute(
                "INSERT INTO audit_log (seq, event_id, occurred_at, event_type, outcome, "
                "actor_kind, detail, row_nonce, prev_hash, row_hash) "
                "VALUES (999, gen_random_uuid(), now(), "
                "'CASE_LISTED', 'SUCCESS', 'SYSTEM', '{\"nope\": 1}', %s, %s, %s)",
                (bytes(16), bytes(32), bytes(32)),
            )


def test_u33_no_seeded_value_appears_in_any_audit_column(world: World) -> None:
    api = world.api
    api.get("bharat", f"/entities/{world.entities['E-1']}")
    api.get("bharat", "/search/entities", q="9100000001")
    api.get("asha", f"/links/{world.links['L-2']}/explanation")
    dump = json.dumps(api.audit_rows(), default=str)
    for value in ("9100000001", "MH12AB1234", "Irfan", "Accused"):
        assert value not in dump


def test_u34_client_supplied_actor_fields_are_ignored(world: World) -> None:
    api = world.api
    response = api.client.post(
        f"/links/{world.links['L-2']}/confirm",
        headers=api.h("bharat"),
        json={"occurred_at": "2001-01-01T00:00:00Z", "actor_user_id": str(uuid.uuid4())},
    )
    assert response.status_code == 422
    ok = api.post("bharat", f"/links/{world.links['L-2']}/confirm", {})
    assert ok.status_code == 200
    row = api.audit_rows("LINK_CONFIRMED")[-1]
    assert row["occurred_at"].year >= 2026 and row["actor_role"] == "INVESTIGATOR"


def test_the_event_registry_and_its_table_agree(api: Api) -> None:
    with api.owner() as conn:
        stored = [
            (r["event_type"], r["detail_key"], r["owner_ref"])
            for r in many(
                conn,
                "SELECT * FROM audit_detail_key_owner ORDER BY event_type, detail_key, owner_ref",
            )
        ]
    assert set(stored) == set(registry_rows())
    assert one(api.owner(), "SELECT count(*) AS n FROM audit_log") is not None
    assert set(EVENTS) >= {"LINK_PROMOTED", "LINK_WITHDRAWN", "ENGINE_DIVERGENCE_REVERTED"}
    assert not any(
        SEQ_KEYS.search(k) for k in keys_of({"detail": {"line_from": 1}}) - {"line_from"}
    )
    assert Actor("SYSTEM").kind == "SYSTEM"
