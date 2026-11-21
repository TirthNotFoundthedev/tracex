"""Reading the audit log under the row-level rule (U35-U52) and engine divergence (U50, U54)."""

import json
import re
import uuid
from typing import Any

import pytest

from tests.api.conftest import Api, World, case_notes, upload_case
from tests.api.helpers import SEQ_KEYS, ctx_for, keys_of
from tracex_api import engine_bridge
from tracex_api.db import many, one
from tracex_api.engine_bridge import persist_result, reconcile
from tracex_engine.matching import (
    HistoryEntry,
    LinkState,
    RunRecord,
    RunResult,
    RunStatus,
    TransitionRecord,
)


def read_all(api: Api, user: str, **params: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    cursor = None
    while True:
        query = {**params, "limit": 100, **({"cursor": cursor} if cursor else {})}
        page = api.get(user, "/audit", **query)
        assert page.status_code == 200, page.text
        items += page.json()["items"]
        cursor = page.json()["next_cursor"]
        if not cursor:
            return items


def gita_activity(api: Api, world: World) -> None:
    stub = api.get("gita", f"/entities/{world.entities['E-5']}").json()["stubs"][0]
    api.post(
        "gita",
        "/access-requests",
        {"stub_id": stub["stub_id"], "reason": "Same vehicle is in my case"},
    )


def test_u35_u36_rows_of_a_hidden_link_do_not_exist_for_other_readers(world: World) -> None:
    api = world.api
    gita_activity(api, world)
    gita = api.get("gita", "/me").json()["user_id"]
    meena = api.get("meena", "/me").json()["user_id"]
    for user in ("charu", "deepak"):
        rows = read_all(api, user)
        text = json.dumps(rows)
        assert world.cases["C-301"] not in text and world.links["L-3"] not in text
        assert gita not in text and meena not in text
        assert not [r for r in rows if r["event_type"] == "LINK_CONFIRMED"]
    own = [r for r in read_all(api, "deepak") if r["actor"].get("user_id")]
    assert all(r["actor"]["role"] == "SENIOR" or r["refs"] for r in own) or own == []
    assert any(r["event_type"] == "AUDIT_VIEWED" for r in read_all(api, "deepak"))


def test_u37_u40_denied_probes_and_stub_views_are_shown_to_the_chain_of_command(
    world: World,
) -> None:
    api = world.api
    api.get("bharat", f"/links/{world.links['L-1']}")
    api.get("bharat", f"/links/{uuid.uuid4()}")
    api.get("bharat", f"/entities/{world.entities['E-1']}")
    bharat = api.get("bharat", "/me").json()["user_id"]
    denied = read_all(api, "charu", event_type="ACCESS_DENIED", actor_user_id=bharat)
    assert len(denied) == 2
    shapes = {
        json.dumps(
            {
                k: (v if k != "target_id" else "x")
                for k, v in r.items()
                if k not in ("row_ref", "occurred_at")
            },
            sort_keys=True,
        )
        for r in denied
    }
    assert (
        len(shapes) == 1
        and denied[0]["reason_code"] == "R2_NOT_VISIBLE"
        and denied[0]["refs"] == []
    )
    stubs = read_all(api, "charu", event_type="STUB_VIEWED", actor_user_id=bharat)
    assert len(stubs) == 1
    assert [r["case_id"] for r in stubs[0]["refs"]] == [world.cases["C-101"]]
    assert "stub_ids" not in stubs[0]["detail"] and "near_entity_ids" in stubs[0]["detail"]
    farid = read_all(api, "farid")
    assert not [r for r in farid if r["actor"].get("user_id") == bharat]


def test_u38_the_approver_sees_only_her_own_decision_with_hidden_fields_dropped(
    world: World,
) -> None:
    api = world.api
    stub = api.get("bharat", f"/entities/{world.entities['E-1']}").json()["stubs"][0]
    created = api.post(
        "bharat",
        "/access-requests",
        {"stub_id": stub["stub_id"], "reason": "Same phone is in my case"},
    ).json()
    assert (
        api.post("farid", f"/access-requests/{created['request_id']}/approve", {}).status_code
        == 200
    )
    rows = read_all(api, "farid")
    types = [r["event_type"] for r in rows]
    assert "ACCESS_REQUEST_CREATED" not in types
    [approved] = [r for r in rows if r["event_type"] == "ACCESS_REQUEST_APPROVED"]
    assert [r["case_id"] for r in approved["refs"]] == [world.cases["C-201"]]
    assert "grant_id" not in approved["detail"] and "target_id" not in approved


def test_u39_a_senior_with_both_cases_in_coverage_sees_the_creation_in_full(world: World) -> None:
    api = world.api
    rows = read_all(api, "deepak", event_type="LINK_AUTO_CREATED")
    [l1] = [r for r in rows if r.get("target_id") == world.links["L-1"]]
    assert {r["case_id"] for r in l1["refs"]} == {world.cases["C-101"], world.cases["C-201"]}
    assert set(l1["detail"]) == {"run_id", "band", "score", "entity_ids"}
    assert world.links["L-3"] not in json.dumps(rows)


def test_u41_filters_on_what_the_reader_cannot_see_equal_filters_on_nothing(world: World) -> None:
    api = world.api
    gita_activity(api, world)
    gita = api.get("gita", "/me").json()["user_id"]
    empty = api.get("charu", "/audit", case_id=str(uuid.uuid4())).json()
    assert empty["items"] == [] and empty["result_count"] == 0 and empty["next_cursor"] is None
    for params in (
        {"case_id": world.cases["C-301"]},
        {"case_id": "C-999"},
        {"actor_user_id": gita},
        {"actor_user_id": str(uuid.uuid4())},
        {"target_id": world.links["L-3"]},
    ):
        got = api.get("charu", "/audit", **params).json()
        assert got == empty, params
    for sort in ("occurred_at", "event_type", "outcome"):
        assert api.get("charu", "/audit", sort=sort, case_id=world.cases["C-301"]).json() == empty


def test_u42_u43_admin_sees_system_events_and_officers_below_supervisor_are_refused(
    world: World,
) -> None:
    api = world.api
    rows = read_all(api, "hari")
    assert rows and all(not r["refs"] for r in rows if r["event_type"] != "DATA_UPLOADED")
    assert not [
        r
        for r in rows
        if r["event_type"].startswith("LINK_")
        or r["event_type"].endswith("_VIEWED")
        and r["actor"].get("role") != "ADMIN"
    ]
    assert api.get("asha", "/audit").status_code == 403
    assert api.get("bharat", "/audit").status_code == 403
    denied = api.audit_rows("ACCESS_DENIED")
    assert denied[-1]["detail"]["http_status"] == 403


def test_u44_u47_pages_chain_and_never_leak_sequence_numbers(world: World) -> None:
    api = world.api
    api.post("meena", "/audit/verify")
    first = api.get("charu", "/audit", limit=2).json()
    second = api.get("charu", "/audit", limit=100, cursor=first["next_cursor"]).json()
    assert any(r["event_type"] == "AUDIT_VIEWED" for r in second["items"])
    for user in ("charu", "meena", "hari"):
        rows = read_all(api, user)
        assert not [k for k in keys_of(rows) if SEQ_KEYS.search(k)]
        for row in rows:
            if row["event_type"] == "AUDIT_VIEWED":
                assert set(row["detail"]) <= {"filter_keys", "result_count", "redacted"}
            if row["event_type"] == "AUDIT_VERIFY_RUN":
                assert set(row["detail"]) <= {"result"}
    mine = {
        r["target_id"]: r["row_ref"]
        for r in read_all(api, "charu")
        if r.get("target_id") == world.links["L-2"] and r["event_type"] == "LINK_AUTO_CREATED"
    }
    other = {
        r["target_id"]: r["row_ref"]
        for r in read_all(api, "meena")
        if r.get("target_id") == world.links["L-2"] and r["event_type"] == "LINK_AUTO_CREATED"
    }
    assert mine and mine != other and mine.keys() == other.keys()


def test_u48_a_proposal_and_a_users_logins_stay_inside_coverage(world: World) -> None:
    api = world.api
    with api.owner() as conn:
        gita = str(one(conn, "SELECT id FROM users WHERE username = 'gita'")["id"])  # type: ignore[index]
    api.post(
        "hari",
        "/pending-changes",
        {"kind": "USER_ROLE", "subject_user_id": gita, "new_value": {"role": "SUPERVISOR"}},
    )
    api.login("gita")
    api.client.post("/auth/login", json={"username": "gita", "password": "wrong-password"})
    seen_by_deepak = json.dumps(read_all(api, "deepak"))
    assert gita not in seen_by_deepak and "gita" not in seen_by_deepak
    seen_by_meena = read_all(api, "meena")
    types = {r["event_type"] for r in seen_by_meena}
    assert {"CHANGE_PROPOSED", "AUTH_LOGIN_SUCCESS", "AUTH_LOGIN_FAILED"} <= types
    assert "gita" in json.dumps(seen_by_meena)


def test_u49_cursors_are_opaque_bound_and_expire(world: World) -> None:
    api = world.api
    cursor = api.get("charu", "/audit", limit=1).json()["next_cursor"]
    assert cursor
    import base64

    raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
    assert b"seq" not in raw and not re.search(rb"\d{6,}", raw)
    assert api.get("meena", "/audit", cursor=cursor).status_code == 422
    assert api.get("charu", "/audit", cursor=cursor, outcome="DENIED").status_code == 422
    assert api.get("charu", "/audit", cursor=cursor[:-3] + "AAA").status_code == 422
    assert api.get("charu", "/audit", cursor="not-a-cursor-at-all-xx").status_code == 422
    api.clock.advance(minutes=16)
    api.login("charu")
    assert api.get("charu", "/audit", cursor=cursor).status_code == 422


def test_u50_a_decision_commits_and_audits_before_the_engine_call(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    api = world.api

    def engine_down(*_: object, **__: object) -> engine_bridge.DecisionOutcome:
        return engine_bridge.DecisionOutcome(False, "ENGINE_DOWN")

    monkeypatch.setattr("tracex_api.routers.links.send_decision", engine_down)
    response = api.post("bharat", f"/links/{world.links['L-2']}/confirm", {})
    assert response.status_code == 200 and response.json()["state"] == "CONFIRMED"
    assert len(api.audit_rows("LINK_CONFIRMED")) == 2  # L-3 by meena, L-2 now
    with api.owner() as conn:
        assert one(conn, "SELECT acked_at FROM decision_outbox") == {"acked_at": None}
        engine_state = api.engine.links.get(world.links["L-2"])
    assert engine_state is not None and engine_state.state.value == "AUTO"
    monkeypatch.undo()
    with api.owner() as conn:
        ctx = ctx_for(api, conn)
        counts = reconcile(ctx)
    assert counts["replayed"] == 1
    edge = api.engine.links.get(world.links["L-2"])
    assert edge is not None and edge.state.value == "CONFIRMED"


def test_u50_the_engine_promotes_and_withdraws_in_a_rerun(world: World) -> None:
    api = world.api
    link_id = world.links["L-2"]
    with api.owner() as conn:
        conn.execute("UPDATE links SET state = 'SUGGESTED' WHERE link_id = %s", (link_id,))
        conn.commit()
    edge = api.engine.links.get(link_id)
    assert edge is not None
    api.engine.links.put(edge.with_changes(state=LinkState.SUGGESTED))
    run_id = str(uuid.uuid4())
    with api.owner() as conn:
        conn.execute(
            "INSERT INTO match_runs (id, started_at, ruleset_version, thresholds_version, status) "
            "VALUES (%s, now(), 'engine-matching/1.1', 1, 'SUCCEEDED')",
            (uuid.UUID(run_id),),
        )
        conn.commit()
    api.engine.links.put(edge.with_changes(state=LinkState.AUTO, match_run_id=run_id))
    promoted = TransitionRecord(
        link_id,
        LinkState.SUGGESTED,
        LinkState.AUTO,
        "engine",
        run_id,
        None,
        "PROMOTED",
        "2026-11-21T10:00:00.000Z",
    )
    record = RunRecord(
        run_id,
        "2026-11-21T10:00:00.000Z",
        None,
        "u",
        (),
        "engine-matching/1.1",
        1,
        {},
        {},
        0,
        RunStatus.SUCCEEDED,
    )
    with api.api_role() as conn:
        ctx = ctx_for(api, conn)
        persist_result(ctx, RunResult(record, (promoted,)), run_id)
        ctx.commit()
    assert [r["detail"]["new_state"] for r in api.audit_rows("LINK_PROMOTED")] == ["AUTO"]
    assert api.audit_rows("LINK_PROMOTED")[0]["actor_kind"] == "SYSTEM"


def test_u54_a_record_that_disagrees_with_postgres_is_rejected_and_the_edge_reverted(
    world: World,
) -> None:
    api = world.api
    link_id = world.links["L-2"]
    edge = api.engine.links.get(link_id)
    assert edge is not None
    api.engine.links.put(edge.with_changes(state=LinkState.CONFIRMED))
    run_id = str(uuid.uuid4())
    with api.owner() as conn:
        conn.execute(
            "INSERT INTO match_runs (id, started_at, ruleset_version, thresholds_version, status) "
            "VALUES (%s, now(), 'engine-matching/1.1', 1, 'SUCCEEDED')",
            (uuid.UUID(run_id),),
        )
        conn.commit()
    bad = TransitionRecord(
        link_id,
        LinkState.SUGGESTED,
        LinkState.CONFIRMED,
        "engine",
        run_id,
        None,
        None,
        "2026-11-21T10:00:00.000Z",
    )
    record = RunRecord(
        run_id,
        "2026-11-21T10:00:00.000Z",
        None,
        "u",
        (),
        "engine-matching/1.1",
        1,
        {},
        {},
        0,
        RunStatus.SUCCEEDED,
    )
    before = len(api.audit_rows("LINK_CONFIRMED"))
    with api.api_role() as conn:
        ctx = ctx_for(api, conn)
        persist_result(ctx, RunResult(record, (bad,)), run_id)
        ctx.commit()
        assert ctx.state.alerts
    assert api.engine.links.get(link_id).state.value == "AUTO"  # type: ignore[union-attr]
    assert len(api.audit_rows("ENGINE_DIVERGENCE_REVERTED")) == 1
    assert len(api.audit_rows("LINK_CONFIRMED")) == before
    with api.owner() as conn:
        assert one(conn, "SELECT state FROM links WHERE link_id = %s", (link_id,)) == {
            "state": "AUTO"
        }


def test_u54_a_forged_decision_in_the_engine_store_never_becomes_a_human_decision(
    world: World,
) -> None:
    api = world.api
    link_id = world.links["L-2"]
    edge = api.engine.links.get(link_id)
    assert edge is not None
    forged = HistoryEntry(
        LinkState.AUTO,
        LinkState.CONFIRMED,
        str(uuid.uuid4()),
        "2026-11-21T10:00:00.000Z",
        None,
        None,
        str(uuid.uuid4()),
    )
    api.engine.links.put(
        edge.with_changes(state=LinkState.CONFIRMED, history=(*edge.history, forged))
    )
    before = len(api.audit_rows("LINK_CONFIRMED"))
    with api.api_role() as conn:
        ctx = ctx_for(api, conn)
        counts = reconcile(ctx)
    assert counts["reverted"] == 1
    reverted = api.engine.links.get(link_id)
    assert reverted is not None and reverted.state.value == "AUTO"
    assert all(h.decision_id != forged.decision_id for h in reverted.history)
    assert len(api.audit_rows("ENGINE_DIVERGENCE_REVERTED")) == 1
    assert len(api.audit_rows("LINK_CONFIRMED")) == before


def test_reconcile_withdraws_rows_whose_edge_is_gone_and_stubs_unknown_runs(world: World) -> None:
    api = world.api
    link_id = world.links["L-2"]
    api.engine.links.remove(link_id)
    with api.api_role() as conn:
        ctx = ctx_for(api, conn)
        counts = reconcile(ctx)
    assert counts["withdrawn"] == 1
    with api.owner() as conn:
        assert one(conn, "SELECT state FROM links WHERE link_id = %s", (link_id,)) == {
            "state": "WITHDRAWN"
        }
    assert len(api.audit_rows("LINK_WITHDRAWN")) == 1
    edge = api.engine.links.get(world.links["L-1"])
    assert edge is not None
    unknown = str(uuid.uuid4())
    api.engine.links.remove(world.links["L-1"])
    api.engine.links.put(edge.with_changes(match_run_id=unknown))
    with api.owner() as conn:
        conn.execute(
            "UPDATE links SET state = 'WITHDRAWN' WHERE link_id = %s", (world.links["L-1"],)
        )
        conn.commit()
    with api.api_role() as conn:
        ctx = ctx_for(api, conn)
        reconcile(ctx)
    with api.owner() as conn:
        stub = one(conn, "SELECT status, error_code FROM match_runs WHERE id = %s", (unknown,))
    assert stub == {"status": "FAILED", "error_code": "RECONCILED"}
    assert (
        many(
            api.owner(),
            "SELECT 1 AS x FROM links WHERE link_id = %s AND state = 'AUTO'",
            (world.links["L-1"],),
        )
        == []
    )


def test_u51_reading_requests_grants_and_changes_is_audited(world: World) -> None:
    api = world.api
    stub = api.get("bharat", f"/entities/{world.entities['E-1']}").json()["stubs"][0]
    created = api.post(
        "bharat",
        "/access-requests",
        {"stub_id": stub["stub_id"], "reason": "Same phone is in my case"},
    ).json()
    approved = api.post("farid", f"/access-requests/{created['request_id']}/approve", {}).json()
    api.get("bharat", "/access-requests")
    api.get("farid", f"/access-requests/{created['request_id']}")
    api.get("bharat", f"/grants/{approved['grant']['grant_id']}")
    proposed = api.post(
        "hari",
        "/pending-changes",
        {"kind": "THRESHOLDS", "new_value": {"high_min": 85, "medium_min": 50}},
    ).json()
    api.get("meena", f"/pending-changes/{proposed['change_id']}")
    assert approved["grant"]["grant_id"] in [
        g for r in api.audit_rows("GRANT_VIEWED") for g in r["detail"]["grant_ids"]
    ]
    assert created["request_id"] in [
        g for r in api.audit_rows("ACCESS_REQUEST_VIEWED") for g in r["detail"]["request_ids"]
    ]
    assert proposed["change_id"] in [
        g for r in api.audit_rows("CHANGE_VIEWED") for g in r["detail"]["change_ids"]
    ]


def test_u52_an_upload_names_its_case_so_that_cases_supervisor_sees_it(world: World) -> None:
    api = world.api
    upload_case(
        api,
        "C-101",
        "Rivergate",
        {"notes-02.txt": case_notes("C-101", "Nothing more to add.")["notes.txt"]},
    )
    rows = api.audit_rows("DATA_UPLOADED")
    assert [r["refs"] for r in rows][-1] == [
        {"case_id": world.cases["C-101"], "district_id": rows[-1]["refs"][0]["district_id"]}
    ]
    seen = read_all(api, "charu", event_type="DATA_UPLOADED")
    assert any(r["refs"] and r["refs"][0]["case_id"] == world.cases["C-101"] for r in seen)
    assert (
        many(api.owner(), "SELECT 1 AS x FROM audit_log WHERE event_type = 'DATA_UPLOADED'") != []
    )
